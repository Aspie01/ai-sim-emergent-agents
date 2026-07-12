# Operating Thalren Vale Safely

This page gives the smallest verified workflows for inspecting, running, and
checking the current simulator. It does not authorize a research tier. In
particular, do not run S0, S1, P1, P2, Full, or any Core Replication V2 matrix:
those remain **Planned, not implemented** and separately gated.

## Prerequisites

The package requires Python 3.10 or newer. The core dependency is `noise`;
pytest and build tooling are in the `dev` extra. From the repository root,
install only what the workflow needs:

```bash
python -m pip install -e .
python -m pip install -e ".[dev]"
```

The optional `analysis` and `dashboard` extras can be added separately for
those workflows. They are not required for the simulator or test suite.

## Inspect commands without running the simulation

```bash
REPO=/home/lfs/Projects/ai-sim-emergent-agents
PYTHONPATH="$REPO/src" python -m thalren_vale --help
python "$REPO/run_experiments.py" --help
```

The simulator parser and experiment-runner parser both set
`allow_abbrev=False`; use complete option names.

## Run one bounded engineering simulation

Run direct simulator examples only from a fresh temporary working directory.
The simulator writes relative paths such as `data/`, `logs/`, and
`dashboard_data.json` beneath its current directory.

```bash
REPO=/home/lfs/Projects/ai-sim-emergent-agents
RUN_DIR="$(mktemp -d /tmp/thalren-vale-handbook.XXXXXX)"
cd "$RUN_DIR"
PYTHONPATH="$REPO/src" PYTHONHASHSEED=0 \
  python -m thalren_vale \
    --seed 42 \
    --ticks 5 \
    --condition handbook-smoke \
    --log-mode metrics_only
```

This is a bounded engineering smoke run, not a scientific replicate. Its
required outputs appear under `$RUN_DIR/data/`. Keep or remove that temporary
directory according to your own evidence needs; never delete a pre-existing
directory on the assumption that it came from this example.

Important configuration controls include:

- `--seed`: explicit simulation seed;
- `--ticks`: requested horizon;
- `--condition`: filename-safe run label;
- `--log-mode`: `full`, `summary`, `metrics_only`, or `off`;
- `--disable-antistag`, `--disable-layer`, and `--disable-raids`: distinct
  behavior controls.

The `off` log mode still writes required structured artifacts. It suppresses
optional presentation output; it does not disable evidence recording.

## Find one direct run's outputs

For condition `handbook-smoke` and seed `42`:

```text
$RUN_DIR/data/metrics_handbook-smoke_seed_42.csv
$RUN_DIR/data/faction_events_handbook-smoke_seed_42.csv
$RUN_DIR/data/beliefs_handbook-smoke_seed_42.csv
$RUN_DIR/data/run_summaries.csv
$RUN_DIR/data/run_manifest_handbook-smoke_seed_42.json
```

The run manifest is published after required writers are finalized and closed,
but it is not sufficient alone. Trust a run only after validating the complete
artifact set as described in
[Identifying valid runs](../data/identifying-valid-runs.md).

Validate this direct-run layout with the run-level validator:

```bash
REPO=/home/lfs/Projects/ai-sim-emergent-agents
RUN_DIR=/absolute/path/to/the/fresh/run/directory
PYTHONPATH="$REPO/src" RUN_DIR="$RUN_DIR" python -c '
import os
from pathlib import Path
from thalren_vale.artifact_validation import inspect_run_outputs
report = inspect_run_outputs(
    Path(os.environ["RUN_DIR"]),
    "handbook-smoke",
    42,
    expected_ticks=5,
    mode="strict",
)
print(f"{report.classification}: valid={report.valid}, v2_ready={report.v2_ready}")
for error in report.errors:
    print(error)
raise SystemExit(0 if report.valid else 1)
'
```

This validates `$RUN_DIR/data/...` directly. The plan-based runner verifier
below expects a different batch layout and is not a substitute for this
command.

## Run tests

From the repository root:

```bash
python -m pytest -q
```

The default suite is restricted by `pyproject.toml` to `tests/`. The root-level
`test_parse_logs.py` is therefore not included unless named explicitly:

```bash
python -m pytest -q test_parse_logs.py
```

For the complete engineering verification chain:

```bash
python -m pytest -q
python -m compileall -q src run_experiments.py tests
git diff --check
```

See [Test reference](../reference/test-reference.md) for the evidence and
limitations of each suite.

## Validate existing batch outputs without launching children

Use an existing plan and explicitly identify its output root:

```bash
REPO=/home/lfs/Projects/ai-sim-emergent-agents
python "$REPO/run_experiments.py" \
  --plan /absolute/path/to/plan.json \
  --output-dir /absolute/path/to/existing-output-root \
  --verify \
  --validation-mode strict
```

