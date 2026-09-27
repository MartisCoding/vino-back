from typing import Literal

from pydantic import BaseModel, ConfigDict


class RecognitionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    slug: str


class CVRecognitionResult(BaseModel):
    id: int | str
    score: float
    payload: RecognitionPayload


class CVInferenceResponse(BaseModel):
    request_id: str
    results: list[CVRecognitionResult]
    expected_score: float | None = None
    error: str | None = None


class OCRLine(BaseModel):
    text: str
    confidence: float | None = None


class OCREvidence(BaseModel):
    field: str
    ocr_text: str
    catalog_key: str
    ocr_indices: list[int]
    similarity: float
    weighted_similarity: float
    contribution: float
    matched_words: int | None = None


class OCRCandidate(BaseModel):
    wine_id: str
    name: str
    producer: str | None = None
    image_url: str | None = None
    match_score: float
    evidence: list[OCREvidence]
    evidence_coverage: float | None = None


class OCRTiming(BaseModel):
    model_loading: float = 0.0
    catalog_loading: float = 0.0
    image_decode: float = 0.0
    craft_detect: float = 0.0
    parseq_ocr: float = 0.0
    catalog_match: float = 0.0
    request_total: float = 0.0


class OCRResult(BaseModel):
    status: Literal["matched", "ambiguous", "unresolved", "error"]

    ocr_lines: list[OCRLine] = []
    best_match: OCRCandidate | None = None
    alternatives: list[OCRCandidate] = []
    candidates: list[OCRCandidate] = []

    score_type: str

    image_path: str | None = None
    timing_seconds: OCRTiming | None = None

    rejection_reason: str | None = None
    error: str | None = None


class OCRInferenceResponse(BaseModel):
    request_id: str
    result: OCRResult


class ResolutionSource(BaseModel):
    source: Literal["cv", "ocr", "both"]
    reason: Literal[
        "both_agree",
        "ocr_variant_override",
        "cv_conflict",
        "cv_only",
        "ocr_only",
    ]


class RecognitionResolution(BaseModel):
    resolved: bool
    detected_slug: str | None = None
    alternatives: list[str] | None = None
    source: ResolutionSource | None = None
    error: str | None = None