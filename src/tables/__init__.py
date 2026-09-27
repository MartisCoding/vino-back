from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.tables.recognition_result import RecognitionResult
from src.tables.recognition_task import RecognitionTask
from src.tables.uploaded_images import UploadedImage
from src.tables.wine_image import WineImage
from src.tables.wines import Wine

__all__ = [
    "Base",
    "RecognitionResult",
    "RecognitionTask",
    "UploadedImage",
    "Wine",
    "WineImage",
]