With `--plan`, this path reads expected run directories and does not start a
simulation or create the output root. `strict` requires schema-2 run evidence.
The default `auto` mode also accepts readable schema-1 legacy evidence.

An exit status of zero means the expected runs were valid under the selected
artifact mode. It does **not** mean they are V2-ready: the current CLI does not
supply the complete external expected-run contract needed for that decision.

Do not use inline `--seeds --verify` when strict read-only filesystem behavior
is required. Inline mode writes `/tmp/thalren_inline_plan.json` before
verification.

## Batch execution boundary

The generic runner accepts a plan, but execution is allowed only into an absent
or truly empty output root. Current `--resume` and `--overwrite` options are
compatibility flags; neither permits reuse of a nonempty root. Allocate a new
root instead.

The runner does not yet provide:

- functional nonempty-root resume;
- immutable retry/attempt directories;
- an append-only attempt ledger or supersession;
- stop-on-first-failure dispatch;
- clean-tag/environment/plugin preflight;
- a nonexecuting V2 matrix expansion command;
- V2-ready evidence production.

For these reasons, the handbook does not prescribe a V2 execution command.
Read [Runner and configurations](../experiments/runner-and-configurations.md)
before using the generic batch runner.

## Reproduce a run

At minimum, preserve and match:

1. repository commit and clean/dirty state;
2. exact effective configuration, condition, seed, and tick horizon;
3. Python environment and `PYTHONHASHSEED=0`;
4. plugin files and policy;
5. structured artifact schemas;
6. final canonical state hash.

The current manifest records commit and dirty status but not a tag,
environment fingerprint, or plugin inventory. Matching state hashes is useful
engineering evidence, but current outputs remain non-V2-ready.

## Inspect artifacts and compare two conditions

Validate both expected cells first with the plan-based `--verify` command.
Then select two condition directories for the same seed and inspect only
declared fields:

```bash
CELL_A=/absolute/path/to/output-root/condition_a/seed_42
CELL_B=/absolute/path/to/output-root/condition_b/seed_42
python - "$CELL_A" "$CELL_B" <<'PY'
import csv
from collections import Counter
import json
from pathlib import Path
import sys

for label, cell in zip(("A", "B"), map(Path, sys.argv[1:])):
    data = cell / "data"
    manifest_path, = data.glob("run_manifest_*.json")
    metrics_path, = data.glob("metrics_*.csv")
    events_path, = data.glob("faction_events_*.csv")
    summary_path = data / "run_summaries.csv"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with metrics_path.open(newline="", encoding="utf-8") as handle:
        final = None
        for final in csv.DictReader(handle):
            pass
    if final is None:
        raise SystemExit(f"no metric rows in {metrics_path}")
    with events_path.open(newline="", encoding="utf-8") as handle:
        event_counts = Counter(
            row["event_type"] for row in csv.DictReader(handle)
        )
    with summary_path.open(newline="", encoding="utf-8") as handle:
        summary_reader = csv.DictReader(handle)
        summary = next(summary_reader, None)
        if summary is None or next(summary_reader, None) is not None:
            raise SystemExit(f"expected exactly one summary row in {summary_path}")
    print(label, {
        "seed": manifest["seed"],
        "condition": manifest["condition"],
        "requested_ticks": manifest["requested_ticks"],
        "final_tick": manifest["final_tick"],
        "configuration": manifest["configuration"],
        "state_hash": manifest["state_hash"],
        "final_population": final["population"],
        "final_faction_count": final["faction_count"],
        "final_gini": final["gini"],
        "event_counts": dict(sorted(event_counts.items())),
        "run_summary": summary,
    })
PY
```

Confirm equal seed and horizon, expected effective-control differences, valid
terminal state, and compatible provenance before interpreting the printed
values. Seed is the replicate unit. This is a descriptive inspection workflow,
not a definition of a scientific contrast or estimand.

## Implementation evidence

- Source: [`src/thalren_vale/sim.py`](../../../src/thalren_vale/sim.py),
  [`src/thalren_vale/config.py`](../../../src/thalren_vale/config.py),
  [`run_experiments.py`](../../../run_experiments.py)
- Tests: [`tests/test_log_modes.py`](../../../tests/test_log_modes.py),
  [`tests/test_experiment_runner.py`](../../../tests/test_experiment_runner.py),
  [`tests/test_reproducibility.py`](../../../tests/test_reproducibility.py)
- Packaging: [`pyproject.toml`](../../../pyproject.toml)
- Verification used for this handbook page: source and test inspection only;
  no simulation or experiment was launched during drafting.
