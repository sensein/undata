"""V2 element mapping model — bidirectional transforms between elements."""

from datetime import datetime

from sqlalchemy import Float, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class ElementMappingV2(Base):
    __tablename__ = "element_mapping_v2"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_element_uri: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_element_uri: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    function_type: Mapped[str] = mapped_column(String(50), nullable=False)
    expression: Mapped[str | None] = mapped_column(Text)
    expression_type: Mapped[str | None] = mapped_column(String(50))
    sssom_predicate: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    attributed_to: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
