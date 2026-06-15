import logging
from twilio.rest import Client
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_NUMBER

logger = logging.getLogger(__name__)
_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_sms(to: str, body: str) -> bool:
    """Send SMS. Returns True on success."""
    try:
        # Normalize to E.164
        digits = "".join(c for c in to if c.isdigit())
        if len(digits) == 10:
            digits = "1" + digits
        to_e164 = f"+{digits}"

        _client.messages.create(body=body, from_=TWILIO_NUMBER, to=to_e164)
        logger.info("SMS sent to %s", to_e164)
        return True
    except Exception as e:
        logger.error("SMS send failed to %s: %s", to, e)
        return False
