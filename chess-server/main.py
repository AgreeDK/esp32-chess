import logging
import json
import chess

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import engine, Base, SessionLocal
from connection_manager import ConnectionManager
from game_manager import GameManager
from ai_player import AIPlayer
from device_manager import get_or_create_device, is_valid_mac, CLI_MAC

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Globale singletons ─────────────────────────────────────────────────────────
connections = ConnectionManager()
games = GameManager()
ai = AIPlayer(skill_level=10, think_ms=500)


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ai.start()
    logger.info("chess-server klar ✓")
    yield
    try:
        ai.stop()
    except Exception as e:
        logger.warning(f"Stockfish shutdown advarsel: {e}")
    logger.info("chess-server lukket ned")


app = FastAPI(title="chess-server", version="0.3.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── HTTP endpoints ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/api")
def api_status():
    return {"service": "chess-server", "version": "0.3.0", "status": "ok"}


@app.get("/games")
def list_games():
    """Vis alle aktive spil."""
    summary = []
    for gid, session in games._games.items():
        summary.append({
            "game_id": gid,
            "mode": session.mode,
            "status": session.status,
            "turn": session.turn,
            "fullmove": session.board.fullmove_number,
            "players": connections.players_in_room(gid),
        })
    return {"active_games": summary}


@app.get("/devices")
def list_devices():
    """Vis alle registrerede enheder."""
    db = SessionLocal()
    try:
        from models import Device
        devices = db.query(Device).all()
        return {"devices": [
            {"id": d.id, "mac": d.mac_address, "name": d.name, "elo": d.elo}
            for d in devices
        ]}
    finally:
        db.close()


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Klienten skal sende en 'new_game'- eller 'join'-besked som det første,
    med mac_address feltet udfyldt.

    Understøttede beskedtyper:
        new_game    → opret nyt spil  (kræver: mac_address)
        join        → tilslut spil    (kræver: mac_address, game_id)
        move        → udfør et træk   (kræver: from, to)
        resign      → opgiv spillet
        ping        → keepalive
    """
    game_id: str | None = None
    device_name: str = "ukendt"

    await websocket.accept()

    try:
        async for raw in websocket.iter_text():
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Ugyldig JSON"})
                continue

            msg_type = msg.get("type", "")

            # ── new_game ──────────────────────────────────────────────────────
            if msg_type == "new_game":
                mac = msg.get("mac_address", "").strip()
                if not mac:
                    mac = CLI_MAC

                if not is_valid_mac(mac):
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Ugyldig MAC-adresse: '{mac}'"
                    })
                    continue

                db = SessionLocal()
                try:
                    device = get_or_create_device(db, mac, name=msg.get("device_name", ""))
                    device_name = device.name
                finally:
                    db.close()

                mode = msg.get("mode", "vs_stockfish")
                session = games.create_game(mode=mode)
                game_id = session.game_id
                connections.join_room(websocket, game_id, device_name)

                await websocket.send_json({
                    **session.state_dict(),
                    "type": "game_created",
                    "game_id": game_id,
                    "device": device_name,
                })
                logger.info(f"[{game_id}] '{device_name}' oprettede spil ({mode})")

            # ── join ──────────────────────────────────────────────────────────
            elif msg_type == "join":
                mac = msg.get("mac_address", "").strip()
                if not mac:
                    mac = CLI_MAC

                if not is_valid_mac(mac):
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Ugyldig MAC-adresse: '{mac}'"
                    })
                    continue

                gid = msg.get("game_id", "")
                session = games.get_game(gid)
                if not session:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Spil '{gid}' ikke fundet"
                    })
                    continue

                db = SessionLocal()
                try:
                    device = get_or_create_device(db, mac, name=msg.get("device_name", ""))
                    device_name = device.name
                finally:
                    db.close()

                game_id = gid
                connections.join_room(websocket, game_id, device_name)

                await websocket.send_json({
                    **session.state_dict(),
                    "type": "joined",
                    "device": device_name,
                })
                logger.info(f"[{game_id}] '{device_name}' tilsluttede sig")

            # ── move ──────────────────────────────────────────────────────────
            elif msg_type == "move":
                if not game_id:
                    await websocket.send_json({"type": "error", "message": "Ikke tilsluttet et spil"})
                    continue

                from_sq = msg.get("from", "")
                to_sq = msg.get("to", "")

                ok, err, session = games.apply_move(game_id, from_sq, to_sq)
                if not ok:
                    await websocket.send_json({"type": "error", "message": err})
                    continue

                await connections.broadcast(game_id, session.state_dict())

                if session.status != "playing":
                    continue

                if session.mode == "vs_stockfish" and session.turn == "black":
                    ai_move = ai.best_move(session.board)
                    if ai_move:
                        from_uci = chess.square_name(ai_move.from_square)
                        to_uci = chess.square_name(ai_move.to_square)
                        session.board.push(ai_move)
                        session.fen_history.append(session.board.fen())

                        await connections.broadcast(game_id, {
                            "type": "move",
                            "from": from_uci,
                            "to": to_uci,
                            "game_id": game_id,
                        })
                        await connections.broadcast(game_id, session.state_dict())

            # ── resign ────────────────────────────────────────────────────────
            elif msg_type == "resign":
                if game_id:
                    session = games.resign(game_id)
                    if session:
                        await connections.broadcast(game_id, {
                            "type": "state",
                            "game_id": game_id,
                            "fen": session.board.fen(),
                            "turn": session.turn,
                            "status": "resigned",
                            "winner": None,
                            "in_check": False,
                            "fullmove": session.board.fullmove_number,
                        })

            # ── ping ──────────────────────────────────────────────────────────
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Ukendt beskedtype: '{msg_type}'"
                })

    except WebSocketDisconnect:
        if game_id:
            connections.disconnect(websocket, game_id)
            logger.info(f"[{game_id}] '{device_name}' afbrudt")
