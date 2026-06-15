"""
In-memory job store with JSON persistence.
Tracks per-tech state and all submitted jobs for the day.
"""
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
STATE_FILE = Path(__file__).parent / "state.json"

# ── State keys ───────────────────────────────────────────────────────────────
# tech_state[phone] = {
#   "state": "idle" | "awaiting_notes" | "awaiting_wallfish_photos" | "eod_submitted",
#   "current_job_id": str | None,
#   "wallfish_photos_received": int,
#   "today_job_ids": [str],
# }
_tech_state: dict = {}

# job_store[work_order_id] = { all fields + pay + status }
_job_store: dict = {}


def _load():
    global _tech_state, _job_store
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            _tech_state = data.get("tech_state", {})
            _job_store = data.get("job_store", {})
        except Exception as e:
            logger.warning("Could not load state: %s", e)


def _save():
    try:
        STATE_FILE.write_text(
            json.dumps({"tech_state": _tech_state, "job_store": _job_store}, indent=2)
        )
    except Exception as e:
        logger.warning("Could not persist state: %s", e)


_load()


# ── Tech state ───────────────────────────────────────────────────────────────

def get_tech_state(phone: str) -> dict:
    return _tech_state.get(phone, {
        "state": "idle",
        "current_job_id": None,
        "wallfish_photos_received": 0,
        "today_job_ids": [],
        "eod_submitted": False,
    })


def set_tech_state(phone: str, **kwargs):
    current = get_tech_state(phone)
    current.update(kwargs)
    _tech_state[phone] = current
    _save()


def reset_tech_state(phone: str):
    _tech_state[phone] = {
        "state": "idle",
        "current_job_id": None,
        "wallfish_photos_received": 0,
        "today_job_ids": _tech_state.get(phone, {}).get("today_job_ids", []),
        "eod_submitted": False,
    }
    _save()


# ── Job store ────────────────────────────────────────────────────────────────

def save_job(job: dict) -> str:
    work_order_id = job["work_order_id"]
    job["submitted_at"] = datetime.now().isoformat()
    job["status"] = "pending"  # yellow
    _job_store[work_order_id] = job

    phone = job.get("tech_phone", "")
    if phone:
        state = get_tech_state(phone)
        ids = state.get("today_job_ids", [])
        if work_order_id not in ids:
            ids.append(work_order_id)
        set_tech_state(phone, today_job_ids=ids, current_job_id=work_order_id)

    _save()
    return work_order_id


def get_job(work_order_id: str) -> Optional[dict]:
    return _job_store.get(work_order_id)


def update_job_status(work_order_id: str, status: str, reason: str = ""):
    if work_order_id in _job_store:
        _job_store[work_order_id]["status"] = status
        if reason:
            _job_store[work_order_id]["status_reason"] = reason
        _save()


def append_job_note(work_order_id: str, note: str, photo_urls: list = None):
    if work_order_id in _job_store:
        notes = _job_store[work_order_id].get("notes", [])
        entry = {"timestamp": datetime.now().isoformat(), "text": note}
        if photo_urls:
            entry["photos"] = photo_urls
        notes.append(entry)
        _job_store[work_order_id]["notes"] = notes
        _save()


def get_todays_jobs() -> list[dict]:
    today = date.today().isoformat()
    return [
        j for j in _job_store.values()
        if j.get("submitted_at", "").startswith(today)
    ]


def get_jobs_for_tech(phone: str) -> list[dict]:
    today = date.today().isoformat()
    return [
        j for j in _job_store.values()
        if j.get("tech_phone") == phone
        and j.get("submitted_at", "").startswith(today)
    ]


def reset_daily_state():
    """Called at midnight to clear today_job_ids and eod flags."""
    for phone in _tech_state:
        _tech_state[phone]["today_job_ids"] = []
        _tech_state[phone]["eod_submitted"] = False
        _tech_state[phone]["state"] = "idle"
    _save()
