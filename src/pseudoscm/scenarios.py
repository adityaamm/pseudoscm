"""Scenario injectors — pseudoscm.

Injected, never generated, for the reason `pseudohcm`'s de-growth is: a base corpus
that already contained the scenario would change the shape of every fixture written
against it.
"""
from __future__ import annotations

from datetime import date

from contract.markers import RESERVED_ID_NAMESPACE

from pseudoscm.generator import Corpus


def _namespaced(code: str) -> str:
    return code if code.startswith(RESERVED_ID_NAMESPACE) else (
        RESERVED_ID_NAMESPACE + code)


def inject_supply_disruption(corpus: Corpus, *, start: date, end: date,
                             unit_codes: tuple[str, ...] = ()) -> dict:
    """Service collapses at some sites and not others, over a window.

    **THE SCENARIO PILLAR E EXISTS FOR, ARRIVING FROM THE OTHER SIDE.**

    Pillar E's second hypothesis for an anomalous unit is *the unit is constrained by
    something other than its people* — and a supply disruption is precisely that. The
    affected sites will show poor attainment against ordinary ratings, which is
    Anomaly A: underperforming unit, generous ratings.

    The pillar must present that alongside the other three explanations and choose none
    of them, because from inside the HCM the four are genuinely indistinguishable. This
    corpus is what makes the claim testable: **here, the true cause is known and it is
    not the people**, so a build that quietly concluded "ratings are not
    discriminating" can be caught doing it.

    Affected sites only, deliberately. A disruption hitting every unit equally would
    move the whole distribution and standardise away to nothing — which is a real
    effect, and a different test.
    """
    stamped = {_namespaced(code) for code in unit_codes}
    adjusted = 0
    touched: set[str] = set()
    for metric in corpus.business_unit_metrics:
        period_start = date.fromisoformat(metric["period_start"])
        if not (start <= period_start <= end):
            continue
        if stamped and metric["source_unit_id"] not in stamped:
            continue
        plan = metric["plan"]
        # Both directions mean the same thing: worse than planned.
        metric["actual"] = round(
            plan * (0.55 if metric["direction"] == "HIGHER_IS_BETTER" else 1.65), 2)
        touched.add(metric["source_unit_id"])
        adjusted += 1
    return {"metrics_adjusted": adjusted, "units_affected": len(touched),
            "window": [start.isoformat(), end.isoformat()]}


def inject_unstated_comparability(corpus: Corpus, *, metric_key: str) -> dict:
    """Strip the comparability flag from one measure entirely.

    Null must never read as true. A shared-services site carried on a measure designed
    for a manufacturing one looks anomalous permanently, and only the customer can say
    whether the measure travels — so the product has to report the silence rather than
    resolve it.
    """
    adjusted = 0
    for metric in corpus.business_unit_metrics:
        if metric["metric_key"] == metric_key:
            metric["comparable_across_units"] = None
            adjusted += 1
    return {"metrics_adjusted": adjusted, "metric_key": metric_key}
