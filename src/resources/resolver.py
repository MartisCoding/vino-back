from collections.abc import Iterable

from src.models.inference import (
    CVInferenceResponse,
    OCRInferenceResponse,
    RecognitionResolution,
    ResolutionSource,
)
from src.tables import Wine


class RecognitionResolver:
    def __init__(self):
        pass

    def resolve(
        self,
        cv_response: CVInferenceResponse,
        ocr_response: OCRInferenceResponse,
        cv_wine: Wine | None,
        ocr_wine: Wine | None,
    ) -> RecognitionResolution:

        cv_slug = self.get_cv_slug(cv_response)
        ocr_slug = self.get_ocr_slug(ocr_response)

        if cv_wine is None and ocr_wine is None:
            return RecognitionResolution(
                resolved=False,
                error="no_recognition_result",
            )

        if cv_wine is None:
            return self._resolve_ocr_only(
                ocr_response=ocr_response,
                ocr_wine=ocr_wine,
                ocr_slug=ocr_slug,
            )

        if ocr_wine is None:
            return self._resolve_cv_only(
                cv_wine=cv_wine,
                cv_slug=cv_slug,
                cv_response=cv_response,
            )

        if cv_wine.id == ocr_wine.id:
            return RecognitionResolution(
                resolved=True,
                detected_slug=cv_wine.slug,
                alternatives=self._collect_alternatives(
                    selected_slug=cv_wine.slug,
                    cv_response=cv_response,
                    ocr_response=ocr_response,
                ),
                source=ResolutionSource(
                    source="both",
                    reason="both_agree",
                ),
            )

        if self._same_family(cv_wine, ocr_wine):
            return RecognitionResolution(
                resolved=True,
                detected_slug=ocr_wine.slug,
                alternatives=self._collect_alternatives(
                    selected_slug=ocr_wine.slug,
                    cv_response=cv_response,
                    ocr_response=ocr_response,
                ),
                source=ResolutionSource(
                    source="ocr",
                    reason="ocr_variant_override",
                ),
            )

        return RecognitionResolution(
            resolved=True,
            detected_slug=cv_wine.slug,
            alternatives=self._collect_alternatives(
                selected_slug=cv_wine.slug,
                cv_response=cv_response,
                ocr_response=ocr_response,
            ),
            source=ResolutionSource(
                source="cv",
                reason="cv_conflict",
            ),
        )

    def _resolve_cv_only(
        self,
        cv_wine: Wine,
        cv_slug: str | None,
        cv_response: CVInferenceResponse,
    ) -> RecognitionResolution:
        return RecognitionResolution(
            resolved=True,
            detected_slug=(
                cv_wine.slug
                if cv_wine is not None
                else cv_slug
            ),
            alternatives=self._collect_cv_alternatives(
                selected_slug=(
                    cv_wine.slug
                    if cv_wine is not None
                    else cv_slug
                ),
                response=cv_response,
            ),
            source=ResolutionSource(
                source="cv",
                reason="cv_only",
            ),
        )

    def _resolve_ocr_only(
        self,
        ocr_response: OCRInferenceResponse,
        ocr_wine: Wine | None,
        ocr_slug: str | None,
    ) -> RecognitionResolution:

        if (
            ocr_response.result.status != "matched"
            or ocr_wine is None
        ):
            return RecognitionResolution(
                resolved=False,
                error="ocr_result_ambiguous",
            )

        return RecognitionResolution(
            resolved=True,
            detected_slug=ocr_wine.slug,
            alternatives=self._collect_ocr_alternatives(
                selected_slug=ocr_wine.slug,
                response=ocr_response,
            ),
            source=ResolutionSource(
                source="ocr",
                reason="ocr_only",
            ),
        )

    @staticmethod
    def get_cv_slug(
        response: CVInferenceResponse,
    ) -> str | None:
        if response.error:
            return None

        if not response.results:
            return None

        best = max(
            response.results,
            key=lambda result: result.score,
        )

        return best.payload.slug

    @staticmethod
    def get_ocr_slug(
        response: OCRInferenceResponse,
    ) -> str | None:
        result = response.result

        if result.error:
            return None

        if result.status not in {"matched", "ambiguous"}:
            return None

        if result.best_match is None:
            return None

        return result.best_match.wine_id

    @staticmethod
    def _same_family(
        left: Wine,
        right: Wine,
    ) -> bool:
        left_name = RecognitionResolver._normalize_name(left.name)
        right_name = RecognitionResolver._normalize_name(right.name)

        left_winery = RecognitionResolver._normalize_name(left.winery)
        right_winery = RecognitionResolver._normalize_name(right.winery)

        if (
            left_winery
            and right_winery
            and left_winery != right_winery
        ):
            return False

        if left_name == right_name:
            return True

        left_tokens = set(left_name.split())
        right_tokens = set(right_name.split())

        if not left_tokens or not right_tokens:
            return False

        common = left_tokens & right_tokens

        smaller_size = min(
            len(left_tokens),
            len(right_tokens),
        )

        return (
            len(common) / smaller_size >= 0.8
        )

    @staticmethod
    def _normalize_name(
        value: str | None,
    ) -> str:
        if not value:
            return ""

        return " ".join(
            value.casefold()
            .replace("ё", "е")
            .split()
        )

    def _collect_alternatives(
        self,
        selected_slug: str,
        cv_response: CVInferenceResponse,
        ocr_response: OCRInferenceResponse,
    ) -> list[str]:
        result: list[str] = []

        result.extend(
            self._collect_cv_alternatives(
                selected_slug=selected_slug,
                response=cv_response,
            )
        )

        result.extend(
            self._collect_ocr_alternatives(
                selected_slug=selected_slug,
                response=ocr_response,
            )
        )

        return self._unique(result)

    @staticmethod
    def _collect_cv_alternatives(
        selected_slug: str | None,
        response: CVInferenceResponse,
    ) -> list[str]:
        if selected_slug is None:
            return []

        return RecognitionResolver._unique(
            result.payload.slug
            for result in response.results
            if result.payload.slug != selected_slug
        )

    @staticmethod
    def _collect_ocr_alternatives(
        selected_slug: str | None,
        response: OCRInferenceResponse,
    ) -> list[str]:
        if selected_slug is None:
            return []

        slugs: list[str] = []

        for candidate in response.result.candidates:
            if candidate.wine_id != selected_slug:
                slugs.append(candidate.wine_id)

        return RecognitionResolver._unique(slugs)

    @staticmethod
    def _unique(
        values: Iterable[str],
    ) -> list[str]:
        return list(dict.fromkeys(values))