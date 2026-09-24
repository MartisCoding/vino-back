from datetime import datetime
from src.tables import Base
from sqlalchemy import DateTime, String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

class WineImage(Base):
    __tablename__ = "wine_images"

    id: Mapped[int] = mapped_column(primary_key=True)

    wine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("wines.id"),
        nullable=False,
    )
    wine_external_id: Mapped[str] = mapped_column(String(255), ForeignKey("wines.external_id"), nullable=False)
    
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)