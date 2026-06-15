import base64
import logging
import re
from typing import Optional

import anthropic
import requests

from config import ANTHROPIC_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN

logger = logging.getLogger(__name__)
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_WORK_ORDER_PROMPT = """You are reading a screenshot from Oracle Field Service (OFS) used by a fiber installation company called Prime Fiber / Metronet.

Extract the following fields exactly as they appear. If a field is not visible, return null for that field.

Return ONLY valid JSON, no explanation:

{
  "work_order_id": "",
  "subscriber_id": "",
  "subscriber_name": "",
  "address": "",
  "city": "",
  "state": "",
  "zip": "",
  "phone": "",
  "time_slot": "",
  "delivery_window": "",
  "activity_type": "",
  "is_apartment": false,
  "raw_text": ""
}

Notes:
- is_apartment: set true if address contains "APT", "UNIT", "#", or subscriber type says apartment
- activity_type: look for values like "Full Install", "Inside Only", "Outside Drop", "Reconnect", etc.
- raw_text: include any other text visible in the screenshot that might be relevant
- If this does not appear to be a work order screenshot, set work_order_id to "NOT_A_WORK_ORDER"
"""

_EOD_PROMPT = """You are reading an end-of-day route completion screenshot from Oracle Field Service used by a fiber installation crew.

This is a route summary screen, not an individual work order.

Extract:
{
  "is_eod_screenshot": true,
  "completed_work_orders": [],
  "pending_work_orders": [],
  "total_jobs_shown": 0,
  "date": "",
  "raw_text": ""
}

If this is NOT a route/day summary screen, return {"is_eod_screenshot": false}.
"""


def _fetch_media(media_url: str) -> bytes:
    """Download Twilio media with auth credentials."""
    resp = requests.get(
        media_url,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content


def _image_to_b64(data: bytes, content_type: str = "image/jpeg") -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": content_type,
            "data": base64.standard_b64encode(data).decode("utf-8"),
        },
    }


def _parse_json_from_response(text: str) -> dict:
    import json
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON found in response: {text[:200]}")


def extract_work_order(media_url: str, content_type: str = "image/jpeg") -> Optional[dict]:
    """Run Claude vision on a work order screenshot. Returns extracted fields dict."""
    try:
        image_data = _fetch_media(media_url)
        image_block = _image_to_b64(image_data, content_type)

        response = _client.messages.create(
            model="claude-opus-4-8",  # best vision accuracy for field docs
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        image_block,
                        {"type": "text", "text": _WORK_ORDER_PROMPT},
                    ],
                }
            ],
        )
        result = _parse_json_from_response(response.content[0].text)
        return result
    except Exception as e:
        logger.error("Vision extraction failed: %s", e)
        return None


def classify_eod_screenshot(media_url: str, content_type: str = "image/jpeg") -> Optional[dict]:
    """Determine if screenshot is an EOD route summary and extract data."""
    try:
        image_data = _fetch_media(media_url)
        image_block = _image_to_b64(image_data, content_type)

        response = _client.messages.create(
            model="claude-opus-4-8",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        image_block,
                        {"type": "text", "text": _EOD_PROMPT},
                    ],
                }
            ],
        )
        return _parse_json_from_response(response.content[0].text)
    except Exception as e:
        logger.error("EOD classification failed: %s", e)
        return None
