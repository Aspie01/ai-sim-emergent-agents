#!/usr/bin/env python3
"""Versioned, resumable experiment runner for Thalren Vale."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import signal
import shlex
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / 'src'
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from thalren_vale.artifact_validation import (  # noqa: E402
    ExpectedRunContract,
    ValidationMode,
    ValidationPolicy,
    artifact_paths,
    inspect_run_outputs,
)
from thalren_vale.attempt_ledger import AttemptLedger  # noqa: E402
from thalren_vale.reproducibility import (  # noqa: E402
    environment_fingerprint,
    plugin_inventory,
)

PLAN_SCHEMA_VERSION = 1
RUNNER_SCHEMA_VERSION = 1
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RESULT_COMPLETED = 'completed'
RESULT_WALL_CLOCK_LIMIT = 'wall_clock_limit'
RESULT_EXCEPTION = 'exception'
RESULT_INVALID_OUTPUT = 'invalid_output'
RESULT_CANCELLED = 'cancelled'
RESULT_SUPERSEDED = 'superseded'
_REQUIRED_CELL_KEYS = frozenset({
    'condition', 'seed', 'ticks', 'extra_args', 'timeout_seconds',
})
_OPTIONAL_CELL_KEYS = frozenset({'announcement'})
_RESERVED_ROOT_NAMES = frozenset({'experiment_manifest.json', 'run_index.csv'})
_UNCONTRACTED_SOCIAL_FLAGS = frozenset({
    '--enable-social-memory',
    '--disable-social-memory',
    '--enable-social-partner-bias',
    '--disable-social-partner-bias',
    '--maximum-social-ties',
    '--relationship-decay-interval',
})
_UNCONTRACTED_COALITION_FLAGS = frozenset({
    '--enable-coalition-emergence',
    '--disable-coalition-emergence',
    '--coalition-minimum-size',
    '--coalition-trust-threshold',
    '--coalition-familiarity-threshold',
    '--coalition-maximum-grievance',
    '--coalition-persistence-ticks',
    '--maximum-active-coalitions',
})
_UNCONTRACTED_LANGUAGE_FLAGS = frozenset({
    '--enable-language-evolution',
    '--disable-language-evolution',
    '--maximum-language-associations',
    '--maximum-signal-length',
    '--language-learning-rate',
    '--language-reinforcement-rate',
    '--language-forgetting-interval',
    '--enable-language-invention',
    '--disable-language-invention',
})
_UNCONTRACTED_DIALECT_FLAGS = frozenset({
    '--enable-coalition-dialect-influence',
    '--disable-coalition-dialect-influence',
    '--same-coalition-learning-multiplier',
    '--same-coalition-reinforcement-multiplier',
})
_UNCONTRACTED_LANGUAGE_CONTACT_FLAGS = frozenset({
    '--enable-language-contact',
    '--disable-language-contact',
    '--cross-group-learning-multiplier',
    '--borrowing-exposure-threshold',
    '--borrowing-confidence-threshold',
})
_UNCONTRACTED_INTERGENERATIONAL_LANGUAGE_FLAGS = frozenset({
    '--enable-intergenerational-language',
    '--disable-intergenerational-language',
    '--maximum-parental-meanings-per-parent',
    '--intergenerational-learning-strength',
})
_UNCONTRACTED_COMPOSITIONAL_PROTOLANGUAGE_FLAGS = frozenset({
    '--enable-compositional-protolanguage',
    '--disable-compositional-protolanguage',
    '--maximum-resource-morpheme-length',
    '--modality-morpheme-length',
})
_UNCONTRACTED_GRAMMAR_EVOLUTION_FLAGS = frozenset({
    '--enable-grammar-evolution',
    '--disable-grammar-evolution',
    '--order-adoption-threshold',
})
_UNCONTRACTED_FACTION_RELATIONSHIP_TRUST_FLAGS = frozenset({
    '--enable-faction-relationship-trust',
    '--disable-faction-relationship-trust',
    '--faction-relationship-trust-threshold',
})
_UNCONTRACTED_PRODUCTION_TRIAL_FLAGS = frozenset({
    '--enable-production-trial',
    '--disable-production-trial',
    '--production-trial-interval',
})
_UNCONTRACTED_COALITION_INTELLIGIBILITY_FLAGS = frozenset({
    '--enable-coalition-intelligibility',
    '--disable-coalition-intelligibility',
    '--coalition-intelligibility-threshold',
})
_UNCONTRACTED_LANGUAGE_COEVOLUTION_FLAGS = frozenset({
    '--enable-language-coevolution',
    '--disable-language-coevolution',
    '--intelligibility-reward',
    '--intelligibility-penalty',
})
_UNCONTRACTED_LEXICAL_EVOLUTION_FLAGS = frozenset({
    '--enable-lexical-evolution',
    '--disable-lexical-evolution',
    '--lexical-mutation-rate',
    '--maximum-lexical-lineage-depth',
})


class UnsafeResumeError(ValueError):
    """Raised when resume would overwrite or reuse untrusted evidence."""


def _reject_uncontracted_social_args(extra_args: tuple[str, ...]) -> None:
    """Keep engineering-only social controls out of research execution."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_SOCIAL_FLAGS
        ):
            raise ValueError(
                f'uncontracted social control is not permitted in the '
                f'experiment runner: {argument}')


def _reject_uncontracted_coalition_args(extra_args: tuple[str, ...]) -> None:
    """Reject every spelling of uncontracted coalition controls preflight."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_COALITION_FLAGS
        ):
            raise ValueError(
                f'uncontracted coalition control is not permitted in the '
                f'experiment runner: {argument}')


def _reject_uncontracted_language_args(extra_args: tuple[str, ...]) -> None:
    """Reject every spelling of engineering-only language controls."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_LANGUAGE_FLAGS
        ):
            raise ValueError(
                f'uncontracted language control is not permitted in the '
                f'experiment runner: {argument}')


def _reject_uncontracted_dialect_args(extra_args: tuple[str, ...]) -> None:
    """Reserve the complete dialect option family, including every prefix."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_DIALECT_FLAGS
        ):
            raise ValueError(
                f'uncontracted dialect control is not permitted in the '
                f'experiment runner: {argument}')


def _reject_uncontracted_language_contact_args(
    extra_args: tuple[str, ...],
) -> None:
    """Reserve every exact, equals, and proper-prefix contact option."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_LANGUAGE_CONTACT_FLAGS
        ):
            raise ValueError(
                f'uncontracted language contact control is not permitted in '
                f'the experiment runner: {argument}')


def _reject_uncontracted_intergenerational_language_args(
    extra_args: tuple[str, ...],
) -> None:
    """Reserve every exact, equals, and prefix transmission option."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_INTERGENERATIONAL_LANGUAGE_FLAGS
        ):
            raise ValueError(
                f'uncontracted intergenerational language control is not '
                f'permitted in the experiment runner: {argument}')


def _reject_uncontracted_compositional_protolanguage_args(
    extra_args: tuple[str, ...],
) -> None:
    """Reserve every exact, equals, and prefix composition option."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_COMPOSITIONAL_PROTOLANGUAGE_FLAGS
        ):
            raise ValueError(
                f'uncontracted compositional protolanguage control is not '
                f'permitted in the experiment runner: {argument}')


