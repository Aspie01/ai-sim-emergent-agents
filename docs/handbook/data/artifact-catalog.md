# Artifact Catalog

This catalog describes artifacts produced or consumed by the current revision.
“Canonical” means the artifact participates in the current run-evidence
contract; it does not mean that the artifact is independently trustworthy or
research-ready. A canonical run requires the complete validated set.

## Required run artifacts

| Name | Producer | Creation point | Default location | Format / schema | Authority | Validity conditions | Consumer | Failure behaviour | Reproducibility role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tick metrics | `MetricsLogger.record_tick()` | End of every fully completed tick | `data/metrics_<condition>_seed_<N>.csv` | CSV, metrics schema 2, exact `METRICS_HEADER` | Canonical run evidence | Exact header; one contiguous row per tick 1 through `final_tick`; correct seed, numeric domains, cumulative monotonicity, inventory checksum/row count, and cross-file agreement | Validator, analysts, humans | Missing, empty, header-only, malformed, gapped, stale, or mismatched files invalidate strict evidence | Records the authoritative end-of-tick observational sequence, but not enough state to recompute the state hash |
| Structured events | `MetricsLogger.record_event()` from the drained observation journal | During end-of-tick observation; pending partial-tick journal may be sealed as audit data | `data/faction_events_<condition>_seed_<N>.csv` | CSV, event schema 1 | Canonical run evidence | Exact header; registered types; valid tick/seed; nondecreasing order; no row beyond `final_tick`; explicit zero-event policy; inventory and counter agreement | Validator, event analysis, humans | Zero rows are valid only under the sealed explicit policy; malformed or beyond-final rows invalidate the run | Records realized emitted events, not opportunities, scans, or failed unobserved attempts |
| Belief snapshots | `MetricsLogger.record_beliefs()` | Every 100 ticks | `data/beliefs_<condition>_seed_<N>.csv` | CSV, beliefs schema 1 | Canonical run evidence under the current contract | Exact header; cadence; one distinct identity per living inhabitant; population-count agreement; inventory checksum/row count | Validator, belief analysis, humans | Header-only is valid before any required living-population cadence; omitted/duplicate/off-cadence rows invalidate later runs | Captures periodic observations only, not complete belief history |
| Run summary | `MetricsLogger.finalize()` | Required finalization | `data/run_summaries.csv` | CSV, summary schema 1 | Canonical run evidence | Strict runs require exactly one row in the run directory, correct condition/seed, valid domains, and deterministic cross-checks against metrics/events | Validator, run-level analysis, humans | Missing/header-only/multiple/mismatched rows invalidate strict evidence | Condenses the run; wall-clock and peak-memory fields are operational and nondeterministic |
| Run manifest | `write_run_manifest()` | Last explicit required publication after writer close and state hashing | `data/run_manifest_<condition>_seed_<N>.json` | JSON, run-manifest schema 2 | Canonical seal and provenance index | Valid JSON/object; exact identity and termination fields; valid writer health, state-hash shape, configuration, policies, schemas, and inventory; must be checked with all listed artifacts | Validator, runner, humans | Missing/malformed/unsafe manifest means invalid evidence; failed atomic publication may leave `.error.txt` | Stores state hash, effective configuration, commit/dirty state, termination, checksums, and row counts; lacks complete V2 provenance |

The manifest inventory covers metrics, events, beliefs, and summary. The
manifest lists itself as a required output but does not checksum itself.

### Belief identity caveat

The beliefs header is:

```text
seed,tick,inhabitant_id,faction,beliefs
```

Current `record_beliefs()` writes `inhabitant.name` in the `inhabitant_id`
column, not the stable numeric inhabitant ID. Validation checks nonempty and
unique values within each tick but does not establish that they are stable IDs.
Treat this column as a display-name identity in current artifacts.

## Batch-runner artifacts

