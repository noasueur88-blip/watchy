from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


DATA_DIR = Path(__file__).resolve().parent / "data"
STATE_FILE = DATA_DIR / "state.json"

DEFAULT_STATE = {
    "maintenance": False,
    "user_scores": {},
    "bad_words": ["hack", "nuke", "raid", "ddos", "exploit"],
}

_LOCK = Lock()


def _ensure_state_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps(DEFAULT_STATE, indent=2), encoding="utf-8")


def load_state() -> dict:
    _ensure_state_file()
    with _LOCK:
        with STATE_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

    state = DEFAULT_STATE.copy()
    state.update(data)
    state["user_scores"] = {str(k): int(v) for k, v in state.get("user_scores", {}).items()}
    return state


def save_state(state: dict) -> None:
    _ensure_state_file()
    payload = {
        "maintenance": bool(state.get("maintenance", False)),
        "user_scores": {str(k): int(v) for k, v in state.get("user_scores", {}).items()},
        "bad_words": list(state.get("bad_words", DEFAULT_STATE["bad_words"])),
    }
    with _LOCK:
        with STATE_FILE.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
