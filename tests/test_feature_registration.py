"""Every control family must be registered in every layer that gates it.

Three milestones in a row shipped a mechanism that reached the layer its
author was thinking about and silently missed the next one out. Composition
reached ``communicate`` but not one barter branch. Grammar reached the hash
but not the disabled-state guard. The three newest families reached artifact
validation but not the V2-readiness veto. The full suite stayed green each
time, because every test exercised behaviour rather than coverage.

These tests check coverage instead. A new control family must be declared in
``FAMILY_REGISTRATION`` and must reach every layer named there, or the suite
fails with the specific layer identified.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from thalren_vale.config import SimulationConfig


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


# family stem -> the hook each gating layer requires. Names are declared
# rather than derived because the layers do not share a naming convention:
# the social family's guard is `_require_empty_disabled_relationships`, while
# grammar's is `_require_pristine_disabled_grammar_state`.
FAMILY_REGISTRATION = {
    "social": {
        "pristine_guard": "_require_empty_disabled_relationships",
        "artifact_validator": "_validate_social_configuration",
        "runner_rejector": "_reject_uncontracted_social_args",
    },
    "language": {
        "pristine_guard": "_require_pristine_disabled_language_state",
        "artifact_validator": "_validate_language_configuration",
        "runner_rejector": "_reject_uncontracted_language_args",
    },
    "coalition": {
        "pristine_guard": "_require_empty_disabled_coalition_state",
        "artifact_validator": "_validate_coalition_configuration",
        "runner_rejector": "_reject_uncontracted_coalition_args",
    },
    "dialect": {
        "pristine_guard": "_require_pristine_disabled_dialect_state",
        "artifact_validator": "_validate_dialect_configuration",
        "runner_rejector": "_reject_uncontracted_dialect_args",
    },
    "language_contact": {
        "pristine_guard": "_require_pristine_disabled_contact_state",
        "artifact_validator": "_validate_language_contact_configuration",
        "runner_rejector": "_reject_uncontracted_language_contact_args",
    },
    "intergenerational_language": {
        "pristine_guard": "_require_pristine_disabled_intergenerational_state",
        "artifact_validator": (
            "_validate_intergenerational_language_configuration"),
        "runner_rejector": (
            "_reject_uncontracted_intergenerational_language_args"),
    },
    "lexical_evolution": {
        "pristine_guard": "_require_pristine_disabled_lexical_state",
        "artifact_validator": "_validate_lexical_evolution_configuration",
        "runner_rejector": "_reject_uncontracted_lexical_evolution_args",
    },
    "compositional_protolanguage": {
        "pristine_guard": "_require_pristine_disabled_compositional_state",
        "artifact_validator": (
            "_validate_compositional_protolanguage_configuration"),
        "runner_rejector": (
            "_reject_uncontracted_compositional_protolanguage_args"),
    },
    "grammar_evolution": {
        "pristine_guard": "_require_pristine_disabled_grammar_state",
        "artifact_validator": "_validate_grammar_evolution_configuration",
        "runner_rejector": "_reject_uncontracted_grammar_evolution_args",
    },
    "language_coevolution": {
        "pristine_guard": "_require_pristine_disabled_coevolution_state",
        "artifact_validator": "_validate_language_coevolution_configuration",
        "runner_rejector": "_reject_uncontracted_language_coevolution_args",
    },
    "faction_relationship_trust": {
        # Selecting the social model owns no runtime state; it only chooses
        # which existing store the faction layer reads.
        "pristine_guard": None,
        "artifact_validator": (
            "_validate_faction_relationship_trust_configuration"),
        "runner_rejector": (
            "_reject_uncontracted_faction_relationship_trust_args"),
    },
    "production_trial": {
        # Owns no runtime state: each trial occasion is derived per utterance
        # from a seed domain, so there is nothing to hold pristine.
        # `test_stateless_families_own_no_runtime_state` proves the claim.
        "pristine_guard": None,
        "artifact_validator": "_validate_production_trial_configuration",
        "runner_rejector": "_reject_uncontracted_production_trial_args",
    },
    "coalition_intelligibility": {
        # Owns no runtime state: it only reads the intelligibility that
        # coevolution writes, so there is nothing to hold pristine. A vacuous
        # guard would weaken the check, so the declaration is None and
        # `test_stateless_families_own_no_runtime_state` proves the claim
        # rather than taking it on trust.
        "pristine_guard": None,
        "artifact_validator": (
            "_validate_coalition_intelligibility_configuration"),
        "runner_rejector": (
            "_reject_uncontracted_coalition_intelligibility_args"),
    },
}

REQUIRED_LAYERS = (
    "pristine_guard", "artifact_validator", "runner_rejector")


def _module_tree(relative: str) -> ast.Module:
    # utf-8-sig, not utf-8: several legacy modules legitimately carry a BOM,
    # which `ast.parse` rejects as a non-printable character.
    return ast.parse(
        (PROJECT_ROOT / relative).read_text(encoding="utf-8-sig"))


def _defined_functions(relative: str) -> set[str]:
    return {
        node.name for node in ast.walk(_module_tree(relative))
        if isinstance(node, ast.FunctionDef)
    }


def _calls_within(relative: str, function_name: str) -> set[str]:
    """Return every plain-name call made inside one named function."""
    for node in ast.walk(_module_tree(relative)):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return {
                sub.func.id for sub in ast.walk(node)
                if isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
            }
    raise AssertionError(f"{relative} defines no {function_name}")


def _manifest_families() -> set[str]:
    config = SimulationConfig()
    config.validate()
    return {
        key[: -len("_controls_status")]
        for key in config.manifest_dict()
        if key.endswith("_controls_status")
    }


# ── Declaration completeness ────────────────────────────────────────────────

def test_every_manifest_control_family_is_declared():
    """A family that ships controls must declare where it is gated."""
    undeclared = sorted(_manifest_families() - set(FAMILY_REGISTRATION))
    assert not undeclared, (
        f"control families with no registration entry: {undeclared}")


def test_no_registration_entry_is_stale():
    """A removed family must not keep a registration entry."""
    stale = sorted(set(FAMILY_REGISTRATION) - _manifest_families())
    assert not stale, f"registration entries with no control family: {stale}"


def test_every_family_declares_every_layer():
    incomplete = {
        family: sorted(set(REQUIRED_LAYERS) - set(hooks))
        for family, hooks in FAMILY_REGISTRATION.items()
        if set(REQUIRED_LAYERS) - set(hooks)
    }
    assert not incomplete, f"families missing a layer: {incomplete}"


# ── Each declared hook exists ───────────────────────────────────────────────

def test_stateless_families_own_no_runtime_state():
    """A family declaring no pristine guard must genuinely own no state.

    Declaring `pristine_guard: None` is how a family opts out of the
    disabled-state check. That opt-out has to be falsifiable, or it becomes a
    way to silently skip the guard: any family that later grows runtime state
    on `SimulationState` must declare a guard for it.
    """
    from thalren_vale.state import SimulationState

    owned = set(SimulationState.__dataclass_fields__)
    offenders = sorted(
        family for family, hooks in FAMILY_REGISTRATION.items()
        if hooks["pristine_guard"] is None and family in owned
    )
    assert not offenders, (
        f"families declaring no state but owning runtime state: {offenders}")


@pytest.mark.parametrize("family", sorted(FAMILY_REGISTRATION))
def test_declared_hooks_exist(family):
    hooks = FAMILY_REGISTRATION[family]
    missing = []
    if hooks["pristine_guard"] is not None and hooks[
        "pristine_guard"
    ] not in _defined_functions("src/thalren_vale/reproducibility.py"):
        missing.append(hooks["pristine_guard"])
    if hooks["artifact_validator"] not in _defined_functions(
        "src/thalren_vale/artifact_validation.py"
    ):
        missing.append(hooks["artifact_validator"])
    if hooks["runner_rejector"] not in _defined_functions(
        "run_experiments.py"
    ):
        missing.append(hooks["runner_rejector"])
    assert not missing, f"{family} declares absent hooks: {missing}"


# ── Each hook is actually reached ───────────────────────────────────────────

@pytest.mark.parametrize("family", sorted(FAMILY_REGISTRATION))
def test_pristine_guard_is_reached_by_the_hash(family):
    """A guard that exists but is never called protects nothing."""
    guard = FAMILY_REGISTRATION[family]["pristine_guard"]
    if guard is None:
        pytest.skip(f"{family} owns no runtime state")
    called = _calls_within(
        "src/thalren_vale/reproducibility.py", "canonical_state_hash")
    assert guard in called, (
        f"{family}: canonical_state_hash never calls {guard}")


@pytest.mark.parametrize("family", sorted(FAMILY_REGISTRATION))
def test_artifact_validator_is_reached(family):
    validator = FAMILY_REGISTRATION[family]["artifact_validator"]
    called = _calls_within(
        "src/thalren_vale/artifact_validation.py", "_validate_strict")
    assert validator in called, (
        f"{family}: _validate_strict never calls {validator}")


@pytest.mark.parametrize("family", sorted(FAMILY_REGISTRATION))
@pytest.mark.parametrize("site", ["_freeze_cell", "load_plan"])
def test_runner_rejector_is_reached_at_both_containment_sites(family, site):
    """Containment must hold at both sites, before any output-root work."""
    rejector = FAMILY_REGISTRATION[family]["runner_rejector"]
    called = _calls_within("run_experiments.py", site)
    assert rejector in called, f"{family}: {site} never calls {rejector}"


# ── Readiness gate coverage ─────────────────────────────────────────────────

def test_every_family_reaches_the_readiness_gate():
    """Restates the V2-readiness coverage check beside the other layers.

    This is the specific omission that let nondefault compositional, grammar,
    and coevolution controls classify as v2_ready.
    """
    import inspect

    from thalren_vale.artifact_validation import _readiness_issues

    source = inspect.getsource(_readiness_issues)
    uncovered = sorted(
        family for family in FAMILY_REGISTRATION
        if f'"{family}_controls_status"' not in source
    )
    assert not uncovered, (
        f"control families outside the readiness gate: {uncovered}")


# ── Owner threading through the economy layer ───────────────────────────────

OWNER_FAMILIES = (
    "language", "dialect", "contact", "lexical", "compositional", "grammar",
    "coevolution",
)


def _owner_family(parameter_name: str) -> str | None:
    for family in OWNER_FAMILIES:
        if parameter_name in (f"{family}_config", f"{family}_runtime"):
            return family
    return None


def _economy_owner_gaps() -> list[str]:
    """Return call sites that drop an owner family their callee accepts.

    `_individual_barter` forks on partner bias. The compositional owners were
    forwarded down one branch and not the other, so enabling composition with
    partner bias raised `missing_compositional_protolanguage_inputs` and
    killed the run. Every compositional test drove `communicate` directly, so
    nothing caught it.
    """
    tree = _module_tree("src/thalren_vale/economy.py")

    accepts: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        names = {a.arg for a in node.args.kwonlyargs}
        names |= {a.arg for a in node.args.args}
        families = {_owner_family(name) for name in names} - {None}
        if families:
            accepts[node.name] = families

    gaps = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else None
        if name not in accepts:
            continue
        passed = {
            _owner_family(keyword.arg) for keyword in node.keywords
            if keyword.arg
        } - {None}
        if not passed:
            # A feature-disabled fast path passes no owners at all.
            continue
        missing = accepts[name] - passed
        if missing:
            gaps.append(
                f"line {node.lineno}: {name}() omits {sorted(missing)}")
    return gaps


def test_economy_call_sites_forward_every_owner_their_callee_accepts():
    gaps = _economy_owner_gaps()
    assert not gaps, "economy owner threading gaps:\n  " + "\n  ".join(gaps)


# ── Owner forwarding through delegation ─────────────────────────────────────

# Feature-owner families. `social_config` is deliberately absent: it is the
# structural gate every barter path carries, so its presence would not signal
# that a call is forwarding language owners.
OWNER_FAMILIES = (
    "language", "dialect", "contact", "lexical", "compositional",
    "grammar", "coevolution", "trial", "intergenerational",
)

OWNER_FORWARDING_MODULES = (
    "src/thalren_vale/language.py",
    "src/thalren_vale/economy.py",
    "src/thalren_vale/sim.py",
    "src/thalren_vale/coalitions.py",
    "src/thalren_vale/social.py",
    "src/thalren_vale/reproducibility.py",
)

# (caller, callee, parameter) triples that legitimately do not forward, each
# with the reason it is safe. Anything not listed here is reported.
KNOWN_NON_FORWARDING = {
    # `communicate` raises if contact inputs are present on this path, so
    # `contact_config` is provably None and forwarding it would be noise.
    ("communicate", "validate_agent_language_state", "contact_config"),
}


def _owner_parameters(node: ast.FunctionDef) -> set[str]:
    names = {a.arg for a in node.args.args}
    names |= {a.arg for a in node.args.kwonlyargs}
    return {
        name for name in names
        if name.endswith(("_config", "_runtime"))
        and any(name.startswith(family) for family in OWNER_FAMILIES)
    }


def _owner_forwarding_gaps() -> list[str]:
    """Return calls that forward some feature owners but drop others.

    A function that accepts an owner and hands work to another function
    accepting the same owner must pass it, or the feature silently does
    nothing on that path. This has happened five times: composition missing
    the partner-bias barter branch, grammar missing the disabled-state guard,
    three control families missing the readiness veto, maintenance dropping
    the coalition threshold, and `communicate` dropping an owner when it
    delegates to the contact variant.

    Calls forwarding *none* of the shared owners are skipped: those are the
    deliberate feature-disabled fast paths. Calls using `**` unpacking are
    skipped because their keywords are not statically known.
    """
    gaps: list[str] = []
    for relative in OWNER_FORWARDING_MODULES:
        tree = _module_tree(relative)
        accepts = {
            node.name: _owner_parameters(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and _owner_parameters(node)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            mine = _owner_parameters(node)
            if not mine:
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                if not isinstance(call.func, ast.Name):
                    continue
                callee = call.func.id
                if callee not in accepts or callee == node.name:
                    continue
                if any(keyword.arg is None for keyword in call.keywords):
                    continue
                passed = {k.arg for k in call.keywords if k.arg}
                shared = mine & accepts[callee]
                forwarded = shared & passed
                missing = {
                    name for name in shared - passed
                    if (node.name, callee, name) not in KNOWN_NON_FORWARDING
                }
                if forwarded and missing:
                    gaps.append(
                        f"{relative}:{call.lineno} {node.name}() -> "
                        f"{callee}() drops {sorted(missing)}")
    return gaps


def test_delegated_calls_forward_every_feature_owner():
    gaps = _owner_forwarding_gaps()
    assert not gaps, "owner forwarding gaps:\n  " + "\n  ".join(gaps)
