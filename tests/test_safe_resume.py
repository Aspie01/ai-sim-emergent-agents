"""Contract-matched safe resume decisions.

Every test here asks one question: can this resume prove it is safe? The
answers must be conservative, because the two failure modes are silently
skipping a cell that never produced valid evidence, and re-running over
evidence that already existed.
"""

from __future__ import annotations

import pytest

from thalren_vale.safe_resume import (
    REATTEMPT,
    REFUSE,
    SKIP,
    CellEvidence,
    ResumeContract,
    decide_resume,
)


def contract(**overrides):
    base = dict(
        experiment_id="exp-v1",
        plan_sha256="a" * 64,
        commit="b" * 40,
        tag="run-ready-v1",
        dirty=False,
        environment_fingerprint="env-1",
        config_fingerprint="cfg-1",
    )
    base.update(overrides)
    return ResumeContract(**base)


def completed(cell_id, attempt=1, valid=True):
    return CellEvidence(cell_id=cell_id, selected_attempt=attempt,
                        result="completed", artifacts_valid=valid)


def decide(recorded=None, current=None, evidence=None, cells=("c/seed_1",)):
    return decide_resume(
        recorded=contract() if recorded is None else recorded,
        current=contract() if current is None else current,
        evidence=evidence or {},
        planned_cells=cells,
    )


# ── Refusal is the default ──────────────────────────────────────────────────

def test_a_root_with_no_recorded_contract_is_refused():
    plan = decide_resume(
        recorded=None, current=contract(), evidence={},
        planned_cells=("c/seed_1",))
    assert plan.refused
    assert "no recorded resume contract" in plan.reason


@pytest.mark.parametrize("field,value", [
    ("experiment_id", "other-v1"),
    ("plan_sha256", "c" * 64),
    ("commit", "d" * 40),
    ("tag", "run-ready-v2"),
    ("environment_fingerprint", "env-2"),
    ("config_fingerprint", "cfg-2"),
])
def test_any_contract_field_mismatch_refuses(field, value):
    plan = decide(current=contract(**{field: value}))
    assert plan.refused
    assert field in plan.reason


def test_a_mismatch_names_every_differing_field():
    plan = decide(current=contract(commit="d" * 40, tag="other"))
    assert "commit" in plan.reason and "tag" in plan.reason


@pytest.mark.parametrize("dirty", [True, None])
def test_a_dirty_or_unknown_tree_is_refused(dirty):
    """Matching dirty flags prove nothing about matching working trees."""
    plan = decide(recorded=contract(dirty=dirty), current=contract(dirty=dirty))
    assert plan.refused
    assert "clean revision" in plan.reason


def test_evidence_for_a_cell_the_plan_does_not_define_refuses():
    plan = decide(evidence={"ghost/seed_9": completed("ghost/seed_9")},
                  cells=("c/seed_1",))
    assert plan.refused
    assert "ghost/seed_9" in plan.reason


def test_a_refused_plan_offers_no_work():
    plan = decide(current=contract(commit="d" * 40))
    assert plan.cells_to_run() == []
    assert plan.cells_to_skip() == []


# ── Skipping requires everything to line up ─────────────────────────────────

def test_a_completed_and_valid_selected_attempt_is_skipped():
    plan = decide(evidence={"c/seed_1": completed("c/seed_1")})
    assert not plan.refused
    assert plan.per_cell["c/seed_1"].outcome == SKIP
    assert plan.cells_to_skip() == ["c/seed_1"]


def test_a_cell_with_no_attempt_is_reattempted():
    plan = decide(evidence={})
    assert plan.per_cell["c/seed_1"].outcome == REATTEMPT
    assert plan.cells_to_run() == ["c/seed_1"]


def test_a_cell_whose_attempts_all_failed_is_reattempted():
    """Prior attempts are preserved; none of them selected, so none satisfied."""
    evidence = {"c/seed_1": CellEvidence(
        cell_id="c/seed_1", selected_attempt=None, result="exception",
        artifacts_valid=False)}
    decision = decide(evidence=evidence).per_cell["c/seed_1"]
    assert decision.outcome == REATTEMPT
    assert "no attempt is selected" in decision.reason


