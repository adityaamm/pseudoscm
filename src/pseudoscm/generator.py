"""Deterministic generation — pseudoscm, the Supply Chain emulator.

Same rule as its siblings: the output is not a claim about the world. It is the
reproducible result of a published rule set with stated parameters. Same seed, same
parameters, byte-identical output.

**THE DOMAIN, NEVER A VENDOR'S SCHEMA — D91.** Nothing here is modelled on any
particular supply chain product's tables, field names or documentation. What is
modelled is what every such system holds in some form: an operating unit, a service or
efficiency measure, a period, a target and an outcome.

WHY THIS EMULATOR EMITS NO CATALOGUE

It measures how well things are fulfilled and does **not** define what they are. The
catalogue belongs to `pseudocrm` alone. Two systems producing offering records would
mean deciding whether an SCM item and a CRM product are the same thing, which is
cross-system identity resolution — out of scope for inference under D56 — and a harness
that quietly emitted matching codes from both would hide that question instead of
posing it.

An emulator contributing one entity is a smaller emulator, not a lesser one.

WHY THREE OF ITS FOUR MEASURES ARE LOWER-IS-BETTER

**This is the corpus where a direction bug is unmissable.** Financial data leans
higher-is-better and a product could carry a wrong default a long way on it. Operations
data does not: cost to serve, defect rate and lead time all improve as they fall, so a
build that assumed higher-is-better would report a well-run supply chain as failing on
three measures out of four, in every unit, in every period.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from pseudoscm.calendar import periods as calendar_periods
from pseudoscm.marking import mark

HISTORY_START = date(2024, 1, 1)
HISTORY_END = date(2026, 12, 31)

MEASURES: tuple[tuple[str, str, str, str], ...] = (
    ("otif_pct", "On time in full", "HIGHER_IS_BETTER", "percent"),
    ("cost_to_serve", "Cost to serve", "LOWER_IS_BETTER", "GBP"),
    ("defect_rate_ppm", "Defect rate", "LOWER_IS_BETTER", "ppm"),
    ("order_lead_time_days", "Order lead time", "LOWER_IS_BETTER", "days"),
)


@dataclass
class Parameters:
    """Every parameter documented and adjustable. Nothing hidden."""

    seed: int = 20260902
    units: int = 12
    history_start: date = HISTORY_START
    history_end: date = HISTORY_END

    # MONTHLY by default, not quarterly.
    #
    # Deliberate, and the most useful thing this emulator does for the product. An
    # operations function reports monthly while finance reports quarterly and HR runs
    # an annual review, so a corpus built from all three has three clocks that do not
    # align. `org_unit_performance` maps each measurement period onto the review cycle
    # it overlaps most and counts the ones that overlap none; neither path is exercised
    # by a corpus where every emulator uses the same calendar.
    months_per_period: int = 1

    org_unit_codes: tuple[str, ...] = ()

    performance_spread: float = 0.09
    unstated_comparability: float = 0.2
    late_plans: float = 0.05


@dataclass
class Corpus:
    business_unit_metrics: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {"BusinessUnitMetric": len(self.business_unit_metrics)}


def periods(params: Parameters) -> list[tuple[date, date]]:
    """Measurement periods for these parameters. Arithmetic in `calendar.py` — D98."""
    return calendar_periods(params.history_start, params.history_end,
                            params.months_per_period)


def unit_codes(params: Parameters) -> list[str]:
    if params.org_unit_codes:
        return list(params.org_unit_codes)
    return [f"SITE-{n:03d}" for n in range(1, params.units + 1)]


def generate(params: Parameters | None = None) -> Corpus:
    """The full corpus. Seeded locally — never the module-level RNG."""
    params = params or Parameters()
    rng = random.Random(params.seed)
    corpus = Corpus()

    for start, end in periods(params):
        for code in unit_codes(params):
            for key, label, direction, measure in MEASURES:
                plan = float(rng.randrange(10, 400))
                actual = round(plan * (1 + rng.uniform(-params.performance_spread,
                                                       params.performance_spread)), 2)
                corpus.business_unit_metrics.append(mark({
                    # D125. WHEN WE CAME TO HOLD THIS FIGURE AS OUR CLAIM.
                    #
                    # Finance restates every close, and until this column existed a
                    # restated figure overwrote the earlier version's validity window —
                    # so a chart shown in March could not be reproduced after a Q1
                    # restatement. The period close is the moment the figure became
                    # ours, which is the honest reading and the one a source can state.
                    "tx_from": datetime.combine(
                        end, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                    "tx_to": None,
                    "metric_id": f"BUM-{code}-{start.isoformat()}-{key}",
                    "source_unit_id": code,
                    "metric_key": key,
                    "label": label,
                    "unit_of_measure": measure,
                    "direction": direction,
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                    "actual": actual,
                    "plan": plan,
                    "plan_set_on": (
                        date.fromordinal(start.toordinal() + 10).isoformat()
                        if rng.random() < params.late_plans
                        else date.fromordinal(start.toordinal() - 20).isoformat()),
                    "comparable_across_units": (
                        None if rng.random() < params.unstated_comparability else True),
                    "valid_from": start.isoformat(),
                    "valid_to": None,
                }))
    return corpus
