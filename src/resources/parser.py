# src/resources/wine_parser.py

import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.config import ParserConfig
from src.models.wine import ParsedWine


class WineParser:

    def __init__(
        self,
        config: ParserConfig,
        http_client: httpx.AsyncClient | None = None,
    ):
        self._base_url = config.base_url.rstrip("/")
        self._max_retries = config.max_retries
        self._retry_delay = config.retry_delay
        self._http_client = http_client or httpx.AsyncClient(
            timeout=config.timeout,
        )

    @staticmethod
    def _text(el) -> str | None:
        return el.get_text(strip=True) if el else None

    @staticmethod
    def _parse_wine_page(
        html: str,
        source_url: str,
    ) -> ParsedWine:
        soup = BeautifulSoup(html, "html.parser")

        name = WineParser._text(
            soup.select_one(
                "h1.wine-main-title-block__title",
            ),
        )

        winery = WineParser._text(
            soup.select_one(
                ".wine-main-title-block__manufacturer",
            ),
        )

        details: dict[str, list[str | None]] = {}

        for card in soup.select(
            ".wine-detail-info__detail",
        ):
            label = WineParser._text(
                card.select_one(
                    ".wine-detail-info__detail-label",
                ),
            )

            values = [
                WineParser._text(value)
                for value in card.select(
                    ".wine-detail-info__detail-value",
                )
            ]

            if label:
                details[label] = values

        region = (
            details.get("Регион") or [None]
        )[0]

        country = (
            details.get("Страна") or [None]
        )[0]

        rating_text = WineParser._text(
            soup.select_one(
                ".wine-main-title-block__rating-text",
            ),
        )

        rating = 0.0

        if rating_text:
            match = re.search(
                r"[\d.,]+",
                rating_text,
            )

            if match:
                rating = float(
                    match.group().replace(",", "."),
                )

        description = WineParser._text(
            soup.select_one(".wine-page__description"),
        )

        if not description:
            meta = soup.find(
                "meta",
                attrs={"name": "description"},
            )

            description = (
                meta["content"].strip() # type: ignore
                if meta and meta.get("content")
                else ""
            )

        external_id = (
            source_url.rstrip("/").split("/")[-1]
        )

        if not name:
            raise ValueError(
                f"Could not parse wine page: {source_url}",
            )

        return ParsedWine(
            slug=external_id,
            name=name,
            country=country or "",
            region=region or "",
            winery=winery or "",
            rating=rating,
            description=description or "",
            source_url=source_url,
        )

    def _build_url(
        self,
        wine_url_or_slug: str,
    ) -> str:
        return (
            wine_url_or_slug
            if wine_url_or_slug.startswith("http")
            else urljoin(
                f"{self._base_url}/",
                wine_url_or_slug,
            )
        )

    async def _fetch_html(
        self,
        url: str,
    ) -> str:
        attempt = 1

        while True:
            try:
                logger.debug(
                    "Fetching wine source page url={} attempt={}",
                    url,
                    attempt,
                )

                response = await self._http_client.get(url)
                response.raise_for_status()

                return response.text

            except httpx.HTTPError:
                if attempt >= self._max_retries:
                    raise

                await asyncio.sleep(
                    self._retry_delay,
                )

                attempt += 1

    async def fetch(
        self,
        wine_url_or_slug: str,
    ) -> ParsedWine:
        url = self._build_url(wine_url_or_slug)
        html = await self._fetch_html(url)

        return self._parse_wine_page(
            html,
            source_url=url,
        )

    async def exists(
        self,
        wine_url_or_slug: str,
    ) -> bool:
        url = self._build_url(wine_url_or_slug)

        try:
            await self._fetch_html(url)

        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return False

            raise

        return True

    async def close(self) -> None:
        await self._http_client.aclose()