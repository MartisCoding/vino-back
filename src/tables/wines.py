from datetime import datetime

from sqlalchemy import Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.tables import Base


class Wine(Base):
    __tablename__ = "wines"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    country: Mapped[str] = mapped_column(String(255), nullable=False)
    
    region: Mapped[str] = mapped_column(String(255), nullable=False)
    
    winery: Mapped[str] = mapped_column(String(255), nullable=False)
    
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    
    description: Mapped[str] = mapped_column(String(4096), nullable=False)
    
    source_url: Mapped[str] = mapped_column(String(255), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), server_onupdate=func.now(), nullable=False)
    
