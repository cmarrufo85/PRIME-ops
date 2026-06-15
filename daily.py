"""
Daily scheduled tasks:
- 6pm: remind techs who haven't sent EOD screenshot
- 7pm: push supervisor report to Carlos
- Midnight: reset daily state
"""
import logging
from datetime import date

from config import SUPERVISOR_COMP_RATE, SUPERVISOR_NUMBER
from crew import all_techs, get_tech
from jobs import get_jobs_for_tech, get_tech_state, get_todays_jobs, reset_daily_state
from sms import send_sms

logger = logging.getLogger(__name__)

STATUS_EMOJI = {"pending": "🟡", "green": "🟢", "red": "🔴"}


def eod_reminder():
    """6pm — text any tech who hasn't submitted EOD screenshot."""
    techs = all_techs()
    for tech in techs:
        phone = tech["phone"]
        state = get_tech_state(phone)
        jobs_today = get_jobs_for_tech(phone)

        if not jobs_today:
            continue  # no jobs today, skip

        if not state.get("eod_submitted"):
            send_sms(
                phone,
                f"PRIME: Hey {tech['name']} — still need your end-of-day route screenshot. "
                "Send it when you're wrapped up.",
            )
            logger.info("EOD reminder sent to %s", tech["name"])


def supervisor_report():
    """7pm — send daily summary to Carlos."""
    today = date.today().strftime("%B %d, %Y")
    all_jobs = get_todays_jobs()
    techs = all_techs()

    lines = [f"PRIME Daily Report — {today}", ""]

    total_crew_pay = 0.0
    tech_summaries = []
    flags = []

    for tech in techs:
        phone = tech["phone"]
        jobs = get_jobs_for_tech(phone)
        if not jobs:
            continue

        tech_total = sum(j.get("pay", {}).get("total", 0) for j in jobs)
        total_crew_pay += tech_total
        tech_summaries.append(
            f"  {tech['name']}: {len(jobs)} job{'s' if len(jobs) != 1 else ''} — ${tech_total:.0f}"
        )

        state = get_tech_state(phone)
        if not state.get("eod_submitted"):
            flags.append(f"⚠️ {tech['name']}: No EOD screenshot received")

        for job in jobs:
            notes = job.get("notes", [])
            for n in notes:
                if n.get("text") and any(
                    word in n["text"].lower()
                    for word in ["damage", "issue", "problem", "missing", "broken"]
                ):
                    flags.append(
                        f"⚠️ {tech['name']} — WO#{job['work_order_id']}: "
                        f"Note flagged: {n['text'][:80]}"
                    )

    if tech_summaries:
        lines.append("JOBS TODAY:")
        lines.extend(tech_summaries)
    else:
        lines.append("No jobs submitted today.")

    lines.append("")
    lines.append(f"Total Crew Pay: ${total_crew_pay:.0f}")
    comp = total_crew_pay * SUPERVISOR_COMP_RATE
    lines.append(f"Your 10% Supervisor Comp: ${comp:.0f}")

    pending = sum(1 for j in all_jobs if j.get("status") == "pending")
    confirmed = sum(1 for j in all_jobs if j.get("status") == "green")
    declined = sum(1 for j in all_jobs if j.get("status") == "red")

    lines.append("")
    lines.append(f"Job Status: 🟡 {pending} pending  🟢 {confirmed} confirmed  🔴 {declined} declined")

    if flags:
        lines.append("")
        lines.append("FLAGS:")
        lines.extend(flags)

    report_text = "\n".join(lines)
    send_sms(SUPERVISOR_NUMBER, report_text)
    logger.info("Supervisor report sent")


def midnight_reset():
    """Reset daily state for a new day."""
    reset_daily_state()
    logger.info("Daily state reset at midnight")
