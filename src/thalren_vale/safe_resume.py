"""Decide, per cell, whether a resume may skip work or must re-attempt it.

`CORE_REPLICATION_V2_PLAN.md` §7: "Process exit success alone is never evidence
completion. Resume may skip only the selected attempt whose terminal state and
artifacts deeply validate against the exact frozen contract." §9.10 lists what
must match before any resume is permitted at all: plan snapshot and hash,
commit, tag, clean status, exact config, environment fingerprint, attempt
status, and deep artifact validity.

This module is the decision only. It reads nothing, writes nothing, and
executes nothing, so it cannot damage evidence while the rules are being
settled. The runner still refuses every nonempty output root; wiring this in is
a separate step, and deliberately so — a bug here would either silently skip a
cell that never produced valid evidence, or re-run over evidence that already
existed.

Every ambiguity resolves to REFUSE. A resume that cannot prove it is safe is
not safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Per-cell outcomes.
SKIP = "skip"              # a selected attempt deeply validates; do not re-run
REATTEMPT = "reattempt"    # no valid selected attempt; run a new one

# Batch-level outcome. Refusal is never per-cell: a contract mismatch means the
# whole root belongs to a different experiment than the one being resumed.
REFUSE = "refuse"


@dataclass(frozen=True)
class ResumeContract:
    """The identity a resume must match exactly.

    Recorded when the batch first ran, and recomputed at resume. Fields are
    compared for exact equality; there is no notion of a compatible-enough
    revision or environment.
    """

    experiment_id: str
    plan_sha256: str
    commit: str | None
    tag: str | None
    dirty: bool | None
    environment_fingerprint: str
    config_fingerprint: str


@dataclass(frozen=True)
class CellEvidence:
    """What is known about one cell's most recent selected attempt."""

    cell_id: str
    selected_attempt: int | None
    result: str | None
    artifacts_valid: bool
    validation_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResumeDecision:
    outcome: str
    reason: str
    cell_id: str | None = None


@dataclass(frozen=True)
class ResumePlan:
    """The complete decision for a resume attempt."""

    outcome: str
    reason: str
    per_cell: dict[str, ResumeDecision] = field(default_factory=dict)

    @property
    def refused(self) -> bool:
        return self.outcome == REFUSE

    def cells_to_run(self) -> list[str]:
        if self.refused:
            return []
        return [cell_id for cell_id, decision in self.per_cell.items()
                if decision.outcome == REATTEMPT]

    def cells_to_skip(self) -> list[str]:
        if self.refused:
            return []
        return [cell_id for cell_id, decision in self.per_cell.items()
                if decision.outcome == SKIP]


# Results that can even be considered for skipping. Anything else -- timeout,
# cancellation, exception, invalid output -- is censored evidence that must be
# preserved but never satisfies a cell.
_COMPLETED = "completed"


def _contract_mismatches(recorded: ResumeContract,
                         current: ResumeContract) -> list[str]:
    """Every field that differs, named. Order is fixed for reproducible text."""
    fields = (
        ("experiment_id", recorded.experiment_id, current.experiment_id),
        ("plan_sha256", recorded.plan_sha256, current.plan_sha256),
        ("commit", recorded.commit, current.commit),
        ("tag", recorded.tag, current.tag),
        ("dirty", recorded.dirty, current.dirty),
        ("environment_fingerprint",
         recorded.environment_fingerprint, current.environment_fingerprint),
        ("config_fingerprint",
         recorded.config_fingerprint, current.config_fingerprint),
    )
    return [f"{name}: recorded {was!r}, now {now!r}"
            for name, was, now in fields if was != now]


def decide_resume(
    *,
    recorded: ResumeContract | None,
    current: ResumeContract,
    evidence: dict[str, CellEvidence],
    planned_cells: tuple[str, ...],
) -> ResumePlan:
    """Return the resume decision for a whole batch.

    Refuses outright when the recorded identity is missing or differs in any
    field, when the working tree is dirty, or when the planned cells do not
    match the cells the root was created for. Otherwise decides each cell
    independently: skip only a selected, completed, deeply valid attempt.
    """
    if recorded is None:
        return ResumePlan(
            REFUSE,
            "output root has no recorded resume contract; it was not produced "
            "by a run that can be resumed")

    mismatches = _contract_mismatches(recorded, current)
    if mismatches:
        return ResumePlan(
            REFUSE,
            "resume contract does not match the existing output root: "
            + "; ".join(mismatches))

    # A dirty tree cannot be resumed even when it matches what was recorded,
    # because "recorded dirty, still dirty" says nothing about whether the two
    # working trees contained the same uncommitted changes.
    if current.dirty is not False:
        return ResumePlan(
            REFUSE,
            "resume requires a clean revision; the working tree is dirty or "
            "its status could not be read")

    recorded_cells = tuple(evidence)
    unknown = [cell for cell in recorded_cells if cell not in planned_cells]
    if unknown:
        return ResumePlan(
            REFUSE,
            "output root contains cells the plan does not define: "
            + ", ".join(sorted(unknown)))

    per_cell: dict[str, ResumeDecision] = {}
    for cell_id in planned_cells:
        per_cell[cell_id] = _decide_cell(cell_id, evidence.get(cell_id))
    return ResumePlan("resume", "contract matches", per_cell)


def _decide_cell(cell_id: str, found: CellEvidence | None) -> ResumeDecision:
    """Skip only a selected, completed, deeply valid attempt."""
    if found is None:
        return ResumeDecision(REATTEMPT, "no attempt recorded", cell_id)
    if found.selected_attempt is None:
        return ResumeDecision(
            REATTEMPT, "no attempt is selected; prior attempts are preserved "
                       "and none of them satisfied the cell", cell_id)
    if found.result != _COMPLETED:
        return ResumeDecision(
            REATTEMPT,
            f"selected attempt {found.selected_attempt} ended "
            f"{found.result!r}, which is censored evidence rather than a "
            "completed observation", cell_id)
    if not found.artifacts_valid:
        detail = "; ".join(found.validation_errors) or "no detail recorded"
        return ResumeDecision(
            REATTEMPT,
            f"selected attempt {found.selected_attempt} completed but its "
            f"artifacts do not deeply validate ({detail}); process exit "
            "success alone is never evidence completion", cell_id)
    return ResumeDecision(
        SKIP,
        f"selected attempt {found.selected_attempt} completed and deeply "
        "validates", cell_id)