| Name | Producer | Creation point | Default location | Format / schema | Authority | Validity conditions | Consumer | Failure behaviour | Reproducibility role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Experiment plan | User/operator; consumed by `load_plan()` | Before root creation | User-selected `.json` | JSON, plan schema 1 | Execution input, not evidence by itself | Supported schema, safe unique condition names, valid seeds/ticks/timeouts/argument forms | Runner, `--verify` | Parse/validation failure aborts before child/root mutation | Raw bytes are SHA-256 hashed, but the current runner does not copy an immutable plan snapshot |
| Batch manifest | Runner | Before first child, after each result, and at batch end | `<root>/experiment_manifest.json` | JSON, runner schema 1 | Operational batch metadata, not a substitute for run validation | Current implementation has no independent deep validator; inspect plan hash, code fields, results, and `complete` cautiously | Humans, ad hoc tooling | Atomically replaced; may describe only persisted results if orchestration aborts | Records plan hash/path and commit/dirty state, but no tag/environment/attempt ledger |
| Run index | Runner | After each persisted result | `<root>/run_index.csv` | CSV, unversioned projection | Derived operational index | Must agree with batch manifest and each validated run; current validator does not enforce this | Humans, simple analysis | Directly rewritten; interruption can leave stale/partial index | Lists condition, seed, status, elapsed time, return code, hash, and relative path |
| Runner stderr | Runner | After a child writes stderr, timeout, or launch exception | `<root>/<condition>/seed_<N>/runner_stderr.txt` | UTF-8 text | Diagnostic | Never establishes completion; interpret with process and artifact status | Humans | May be absent on success or present for warnings on an otherwise valid child | Explains runner/child failure context only |
| Runner stdout | Runner | Only when a failed child produced stdout | `<root>/<condition>/seed_<N>/runner_stdout.txt` | UTF-8 text | Diagnostic | Never canonical; use with validated structured outputs | Humans | Successful child stdout is discarded | Failure diagnosis only |

The runner has no current attempt manifest, immutable attempt directory,
append-only ledger, selected-attempt record, or supersession record.

## Optional simulator outputs

| Name | Producer | Creation point | Default location | Format / schema | Authority | Validity conditions | Consumer | Failure behaviour | Reproducibility role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Full text log | `_LogTee` / simulator display | Throughout `full` log mode | `logs/run_<condition>_seed_<N>_<timestamp>.txt` | Text, unversioned | Diagnostic narrative | May aid debugging; never replaces structured validation | Humans, legacy parsers | Absent in non-full modes; optional failure does not define run validity | Timestamped and presentation-dependent; not canonical |
| Dashboard snapshot | `dashboard_bridge.write_dashboard_snapshot()` | Every 25 ticks in `full` mode | `dashboard_data.json` | Compact JSON, unversioned | Live diagnostic | Last-write snapshot only; not manifest-inventoried or checksummed | Dashboard UI, humans | Atomically replaced through `dashboard_data.json.tmp`; absence does not invalidate run | Not a reproduction or evidence artifact |
| Era export | simulator `export_era_data()` | Every 50 ticks in `full` mode | `era_export_<condition>_seed_<N>.txt` | Text, unversioned | Diagnostic | Narrative/heuristic content only | Humans, external narrative tooling | Overwritten; absence/failure is optional | No canonical role |
| Manual chronicle | simulator `export_to_mythology_file()` | Every 50 ticks and finalization when mythology is disabled and full output is enabled | `manual_chronicle_<condition>_seed_<N>.txt` | Text, unversioned | Diagnostic | Narrative content only | Humans, external narrative tooling | Appended; absence/failure is optional | No canonical role |
| Generated history | `mythology_final_summary()` | Optional finalization with mythology enabled | `history_<timestamp>.txt` | Text, unversioned | External/generated narrative | Depends on optional model/service behavior; never canonical | Humans | Network/model/fallback behavior can vary; optional | Must not be used for deterministic state comparison |
| RA faction beliefs | `RATracker` | Per tick when `--enable-belief-tracking` | `data/ra_faction_beliefs_<condition>_seed_<N>.csv` | CSV, subsystem-specific header | Optional diagnostic | Not included in required inventory or strict run validation | `analyze_ra.py`, humans | Tracker errors are not required-artifact failures | Exploratory observation only |
| RA annexations | `RATracker` | On observed annexation context when enabled | `data/ra_annexations_<condition>_seed_<N>.csv` | CSV, subsystem-specific header | Optional diagnostic | Same boundary as other RA outputs | `analyze_ra.py`, humans | May be empty or absent without invalidating canonical run | Exploratory observation only |
| RA follow-ups | `RATracker` | Scheduled follow-up observations when enabled | `data/ra_followups_<condition>_seed_<N>.csv` | CSV, subsystem-specific header | Optional diagnostic | Same boundary as other RA outputs | `analyze_ra.py`, humans | May be incomplete if run ends before follow-up | Exploratory observation only |
| Manifest error diagnostic | Simulator finalization | If manifest publication raises | `data/run_manifest_<condition>_seed_<N>.error.txt` | Text traceback | Diagnostic failure record | Its presence does not validate the run | Humans | May itself fail to write | Evidence that sealing failed, not a replacement manifest |