def _reject_uncontracted_grammar_evolution_args(
    extra_args: tuple[str, ...],
) -> None:
    """Reserve every exact, equals, and prefix grammar option."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_GRAMMAR_EVOLUTION_FLAGS
        ):
            raise ValueError(
                f'uncontracted grammar evolution control is not '
                f'permitted in the experiment runner: {argument}')


def _reject_uncontracted_faction_relationship_trust_args(
    extra_args: tuple[str, ...],
) -> None:
    """Reserve every exact, equals, and prefix faction-model option."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_FACTION_RELATIONSHIP_TRUST_FLAGS
        ):
            raise ValueError(
                f'uncontracted faction relationship trust control is not '
                f'permitted in the experiment runner: {argument}')


def _reject_uncontracted_production_trial_args(
    extra_args: tuple[str, ...],
) -> None:
    """Reserve every exact, equals, and prefix production-trial option."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_PRODUCTION_TRIAL_FLAGS
        ):
            raise ValueError(
                f'uncontracted production trial control is not permitted in '
                f'the experiment runner: {argument}')


def _reject_uncontracted_coalition_intelligibility_args(
    extra_args: tuple[str, ...],
) -> None:
    """Reserve every exact, equals, and prefix gating option."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_COALITION_INTELLIGIBILITY_FLAGS
        ):
            raise ValueError(
                f'uncontracted coalition intelligibility control is not '
                f'permitted in the experiment runner: {argument}')


