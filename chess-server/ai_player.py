import chess
import chess.engine
import logging

logger = logging.getLogger(__name__)

STOCKFISH_PATH = "/usr/games/stockfish"   # standard sti på Ubuntu/Debian
DEFAULT_SKILL = 10                        # 0–20
DEFAULT_THINK_MS = 500                    # tænketid i ms


class AIPlayer:
    def __init__(
        self,
        stockfish_path: str = STOCKFISH_PATH,
        skill_level: int = DEFAULT_SKILL,
        think_ms: int = DEFAULT_THINK_MS,
    ):
        self.stockfish_path = stockfish_path
        self.skill_level = skill_level
        self.think_ms = think_ms
        self._engine: chess.engine.SimpleEngine | None = None

    def start(self):
        """Start Stockfish-processen."""
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
            self._engine.configure({"Skill Level": self.skill_level})
            logger.info(f"Stockfish startet (skill={self.skill_level}, think={self.think_ms}ms)")
        except FileNotFoundError:
            raise RuntimeError(
                f"Stockfish ikke fundet på '{self.stockfish_path}'. "
                "Installer med: sudo apt install stockfish"
            )

    def stop(self):
        """Stop Stockfish-processen."""
        if self._engine:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None
            logger.info("Stockfish stoppet")

    def best_move(self, board: chess.Board) -> chess.Move | None:
        """Returnér Stockfishs bedste træk for den givne brætposition."""
        if not self._engine:
            raise RuntimeError("AIPlayer er ikke startet — kald start() først")
        if board.is_game_over():
            return None

        limit = chess.engine.Limit(time=self.think_ms / 1000)
        result = self._engine.play(board, limit)
        return result.move

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()
