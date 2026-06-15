from dataclasses import dataclass, field
from typing import Optional

# ── Base rates ──────────────────────────────────────────────────────────────
FULL_INSTALL_EXP = 110
FULL_INSTALL_INEXP = 95
INSIDE_ONLY = 50
OUTSIDE_DROP_EXP = 60
OUTSIDE_DROP_INEXP = 45

# ── Add-ons ─────────────────────────────────────────────────────────────────
APT_ADDON = 20
EXTENDER_RATE = 7    # per unit
WALLFISH_ADDON = 20
BURIED_DROP_ADDON = 50


@dataclass
class PayBreakdown:
    base_type: str
    base_amount: float
    apt: bool = False
    extender_count: int = 0
    wallfish: bool = False
    buried_drop: bool = False
    line_items: list[tuple[str, float]] = field(default_factory=list)
    total: float = 0.0

    def build(self):
        self.line_items = [(self.base_type, self.base_amount)]
        running = self.base_amount

        if self.apt:
            self.line_items.append(("Apartment add-on", APT_ADDON))
            running += APT_ADDON

        if self.extender_count:
            amt = self.extender_count * EXTENDER_RATE
            self.line_items.append((f"Extender x{self.extender_count}", amt))
            running += amt

        if self.wallfish:
            self.line_items.append(("Wallfish", WALLFISH_ADDON))
            running += WALLFISH_ADDON

        if self.buried_drop:
            self.line_items.append(("Buried drop", BURIED_DROP_ADDON))
            running += BURIED_DROP_ADDON

        self.total = running
        return self

    def format_text(self) -> str:
        lines = [f"  {label}: ${amt:.0f}" for label, amt in self.line_items]
        lines.append("─────────────────")
        lines.append(f"  Estimated Total: ${self.total:.0f}")
        return "\n".join(lines)


def calculate_pay(
    activity_type: str,
    experienced: bool,
    apt: bool = False,
    extender_count: int = 0,
    wallfish: bool = False,
    buried_drop: bool = False,
) -> PayBreakdown:
    atype = activity_type.lower()

    if "inside" in atype and "outside" not in atype:
        base_type = "Inside portion only"
        base_amount = INSIDE_ONLY
    elif "outside" in atype or "drop" in atype and "inside" not in atype:
        base_type = "Outside drop"
        base_amount = OUTSIDE_DROP_EXP if experienced else OUTSIDE_DROP_INEXP
    else:
        # Default: full install
        base_type = "Full install (experienced)" if experienced else "Full install (new hire)"
        base_amount = FULL_INSTALL_EXP if experienced else FULL_INSTALL_INEXP

    return PayBreakdown(
        base_type=base_type,
        base_amount=base_amount,
        apt=apt,
        extender_count=extender_count,
        wallfish=wallfish,
        buried_drop=buried_drop,
    ).build()