def _reject_uncontracted_language_coevolution_args(
    extra_args: tuple[str, ...],
) -> None:
    """Reserve every exact, equals, and prefix coevolution option."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_LANGUAGE_COEVOLUTION_FLAGS
        ):
            raise ValueError(
                f'uncontracted language coevolution control is not '
                f'permitted in the experiment runner: {argument}')


def _reject_uncontracted_lexical_evolution_args(
    extra_args: tuple[str, ...],
) -> None:
    """Reserve every exact, equals, and prefix lexical-evolution option."""
    for argument in extra_args:
        option_name = argument.split('=', 1)[0]
        if any(
            option_name == flag
            or (
                option_name.startswith('--')
                and len(option_name) > 2
                and flag.startswith(option_name)
            )
            for flag in _UNCONTRACTED_LEXICAL_EVOLUTION_FLAGS
        ):
            raise ValueError(
                f'uncontracted lexical evolution control is not permitted in '
                f'the experiment runner: {argument}')


@dataclass(frozen=True)
class _FrozenCell:
    """Validated cell values detached from every caller-owned container."""

    condition: str
    seed: int
    ticks: int
    extra_args: tuple[str, ...]
    timeout_seconds: int | None
    announcement: str | None


def _freeze_cell(cell: object) -> _FrozenCell:
    """Copy and validate one exact built-in cell mapping exactly once."""
    if type(cell) is not dict:
        raise ValueError('cell must be an exact built-in dict')

    snapshot = dict.copy(cell)
    if any(type(key) is not str for key in snapshot):
        raise ValueError('cell keys must be exact strings')
    keys = frozenset(snapshot)
    missing = _REQUIRED_CELL_KEYS - keys
    unexpected = keys - _REQUIRED_CELL_KEYS - _OPTIONAL_CELL_KEYS
    if missing:
        raise ValueError(f'missing cell keys: {sorted(missing)}')
    if unexpected:
        raise ValueError(f'unexpected cell keys: {sorted(unexpected)}')

    condition = snapshot['condition']
    seed = snapshot['seed']
    ticks = snapshot['ticks']
    extra_args = snapshot['extra_args']
    timeout_seconds = snapshot['timeout_seconds']
    announcement = snapshot['announcement'] if 'announcement' in snapshot else None

    if type(condition) is not str or not condition or not _SAFE_NAME.fullmatch(
        condition
    ):
        raise ValueError(f'unsafe condition name: {condition!r}')
    if condition in _RESERVED_ROOT_NAMES:
        raise ValueError(f'reserved condition name: {condition!r}')
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    if type(ticks) is not int or ticks < 1:
        raise ValueError('ticks must be a positive integer')
    if type(extra_args) is not list:
        raise ValueError('extra_args must be an exact list of strings')
    frozen_extra_args = tuple(extra_args)
    if not all(type(item) is str for item in frozen_extra_args):
        raise ValueError('extra_args must be an exact list of strings')
    _reject_uncontracted_social_args(frozen_extra_args)
    _reject_uncontracted_coalition_args(frozen_extra_args)
    _reject_uncontracted_language_args(frozen_extra_args)
    _reject_uncontracted_dialect_args(frozen_extra_args)
    _reject_uncontracted_language_contact_args(frozen_extra_args)
    _reject_uncontracted_intergenerational_language_args(frozen_extra_args)
    _reject_uncontracted_lexical_evolution_args(frozen_extra_args)
    _reject_uncontracted_compositional_protolanguage_args(frozen_extra_args)
    _reject_uncontracted_grammar_evolution_args(frozen_extra_args)
    _reject_uncontracted_language_coevolution_args(frozen_extra_args)
    _reject_uncontracted_coalition_intelligibility_args(frozen_extra_args)
    _reject_uncontracted_production_trial_args(frozen_extra_args)
    _reject_uncontracted_faction_relationship_trust_args(frozen_extra_args)
    if timeout_seconds is not None and (
        type(timeout_seconds) is not int or timeout_seconds < 1
    ):
        raise ValueError('timeout_seconds must be positive or null')
    if announcement is not None and type(announcement) is not str:
        raise ValueError('announcement must be a string or null')

    return _FrozenCell(
        condition=condition,
        seed=seed,
        ticks=ticks,
        extra_args=frozen_extra_args,
        timeout_seconds=timeout_seconds,
        announcement=announcement,
    )


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
    _validate_revision_contract(plan)
    _validate_environment_contract(plan)
    if plan.get('fail_fast') is not None and type(plan['fail_fast']) is not bool:
        raise ValueError('fail_fast must be true or false')
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
        parsed_extra = shlex.split(extra) if isinstance(extra, str) else extra
        if not all(type(item) is str for item in parsed_extra):
            raise ValueError(
                f"condition {name}: extra_args must contain only exact strings")
        _reject_uncontracted_social_args(tuple(parsed_extra))
        _reject_uncontracted_coalition_args(tuple(parsed_extra))
        _reject_uncontracted_language_args(tuple(parsed_extra))
        _reject_uncontracted_dialect_args(tuple(parsed_extra))
        _reject_uncontracted_language_contact_args(tuple(parsed_extra))
        _reject_uncontracted_intergenerational_language_args(
            tuple(parsed_extra))
        _reject_uncontracted_lexical_evolution_args(tuple(parsed_extra))
        _reject_uncontracted_compositional_protolanguage_args(
            tuple(parsed_extra))
        _reject_uncontracted_grammar_evolution_args(tuple(parsed_extra))
        _reject_uncontracted_language_coevolution_args(
            tuple(parsed_extra))
        _reject_uncontracted_coalition_intelligibility_args(
            tuple(parsed_extra))
        _reject_uncontracted_production_trial_args(tuple(parsed_extra))
        _reject_uncontracted_faction_relationship_trust_args(
            tuple(parsed_extra))
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
        return {'commit': commit, 'tag': _annotated_tag(), 'dirty': dirty}
    except (OSError, subprocess.SubprocessError):
        return {'commit': None, 'tag': None, 'dirty': None}


def _annotated_tag() -> str | None:
    """Return the annotated tag naming HEAD exactly, or None.

    `--exact-match` matters: plain `git describe` reports the nearest ancestor
    tag with a distance suffix, which would record an untagged revision as
    tagged.
    """
    try:
        completed = subprocess.run(
            ['git', 'describe', '--exact-match', '--tags', 'HEAD'],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


class RevisionContractError(ValueError):
    """HEAD does not satisfy the revision contract a plan declared."""


_EXPECTED_COMMIT = re.compile(r'[0-9a-f]{40}')

# A plan opts into revision enforcement by declaring any of these. Enforcement
# is opt-in because the runner is also used for engineering characterization on
# untagged working revisions, and root AGENTS.md forbids tagging a run-ready
# revision unless explicitly requested. A plan that says nothing about its
# revision therefore behaves exactly as before; a plan that makes a provenance
# claim has that claim checked before anything executes.
_REVISION_CONTRACT_KEYS = (
    'expected_commit', 'expected_tag', 'require_clean_revision')


def _validate_revision_contract(plan: dict) -> None:
    """Reject a malformed revision contract while loading the plan.

    Shape errors are rejected here rather than at preflight so that a
    typo cannot silently disable enforcement: a plan carrying
    ``expected_commit: ""`` must fail loudly instead of reading as absent.
    """
    commit = plan.get('expected_commit')
    if commit is not None and (
            type(commit) is not str or not _EXPECTED_COMMIT.fullmatch(commit)):
        raise ValueError(
            'expected_commit must be a 40-character lowercase hex commit id')

    tag = plan.get('expected_tag')
    if tag is not None and (type(tag) is not str or not tag.strip()):
        raise ValueError('expected_tag must be a nonempty string')

    require_clean = plan.get('require_clean_revision')
    if require_clean is not None and type(require_clean) is not bool:
        # Exact identity, not truthiness: `1` would otherwise read as True and
        # record a boolean the plan never stated.
        raise ValueError('require_clean_revision must be true or false')


def _declares_revision_contract(plan: dict) -> bool:
    return any(plan.get(key) is not None for key in _REVISION_CONTRACT_KEYS)


def _preflight_revision_contract(plan: dict) -> dict:
    """Fail closed before execution when HEAD violates the plan's contract.

    Returns the evidence to record either way. When a plan declares no
    contract this records the revision and enforces nothing, which is the
    pre-existing behaviour.

    An unreadable revision is a failure, not a pass. A plan that claims to run
    at a known commit cannot be honoured where the commit cannot be read, and
    treating that as success would record `code_dirty: null` under a provenance
    claim the runner never actually checked.
    """
    revision = _code_revision()
    evidence = {
        'enforced': False,
        'expected_commit': plan.get('expected_commit'),
        'expected_tag': plan.get('expected_tag'),
        'require_clean_revision': plan.get('require_clean_revision'),
        'revision': revision,
    }
    if not _declares_revision_contract(plan):
        return evidence
    evidence['enforced'] = True

    if revision['commit'] is None:
        raise RevisionContractError(
            'plan declares a revision contract but the repository revision '
            'could not be read; refusing to execute under an unverifiable '
            'revision')

    expected_commit = plan.get('expected_commit')
    if expected_commit is not None and revision['commit'] != expected_commit:
        raise RevisionContractError(
            f'plan expects commit {expected_commit} but HEAD is '
            f'{revision["commit"]}; a plan cannot be executed against a '
            'different revision than the one it was frozen against')

    expected_tag = plan.get('expected_tag')
    if expected_tag is not None:
        if revision['tag'] is None:
            raise RevisionContractError(
                f'plan expects annotated tag {expected_tag!r} but no annotated '
                'tag resolves exactly to HEAD')
        if revision['tag'] != expected_tag:
            raise RevisionContractError(
                f'plan expects annotated tag {expected_tag!r} but HEAD is '
                f'tagged {revision["tag"]!r}')

    if plan.get('require_clean_revision'):
        if revision['dirty'] is None:
            raise RevisionContractError(
                'plan requires a clean revision but the working tree status '
                'could not be read')
        if revision['dirty']:
            raise RevisionContractError(
                'plan requires a clean revision but the parent repository has '
                'uncommitted changes; commit or stash them, or remove '
                'require_clean_revision from the plan')

    return evidence


class EnvironmentContractError(ValueError):
    """The environment does not satisfy the contract a plan declared."""


_ENVIRONMENT_CONTRACT_KEYS = (
    'expected_environment_fingerprint', 'require_empty_plugin_inventory')


def _environment_record() -> dict:
    """Everything section 10 requires about the environment, recorded always.

    The plugin inventory is recorded in full rather than only as part of the
    fingerprint digest. A bare hash mismatch says something changed but not
    what, and "which plugin appeared" is exactly the question someone auditing a
    mismatched run needs answered.
    """
    inventory = plugin_inventory(PROJECT_ROOT)
    return {
        'fingerprint': environment_fingerprint(PROJECT_ROOT),
        'python_version': '%d.%d.%d' % sys.version_info[:3],
        'python_implementation': platform.python_implementation(),
        'python_executable': os.path.abspath(sys.executable),
        'system': platform.system(),
        'machine': platform.machine(),
        # The runner forces PYTHONHASHSEED=0 into every child, so the policy is
        # a property of the runner rather than of whatever shell invoked it.
        'pythonhashseed_policy': 'forced_zero_for_children',
        'plugin_inventory': inventory,
        'plugin_count': len(inventory),
    }


def _validate_environment_contract(plan: dict) -> None:
    """Reject a malformed environment contract while loading the plan."""
    fingerprint = plan.get('expected_environment_fingerprint')
    if fingerprint is not None and (
            type(fingerprint) is not str
            or not re.fullmatch(r'[0-9a-f]{64}', fingerprint)):
        raise ValueError(
            'expected_environment_fingerprint must be a 64-character '
            'lowercase hex digest')
    require_empty = plan.get('require_empty_plugin_inventory')
    if require_empty is not None and type(require_empty) is not bool:
        raise ValueError(
            'require_empty_plugin_inventory must be true or false')


def _declares_environment_contract(plan: dict) -> bool:
    return any(plan.get(key) is not None
               for key in _ENVIRONMENT_CONTRACT_KEYS)


def _preflight_environment_contract(plan: dict) -> dict:
    """Fail closed before execution when the environment violates the plan.

    Opt-in for the same reason the revision contract is: the runner serves
    engineering characterization on whatever interpreter is to hand, and a
    mandatory fingerprint match would make the runner unusable outside the one
    machine that produced the expected digest.
    """
    environment = _environment_record()
    evidence = {
        'enforced': False,
        'expected_environment_fingerprint': plan.get(
            'expected_environment_fingerprint'),
        'require_empty_plugin_inventory': plan.get(
            'require_empty_plugin_inventory'),
        'environment': environment,
    }
    if not _declares_environment_contract(plan):
        return evidence
    evidence['enforced'] = True

    expected = plan.get('expected_environment_fingerprint')
    if expected is not None and environment['fingerprint'] != expected:
        raise EnvironmentContractError(
            f'plan expects environment fingerprint {expected} but this '
            f'environment is {environment["fingerprint"]}; interpreter, '
            f'platform, or plugin inventory differs. Plugins present: '
            f'{[entry["name"] for entry in environment["plugin_inventory"]] or "none"}')

    if plan.get('require_empty_plugin_inventory'):
        if environment['plugin_inventory']:
            names = ', '.join(
                entry['name'] for entry in environment['plugin_inventory'])
            raise EnvironmentContractError(
                f'plan requires an empty plugin inventory but plugins are '
                f'present: {names}. Plugins can alter a run, so a cell that '
                'declares none must not execute beside them')

    return evidence


def _config_fingerprint(cells: list[dict]) -> str:
    """Digest the controls every cell will run under, independent of order.

    Complements `plan_sha256`, which digests the plan's raw bytes and therefore
    changes when a comment or whitespace does. This changes only when what a
    cell actually runs changes, which is the sensitivity a resume needs: a
    reformatted plan should still resume, an edited condition should not.

    Order is excluded deliberately -- `_schedule_id` covers that separately, so
    a reordered matrix is reported as a schedule change rather than as a
    different configuration.
    """
    payload = sorted(
        [cell['condition'], cell['seed'], cell['ticks'],
         list(cell['extra_args']), cell['timeout_seconds']]
        for cell in cells
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _schedule_id(cells: list[dict]) -> str:
    """Digest the dispatch order itself.

    Section 11.2 requires resume to preserve schedule identity and record
    deviations rather than silently regenerating order, so the order needs a
    name of its own that a later run can be compared against.
    """
    ordered = [f"{cell['condition']}/seed_{cell['seed']}" for cell in cells]
    encoded = json.dumps(ordered, separators=(',', ':'),
                         ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _resume_contract_record(
    *,
    experiment_id: str,
    plan_hash: str,
    revision: dict,
    environment: dict,
    config_fingerprint: str,
) -> dict:
    """The identity a later resume must match exactly.

    Written as one block rather than left implicit across the revision and
    environment records, because a resume compares a single contract and
    reassembling one from scattered fields is where a field quietly goes
    missing.
    """
    return {
        'experiment_id': experiment_id,
        'plan_sha256': plan_hash,
        'commit': revision.get('commit'),
        'tag': revision.get('tag'),
        'dirty': revision.get('dirty'),
        'environment_fingerprint': environment.get('fingerprint'),
        'config_fingerprint': config_fingerprint,
    }


def expected_outputs(run_dir: Path, condition: str, seed: int) -> dict[str, Path]:
    paths = artifact_paths(run_dir, condition, seed)
    return {
        'metrics': paths['metrics'],
        'events': paths['events'],
        'beliefs': paths['beliefs'],
        'run_summary': paths['summary'],
        'run_manifest': paths['manifest'],
    }


def validate_run_outputs(
    run_dir: Path,
    condition: str,
    seed: int,
    expected_ticks: int | None = None,
    *,
    mode: ValidationMode = 'auto',
    policy: ValidationPolicy | None = None,
    expected_contract: ExpectedRunContract | None = None,
) -> tuple[bool, list[str]]:
    """Compatibility wrapper around detailed streaming validation."""
    report = inspect_run_outputs(
        run_dir,
        condition,
        seed,
        expected_ticks=expected_ticks,
        mode=mode,
        policy=policy,
        expected_contract=expected_contract,
    )
    return report.valid, report.errors


def classify_result(
    returncode: int | None,
    valid_outputs: bool,
    *,
    timed_out: bool = False,
) -> str:
    """Classify outcomes; SIGTERM is an external exception, not cancellation."""
    if returncode == 0 and valid_outputs:
        return RESULT_COMPLETED
    if timed_out:
        return RESULT_WALL_CLOCK_LIMIT
    if returncode in {-signal.SIGINT, 128 + signal.SIGINT}:
        return RESULT_CANCELLED
    if returncode not in (0, None):
        return RESULT_EXCEPTION
    return RESULT_INVALID_OUTPUT


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def _simulation_command(
    seed: int,
    condition: str,
    ticks: int,
    extra_args: tuple[str, ...],
    plan_identity: str | None = None,
    plan_sha256: str | None = None,
) -> list[str]:
    """Build the simulator child command; tests may replace it with a tiny child.

    Plan identity travels on argv rather than through the environment so the
    provenance a child recorded is visible in the command that produced it.
    """
    command = [
        sys.executable, '-m', 'thalren_vale', '--seed', str(seed),
        '--condition', condition, '--ticks', str(ticks),
    ]
    if plan_identity is not None:
        command += ['--plan-identity', plan_identity]
    if plan_sha256 is not None:
        command += ['--plan-sha256', plan_sha256]
    command += list(extra_args)
    return command


def _safe_existing_ancestor(path: Path) -> Path:
    """Return the nearest existing ancestor after rejecting symlink components.

    Paths are inspected lexically rather than resolved so a missing destination
    cannot hide an existing symlinked parent that ``mkdir`` would follow.
    """
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    existing = current
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            raise UnsafeResumeError(
                f'cannot safely use symlinked path component {current}')
        if not current.exists():
            break
        existing = current
    return existing


def _strict_lexical_descendant(
    path: Path,
    parent: Path,
    *,
    label: str,
) -> Path:
    """Return a safe nonempty lexical relative path or reject containment."""
    if not path.is_absolute() or not parent.is_absolute():
        raise UnsafeResumeError(f'{label} must use absolute paths')
    try:
        relative = path.relative_to(parent)
    except ValueError as exc:
        raise UnsafeResumeError(
            f'{label} escapes its validated parent: {path}') from exc
    if not relative.parts or any(part in {'', '.', '..'} for part in relative.parts):
        raise UnsafeResumeError(
            f'{label} is not a strict safe descendant: {path}')
    if parent.joinpath(*relative.parts) != path:
        raise UnsafeResumeError(
            f'{label} uses an alternate lexical spelling: {path}')
    return relative


def _validate_contained_path(
    path: Path,
    parent: Path,
    resolved_parent: Path,
    *,
    label: str,
) -> Path:
    """Prove lexical and resolved containment without following symlink entries."""
    relative = _strict_lexical_descendant(path, parent, label=label)
    _safe_existing_ancestor(path)
    try:
        resolved_path = path.resolve(strict=False)
    except OSError as exc:
        raise UnsafeResumeError(
            f'cannot resolve {label} safely: {path}') from exc
    _strict_lexical_descendant(
        resolved_path,
        resolved_parent,
        label=f'resolved {label}',
    )
    return relative


def _validate_root_anchor(
    output_root: Path,
    root_lexical: Path,
    root_resolved: Path,
    root_identity: tuple[int, int],
) -> None:
    """Revalidate the invocation-owned root path, identity, and resolution."""
    if output_root != root_lexical or Path(os.path.abspath(output_root)) != root_lexical:
        raise UnsafeResumeError(
            f'fresh output root lexical path changed: {output_root}')
    _safe_existing_ancestor(root_lexical)
    try:
        root_stat = os.lstat(root_lexical)
        current_resolved = root_lexical.resolve(strict=True)
    except OSError as exc:
        raise UnsafeResumeError(
            f'fresh output root is unavailable: {root_lexical}') from exc
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or stat.S_ISLNK(root_stat.st_mode)
        or (root_stat.st_dev, root_stat.st_ino) != root_identity
    ):
        raise UnsafeResumeError(
            f'fresh output root identity changed: {root_lexical}')
    if current_resolved != root_resolved:
        raise UnsafeResumeError(
            f'fresh output root resolved path changed: {root_lexical}')


def _path_is_nonempty_directory(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def _describe_nonempty_resume_root(
    output_root: Path,
    plan: dict,
    plan_hash: str,
) -> str:
    """Inspect a rejected nonempty root without modifying it."""
    details: list[str] = []
    manifest_path = output_root / 'experiment_manifest.json'
    if manifest_path.is_symlink():
        details.append('experiment manifest is symlinked')
    elif manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if manifest.get('plan_sha256') != plan_hash:
                details.append('plan SHA-256 differs')
            if manifest.get('experiment_id') != plan.get('experiment_id'):
                details.append('experiment identity differs')
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            details.append(f'invalid experiment manifest: {exc}')
    else:
        details.append('matching experiment manifest is unavailable')
    planned_conditions = {condition['name'] for condition in plan['conditions']}
    known_root = {'experiment_manifest.json', 'run_index.csv', *planned_conditions}
    unknown = sorted(path.name for path in output_root.iterdir() if path.name not in known_root)
    if unknown:
        details.append(f'unknown root entries: {unknown}')
    extra_conditions = sorted(
        path.name for path in output_root.iterdir()
        if path.is_dir() and path.name not in planned_conditions)
    if extra_conditions:
        details.append(f'extra condition directories: {extra_conditions}')
    return '; '.join(details) or 'root contains prior batch state'


def _preflight_fresh_output_root(
    output_root: Path,
    *,
    resume: bool,
    overwrite: bool,
    direct: bool,
    plan: dict | None = None,
    plan_hash: str | None = None,
) -> tuple[Path, tuple[int, int]]:
    """Create one absent/empty ordinary root and return its filesystem identity."""
    output_root = Path(os.path.abspath(output_root))
    if output_root.is_symlink():
        raise UnsafeResumeError(
            f'cannot safely use symlinked output root: {output_root}')
    _safe_existing_ancestor(output_root)
    if output_root.exists() and not output_root.is_dir():
        raise UnsafeResumeError(
            f'output root is not an ordinary directory: {output_root}')
    if _path_is_nonempty_directory(output_root):
        if direct:
            mode = 'overwrite' if overwrite else 'resume' if resume else 'run'
            raise UnsafeResumeError(
                f'cannot {mode} in nonempty output root {output_root}: '
                'direct execution requires an absent or truly empty root and '
                'preserved every existing byte unchanged')
        if overwrite:
            raise UnsafeResumeError(
                f'cannot overwrite nonempty output root {output_root}: '
                'this V2 runner preserves existing evidence unchanged; '
                'allocate a new output root instead')
        if resume:
            details = (
                _describe_nonempty_resume_root(output_root, plan, plan_hash)
                if plan is not None and plan_hash is not None
                else 'root contains prior batch state'
            )
            raise UnsafeResumeError(
                f'cannot resume nonempty output root {output_root}: {details}; '
                'this slice permits only absent or truly empty roots and '
                'preserved every existing byte unchanged')
        raise FileExistsError(
            f'output directory is not empty: {output_root}; '
            'this fresh-root runner never reuses, skips, or replaces existing '
            'output, and neither resume nor overwrite relaxes that; '
            'allocate a new output root instead')
    output_root.mkdir(parents=True, exist_ok=True)
    root_stat = os.lstat(output_root)
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
        raise UnsafeResumeError(
            f'output root is not an ordinary directory: {output_root}')
    return output_root, (root_stat.st_dev, root_stat.st_ino)


def _validate_initialized_root(
    output_root: Path,
    root_lexical: Path,
    root_resolved: Path,
    root_identity: tuple[int, int],
    metadata_identities: dict[str, tuple[int, int]],
    condition_identities: dict[str, tuple[int, int]],
    cell_identities: dict[tuple[str, int], tuple[int, int]],
) -> None:
    """Revalidate the exact root entries created by this invocation."""
    _validate_root_anchor(
        output_root, root_lexical, root_resolved, root_identity)

    cells_by_condition: dict[str, set[str]] = {}
    for condition, seed in cell_identities:
        cells_by_condition.setdefault(condition, set()).add(f'seed_{seed}')
    for condition in condition_identities:
        cells_by_condition.setdefault(condition, set())
    expected_root_names = set(metadata_identities) | set(condition_identities)
    actual_entries = {entry.name: entry for entry in output_root.iterdir()}
    if set(actual_entries) != expected_root_names:
        unknown = sorted(set(actual_entries) - expected_root_names)
        missing = sorted(expected_root_names - set(actual_entries))
        raise UnsafeResumeError(
            f'fresh output root layout changed; unknown={unknown}, '
            f'missing={missing}')

    for name, expected_identity in metadata_identities.items():
        path = actual_entries[name]
        mode = os.lstat(path).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise UnsafeResumeError(
                f'runner metadata is not an ordinary file: {path}')
        path_stat = os.lstat(path)
        if (path_stat.st_dev, path_stat.st_ino) != expected_identity:
            raise UnsafeResumeError(
                f'runner metadata identity changed: {path}')
    for condition, expected_cells in cells_by_condition.items():
        condition_path = actual_entries[condition]
        condition_stat = os.lstat(condition_path)
        condition_mode = condition_stat.st_mode
        if stat.S_ISLNK(condition_mode) or not stat.S_ISDIR(condition_mode):
            raise UnsafeResumeError(
                f'condition path is not an ordinary directory: {condition_path}')
        if (
            condition_stat.st_dev,
            condition_stat.st_ino,
        ) != condition_identities[condition]:
            raise UnsafeResumeError(
                f'condition path identity changed: {condition_path}')
        actual_cells = {entry.name: entry for entry in condition_path.iterdir()}
        if set(actual_cells) != expected_cells:
            unknown = sorted(set(actual_cells) - expected_cells)
            missing = sorted(expected_cells - set(actual_cells))
            raise UnsafeResumeError(
                f'condition layout changed for {condition!r}; '
                f'unknown={unknown}, missing={missing}')
        for cell_name, cell_path in actual_cells.items():
            cell_stat = os.lstat(cell_path)
            cell_mode = cell_stat.st_mode
            if stat.S_ISLNK(cell_mode) or not stat.S_ISDIR(cell_mode):
                raise UnsafeResumeError(
                    f'cell path is not an ordinary directory: {cell_path}')
            seed = int(cell_name.removeprefix('seed_'))
            expected_identity = cell_identities[(condition, seed)]
            if (cell_stat.st_dev, cell_stat.st_ino) != expected_identity:
                raise UnsafeResumeError(
                    f'cell path identity changed: {cell_path}')


def _cell_paths(
    output_root: Path,
    root_resolved: Path,
    cell: _FrozenCell,
    *,
    require_run_absent: bool,
) -> tuple[Path, Path]:
    """Construct and contain paths using only one frozen cell record."""
    condition_path = output_root / cell.condition
    run_component = f'seed_{cell.seed}'
    run_dir = condition_path / run_component

    condition_relative = _validate_contained_path(
        condition_path,
        output_root,
        root_resolved,
        label='condition path',
    )
    if condition_relative.parts != (cell.condition,):
        raise UnsafeResumeError(
            f'condition path is not canonical: {condition_path}')
    resolved_condition = condition_path.resolve(strict=False)
    run_relative = _validate_contained_path(
        run_dir,
        condition_path,
        resolved_condition,
        label='run directory',
    )
    if run_relative.parts != (run_component,):
        raise UnsafeResumeError(f'run directory is not canonical: {run_dir}')
    _validate_contained_path(
        run_dir,
        output_root,
        root_resolved,
        label='run directory beneath output root',
    )
    if require_run_absent and os.path.lexists(run_dir):
        raise UnsafeResumeError(
            f'cannot safely execute existing cell {cell.condition} '
            f'seed {cell.seed}: cells must be absent in the fresh invocation; '
            'existing artifacts were preserved unchanged')
    return condition_path, run_dir


def _ordinary_identity(path: Path, *, directory: bool, label: str) -> tuple[int, int]:
    """Return an ordinary path identity without following a symlink."""
    try:
        path_stat = os.lstat(path)
    except OSError as exc:
        raise UnsafeResumeError(f'{label} is unavailable: {path}') from exc
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if stat.S_ISLNK(path_stat.st_mode) or not expected(path_stat.st_mode):
        kind = 'directory' if directory else 'file'
        raise UnsafeResumeError(f'{label} is not an ordinary {kind}: {path}')
    return path_stat.st_dev, path_stat.st_ino


def _run_cells_in_fresh_root(
    cells: list[dict],
    output_root: Path,
    *,
    resume: bool = False,
    overwrite: bool = False,
    direct: bool = False,
    fail_fast: bool = False,
    plan: dict | None = None,
    plan_hash: str | None = None,
    batch_manifest: dict | None = None,
) -> tuple[list[dict], Path]:
    """Own one complete fresh-root invocation; no per-cell capability escapes."""
    for flag_name, flag_value in (
        ('resume', resume),
        ('overwrite', overwrite),
        ('direct', direct),
        ('fail_fast', fail_fast),
    ):
        if type(flag_value) is not bool:
            raise ValueError(f'{flag_name} must be a boolean')
    if type(cells) is not list:
        raise ValueError('cells must be an exact built-in list')
    caller_cells = tuple(cells)
    frozen_cells = tuple(_freeze_cell(cell) for cell in caller_cells)
    del caller_cells
    del cells

    seen_cells: set[tuple[str, int]] = set()
    for cell in frozen_cells:
        identity = (cell.condition, cell.seed)
        if identity in seen_cells:
            raise ValueError(
                f'duplicate cell in one fresh invocation: '
                f'{cell.condition} seed {cell.seed}')
        seen_cells.add(identity)

    requested_root = Path(os.path.abspath(output_root))
    _safe_existing_ancestor(requested_root)
    requested_resolved = requested_root.resolve(strict=False)
    for cell in frozen_cells:
        _cell_paths(
            requested_root,
            requested_resolved,
            cell,
            require_run_absent=False,
        )

    output_root, root_identity = _preflight_fresh_output_root(
        output_root,
        resume=resume,
        overwrite=overwrite,
        direct=direct,
        plan=plan,
        plan_hash=plan_hash,
    )
    root_lexical = output_root
    root_resolved = output_root.resolve(strict=True)
    metadata_identities: dict[str, tuple[int, int]] = {}
    condition_identities: dict[str, tuple[int, int]] = {}
    cell_identities: dict[tuple[str, int], tuple[int, int]] = {}
    results: list[dict] = []
    manifest_path = output_root / 'experiment_manifest.json'

    def validate_root() -> None:
        _validate_initialized_root(
            output_root,
            root_lexical,
            root_resolved,
            root_identity,
            metadata_identities,
            condition_identities,
            cell_identities,
        )

    def validate_metadata_target(path: Path, *, atomic: bool) -> None:
        validate_root()
        relative = _validate_contained_path(
            path,
            output_root,
            root_resolved,
            label='runner metadata path',
        )
        if relative.parts != (path.name,):
            raise UnsafeResumeError(
                f'runner metadata path is not canonical: {path}')
        temporary = path.with_suffix(path.suffix + '.tmp')
        if atomic:
            temporary_relative = _validate_contained_path(
                temporary,
                output_root,
                root_resolved,
                label='runner metadata temporary path',
            )
            if temporary_relative.parts != (temporary.name,):
                raise UnsafeResumeError(
                    f'runner metadata temporary path is not canonical: '
                    f'{temporary}')
            if os.path.lexists(temporary):
                raise UnsafeResumeError(
                    f'runner metadata temporary path already exists: {temporary}')

    def write_manifest() -> None:
        validate_metadata_target(manifest_path, atomic=True)
        _atomic_json(manifest_path, batch_manifest)
        metadata_identities[manifest_path.name] = _ordinary_identity(
            manifest_path,
            directory=False,
            label='runner manifest',
        )

    def write_index() -> None:
        index_path = output_root / 'run_index.csv'
        validate_metadata_target(index_path, atomic=False)
        _write_index(output_root, results)
        metadata_identities[index_path.name] = _ordinary_identity(
            index_path,
            directory=False,
            label='runner index',
        )

    def validate_cell(
        cell: _FrozenCell,
        *,
        require_run_absent: bool,
    ) -> tuple[Path, Path]:
        validate_root()
        return _cell_paths(
            output_root,
            root_resolved,
            cell,
            require_run_absent=require_run_absent,
        )

    def write_cell_text(
        cell: _FrozenCell,
        filename: str,
        content: str,
    ) -> None:
        _condition_path, run_dir = validate_cell(
            cell, require_run_absent=False)
        target = run_dir / filename
        resolved_run_dir = run_dir.resolve(strict=True)
        relative = _validate_contained_path(
            target,
            run_dir,
            resolved_run_dir,
            label='runner diagnostic path',
        )
        if relative.parts != (filename,):
            raise UnsafeResumeError(
                f'runner diagnostic path is not canonical: {target}')
        if os.path.lexists(target):
            raise UnsafeResumeError(
                f'runner diagnostic path already exists: {target}')
        target.write_text(content, encoding='utf-8')

    if batch_manifest is not None:
        write_manifest()

    def execute_cell(cell: _FrozenCell) -> dict:
        condition_path, run_dir = validate_cell(
            cell, require_run_absent=True)
        if cell.condition not in condition_identities:
            condition_path.mkdir()
            condition_identities[cell.condition] = _ordinary_identity(
                condition_path,
                directory=True,
                label='runner-created condition path',
            )
            condition_path, run_dir = validate_cell(
                cell, require_run_absent=True)
        run_dir.mkdir()
        cell_identity = (cell.condition, cell.seed)
        cell_identities[cell_identity] = _ordinary_identity(
            run_dir,
            directory=True,
            label='runner-created cell path',
        )
        validate_cell(cell, require_run_absent=False)

        # Phase 1 of V2_RUNNER_INTEGRATION_PLAN.md: record the attempt while
        # the layout is unchanged. `directory` is '.' because artifacts still
        # live directly under the cell; phase 2 moves them into attempt_NNNN
        # and that becomes the only field that changes.
        cell_id = f'{cell.condition}/seed_{cell.seed}'
        ledger = AttemptLedger(cell_id=cell_id)
        ledger_path = run_dir / 'attempts.jsonl'
        attempt_id = ledger.next_attempt_id()
        ledger.append_to(ledger_path, [ledger.start_attempt(
            attempt_id, directory='.',
            at=datetime.now(timezone.utc).isoformat())])

        command = _simulation_command(
            cell.seed,
            cell.condition,
            cell.ticks,
            cell.extra_args,
            plan_identity=plan.get('experiment_id') if plan else None,
            plan_sha256=plan_hash,
        )
        env = os.environ.copy()
        source_path = str(PROJECT_ROOT / 'src')
        env['PYTHONPATH'] = source_path + os.pathsep + env.get('PYTHONPATH', '')
        env['PYTHONHASHSEED'] = '0'

        print(
            f'  [{cell.condition}] seed={cell.seed}  ...',
            end='',
            flush=True,
        )
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        timed_out = False
        process = None
        try:
            validate_cell(cell, require_run_absent=False)
            process = subprocess.run(
                command, cwd=run_dir, env=env, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                timeout=cell.timeout_seconds,
            )
            returncode = process.returncode
            if process.stderr:
                write_cell_text(cell, 'runner_stderr.txt', process.stderr)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = -1
            write_cell_text(cell, 'runner_stderr.txt', f'timeout: {exc}\n')
        except (OSError, subprocess.SubprocessError) as exc:
            returncode = None
            write_cell_text(
                cell,
                'runner_stderr.txt',
                f'runner exception: {exc}\n',
            )

        elapsed = round(time.perf_counter() - started, 3)
        validate_cell(cell, require_run_absent=False)
        report = inspect_run_outputs(
            run_dir,
            cell.condition,
            cell.seed,
            expected_ticks=cell.ticks,
            mode='strict',
        )
        valid = report.valid
        errors = report.errors
        ok = returncode == 0 and valid
        result = classify_result(returncode, valid, timed_out=timed_out)
        if not ok and process is not None and process.stdout:
            write_cell_text(cell, 'runner_stdout.txt', process.stdout)
        state_hash = None
        validate_cell(cell, require_run_absent=False)
        run_manifest_path = expected_outputs(
            run_dir, cell.condition, cell.seed)['run_manifest']
        if run_manifest_path.is_file():
            try:
                state_hash = json.loads(
                    run_manifest_path.read_text(encoding='utf-8')).get(
                        'state_hash')
            except json.JSONDecodeError:
                pass
        events = [ledger.finish_attempt(
            attempt_id, result=result,
            at=datetime.now(timezone.utc).isoformat(),
            state_hash=state_hash)]
        if ok:
            # Selection is gated on deep validation, not on exit status:
            # "process exit success alone is never evidence completion".
            events.extend(ledger.select_attempt(
                attempt_id, at=datetime.now(timezone.utc).isoformat()))
        ledger.append_to(ledger_path, events)

        print(f"  {'OK' if ok else result.upper()}  ({elapsed:.1f}s)")
        return {
            'seed': cell.seed, 'condition': cell.condition,
            'status': RESULT_COMPLETED if ok else result,
            'result': result,
            'runner_action': 'executed',
            'ok': ok,
            'elapsed': elapsed, 'returncode': returncode,
            'started_at': started_at,
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'state_hash': state_hash,
            'run_dir': str(run_dir.relative_to(output_root)),
            'command': command, 'errors': errors,
            'v2_ready': report.v2_ready,
        }

    stop_reason: dict | None = None
    for position, cell in enumerate(frozen_cells, start=1):
        if cell.announcement:
            print(cell.announcement)
        result = execute_cell(cell)
        result['dispatch_position'] = position
        results.append(result)
        if batch_manifest is not None and 'schedule' in batch_manifest:
            # Actual order, recorded as it happens. Section 11.2 wants
            # deviations recorded rather than the order silently regenerated,
            # so this is written even when it matches the planned order.
            batch_manifest['schedule']['dispatched'].append({
                'position': position,
                'cell_id': f'{cell.condition}/seed_{cell.seed}',
                'started_at': result.get('started_at'),
                'completed_at': result.get('completed_at'),
            })
        if fail_fast and not result['ok']:
            # Persist the stop before declining to dispatch, so a batch that
            # ends early can never be read as one that ran to completion with
            # fewer cells. Recorded even when there is no batch manifest, so
            # the caller sees it too.
            stop_reason = {
                'stopped': True,
                'position': position,
                'of': len(frozen_cells),
                'condition': cell.condition,
                'seed': cell.seed,
                'result': result.get('result'),
                'errors': result.get('errors'),
                'not_dispatched': len(frozen_cells) - position,
            }
        if batch_manifest is not None:
            batch_manifest['results'] = results
            if stop_reason is not None:
                batch_manifest['stop_reason'] = stop_reason
            write_manifest()
            write_index()
        if stop_reason is not None:
            break

    if batch_manifest is not None:
        batch_manifest['completed_at'] = datetime.now(timezone.utc).isoformat()
        # A truncated batch is never complete, even if every cell it managed to
        # dispatch succeeded, because the cells it skipped were never observed.
        #
        # The `stop_reason is None` term is deliberately redundant today: the
        # only stop cause is a non-ok cell, so `all(...)` is already False
        # whenever a stop happened, and no test can isolate this term. It is
        # kept because the plan anticipates stop causes that are not cell
        # failures -- a breached quota must "stop safely ... and never produce a
        # silently truncated `completed` result" -- and under those this term is
        # the only thing standing between a truncated batch and `complete: true`.
        batch_manifest['complete'] = (
            stop_reason is None and all(result['ok'] for result in results))
        batch_manifest['dispatched_cell_count'] = len(results)
        batch_manifest['planned_cell_count'] = len(frozen_cells)
        write_manifest()
    return results, output_root


def run_single(
    seed: int,
    condition: str,
    ticks: int,
    extra_args: list[str],
    output_root: Path,
    *,
    resume: bool = False,
    overwrite: bool = False,
    timeout_seconds: int | None = 86400,
) -> dict:
    """Safely execute one cell only in an absent or truly empty root.

    ``resume`` and ``overwrite`` are accepted for compatibility but never
    authorize adopting, skipping, deleting, or replacing existing output.
    """
    results, _root = _run_cells_in_fresh_root(
        [{
            'seed': seed,
            'condition': condition,
            'ticks': ticks,
            'extra_args': extra_args,
            'timeout_seconds': timeout_seconds,
        }],
        output_root,
        resume=resume,
        overwrite=overwrite,
        direct=True,
    )
    return results[0]


def _write_index(output_root: Path, results: list[dict]) -> None:
    fields = [
        'condition', 'seed', 'status', 'result', 'runner_action', 'ok',
        'elapsed', 'returncode', 'state_hash', 'run_dir',
        'dispatch_position', 'started_at', 'completed_at',
    ]
    with (output_root / 'run_index.csv').open(
            'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)


def _expand_plan_cells(plan: dict) -> list[dict]:
    """Expand a plan into the exact cell list, in dispatch order.

    Extracted so that the nonexecuting expansion command and real execution
    cannot drift: an expansion derived from a second implementation would
    eventually describe cells the runner does not actually dispatch, which is
    the one thing a preflight listing must never do.
    """
    default_ticks = int(plan.get('default_ticks', 5000))
    default_timeout = plan.get('timeout_seconds', 86400)
    if default_timeout is not None:
        default_timeout = int(default_timeout)
        if default_timeout < 1:
            raise ValueError('timeout_seconds must be positive or null')
    cells: list[dict] = []
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
        for index, seed in enumerate(seeds):
            cells.append({
                'seed': seed,
                'condition': name,
                'ticks': ticks,
                'extra_args': extra_args,
                'timeout_seconds': timeout_seconds,
                'announcement': (
                    f'\n── {name}: {len(seeds)} seeds × {ticks} ticks ──'
                    if index == 0 else None
                ),
            })
    return cells


def expand_plan(plan_path: Path, output_root: Path | None = None) -> dict:
    """Describe exactly what a plan would execute, without executing anything.

    Creates no directory, starts no process, and writes no file. The revision
    contract is *reported* rather than enforced: the point of an expansion is to
    inspect a plan before committing to it, and refusing to describe a plan
    because HEAD is currently dirty would defeat that.
    """
    plan, plan_hash = load_plan(plan_path)
    root = output_root or Path('experiment_runs') / plan['experiment_id']
    cells = _expand_plan_cells(plan)

    expanded = []
    for position, cell in enumerate(cells, start=1):
        run_dir = root / cell['condition'] / f"seed_{cell['seed']}"
        expanded.append({
            'dispatch_position': position,
            'cell_id': f"{cell['condition']}/seed_{cell['seed']}",
            'condition': cell['condition'],
            'seed': cell['seed'],
            'ticks': cell['ticks'],
            'extra_args': list(cell['extra_args']),
            'timeout_seconds': cell['timeout_seconds'],
            'output_dir': str(run_dir),
            'command': _simulation_command(
                cell['seed'], cell['condition'], cell['ticks'],
                tuple(cell['extra_args']),
                plan_identity=plan.get('experiment_id'),
                plan_sha256=plan_hash,
            ),
        })

    return {
        'schema_version': RUNNER_SCHEMA_VERSION,
        'experiment_id': plan['experiment_id'],
        'plan_path': str(plan_path.resolve()),
        'plan_sha256': plan_hash,
        'output_root': str(root),
        'cell_count': len(expanded),
        'total_ticks': sum(cell['ticks'] for cell in cells),
        'environment_contract': {
            'expected_environment_fingerprint': plan.get(
                'expected_environment_fingerprint'),
            'require_empty_plugin_inventory': plan.get(
                'require_empty_plugin_inventory'),
            'declared': _declares_environment_contract(plan),
            'environment': _environment_record(),
        },
        'revision_contract': {
            'expected_commit': plan.get('expected_commit'),
            'expected_tag': plan.get('expected_tag'),
            'require_clean_revision': plan.get('require_clean_revision'),
            'declared': _declares_revision_contract(plan),
            'revision': _code_revision(),
        },
        'cells': expanded,
    }


def run_from_plan(
    plan_path: Path,
    output_root: Path | None = None,
    *,
    resume: bool = False,
    overwrite: bool = False,
    fail_fast: bool | None = None,
) -> tuple[list[dict], Path]:
    plan, plan_hash = load_plan(plan_path)
    # Before any output root is touched: a contract violation must not leave a
    # partially created experiment directory behind.
    revision_contract = _preflight_revision_contract(plan)
    environment_contract = _preflight_environment_contract(plan)
    # An explicit argument wins over the plan; otherwise the plan decides, and
    # a plan silent on the matter keeps the historical run-every-cell
    # behaviour. Core Replication V2 cells are expected to set it.
    plan_fail_fast = plan.get('fail_fast')
    if plan_fail_fast is not None and type(plan_fail_fast) is not bool:
        raise ValueError('fail_fast must be true or false')
    if fail_fast is None:
        fail_fast = bool(plan_fail_fast)
    output_root = output_root or Path('experiment_runs') / plan['experiment_id']
    cells = _expand_plan_cells(plan)

    batch_manifest = {
        'schema_version': RUNNER_SCHEMA_VERSION,
        'experiment_id': plan['experiment_id'],
        'plan_schema_version': plan['schema_version'],
        'plan_sha256': plan_hash,
        'plan_path': str(plan_path.resolve()),
        'code': revision_contract['revision'],
        'revision_contract': revision_contract,
        'environment': environment_contract['environment'],
        'environment_contract': environment_contract,
        'resume_contract': _resume_contract_record(
            experiment_id=plan['experiment_id'],
            plan_hash=plan_hash,
            revision=revision_contract['revision'],
            environment=environment_contract['environment'],
            config_fingerprint=_config_fingerprint(cells),
        ),
        'schedule': {
            'schedule_id': _schedule_id(cells),
            'planned_order': [
                f"{cell['condition']}/seed_{cell['seed']}" for cell in cells],
            'dispatched': [],
        },
        'started_at': datetime.now(timezone.utc).isoformat(),
        'completed_at': None,
        'resume_count': 0,
        'results': [],
    }
    return _run_cells_in_fresh_root(
        cells,
        output_root,
        resume=resume,
        overwrite=overwrite,
        direct=False,
        fail_fast=fail_fast,
        plan=plan,
        plan_hash=plan_hash,
        batch_manifest=batch_manifest,
    )


def verify_outputs(
    plan_path: Path,
    output_root: Path,
    *,
    validation_mode: ValidationMode = 'auto',
) -> bool:
    plan, _ = load_plan(plan_path)
    failures = []
    legacy_runs = 0
    schema2_nonready_runs = 0
    for condition in plan['conditions']:
        ticks = int(condition.get('ticks', plan.get('default_ticks', 5000)))
        for seed in parse_seed_range(str(condition.get('seeds', '1-5'))):
            run_dir = output_root / condition['name'] / f'seed_{seed}'
            report = inspect_run_outputs(
                run_dir,
                condition['name'],
                seed,
                expected_ticks=ticks,
                mode=validation_mode,
            )
            if report.classification == 'legacy':
                legacy_runs += 1
                print(
                    f"  ! LEGACY — not V2-ready: {condition['name']} seed={seed}")
            elif report.valid and not report.v2_ready:
                schema2_nonready_runs += 1
                print(
                    f"  ! VALID SCHEMA-2 — not V2-ready: "
                    f"{condition['name']} seed={seed}")
            if not report.valid:
                failures.extend(report.errors)
    for error in failures:
        print(f'  ✗ {error}')
    if not failures:
        if legacy_runs or schema2_nonready_runs:
            print(
                f'  ✓ All expected outputs are valid evidence; '
                f'{legacy_runs} legacy and {schema2_nonready_runs} schema-2 '
                f'run(s) have v2_ready=false.')
        else:
            print('  ✓ All expected outputs are present, valid, and V2-ready.')
    return not failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--plan', type=Path)
    source.add_argument('--seeds', type=str)
    parser.add_argument('--condition', default='baseline')
    parser.add_argument('--ticks', type=int, default=5000)
    parser.add_argument('--extra-args', default='')
    parser.add_argument('--output-dir', type=Path)
    # Neither flag relaxes the fresh-root contract: _preflight_fresh_output_root
    # rejects every nonempty root regardless. They remain accepted so existing
    # invocations keep working, but they do not provide a continuation mode.
    # Nonempty-root resume is gated Core Replication V2 work (AGENTS.md).
    parser.add_argument(
        '--resume', action='store_true',
        help='Accepted for compatibility; does not permit reuse of a nonempty root',
    )
    parser.add_argument(
        '--overwrite', action='store_true',
        help='Accepted for compatibility; does not permit reuse of a nonempty root',
    )
    parser.add_argument('--verify', action='store_true')
    parser.add_argument(
        '--fail-fast', action='store_true',
        help='Stop dispatching after the first cell that does not complete, '
             'recording the stop reason and position',
    )
    parser.add_argument(
        '--expand', action='store_true',
        help='Print the exact cells, order, commands, and paths this plan '
             'would execute, then exit without running anything',
    )
    parser.add_argument(
        '--validation-mode', choices=('strict', 'auto', 'legacy'),
        default='auto',
        help='Validation contract for --verify; default auto preserves explicit legacy reads',
    )
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
    output_root = Path(os.path.abspath(
        args.output_dir or Path('experiment_runs') / plan['experiment_id']))
    if args.expand:
        # Before --verify and before any execution: an expansion must never
        # touch the output root, so it returns ahead of everything that does.
        json.dump(expand_plan(plan_path, output_root), sys.stdout, indent=2)
        sys.stdout.write('\n')
        return 0
    if args.verify:
        return 0 if verify_outputs(
            plan_path, output_root,
            validation_mode=args.validation_mode) else 1
    try:
        results, root = run_from_plan(
            plan_path, output_root, resume=args.resume, overwrite=args.overwrite,
            fail_fast=True if args.fail_fast else None)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    succeeded = sum(result['ok'] for result in results)
    print(f'\nCompleted {succeeded}/{len(results)} runs in {root}')
    return 0 if succeeded == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
