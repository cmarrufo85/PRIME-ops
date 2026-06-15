"""
Local test script — simulates Twilio webhook POSTs with valid signatures.
Run: python3 test_local.py
"""
import requests
import os
from dotenv import load_dotenv
from twilio.request_validator import RequestValidator

load_dotenv()
AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
LOCAL_URL = "http://localhost:5001/sms"
# Flask validates against WEBHOOK_BASE_URL — use same URL for signature
SIGN_URL = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/") + "/sms" or LOCAL_URL
validator = RequestValidator(AUTH_TOKEN)


def post(label, params):
    sig = validator.compute_signature(SIGN_URL, params)
    r = requests.post(LOCAL_URL, data=params, headers={"X-Twilio-Signature": sig})
    print(f"\n{'='*50}")
    print(f"TEST: {label}")
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:200] if r.text else '(empty 204)'}")


# ── Test 1: Unknown number ───────────────────────────────────────────────────
post("Unknown number texts in", {
    "From": "+15551234567",
    "Body": "Hey what is this number",
    "NumMedia": "0",
    "To": "+18066300278",
})

# ── Test 2: Registered tech, text only (no screenshot yet) ──────────────────
post("Chris texts without screenshot", {
    "From": "+18065006215",
    "Body": "On my way to first job",
    "NumMedia": "0",
    "To": "+18066300278",
})

# ── Test 3: Supervisor sends REPORT command ──────────────────────────────────
post("Phil (supervisor) requests report", {
    "From": "+18062393887",
    "Body": "REPORT",
    "NumMedia": "0",
    "To": "+18066300278",
})

print(f"\n{'='*50}")
print("Done. Check your SMS for replies to registered numbers.")
