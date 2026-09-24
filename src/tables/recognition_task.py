from datetime import datetime
from uuid import uuid4
from sqlalchemy import Integer, String, ForeignKey, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from src.tables import Base

class RecognitionTask(Base):
    
    __tablename__ = "recognition_tasks"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    status: Mapped[str] = mapped_column(Enum("pending", "processing", "completed", "failed", name="recognition_task_status"), nullable=False)
    
    uploaded_image_id: Mapped[int] = mapped_column(Integer(), ForeignKey("uploaded_images.id"), nullable=False)
    
    detected_wine_id: Mapped[int | None] = mapped_column(Integer(), ForeignKey("wines.id"), nullable=True)
    detected_wine_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)