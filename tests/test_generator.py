"""The Supply Chain emulator — D97.

Two things make this corpus different from its siblings, and both are deliberate.

**Three of its four measures improve as they fall.** Financial data leans
higher-is-better and a product could carry a wrong default a long way on it. Operations
data does not, so a build that assumed higher-is-better would report a well-run supply
chain as failing on three measures out of four, in every unit, in every period.

**It reports monthly while finance reports quarterly and HR runs an annual review.**
Three clocks that do not align is the ordinary state of a real enterprise, and it is
the only way `org_unit_performance`'s cycle-mapping and its off-axis count are
exercised at all.
"""
from __future__ import annotations

import json
from datetime import date

from contract.markers import SYNTHETIC_MARKER_FIELD, SYNTHETIC_MARKER_VALUE

from pseudoscm.emit import ENTITY_FILES, emit
from pseudoscm.generator import MEASURES, Corpus, Parameters, generate, periods
from pseudoscm.scenarios import inject_supply_disruption, inject_unstated_comparability


def small() -> Parameters:
    return Parameters(units=4, history_end=date(2024, 12, 31))


class TestReproducibility:
    def test_the_same_seed_produces_byte_identical_output(self):
        a = json.dumps(generate(small()).business_unit_metrics, sort_keys=True)
        b = json.dumps(generate(small()).business_unit_metrics, sort_keys=True)
        assert a == b

    def test_a_different_seed_produces_different_output(self):
        a = json.dumps(generate(Parameters(seed=1, units=4,
                                           history_end=date(2024, 6, 30)))
                       .business_unit_metrics, sort_keys=True)
        b = json.dumps(generate(Parameters(seed=2, units=4,
                                           history_end=date(2024, 6, 30)))
                       .business_unit_metrics, sort_keys=True)
        assert a != b

    def test_it_does_not_touch_the_global_random_generator(self):
        import random

        random.seed(1)
        before = random.random()
        random.seed(1)
        generate(small())
        assert random.random() == before


class TestDirectionIsWhereThisCorpusEarnsItsPlace:
    def test_most_measures_improve_as_they_fall(self):
        """**The test that makes a direction bug unmissable.**

        Three of four. A build defaulting to higher-is-better reports a well-run supply
        chain as failing on three measures out of four, everywhere, always.
        """
        lower = [key for key, _, direction, _ in MEASURES
                 if direction == "LOWER_IS_BETTER"]
        assert len(lower) == 3
        assert set(lower) == {"cost_to_serve", "defect_rate_ppm",
                              "order_lead_time_days"}

    def test_at_least_one_measure_improves_as_it_rises(self):
        """The guard against the guard. If every measure ran the same way the corpus
        would be as one-sided as the financial one, in the other direction."""
        assert any(direction == "HIGHER_IS_BETTER" for _, _, direction, _ in MEASURES)

    def test_every_metric_states_a_direction(self):
        for metric in generate(small()).business_unit_metrics:
            assert metric["direction"] in ("HIGHER_IS_BETTER", "LOWER_IS_BETTER")

    def test_no_plan_is_zero(self):
        assert all(m["plan"] != 0 for m in generate(small()).business_unit_metrics)


class TestTheClockDoesNotMatchTheOthers:
    def test_periods_are_monthly_by_default(self):
        """Three clocks that do not align is the ordinary state of a real enterprise,
        and the only thing that exercises the cycle mapping and its off-axis count."""
        assert Parameters().months_per_period == 1
        found = periods(small())
        assert found[0] == (date(2024, 1, 1), date(2024, 1, 31))
        assert len(found) == 12

    def test_periods_abut_exactly_and_drop_a_partial_tail(self):
        """A quarter measured over two months is not a smaller quarter, it is a
        different denominator — and a three-month plan compared against two months of
        actuals reports a shortfall that did not happen."""
        found = periods(Parameters(units=1, history_start=date(2024, 1, 1),
                                   history_end=date(2024, 5, 15),
                                   months_per_period=2))
        assert found == [(date(2024, 1, 1), date(2024, 2, 29)),
                         (date(2024, 3, 1), date(2024, 4, 30))]


