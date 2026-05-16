# chess-server — Fase 2

Python/FastAPI backend til esp32-chess projektet.

## Krav

- Python 3.11+
- Stockfish: `sudo apt install stockfish`
- websocat (til manuel WebSocket-test):
  ```bash
  sudo wget -O /usr/local/bin/websocat https://github.com/vi/websocat/releases/latest/download/websocat.x86_64-unknown-linux-musl
  sudo chmod +x /usr/local/bin/websocat
  ```

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Start server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Stop serveren med `Ctrl+C`.

## Test med CLI-klient

```bash
# Nyt spil (på samme maskine)
python cli_client.py

# Tilslut eksisterende spil
python cli_client.py --game <game_id>

# Mod server på NUC
python cli_client.py --host 192.168.1.x
```

## Test med websocat (Fase 2)

```bash
websocat ws://localhost:8000/ws
{"type":"new_game","mac_address":"aa:bb:cc:dd:ee:ff","device_name":"MinPC"}
{"type":"move","from":"e2","to":"e4","game_id":"<game_id>"}
{"type":"ping"}
```

## HTTP endpoints

```bash
# Serversatus
curl http://localhost:8000/

# Aktive spil
curl http://localhost:8000/games

# Registrerede enheder
curl http://localhost:8000/devices
```

## Beskedprotokol (WebSocket JSON)

| Type | Retning | Felter | Beskrivelse |
|------|---------|--------|-------------|
| `new_game` | → server | `mac_address`, `mode`, `device_name` | Opret nyt spil |
| `join` | → server | `mac_address`, `game_id` | Tilslut eksisterende spil |
| `move` | → server | `from`, `to`, `game_id` | Udfør træk |
| `resign` | → server | | Opgiv spillet |
| `ping` | → server | | Keepalive |
| `game_created` | → klient | `game_id`, `device`, + state | Spil oprettet |
| `joined` | → klient | `device`, + state | Tilsluttet spil |
| `state` | → klient | `fen`, `turn`, `status`, `winner`, `in_check` | Opdateret bræt |
| `move` | → klient | `from`, `to`, `game_id` | AI's træk |
| `error` | → klient | `message` | Fejlbesked |

## Projektstruktur

```
chess-server/
├── main.py               # FastAPI app + WebSocket endpoint
├── connection_manager.py # Aktive forbindelser + rooms
├── game_manager.py       # Spillogik, tur-håndtering
├── ai_player.py          # Stockfish subprocess wrapper
├── device_manager.py     # MAC-baseret auto-registrering
├── models.py             # SQLAlchemy modeller
├── database.py           # DB session setup
├── cli_client.py         # CLI testklient
└── requirements.txt
```