@pytest.mark.parametrize("result", [
    "exception", "wall_clock_limit", "cancelled", "invalid_output",
    "superseded", None,
])
def test_only_a_completed_result_can_be_skipped(result):
    evidence = {"c/seed_1": CellEvidence(
        cell_id="c/seed_1", selected_attempt=1, result=result,
        artifacts_valid=True)}
    decision = decide(evidence=evidence).per_cell["c/seed_1"]
    assert decision.outcome == REATTEMPT
    assert "censored evidence" in decision.reason


def test_a_completed_attempt_with_invalid_artifacts_is_reattempted():
    """Process exit success alone is never evidence completion."""
    evidence = {"c/seed_1": CellEvidence(
        cell_id="c/seed_1", selected_attempt=1, result="completed",
        artifacts_valid=False,
        validation_errors=("metrics csv truncated",))}
    decision = decide(evidence=evidence).per_cell["c/seed_1"]
    assert decision.outcome == REATTEMPT
    assert "do not deeply validate" in decision.reason
    assert "metrics csv truncated" in decision.reason


def test_invalid_artifacts_without_detail_still_reattempt():
    evidence = {"c/seed_1": CellEvidence(
        cell_id="c/seed_1", selected_attempt=1, result="completed",
        artifacts_valid=False)}
    decision = decide(evidence=evidence).per_cell["c/seed_1"]
    assert decision.outcome == REATTEMPT
    assert "no detail recorded" in decision.reason


# ── Mixed batches ───────────────────────────────────────────────────────────

def test_each_cell_is_decided_independently():
    cells = ("c/seed_1", "c/seed_2", "c/seed_3", "c/seed_4")
    evidence = {
        "c/seed_1": completed("c/seed_1"),
        "c/seed_2": completed("c/seed_2", valid=False),
        "c/seed_3": CellEvidence("c/seed_3", 2, "wall_clock_limit", True),
        # seed_4 has no evidence at all
    }
    plan = decide(evidence=evidence, cells=cells)
    assert plan.cells_to_skip() == ["c/seed_1"]
    assert plan.cells_to_run() == ["c/seed_2", "c/seed_3", "c/seed_4"]


def test_every_planned_cell_gets_a_decision():
    cells = ("c/seed_1", "c/seed_2", "c/seed_3")
    plan = decide(evidence={"c/seed_1": completed("c/seed_1")}, cells=cells)
    assert set(plan.per_cell) == set(cells)


def test_an_empty_plan_decides_nothing_but_does_not_refuse():
    plan = decide(evidence={}, cells=())
    assert not plan.refused
    assert plan.per_cell == {}


def test_decisions_carry_their_cell_id():
    plan = decide(evidence={"c/seed_1": completed("c/seed_1")})
    assert plan.per_cell["c/seed_1"].cell_id == "c/seed_1"


# ── The module does not touch anything ──────────────────────────────────────

def test_deciding_is_pure(tmp_path):
    """No filesystem access: the decision must be safe to run anywhere."""
    before = sorted(p.name for p in tmp_path.iterdir())
    decide(evidence={"c/seed_1": completed("c/seed_1")})
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_a_refused_plan_offers_no_work_however_it_was_built():
    """`ResumePlan` is public, so the guard must hold for any construction.

    `decide_resume` never populates per-cell decisions on a refusal, so this
    state is unreachable through it. Constructing it directly is the only way
    to check that a refused plan cannot hand a caller work to do.
    """
    from thalren_vale.safe_resume import ResumeDecision, ResumePlan

    plan = ResumePlan(
        REFUSE, "contract mismatch",
        per_cell={
            "c/seed_1": ResumeDecision(REATTEMPT, "would run", "c/seed_1"),
            "c/seed_2": ResumeDecision(SKIP, "would skip", "c/seed_2"),
        })

    assert plan.refused
    assert plan.cells_to_run() == []
    assert plan.cells_to_skip() == []
