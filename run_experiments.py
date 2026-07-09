#!/usr/bin/env python3
"""Versioned, resumable experiment runner for Thalren Vale."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
PLAN_SCHEMA_VERSION = 1
RUNNER_SCHEMA_VERSION = 1
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RESULT_COMPLETED = 'completed'
RESULT_WALL_CLOCK_LIMIT = 'wall_clock_limit'
RESULT_EXCEPTION = 'exception'
RESULT_INVALID_OUTPUT = 'invalid_output'
RESULT_CANCELLED = 'cancelled'
RESULT_SUPERSEDED = 'superseded'


def parse_seed_range(spec: str) -> list[int]:
    """Parse ``1-5``, ``1,3,5``, or ``42`` into unique ordered seeds."""
    seeds: list[int] = []
    for raw_part in spec.split(','):
        part = raw_part.strip()
        if not part:
            continue
        if '-' in part:
            lo_text, hi_text = part.split('-', 1)
            lo, hi = int(lo_text), int(hi_text)
            if hi < lo:
                raise ValueError(f"descending seed range is invalid: {part}")
            seeds.extend(range(lo, hi + 1))
        else:
            seeds.append(int(part))
    if not seeds:
        raise ValueError("at least one seed is required")
    return list(dict.fromkeys(seeds))


def load_plan(plan_path: Path) -> tuple[dict, str]:
    raw = plan_path.read_bytes()
    plan = json.loads(raw)
    if plan.get('schema_version') != PLAN_SCHEMA_VERSION:
        raise ValueError(
            f"plan schema_version must be {PLAN_SCHEMA_VERSION}")
    experiment_id = plan.get('experiment_id', '')
    if not _SAFE_NAME.fullmatch(experiment_id):
        raise ValueError("experiment_id must be filename-safe")
    conditions = plan.get('conditions')
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("plan must define at least one condition")
    names = set()
    for condition in conditions:
        name = condition.get('name', '')
        if not _SAFE_NAME.fullmatch(name):
            raise ValueError(f"invalid condition name: {name!r}")
        if name in names:
            raise ValueError(f"duplicate condition name: {name}")
        names.add(name)
        parse_seed_range(str(condition.get('seeds', '1-5')))
        if int(condition.get('ticks', plan.get('default_ticks', 5000))) < 1:
            raise ValueError(f"condition {name}: ticks must be positive")
        extra = condition.get('extra_args', [])
        if not isinstance(extra, (str, list)):
            raise ValueError(f"condition {name}: extra_args must be a list or string")
    return plan, hashlib.sha256(raw).hexdigest()


def _code_revision() -> dict:
    try:
        commit = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=PROJECT_ROOT,
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ['git', 'status', '--porcelain'], cwd=PROJECT_ROOT,
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip())
        return {'commit': commit, 'dirty': dirty}
    except (OSError, subprocess.SubprocessError):
        return {'commit': None, 'dirty': None}


def expected_outputs(run_dir: Path, condition: str, seed: int) -> dict[str, Path]:
    data = run_dir / 'data'
    suffix = f'{condition}_seed_{seed}'
    return {
        'metrics': data / f'metrics_{suffix}.csv',
        'events': data / f'faction_events_{suffix}.csv',
        'beliefs': data / f'beliefs_{suffix}.csv',
        'run_summary': data / 'run_summaries.csv',
        'run_manifest': data / f'run_manifest_{suffix}.json',
    }


def validate_run_outputs(run_dir: Path, condition: str, seed: int) -> tuple[bool, list[str]]:
    errors = []
    outputs = expected_outputs(run_dir, condition, seed)
    for label, path in outputs.items():
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty {label}: {path}")
    manifest_path = outputs['run_manifest']
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if manifest.get('seed') != seed:
                errors.append('run manifest seed mismatch')
            if manifest.get('condition') != condition:
                errors.append('run manifest condition mismatch')
            state_hash = manifest.get('state_hash', '')
            if len(state_hash) != 64:
                errors.append('run manifest has invalid state hash')
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid run manifest: {exc}")
    return not errors, errors


def classify_result(
    returncode: int | None,
    valid_outputs: bool,
    *,
    timed_out: bool = False,
) -> str:
    """Classify a run outcome with explicit research-result terminology."""
    if returncode == 0 and valid_outputs:
        return RESULT_COMPLETED
    if timed_out:
        return RESULT_WALL_CLOCK_LIMIT
    if returncode is not None and returncode < 0:
        return RESULT_CANCELLED
    if returncode not in (0, None):
        return RESULT_EXCEPTION
    return RESULT_INVALID_OUTPUT


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def run_single(
    seed: int,
    condition: str,
    ticks: int,
    extra_args: list[str],
    output_root: Path,
    *,
    resume: bool = False,
    timeout_seconds: int | None = 86400,
) -> dict:
    run_dir = output_root / condition / f'seed_{seed}'
    valid, _ = validate_run_outputs(run_dir, condition, seed)
    if resume and valid:
        print(f'  [{condition}] seed={seed}  SKIP (validated)')
        manifest = json.loads(
            expected_outputs(run_dir, condition, seed)['run_manifest']
            .read_text(encoding='utf-8'))
        return {
            'seed': seed, 'condition': condition, 'status': 'skipped',
            'result': RESULT_COMPLETED, 'runner_action': 'skipped_existing',
            'ok': True, 'elapsed': 0.0, 'returncode': 0,
            'state_hash': manifest['state_hash'],
            'run_dir': str(run_dir.relative_to(output_root)),
            'errors': [],
        }

    run_dir.mkdir(parents=True, exist_ok=True)
    # Metrics/event/belief files are opened with "w" by the simulator, but
    # run_summaries.csv is append-oriented for legacy multi-run directories.
    # Each pipeline run has its own directory, so remove stale finalization
    # artifacts before retrying an invalid/incomplete run.
    if resume:
        stale = expected_outputs(run_dir, condition, seed)
        for label in ('run_summary', 'run_manifest'):
            try:
                stale[label].unlink()
            except FileNotFoundError:
                pass
        for stale_name in (
            'runner_stdout.txt',
            'runner_stderr.txt',
            f'data/run_manifest_{condition}_seed_{seed}.error.txt',
        ):
            try:
                (run_dir / stale_name).unlink()
            except FileNotFoundError:
                pass
    command = [
        sys.executable, '-m', 'thalren_vale', '--seed', str(seed),
        '--condition', condition, '--ticks', str(ticks), *extra_args,
    ]
    env = os.environ.copy()
    source_path = str(PROJECT_ROOT / 'src')
    env['PYTHONPATH'] = source_path + os.pathsep + env.get('PYTHONPATH', '')
    env['PYTHONHASHSEED'] = '0'

    print(f'  [{condition}] seed={seed}  ...', end='', flush=True)
    started = time.perf_counter()
    timed_out = False
    try:
        process = subprocess.run(
            command, cwd=run_dir, env=env, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=timeout_seconds,
        )
        returncode = process.returncode
        if process.stderr:
            (run_dir / 'runner_stderr.txt').write_text(
                process.stderr, encoding='utf-8')
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = -1
        (run_dir / 'runner_stderr.txt').write_text(
            f'timeout: {exc}\n', encoding='utf-8')
    except (OSError, subprocess.SubprocessError) as exc:
        returncode = None
        (run_dir / 'runner_stderr.txt').write_text(
            f'runner exception: {exc}\n', encoding='utf-8')

    elapsed = round(time.perf_counter() - started, 3)
    valid, errors = validate_run_outputs(run_dir, condition, seed)
    ok = returncode == 0 and valid
    result = classify_result(returncode, valid, timed_out=timed_out)
    if not ok and 'process' in locals() and process.stdout:
        (run_dir / 'runner_stdout.txt').write_text(
            process.stdout, encoding='utf-8')
    state_hash = None
    manifest_path = expected_outputs(run_dir, condition, seed)['run_manifest']
    if manifest_path.is_file():
        try:
            state_hash = json.loads(
                manifest_path.read_text(encoding='utf-8')).get('state_hash')
        except json.JSONDecodeError:
            pass
    print(f"  {'OK' if ok else result.upper()}  ({elapsed:.1f}s)")
    return {
        'seed': seed, 'condition': condition,
        'status': RESULT_COMPLETED if ok else result,
        'result': result,
        'runner_action': 'executed',
        'ok': ok,
        'elapsed': elapsed, 'returncode': returncode,
        'state_hash': state_hash,
        'run_dir': str(run_dir.relative_to(output_root)),
        'command': command, 'errors': errors,
    }


def _write_index(output_root: Path, results: list[dict]) -> None:
    fields = [
        'condition', 'seed', 'status', 'result', 'runner_action', 'ok',
        'elapsed', 'returncode', 'state_hash', 'run_dir',
    ]
    with (output_root / 'run_index.csv').open(
            'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)


def run_from_plan(
    plan_path: Path,
    output_root: Path | None = None,
    *,
    resume: bool = False,
    overwrite: bool = False,
) -> tuple[list[dict], Path]:
    plan, plan_hash = load_plan(plan_path)
    output_root = output_root or Path('experiment_runs') / plan['experiment_id']
    output_root = output_root.resolve()

    if output_root.exists() and any(output_root.iterdir()):
        if overwrite:
            shutil.rmtree(output_root)
        elif not resume:
            raise FileExistsError(
                f"output directory is not empty: {output_root}; "
                "use --resume or --overwrite")
    output_root.mkdir(parents=True, exist_ok=True)

    manifest_path = output_root / 'experiment_manifest.json'
    if resume and manifest_path.is_file():
        batch_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if batch_manifest.get('plan_sha256') != plan_hash:
            raise ValueError(
                'cannot resume: experiment plan differs from existing manifest')
        batch_manifest['resume_count'] = batch_manifest.get('resume_count', 0) + 1
        batch_manifest['resumed_at'] = datetime.now(timezone.utc).isoformat()
        batch_manifest['completed_at'] = None
        batch_manifest['results'] = []
    else:
        batch_manifest = {
            'schema_version': RUNNER_SCHEMA_VERSION,
            'experiment_id': plan['experiment_id'],
            'plan_schema_version': plan['schema_version'],
            'plan_sha256': plan_hash,
            'plan_path': str(plan_path.resolve()),
            'code': _code_revision(),
            'started_at': datetime.now(timezone.utc).isoformat(),
            'completed_at': None,
            'resume_count': 0,
            'results': [],
        }
    _atomic_json(manifest_path, batch_manifest)

    results = []
    default_ticks = int(plan.get('default_ticks', 5000))
    default_timeout = plan.get('timeout_seconds', 86400)
    if default_timeout is not None:
        default_timeout = int(default_timeout)
        if default_timeout < 1:
            raise ValueError('timeout_seconds must be positive or null')
    for condition in plan['conditions']:
        name = condition['name']
        ticks = int(condition.get('ticks', default_ticks))
        seeds = parse_seed_range(str(condition.get('seeds', '1-5')))
        extra = condition.get('extra_args', [])
        extra_args = shlex.split(extra) if isinstance(extra, str) else list(extra)
        timeout_seconds = condition.get('timeout_seconds', default_timeout)
        if timeout_seconds is not None:
            timeout_seconds = int(timeout_seconds)
            if timeout_seconds < 1:
                raise ValueError(
                    f'condition {name}: timeout_seconds must be positive or null')
        print(f'\n── {name}: {len(seeds)} seeds × {ticks} ticks ──')
        for seed in seeds:
            result = run_single(
                seed, name, ticks, extra_args, output_root, resume=resume,
                timeout_seconds=timeout_seconds)
            results.append(result)
            batch_manifest['results'] = results
            _atomic_json(manifest_path, batch_manifest)
            _write_index(output_root, results)

    batch_manifest['completed_at'] = datetime.now(timezone.utc).isoformat()
    batch_manifest['complete'] = all(result['ok'] for result in results)
    _atomic_json(manifest_path, batch_manifest)
    return results, output_root


def verify_outputs(plan_path: Path, output_root: Path) -> bool:
    plan, _ = load_plan(plan_path)
    failures = []
    for condition in plan['conditions']:
        for seed in parse_seed_range(str(condition.get('seeds', '1-5'))):
            run_dir = output_root / condition['name'] / f'seed_{seed}'
            valid, errors = validate_run_outputs(run_dir, condition['name'], seed)
            if not valid:
                failures.extend(errors)
    for error in failures:
        print(f'  ✗ {error}')
    if not failures:
        print('  ✓ All expected outputs are present and valid.')
    return not failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--plan', type=Path)
    source.add_argument('--seeds', type=str)
    parser.add_argument('--condition', default='baseline')
    parser.add_argument('--ticks', type=int, default=5000)
    parser.add_argument('--extra-args', default='')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--timeout-seconds', type=int, default=86400,
                        help='Per-run timeout; default 86400 (24 hours)')
    args = parser.parse_args()
    if args.resume and args.overwrite:
        parser.error('--resume and --overwrite are mutually exclusive')

    if args.plan:
        plan_path = args.plan
    else:
        plan_path = Path('/tmp/thalren_inline_plan.json')
        inline_plan = {
            'schema_version': PLAN_SCHEMA_VERSION,
            'experiment_id': args.condition,
            'default_ticks': args.ticks,
            'timeout_seconds': args.timeout_seconds,
            'conditions': [{
                'name': args.condition, 'seeds': args.seeds,
                'extra_args': shlex.split(args.extra_args),
            }],
        }
        plan_path.write_text(json.dumps(inline_plan), encoding='utf-8')

    plan, _ = load_plan(plan_path)
    output_root = (
        args.output_dir
        or Path('experiment_runs') / plan['experiment_id']
    ).resolve()
    if args.verify:
        return 0 if verify_outputs(plan_path, output_root) else 1
    try:
        results, root = run_from_plan(
            plan_path, output_root, resume=args.resume, overwrite=args.overwrite)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    succeeded = sum(result['ok'] for result in results)
    print(f'\nCompleted {succeeded}/{len(results)} runs in {root}')
    return 0 if succeeded == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
