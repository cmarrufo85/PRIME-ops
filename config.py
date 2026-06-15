import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER", "+18066300278")

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

SUPERVISOR_NUMBER = os.environ["SUPERVISOR_NUMBER"]

GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
GOOGLE_CREDENTIALS_FILE = Path(
    os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
)

WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "")

# Carlos's 10% supervisor comp rate
SUPERVISOR_COMP_RATE = 0.10

# EOD route screenshot deadline (24h time)
EOD_REMINDER_HOUR = 18   # 6pm
DAILY_REPORT_HOUR = 19   # 7pm
