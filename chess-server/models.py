from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(String, primary_key=True)
    mode = Column(String, default="vs_stockfish")   # vs_stockfish | vs_player
    status = Column(String, default="playing")      # playing | checkmate | draw | resigned
    created_at = Column(DateTime, server_default=func.now())
    fen_history = Column(Text, default="")          # FEN-strenge adskilt af newline


class Move(Base):
    __tablename__ = "moves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, ForeignKey("games.id"))
    ply = Column(Integer)                           # halvtræk-nummer
    uci = Column(String)                            # f.eks. "e2e4"
    timestamp = Column(DateTime, server_default=func.now())


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac_address = Column(String, unique=True)
    name = Column(String, default="ESP32")
    elo = Column(Integer, default=800)