class TestNoCatalogue:
    def test_this_emulator_emits_no_offerings(self):
        """It measures how well things are fulfilled and does not define what they are.
        The catalogue belongs to `pseudocrm` alone — two of them would mean deciding
        whether an SCM item and a CRM product are the same thing, which D56 put out of
        scope for inference."""
        assert set(ENTITY_FILES) == {"BusinessUnitMetric"}
        assert not hasattr(Corpus(), "offerings")


class TestScenarios:
    def test_a_disruption_hits_only_the_named_sites(self):
        """Affected sites only. A disruption hitting every unit equally would move the
        whole distribution and standardise away to nothing — a real effect, and a
        different test."""
        corpus = generate(small())
        result = inject_supply_disruption(
            corpus, start=date(2024, 4, 1), end=date(2024, 6, 30),
            unit_codes=("SITE-001", "SITE-002"))
        assert result["units_affected"] == 2
        for metric in corpus.business_unit_metrics:
            when = date.fromisoformat(metric["period_start"])
            hit = (date(2024, 4, 1) <= when <= date(2024, 6, 30)
                   and metric["source_unit_id"] in ("PSEUDO::SITE-001",
                                                    "PSEUDO::SITE-002"))
            if hit and metric["direction"] == "HIGHER_IS_BETTER":
                assert metric["actual"] < metric["plan"]
            if hit and metric["direction"] == "LOWER_IS_BETTER":
                assert metric["actual"] > metric["plan"], (
                    "a cost above plan IS worse — moving every actual one way would "
                    "have the disrupted sites reporting record efficiency")

    def test_an_unaffected_site_is_untouched(self):
        corpus = generate(small())
        untouched_before = [m["actual"] for m in corpus.business_unit_metrics
                            if m["source_unit_id"] == "PSEUDO::SITE-004"]
        inject_supply_disruption(corpus, start=date(2024, 4, 1), end=date(2024, 6, 30),
                                 unit_codes=("SITE-001",))
        untouched_after = [m["actual"] for m in corpus.business_unit_metrics
                           if m["source_unit_id"] == "PSEUDO::SITE-004"]
        assert untouched_before == untouched_after

    def test_the_base_corpus_contains_no_disruption(self):
        """Injected, never generated."""
        corpus = generate(small())
        otif = [m for m in corpus.business_unit_metrics
                if m["metric_key"] == "otif_pct"]
        assert all(m["actual"] > m["plan"] * 0.8 for m in otif)

    def test_comparability_can_be_stripped_from_one_measure(self):
        """Null must never read as true. A shared-services site carried on a measure
        designed for a manufacturing one looks anomalous permanently."""
        corpus = generate(small())
        result = inject_unstated_comparability(corpus, metric_key="cost_to_serve")
        assert result["metrics_adjusted"] > 0
        stripped = [m for m in corpus.business_unit_metrics
                    if m["metric_key"] == "cost_to_serve"]
        assert all(m["comparable_across_units"] is None for m in stripped)


class TestTheMarker:
    def test_every_emitted_record_carries_it(self):
        corpus = generate(small())
        inject_supply_disruption(corpus, start=date(2024, 4, 1), end=date(2024, 6, 30))
        for attribute in ENTITY_FILES.values():
            rows = getattr(corpus, attribute)
            assert rows, f"{attribute} is empty — this check would pass by vacancy"
            for row in rows:
                assert row[SYNTHETIC_MARKER_FIELD] == SYNTHETIC_MARKER_VALUE

    def test_identifiers_are_moved_into_the_reserved_namespace(self):
        for metric in generate(small()).business_unit_metrics:
            assert metric["metric_id"].startswith("PSEUDO::")
            assert metric["source_unit_id"].startswith("PSEUDO::")


class TestEmission:
    def test_the_file_is_written_even_when_empty(self, tmp_path):
        written = emit(Corpus(), tmp_path)
        assert written == {"BusinessUnitMetric": 0}
        assert (tmp_path / "BusinessUnitMetric.jsonl").exists()

    def test_the_file_round_trips(self, tmp_path):
        corpus = generate(small())
        written = emit(corpus, tmp_path)
        lines = (tmp_path / "BusinessUnitMetric.jsonl").read_text(
            encoding="utf-8").splitlines()
        assert len(lines) == written["BusinessUnitMetric"]
