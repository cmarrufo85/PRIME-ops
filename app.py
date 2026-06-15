import logging
import re
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request
from twilio.request_validator import RequestValidator

from config import (
    DAILY_REPORT_HOUR,
    EOD_REMINDER_HOUR,
    TWILIO_AUTH_TOKEN,
    TWILIO_NUMBER,
    WEBHOOK_BASE_URL,
)
from crew import get_tech, is_registered, is_supervisor
from daily import eod_reminder, midnight_reset, supervisor_report
from jobs import (
    append_job_note,
    get_job,
    get_tech_state,
    reset_tech_state,
    save_job,
    set_tech_state,
)
from pay import calculate_pay
from sheets import log_job
from sms import send_sms
from vision import classify_eod_screenshot, extract_work_order

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Scheduler ────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone="America/Chicago")
scheduler.add_job(eod_reminder, "cron", hour=EOD_REMINDER_HOUR, minute=0)
scheduler.add_job(supervisor_report, "cron", hour=DAILY_REPORT_HOUR, minute=0)
scheduler.add_job(midnight_reset, "cron", hour=0, minute=1)
scheduler.start()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_notes_for_addons(text: str) -> dict:
    """Pull add-on declarations from tech's text message."""
    text_lower = text.lower()
    extender_count = 0
    match = re.search(r"(\d+)\s*extender", text_lower)
    if match:
        extender_count = int(match.group(1))
    elif "extender" in text_lower:
        extender_count = 1

    return {
        "extender_count": extender_count,
        "wallfish": "wallfish" in text_lower or "wall fish" in text_lower,
        "buried_drop": "buried" in text_lower or "buried drop" in text_lower,
    }


def _confirmation_text(tech_name: str, job: dict, pay) -> str:
    notes_list = [n.get("text", "") for n in job.get("notes", []) if n.get("text")]
    notes_str = notes_list[0] if notes_list else "None"

    return (
        f"✓ Job logged — {tech_name}\n"
        f"Customer: {job['subscriber_name']}\n"
        f"Address: {job['address']}, {job['city']}, {job['state']} {job['zip']}\n"
        f"Work Order: {job['work_order_id']}\n"
        f"Type: {job['activity_type']}\n"
        f"\nPAY BREAKDOWN:\n"
        f"{pay.format_text()}\n"
        f"\nSTATUS: 🟡 Pending Metronet confirmation\n"
        f"Notes logged: {notes_str}\n"
        f"\nSend end of day route screenshot when complete."
    )


def _handle_work_order_screenshot(from_number: str, tech: dict, media_url: str, content_type: str, body_text: str):
    """Process a new work order screenshot."""
    logger.info("Processing work order screenshot from %s", tech["name"])

    extracted = extract_work_order(media_url, content_type)

    if not extracted or extracted.get("work_order_id") == "NOT_A_WORK_ORDER":
        send_sms(
            from_number,
            "PRIME: Couldn't read that as a work order. "
            "Make sure you're sending the Oracle work order detail screen. Try again.",
        )
        return

    if not extracted.get("work_order_id"):
        send_sms(
            from_number,
            "PRIME: Got the screenshot but couldn't pull the Work Order ID. "
            "Can you resend a clearer photo of the full screen?",
        )
        return

    # Parse add-ons from any text sent with the screenshot
    addons = _parse_notes_for_addons(body_text or "")

    pay = calculate_pay(
        activity_type=extracted.get("activity_type", "Full Install"),
        experienced=tech["experienced"],
        apt=extracted.get("is_apartment", False),
        extender_count=addons["extender_count"],
        wallfish=addons["wallfish"],
        buried_drop=addons["buried_drop"],
    )

    job = {
        "work_order_id": extracted["work_order_id"],
        "subscriber_id": extracted.get("subscriber_id", ""),
        "subscriber_name": extracted.get("subscriber_name", "Unknown"),
        "address": extracted.get("address", ""),
        "city": extracted.get("city", ""),
        "state": extracted.get("state", ""),
        "zip": extracted.get("zip", ""),
        "phone": extracted.get("phone", ""),
        "time_slot": extracted.get("time_slot", ""),
        "delivery_window": extracted.get("delivery_window", ""),
        "activity_type": extracted.get("activity_type", "Full Install"),
        "is_apartment": extracted.get("is_apartment", False),
        "extender_count": addons["extender_count"],
        "wallfish": addons["wallfish"],
        "buried_drop": addons["buried_drop"],
        "tech_name": tech["name"],
        "tech_phone": from_number,
        "pay": {
            "base_type": pay.base_type,
            "base_amount": pay.base_amount,
            "total": pay.total,
            "line_items": pay.line_items,
        },
        "notes": [],
        "photos": [media_url],
    }

    if body_text and body_text.strip():
        job["notes"].append({
            "timestamp": datetime.now().isoformat(),
            "text": body_text.strip(),
        })

    work_order_id = save_job(job)
    log_job(job)

    set_tech_state(from_number, state="awaiting_notes", current_job_id=work_order_id)

    # Wallfish check — need 2 photos
    if addons["wallfish"]:
        send_sms(
            from_number,
            _confirmation_text(tech["name"], job, pay) + "\n\n"
            "⚠️ Wallfish declared — send 2 photos to complete documentation.",
        )
        set_tech_state(from_number, state="awaiting_wallfish_photos", wallfish_photos_received=0)
    else:
        send_sms(from_number, _confirmation_text(tech["name"], job, pay))


