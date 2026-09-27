from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.tables import Base

    
# In this table we don't store any results of recognition, only the fact of the task being created.
class RecognitionTask(Base):
    __tablename__ = "recognition_tasks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    uploaded_image_id: Mapped[int] = mapped_column(
        Integer(),
        ForeignKey("uploaded_images.id"),
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )