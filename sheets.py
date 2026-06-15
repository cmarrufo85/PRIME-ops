"""
Google Sheets integration.
Tab 1 (Jobs) is written programmatically.
Tabs 2-7 use Google Sheets formulas — set up once via init_spreadsheet().
"""
import logging
from datetime import datetime
from typing import Optional

from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_SHEETS_ID

logger = logging.getLogger(__name__)

# Lazy init — don't crash on startup if Sheets not configured
_gc = None
_sheet = None

HEADERS = [
    "Work Order ID", "Subscriber ID", "Subscriber Name",
    "Address", "City", "State", "ZIP", "Phone",
    "Time Slot", "Delivery Window", "Activity Type",
    "Tech Name", "Tech Phone", "Is Apartment",
    "Extender Count", "Wallfish", "Buried Drop",
    "Base Pay", "Add-ons", "Total Pay",
    "Status", "Status Reason",
    "Notes", "Photo URLs",
    "Submitted At", "Date",
]


def _get_sheet():
    global _gc, _sheet
    if _sheet is not None:
        return _sheet
    if not GOOGLE_SHEETS_ID or not GOOGLE_CREDENTIALS_FILE.exists():
        logger.warning("Google Sheets not configured — skipping sheet write")
        return None
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_file(
            str(GOOGLE_CREDENTIALS_FILE),
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        _gc = gspread.authorize(creds)
        _sheet = _gc.open_by_key(GOOGLE_SHEETS_ID)
        return _sheet
    except Exception as e:
        logger.error("Google Sheets init failed: %s", e)
        return None


def _jobs_tab():
    sheet = _get_sheet()
    if not sheet:
        return None
    try:
        return sheet.worksheet("Jobs")
    except Exception:
        ws = sheet.add_worksheet(title="Jobs", rows=1000, cols=len(HEADERS))
        ws.append_row(HEADERS)
        return ws


def log_job(job: dict) -> bool:
    ws = _jobs_tab()
    if not ws:
        return False
    try:
        notes_text = "; ".join(
            n.get("text", "") for n in job.get("notes", [])
        )
        photo_urls = "; ".join(
            url
            for n in job.get("notes", [])
            for url in n.get("photos", [])
        )
        pay = job.get("pay", {})
        row = [
            job.get("work_order_id", ""),
            job.get("subscriber_id", ""),
            job.get("subscriber_name", ""),
            job.get("address", ""),
            job.get("city", ""),
            job.get("state", ""),
            job.get("zip", ""),
            job.get("phone", ""),
            job.get("time_slot", ""),
            job.get("delivery_window", ""),
            job.get("activity_type", ""),
            job.get("tech_name", ""),
            job.get("tech_phone", ""),
            "Yes" if job.get("is_apartment") else "No",
            job.get("extender_count", 0),
            "Yes" if job.get("wallfish") else "No",
            "Yes" if job.get("buried_drop") else "No",
            pay.get("base_amount", 0),
            pay.get("total", 0) - pay.get("base_amount", 0),
            pay.get("total", 0),
            job.get("status", "pending"),
            job.get("status_reason", ""),
            notes_text,
            photo_urls,
            job.get("submitted_at", ""),
            job.get("submitted_at", "")[:10],
        ]
        ws.append_row(row)
        return True
    except Exception as e:
        logger.error("Sheet log_job failed: %s", e)
        return False


def update_job_status_in_sheet(work_order_id: str, status: str, reason: str = "") -> bool:
    ws = _jobs_tab()
    if not ws:
        return False
    try:
        cell = ws.find(work_order_id)
        if cell:
            status_col = HEADERS.index("Status") + 1
            ws.update_cell(cell.row, status_col, status)
            if reason:
                reason_col = HEADERS.index("Status Reason") + 1
                ws.update_cell(cell.row, reason_col, reason)
        return True
    except Exception as e:
        logger.error("Sheet status update failed: %s", e)
        return False


def init_spreadsheet():
    """
    One-time setup: create all tabs with headers and formulas.
    Run this manually once after providing credentials.
    """
    sheet = _get_sheet()
    if not sheet:
        logger.error("Cannot init — Sheets not configured")
        return

    # Ensure Jobs tab exists
    _jobs_tab()

    tab_configs = [
        ("By Technician", "=SORT(FILTER(Jobs!A:Z, Jobs!L:L<>\"\"), 12, TRUE)"),
        ("By Date", "=SORT(FILTER(Jobs!A:Z, Jobs!Z:Z<>\"\"), 26, FALSE)"),
        ("Open Pending", "=FILTER(Jobs!A:Z, Jobs!U:U=\"pending\")"),
        ("Completed", "=FILTER(Jobs!A:Z, Jobs!U:U=\"green\")"),
        ("Pay Summary", ""),  # complex — set up manually or extend here
        ("Discrepancies", ""),  # written programmatically by daily.py
    ]

    existing = [ws.title for ws in sheet.worksheets()]
    for title, formula in tab_configs:
        if title not in existing:
            ws = sheet.add_worksheet(title=title, rows=1000, cols=30)
            if formula:
                ws.update("A1", [[formula]])
            logger.info("Created tab: %s", title)

    logger.info("Spreadsheet initialized.")