def _handle_eod_screenshot(from_number: str, tech: dict, media_url: str, content_type: str):
    """Process end-of-day route screenshot."""
    logger.info("Processing EOD screenshot from %s", tech["name"])

    eod_data = classify_eod_screenshot(media_url, content_type)

    if not eod_data or not eod_data.get("is_eod_screenshot"):
        # Treat as a new work order instead
        return False  # signal caller to try work order flow

    completed_wos = eod_data.get("completed_work_orders", [])
    pending_wos = eod_data.get("pending_work_orders", [])
    total_shown = eod_data.get("total_jobs_shown", 0)

    state = get_tech_state(from_number)
    submitted_ids = set(state.get("today_job_ids", []))
    eod_ids = set(completed_wos)

    missing_from_prime = eod_ids - submitted_ids
    missing_from_eod = submitted_ids - eod_ids

    set_tech_state(from_number, eod_submitted=True, state="idle")

    lines = [f"✓ EOD route received — {tech['name']}"]
    lines.append(f"Oracle shows: {total_shown} jobs | PRIME logged: {len(submitted_ids)}")

    if missing_from_prime:
        lines.append(f"\n⚠️ In Oracle but NOT logged to PRIME: {', '.join(missing_from_prime)}")
    if missing_from_eod:
        lines.append(f"\n⚠️ Logged to PRIME but NOT in Oracle EOD: {', '.join(missing_from_eod)}")
    if not missing_from_prime and not missing_from_eod:
        lines.append("\n✓ All jobs reconciled.")

    send_sms(from_number, "\n".join(lines))
    return True


# ── Main webhook ─────────────────────────────────────────────────────────────

@app.route("/sms", methods=["POST"])
def sms_webhook():
    # Reconstruct the URL Twilio signed — must match exactly.
    # Behind Railway's proxy, request.url is http:// so we use X-Forwarded-Proto.
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    if WEBHOOK_BASE_URL:
        url = WEBHOOK_BASE_URL.rstrip("/") + "/sms"
    else:
        proto = request.headers.get("X-Forwarded-Proto", request.scheme)
        host = request.headers.get("X-Forwarded-Host", request.host)
        url = f"{proto}://{host}/sms"

    sig = request.headers.get("X-Twilio-Signature", "")
    logger.info("Validating webhook — url=%s sig_present=%s", url, bool(sig))

    if not validator.validate(url, request.form, sig):
        logger.warning("Invalid Twilio signature from %s | url=%s", request.remote_addr, url)
        return "Forbidden", 403

    from_number = request.form.get("From", "").strip()
    body_text = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", 0))

    # Collect media — copy out of request context before threading
    media_items = []
    for i in range(num_media):
        media_items.append({
            "url": request.form.get(f"MediaUrl{i}", ""),
            "content_type": request.form.get(f"MediaContentType{i}", "image/jpeg"),
        })

    # Respond to Twilio immediately — vision/AI calls can take 20-30s
    # and Twilio times out at 15s. All processing runs in a background thread.
    threading.Thread(
        target=_process_message,
        args=(from_number, body_text, media_items),
        daemon=True,
    ).start()

    return ("", 204)


