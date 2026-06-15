from typing import Optional

# Normalize: strip non-digits, drop leading 1
def _norm(number: str) -> str:
    digits = "".join(c for c in number if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


CREW_REGISTRY = {
    "8065006215": {
        "name": "Chris Gonzales",
        "city": "Lubbock",
        "experienced": True,
        "role": "tech",
    },
    "8065437951": {
        "name": "Gabriel Huerta",
        "city": "Lubbock",
        "experienced": True,
        "role": "tech",
    },
    "8063463980": {
        "name": "Mathew Ruiz",
        "city": "Lubbock",
        "experienced": True,
        "role": "tech",
    },
    "8065593355": {
        "name": "Greg Delon",
        "city": "Lubbock",
        "experienced": True,
        "role": "tech",
    },
    "9402177381": {
        "name": "Armando",
        "city": "Wichita Falls",
        "experienced": True,
        "role": "tech",
    },
    "8062393887": {
        "name": "Phil Mata",
        "city": "Lubbock",
        "experienced": True,
        "role": "supervisor",
    },
}


def get_tech(phone: str) -> Optional[dict]:
    key = _norm(phone)
    tech = CREW_REGISTRY.get(key)
    if tech:
        return {**tech, "phone": key}
    return None


def is_registered(phone: str) -> bool:
    return _norm(phone) in CREW_REGISTRY


def is_supervisor(phone: str) -> bool:
    tech = get_tech(phone)
    return tech is not None and tech.get("role") == "supervisor"


def all_techs() -> list[dict]:
    return [
        {**v, "phone": k}
        for k, v in CREW_REGISTRY.items()
        if v.get("role") == "tech"
    ]
