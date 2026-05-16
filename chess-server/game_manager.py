import chess
import uuid
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _game_status(board: chess.Board) -> str:
    """Oversæt python-chess spillstatus til vores protokol-streng."""
    if board.is_checkmate():
        return "checkmate"
    if board.is_stalemate():
        return "stalemate"
    if board.is_insufficient_material():
        return "draw"
    if board.is_seventyfive_moves():
        return "draw"
    if board.is_fivefold_repetition():
        return "draw"
    return "playing"


@dataclass
class GameSession:
    game_id: str
    board: chess.Board = field(default_factory=chess.Board)
    mode: str = "vs_stockfish"   # vs_stockfish | vs_player
    fen_history: list[str] = field(default_factory=list)

    def __post_init__(self):
        # Gem startposition
        self.fen_history.append(self.board.fen())

    @property
    def status(self) -> str:
        return _game_status(self.board)

    @property
    def turn(self) -> str:
        return "white" if self.board.turn == chess.WHITE else "black"

    def state_dict(self) -> dict:
        """Returner spillets tilstand som dict klar til JSON-serialisering."""
        outcome = self.board.outcome()
        winner = None
        if outcome and outcome.winner is not None:
            winner = "white" if outcome.winner == chess.WHITE else "black"

        return {
            "type": "state",
            "game_id": self.game_id,
            "fen": self.board.fen(),
            "turn": self.turn,
            "status": self.status,
            "winner": winner,
            "in_check": self.board.is_check(),
            "fullmove": self.board.fullmove_number,
        }


class GameManager:
    def __init__(self):
        self._games: dict[str, GameSession] = {}

    def create_game(self, mode: str = "vs_stockfish") -> GameSession:
        game_id = str(uuid.uuid4())[:8]
        session = GameSession(game_id=game_id, mode=mode)
        self._games[game_id] = session
        logger.info(f"Nyt spil oprettet: {game_id} ({mode})")
        return session

    def get_game(self, game_id: str) -> GameSession | None:
        return self._games.get(game_id)

    def apply_move(self, game_id: str, from_sq: str, to_sq: str) -> tuple[bool, str, GameSession | None]:
        """
        Forsøg at udføre et træk.
        Returnerer (success, error_message, session).
        """
        session = self.get_game(game_id)
        if not session:
            return False, f"Spil '{game_id}' ikke fundet", None

        if session.status != "playing":
            return False, f"Spillet er slut ({session.status})", session

        # Byg UCI-streng og validér
        uci = from_sq.lower() + to_sq.lower()

        # Håndter forfremmelse — antag altid dronning for nu
        move = chess.Move.from_uci(uci)
        piece = session.board.piece_at(move.from_square)
        if (
            piece
            and piece.piece_type == chess.PAWN
            and chess.square_rank(move.to_square) in (0, 7)
        ):
            move = chess.Move.from_uci(uci + "q")

        if move not in session.board.legal_moves:
            legal_ucis = [m.uci() for m in session.board.legal_moves]
            logger.debug(f"Ugyldigt træk {uci}. Lovlige: {legal_ucis[:5]}...")
            return False, f"Ugyldigt træk: {uci}", session

        session.board.push(move)
        session.fen_history.append(session.board.fen())
        logger.info(f"[{game_id}] Træk: {uci} → {session.board.fen()[:30]}...")
        return True, "", session

    def resign(self, game_id: str) -> GameSession | None:
        session = self.get_game(game_id)
        if session:
            # Markér spillet som opgivet ved at sætte en custom status
            # python-chess har ingen resign — vi tracker det eksternt
            session._resigned = True
        return session

    def remove_game(self, game_id: str):
        self._games.pop(game_id, None)
        logger.info(f"Spil fjernet: {game_id}")