def _process_message(from_number: str, body_text: str, media_items: list):
    """Handle all message logic in a background thread."""
    # ── Unknown sender ───────────────────────────────────────────────────────
    if not is_registered(from_number):
        send_sms(
            from_number,
            "This is the Prime Fiber ops line. Contact your supervisor to get registered.",
        )
        return

    tech = get_tech(from_number)

    # ── Supervisor commands ──────────────────────────────────────────────────
    if is_supervisor(from_number):
        _handle_supervisor_message(from_number, tech, body_text, media_items)
        return

    # ── Tech message routing ─────────────────────────────────────────────────
    tech_state = get_tech_state(from_number)
    current_state = tech_state.get("state", "idle")

    # Has media → screenshot flow
    if media_items:
        image = media_items[0]

        # If collecting wallfish photos
        if current_state == "awaiting_wallfish_photos":
            count = tech_state.get("wallfish_photos_received", 0) + len(media_items)
            current_job_id = tech_state.get("current_job_id")
            if current_job_id:
                append_job_note(current_job_id, "Wallfish photos submitted", [m["url"] for m in media_items])
            if count >= 2:
                set_tech_state(from_number, state="idle", wallfish_photos_received=0)
                send_sms(from_number, "✓ Wallfish photos received. Job fully documented.")
            else:
                set_tech_state(from_number, wallfish_photos_received=count)
                send_sms(from_number, f"Got {count}/2 wallfish photos. Send {2 - count} more.")
            return

        # Try EOD first if tech has already submitted jobs today
        today_jobs = tech_state.get("today_job_ids", [])
        if today_jobs and not tech_state.get("eod_submitted"):
            eod_handled = _handle_eod_screenshot(
                from_number, tech, image["url"], image["content_type"]
            )
            if eod_handled:
                return

        # Default: work order screenshot
        _handle_work_order_screenshot(
            from_number, tech, image["url"], image["content_type"], body_text
        )

    # Text only → notes on current job
    elif body_text:
        current_job_id = tech_state.get("current_job_id")
        if current_job_id:
            addons = _parse_notes_for_addons(body_text)
            append_job_note(current_job_id, body_text)

            if addons["wallfish"]:
                job = get_job(current_job_id)
                if job and not job.get("wallfish"):
                    job["wallfish"] = True
                    set_tech_state(from_number, state="awaiting_wallfish_photos", wallfish_photos_received=0)
                    send_sms(
                        from_number,
                        "✓ Note logged. Wallfish declared — send 2 photos to document.",
                    )
                    return

            send_sms(from_number, f"✓ Note added to WO#{current_job_id}.")
        else:
            send_sms(
                from_number,
                "PRIME: No active job on file. Send a work order screenshot first.",
            )


def _handle_supervisor_message(from_number: str, tech: dict, body: str, media_items: list):
    """Minimal supervisor command handler."""
    body_lower = body.lower().strip()

    if "report" in body_lower:
        supervisor_report()
    elif body_lower.startswith("confirm "):
        wo_id = body.split(" ", 1)[1].strip()
        from jobs import update_job_status
        update_job_status(wo_id, "green")
        from sheets import update_job_status_in_sheet
        update_job_status_in_sheet(wo_id, "green")
        send_sms(from_number, f"✓ WO#{wo_id} marked 🟢 Confirmed.")
    elif body_lower.startswith("decline "):
        parts = body.split(" ", 2)
        wo_id = parts[1].strip()
        reason = parts[2].strip() if len(parts) > 2 else ""
        from jobs import update_job_status
        update_job_status(wo_id, "red", reason)
        from sheets import update_job_status_in_sheet
        update_job_status_in_sheet(wo_id, "red", reason)
        send_sms(from_number, f"✓ WO#{wo_id} marked 🔴 Declined. Reason: {reason}")
    else:
        send_sms(
            from_number,
            "PRIME Supervisor Commands:\n"
            "REPORT — send today's summary now\n"
            "CONFIRM [WO#] — mark job green\n"
            "DECLINE [WO#] [reason] — mark job red",
        )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "PRIME"}, 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
