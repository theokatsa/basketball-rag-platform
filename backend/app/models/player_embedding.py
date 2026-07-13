from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db import Base


class PlayerEmbedding(Base):
    __tablename__ = "player_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season = Column(String, nullable=False)
    embedding = Column(Text, nullable=False)
    source_text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)