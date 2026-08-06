# Command reference

Run these commands from `/home/lfs/Projects/ai-sim-emergent-agents` unless a command explicitly changes into a fresh temporary run directory.

## Inspect the interfaces

```bash
python -m thalren_vale --help
python run_experiments.py --help
```

## Run one bounded simulation safely

The simulator has no `--output-dir`; it writes relative to its working directory. Use a new temporary directory:

```bash
run_dir="$(mktemp -d /tmp/thalren-bounded-run.XXXXXX)"
cd "$run_dir"
PYTHONPATH=/home/lfs/Projects/ai-sim-emergent-agents/src \
PYTHONHASHSEED=0 \
python -m thalren_vale \
  --seed 42 \
  --condition bounded-check \
  --ticks 1 \
  --log-mode metrics_only \
  --disable-antistag
```

This creates the required structured artifacts beneath `$run_dir/data/`. Do not reuse that directory for the same or another direct run when evidence integrity matters.

## Run tests

```bash
python -m pytest -q
```

Focused examples are listed in [test reference](test-reference.md). The default suite discovers `tests/` only; root `test_parse_logs.py` requires an explicit command and covers a legacy parser.

## Compile/import-check Python files

```bash
python -m compileall -q src run_experiments.py tests
```

## Run a generic plan into a fresh root

```bash
python run_experiments.py \
  --plan /absolute/path/to/plan.json \
  --output-dir /absolute/path/to/new-or-empty-root
```

Do not use repository research plans as quick-start examples, and do not launch an S0/S1/P1/P2/Full tier without a separate authorization gate. The current runner rejects every nonempty root, including with `--resume` or `--overwrite`.

## Verify an existing plan root without launching children

```bash
python run_experiments.py \
  --plan /absolute/path/to/plan.json \
  --output-dir /absolute/path/to/existing-root \
  --verify \
  --validation-mode strict
```

`strict` means current schema-2 deep artifact validation. It does not mean `v2_ready`. The CLI verifier supplies no complete `ExpectedRunContract`, so current real runner output is at most valid schema-2 engineering evidence.

## Optional dashboard

```bash
streamlit run src/thalren_vale/dashboard.py
```

The dashboard reads diagnostic `dashboard_data.json`, which is written only by full-mode runs on the 25-tick dashboard cadence. It is not canonical evidence.

## Repository and documentation checks

```bash
python docs/handbook/validate_handbook.py
git diff --check
git status --short
git diff --stat
```

## Commands intentionally not presented as current workflows

- Historical pilot, logging-ablation, cleanup, and source-rewrite scripts.
- Root `experiments.json` as a bounded sample; it requests a large workload.
- `--seeds --verify` as a read-only workflow; inline mode writes a fixed temporary plan.
- `--resume` as continuation; current nonempty roots fail closed.
- Any research tier without explicit authorization.

## Implementation evidence

- Simulator parser: `src/thalren_vale/sim.py::run`.
- Module hash-seed wrapper: `src/thalren_vale/__main__.py`.
- Runner parser and child command: `run_experiments.py`.
- Tests: `tests/test_experiment_runner.py`, `tests/test_log_modes.py`, `tests/test_run_termination.py`.
