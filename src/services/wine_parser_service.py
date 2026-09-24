import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.repositories import WineRepository
from src.tables import Wine

from src.config import ParserConfig

class WineParserService:
    def __init__(
        self,
        wine_repository: WineRepository,
        config: ParserConfig,
        http_client: httpx.AsyncClient | None = None,
    ):
        self._wine_repository = wine_repository
        self._base_url = config.base_url.rstrip("/")
        self._max_retries = config.max_retries
        self._retry_delay = config.retry_delay
        self._http_client = http_client or httpx.AsyncClient(timeout=config.timeout)

    @staticmethod
    def _text(el) -> str | None:
        return el.get_text(strip=True) if el else None

    def _parse_wine_page(self, html: str, source_url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        name = self._text(soup.select_one("h1.wine-main-title-block__title"))
        winery = self._text(soup.select_one(".wine-main-title-block__manufacturer"))

        details: dict[str, list[str | None]] = {}
        for card in soup.select(".wine-detail-info__detail"):
            label = self._text(card.select_one(".wine-detail-info__detail-label"))
            values = [self._text(v) for v in card.select(".wine-detail-info__detail-value")]
            if label:
                details[label] = values

        region = (details.get("Регион") or [None])[0]
        grape = (details.get("Сорт винограда") or [None])[0]

        rating_text = self._text(soup.select_one(".wine-main-title-block__rating-text"))
        rating = None
        if rating_text:
            match = re.search(r"[\d.,]+", rating_text)
            if match:
                rating = float(match.group().replace(",", "."))

        description = self._text(soup.select_one(".wine-page__description"))
        if not description:
            meta = soup.find("meta", attrs={"name": "description"})
            description = meta["content"].strip() if meta and meta.get("content") else None #type: ignore

        external_id = source_url.rstrip("/").split("/")[-1]

        return {
            "external_id": external_id,
            "name": name,
            "winery": winery,
            "region": region,
            "grape": grape,
            "rating": rating,
            "description": description,
            "source_url": source_url,
        }

    def _build_url(self, wine_url_or_slug: str) -> str:
        return (
            wine_url_or_slug
            if wine_url_or_slug.startswith("http")
            else urljoin(f"{self._base_url}/", wine_url_or_slug)
        )

    async def _fetch_html(self, url: str) -> str:
        attempt = 1
        while True:
            try:
                logger.debug("Fetching wine source page url={} attempt={}", url, attempt)
                response = await self._http_client.get(url)
                response.raise_for_status()
                logger.debug("Wine source page fetched successfully url={} status={}", url, response.status_code)
                return response.text
            except httpx.HTTPError:
                if attempt >= self._max_retries:
                    logger.warning("Fetching wine source page failed after retries url={}", url)
                    raise
                logger.warning(
                    "Fetching wine source page failed url={} attempt={} retrying in {}s",
                    url,
                    attempt,
                    self._retry_delay,
                )
                await asyncio.sleep(self._retry_delay)
                attempt += 1

    async def slug_exists(self, wine_url_or_slug: str) -> bool:
        url = self._build_url(wine_url_or_slug)
        try:
            html = await self._fetch_html(url)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                logger.info("Wine slug not found on source url={}", url)
                return False
            raise
        parsed = self._parse_wine_page(html, source_url=url)
        exists = parsed["name"] is not None
        logger.debug("Wine slug source existence check slug={} exists={}", wine_url_or_slug, exists)
        return exists

    async def parse_and_save(self, wine_url_or_slug: str) -> Wine:
        url = self._build_url(wine_url_or_slug)

        html = await self._fetch_html(url)
        parsed = self._parse_wine_page(html, source_url=url)

        if parsed["name"] is None:
            raise ValueError(f"Could not parse wine page, layout may have changed: {url}")

        existing = await self._wine_repository.get_by_external_id(parsed["external_id"])
        if existing is not None:
            return await self._wine_repository.update(existing, **parsed)

        return await self._wine_repository.create(**parsed)

    async def parse_and_save_many(self, wine_urls_or_slugs: list[str]) -> list[Wine]:
        wines = []
        for item in wine_urls_or_slugs:
            wines.append(await self.parse_and_save(item))
        return wines

    async def close(self) -> None:
        logger.debug("Closing wine parser HTTP client")
        await self._http_client.aclose()