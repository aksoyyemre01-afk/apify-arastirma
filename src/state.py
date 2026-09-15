"""Hangi konuların hangi formatta kullanıldığını takip eder (tekrarı önlemek için).

state/used_topics.json dosyası GitHub Actions tarafından her haftalık
çalışmadan sonra repoya commit edilir, böylece haftalar arasında hafıza korunur.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "used_topics.json"

_state: dict | None = None


def _load() -> dict:
    global _state
    if _state is None:
        if STATE_PATH.exists():
            _state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        else:
            _state = {"used": []}
    return _state


def get_used_ids() -> set[str]:
    return {item["id"] for item in _load()["used"]}


def mark_used(topic_id: str, content_type: str) -> None:
    s = _load()
    s["used"].append(
        {
            "id": topic_id,
            "type": content_type,
            "used_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def save() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(_load(), indent=2, ensure_ascii=False), encoding="utf-8")
