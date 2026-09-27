from collections.abc import Iterable

from src.models.inference import (
    CVInferenceResponse,
    OCRInferenceResponse,
    RecognitionResolution,
    ResolutionSource,
)
from src.tables import Wine


class RecognitionResolver:

    def resolve(
        self,
        cv_response: CVInferenceResponse,
        ocr_response: OCRInferenceResponse,
        cv_wine: Wine | None,
        ocr_wine: Wine | None,
    ) -> RecognitionResolution:

        cv_slug = self.get_cv_slug(cv_response)
        ocr_slug = self.get_ocr_slug(ocr_response)

        # OCR has priority whenever it produced a usable result.
        if ocr_wine is not None:
            source = "ocr"

            if cv_wine is not None and cv_wine.id == ocr_wine.id:
                source = "both"
                reason = "both_agree"
            else:
                reason = "ocr_priority"

            return RecognitionResolution(
                resolved=True,
                detected_slug=ocr_wine.slug,
                alternatives=self._collect_alternatives(
                    selected_slug=ocr_wine.slug,
                    cv_response=cv_response,
                    ocr_response=ocr_response,
                ),
                source=ResolutionSource(
                    source=source,
                    reason=reason, #type: ignore
                ),
            )

        # OCR did not produce a usable wine, fallback to CV.
        if cv_wine is not None:
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
                    reason="cv_only",
                ),
            )

        return RecognitionResolution(
            resolved=False,
            error="no_recognition_result",
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

        if result.status != "matched": # CV now functions as a fallback for OCR, so we only consider "matched" results as valid.
            return None

        if result.best_match is None:
            return None

        return result.best_match.wine_id

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

        return RecognitionResolver._unique(
            candidate.wine_id
            for candidate in response.result.candidates
            if candidate.wine_id != selected_slug
        )

    @staticmethod
    def _unique(
        values: Iterable[str],
    ) -> list[str]:
        return list(dict.fromkeys(values))