## Temporary files

Atomic publishers may briefly create:

- `data/run_manifest_<condition>_seed_<N>.json.tmp`;
- `<root>/experiment_manifest.json.tmp`;
- `dashboard_data.json.tmp`.

A leftover temporary file is not completion evidence. The runner rejects stale
or unexpected root entries in an invocation-owned fresh root.

## Derived and historical products

| Name | Producer | Creation / location | Authority and use |
| --- | --- | --- | --- |
| `results.csv` | `parse_logs.py` | User-selected output, historically repository root | Derived heuristic parsing of narrative logs; not canonical current metrics |
| `run_event_summary.csv`, `analysis_report.txt` | `analyze_logs.py` | User-selected/current directory defaults | Derived regex analysis of text logs; not deep-validated evidence |
| `figures/*.png` | `generate_figures.py` | `figures/` | Historical publication figures based on hard-coded derived tables |
| Core Replication V1 analysis tables/figures | historical analysis process and `plot_core_replication.py` | `experiment_runs/core-replication-v1/analysis/` | Historical pilot products; never pool with future V2 |
| Benchmark JSON/CSV | `benchmarks/benchmark_simulation.py` | `benchmarks/results/` by default | Engineering performance measurement, not simulation research evidence |
| `qtable_pop_300_300.json`, `pop_equilibrium_summary.json` | obsolete historical process | Repository root | Severely outdated; never use as current defaults, fixtures, baselines, or evidence |

Derived output is trustworthy only to the extent that its exact inputs and
transformation are identified. Current generic analysis scripts do not replace
strict artifact validation.

## Authority order

For one current run, use this order:

1. deep validation result for the complete run directory;
2. sealed schema-2 manifest and its inventoried structured files;
3. structured metrics/events/beliefs/summary interpreted under their schemas;
4. batch metadata;
5. optional text/dashboard/RA diagnostics;
6. derived tables and figures;
7. historical or obsolete files.

No current artifact set produced by the generic runner is V2-ready because the
complete expected-run provenance contract is not connected.

## Implementation evidence

- Contracts: [`src/thalren_vale/artifact_contract.py`](../../../src/thalren_vale/artifact_contract.py)
- Producers: [`src/thalren_vale/metrics.py`](../../../src/thalren_vale/metrics.py),
  [`src/thalren_vale/reproducibility.py`](../../../src/thalren_vale/reproducibility.py),
  [`src/thalren_vale/dashboard_bridge.py`](../../../src/thalren_vale/dashboard_bridge.py),
  [`src/thalren_vale/ra_tracker.py`](../../../src/thalren_vale/ra_tracker.py),
  [`src/thalren_vale/mythology.py`](../../../src/thalren_vale/mythology.py),
  [`run_experiments.py`](../../../run_experiments.py)
- Validator: [`src/thalren_vale/artifact_validation.py`](../../../src/thalren_vale/artifact_validation.py)
- Tests: [`tests/test_artifact_validation.py`](../../../tests/test_artifact_validation.py),
  [`tests/test_run_termination.py`](../../../tests/test_run_termination.py),
  [`tests/test_log_modes.py`](../../../tests/test_log_modes.py)
