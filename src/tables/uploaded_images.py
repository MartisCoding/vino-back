from datetime import datetime
from src.tables import Base
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

class UploadedImage(Base):
    __tablename__ = "uploaded_images"

    id: Mapped[int] = mapped_column(primary_key=True)

    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
