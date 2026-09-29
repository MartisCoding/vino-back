from collections import defaultdict
from collections.abc import Iterable

from src.models.inference import (
    CVInferenceResponse,
    OCRCandidate,
    OCRInferenceResponse,
    RecognitionResolution,
    ResolutionSource,
)
from src.tables import Wine


class RecognitionResolver:
    def __init__(
        self,
        top_k: int = 5,
        ocr_weight: float = 1.0,
        cv_weight: float = 0.4,
        rrf_k: int = 10,
        cv_min_score: float = 0.65,
    ) -> None:
        self._top_k = top_k
        self._ocr_weight = ocr_weight
        self._cv_weight = cv_weight
        self._rrf_k = rrf_k
        self._cv_min_score = cv_min_score

    def resolve(
        self,
        cv_response: CVInferenceResponse,
        ocr_response: OCRInferenceResponse,
        cv_wine: Wine | None,
        ocr_wine: Wine | None,
    ) -> RecognitionResolution:
        # 1. OCR has priority whenever it produced a usable result.
        if ocr_wine is not None:
            if cv_wine is not None and cv_wine.id == ocr_wine.id:
                source, reason = "both", "both_agree"
            else:
                source, reason = "ocr", "ocr_priority"

            return RecognitionResolution(
                status="resolved",
                detected_slug=ocr_wine.slug,
                alternatives=self._collect_alternatives(
                    selected_slug=ocr_wine.slug,
                    cv_response=cv_response,
                    ocr_response=ocr_response,
                ),
                source=ResolutionSource(
                    source=source,  # type: ignore
                    reason=reason,  # type: ignore
                ),
            )

        # 2. OCR did not produce a usable wine, fallback to CV.
        if cv_wine is not None:
            return RecognitionResolution(
                status="resolved",
                detected_slug=cv_wine.slug,
                alternatives=self._collect_alternatives(
                    selected_slug=cv_wine.slug,
                    cv_response=cv_response,
                    ocr_response=ocr_response,
                ),
                source=ResolutionSource(source="cv", reason="cv_only"),
            )

        ocr_ranked = self._ranked_ocr_slugs(ocr_response, allow_unresolved=True)
        if ocr_ranked:
            cv_ranked = self._ranked_cv_slugs(cv_response)
            return RecognitionResolution(
                status="partially_resolved",
                detected_slug=None,
                alternatives=self._fuse(ocr_ranked, cv_ranked, selected_slug=None),
                source=ResolutionSource(source="ocr", reason="ocr_alternatives_only"),
            )

        # 4. Nothing at all.
        return RecognitionResolution(
            status="unresolved",
            error="no_recognition_result",
        )

    # ------------------------------------------------------------------
    # Primary slug extraction
    # ------------------------------------------------------------------

    def get_cv_slug(self, response: CVInferenceResponse) -> str | None:
        if response.error or not response.results:
            return None

        best = max(response.results, key=lambda r: r.score)
        if best.score < self._cv_min_score:
            return None

        return best.payload.slug

    @staticmethod
    def get_ocr_slug(response: OCRInferenceResponse) -> str | None:
        result = response.result

        if result.error:
            return None

        # CV is a fallback for OCR, so only "matched" is considered valid.
        if result.status != "matched":
            return None

        if result.best_match is None:
            return None

        return result.best_match.slug

    # ------------------------------------------------------------------
    # Alternatives: rank fusion of OCR and CV lists
    # ------------------------------------------------------------------

    def _collect_alternatives(
    self,
    selected_slug: str | None,
    cv_response: CVInferenceResponse,
    ocr_response: OCRInferenceResponse,
) -> list[str]:
        return self._fuse(
            self._ranked_ocr_slugs(ocr_response),
            self._ranked_cv_slugs(cv_response),
            selected_slug=selected_slug,
        )

    def _fuse(
        self,
        ocr_ranked: list[str],
        cv_ranked: list[str],
        selected_slug: str | None,
    ) -> list[str]:
        scores: dict[str, float] = defaultdict(float)

        for rank, slug in enumerate(ocr_ranked):
            scores[slug] += self._ocr_weight / (self._rrf_k + rank + 1)

        for rank, slug in enumerate(cv_ranked):
            scores[slug] += self._cv_weight / (self._rrf_k + rank + 1)

        if selected_slug is not None:
            scores.pop(selected_slug, None)

        ocr_pos = {slug: i for i, slug in enumerate(ocr_ranked)}
        cv_pos = {slug: i for i, slug in enumerate(cv_ranked)}
        inf = float("inf")

        # Higher fused score first; ties -> better OCR rank, then better CV rank.
        ordered = sorted(
            scores,
            key=lambda s: (-scores[s], ocr_pos.get(s, inf), cv_pos.get(s, inf)),
        )
        return ordered[: self._top_k]

    def _ranked_cv_slugs(self, response: CVInferenceResponse) -> list[str]:
        if response.error:
            return []

        results = sorted(response.results, key=lambda r: r.score, reverse=True)

        return self._unique(
            r.payload.slug for r in results if r.score >= self._cv_min_score
        )

    def _ranked_ocr_slugs(
        self,
        response: OCRInferenceResponse,
        allow_unresolved: bool = False,
    ) -> list[str]:
        result = response.result

        if result.error or result.status == "error":
            return []
        if result.status == "unresolved" and not allow_unresolved:
            return []

        pool: list[OCRCandidate] = []
        if result.best_match is not None:
            pool.append(result.best_match)
        pool.extend(result.alternatives)
        pool.extend(result.candidates)

        # Same wine can appear in several lists: keep its best score.
        best: dict[str, float] = {}
        for candidate in pool:
            prev = best.get(candidate.slug)
            if prev is None or candidate.match_score > prev:
                best[candidate.slug] = candidate.match_score

        return sorted(best, key=lambda s: best[s], reverse=True)
    
    @staticmethod
    def _unique(values: Iterable[str]) -> list[str]:
        return list(dict.fromkeys(values))