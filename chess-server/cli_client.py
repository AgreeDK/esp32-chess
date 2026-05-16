#!/usr/bin/env python3
"""
chess-client — CLI testklient til chess-server (Fase 1)

Brug:
    python cli_client.py                     # nyt spil
    python cli_client.py --game <game_id>    # tilslut eksisterende spil
    python cli_client.py --host 192.168.1.x  # anden server
"""

import asyncio
import json
import argparse
import websockets

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8000


def print_board(fen: str):
    """Simpel ASCII-visning af brættet fra FEN-streng."""
    pieces = {
        "r": "♖", "n": "♘", "b": "♗", "q": "♕", "k": "♔", "p": "♙",
        "R": "♜", "N": "♞", "B": "♝", "Q": "♛", "K": "♚", "P": "♟",
    }
    board_fen = fen.split(" ")[0]
    rows = board_fen.split("/")

    print("\n  a b c d e f g h")
    print("  ─────────────────")
    for rank_idx, row in enumerate(rows):
        rank_num = 8 - rank_idx
        line = f"{rank_num}│"
        for ch in row:
            if ch.isdigit():
                line += "· " * int(ch)
            else:
                line += pieces.get(ch, ch) + " "
        print(line)
    print("  ─────────────────")


def print_state(state: dict):
    """Udskriv spillets tilstand."""
    print_board(state.get("fen", ""))
    status = state.get("status", "?")
    turn = state.get("turn", "?")
    check = " ⚠ SKAK!" if state.get("in_check") else ""
    move_num = state.get("fullmove", "?")

    if status == "playing":
        print(f"\nTræk #{move_num} — {turn.upper()} spiller{check}")
    elif status == "checkmate":
        winner = state.get("winner", "?")
        print(f"\n♛ SKAKMAT! {winner.upper()} vinder!")
    elif status in ("stalemate", "draw"):
        print(f"\n½–½ Remis ({status})")
    elif status == "resigned":
        print("\nSpillet er opgivet.")
    print()


async def play(host: str, port: int, game_id: str | None):
    uri = f"ws://{host}:{port}/ws"
    print(f"Forbinder til {uri} …")

    async with websockets.connect(uri) as ws:
        # ── Opret eller tilslut spil ──────────────────────────────────────
        if game_id:
            await ws.send(json.dumps({"type": "join", "game_id": game_id}))
        else:
            await ws.send(json.dumps({"type": "new_game", "mode": "vs_stockfish"}))

        # Modtag bekræftelse
        resp = json.loads(await ws.recv())
        if resp.get("type") == "error":
            print(f"Fejl: {resp['message']}")
            return

        gid = resp.get("game_id", game_id)
        print(f"\n{'Nyt' if not game_id else 'Tilsluttet'} spil: {gid}")
        print("Du spiller HVID mod Stockfish.")
        print("Skriv træk som: e2 e4  (fra-felt til-felt)")
        print("Skriv 'quit' eller 'resign' for at afslutte.\n")
        print_state(resp)

        # ── Spil-løkke ────────────────────────────────────────────────────
        while True:
            # Tjek om spillet er slut
            status = resp.get("status", "playing")
            if status != "playing":
                break

            # Spillerens input (kørende i executor for ikke at blokere event-loop)
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("Dit træk: ").strip().lower()
                )
            except (EOFError, KeyboardInterrupt):
                print("\nAfbrudt.")
                break

            if user_input in ("quit", "exit"):
                break

            if user_input == "resign":
                await ws.send(json.dumps({"type": "resign", "game_id": gid}))
                resp = json.loads(await ws.recv())
                print_state(resp)
                break

            parts = user_input.split()
            if len(parts) != 2:
                print("→ Skriv to felter adskilt af mellemrum, f.eks.: e2 e4\n")
                continue

            from_sq, to_sq = parts
            await ws.send(json.dumps({
                "type": "move",
                "from": from_sq,
                "to": to_sq,
                "game_id": gid,
            }))

            # Modtag svar (kan være fejl, state, AI-træk + state)
            # Rækkefølge fra server ved gyldigt træk:
            #   1. state  (efter spillerens træk, turn="black")
            #   2. move   (Stockfishs træk)
            #   3. state  (efter Stockfishs træk, turn="white")
            # Vi er færdige når vi modtager en state hvor det er hvids tur,
            # eller når spillet er slut.
            done = False
            while not done:
                raw = await ws.recv()
                resp = json.loads(raw)
                rtype = resp.get("type")

                if rtype == "error":
                    print(f"→ {resp['message']}\n")
                    done = True

                elif rtype == "move":
                    # Stockfishs træk — vis det, men vent på den efterfølgende state
                    print(f"Stockfish: {resp['from']} → {resp['to']}")

                elif rtype == "state":
                    print_state(resp)
                    status = resp.get("status", "playing")
                    turn = resp.get("turn", "white")
                    # Stop når spillet er slut, eller når det igen er hvids tur
                    if status != "playing" or turn == "white":
                        done = True

        print("Spillet slut. Farvel!")


def main():
    parser = argparse.ArgumentParser(description="chess-client CLI")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server hostname/IP")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Server port")
    parser.add_argument("--game", default=None, help="Tilslut eksisterende game_id")
    args = parser.parse_args()

    asyncio.run(play(args.host, args.port, args.game))


if __name__ == "__main__":
    main()
