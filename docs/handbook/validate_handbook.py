#!/usr/bin/env python3
"""Bounded integrity checks for Living Technical Handbook v0.1."""

from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import unquote


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HANDBOOK_ROOT = Path(__file__).resolve().parent
DOCUMENTED_COMMIT = "2855bf15a77dffc599f6a0f4ac08721f79a379d4"

REQUIRED_PAGES = {
    "README.md",
    "HANDBOOK_STATUS.md",
    "OWNER_CLARIFICATIONS.md",
    "getting-started/overview.md",
    "getting-started/operations.md",
    "architecture/architecture-overview.md",
    "architecture/repository-map.md",
    "architecture/tick-lifecycle.md",
    "architecture/system-dependency-map.md",
    "architecture/state-ownership-map.md",
    "architecture/data-flow.md",
    "architecture/causal-chains.md",
    "architecture/determinism-and-rng.md",
    "systems/world-and-resources.md",
    "systems/agents-and-population.md",
    "systems/beliefs-and-formal-factions.md",
    "systems/aid-trade-and-relationships.md",
    "systems/informal-coalitions.md",
    "systems/endogenous-language.md",
    "systems/coalition-dialects.md",
    "systems/language-contact.md",
    "systems/intergenerational-language.md",
    "systems/lexical-evolution.md",
    "systems/compositional-protolanguage.md",
    "systems/conflict-technology-diplomacy-religion.md",
    "systems/events-observers-and-plugins.md",
    "experiments/runner-and-configurations.md",
    "experiments/run-lifecycle-and-validation.md",
    "experiments/research-readiness.md",
    "data/output-directory-layout.md",
    "data/artifact-catalog.md",
    "data/identifying-valid-runs.md",
    "data/stale-and-superseded-data.md",
    "reference/command-reference.md",
    "reference/configuration-reference.md",
    "reference/events-and-metrics.md",
    "reference/test-reference.md",
    "reference/glossary.md",
    "troubleshooting/README.md",
    "diagrams/full-system-map.md",
    "diagrams/tick-flow.md",
    "diagrams/social-and-language-causal-chains.md",
    "diagrams/experiment-and-artifact-flow.md",
}

# Each milestone maps to the configuration gate whose presence in source
# proves the mechanism exists, or to None when the milestone contracts
# existing behaviour instead of adding a mechanism. This is what lets the
# handbook be checked against the code rather than only against itself: a
# page calling a milestone planned while its gate exists is a false claim,
# however many other pages agree with it.
MILESTONE_GATES: dict[str, str | None] = {
    "feature/endogenous-language-v1": "language_evolution_enabled",
    "feature/coalition-dialects-v1": "coalition_dialect_influence_enabled",
    "feature/language-contact-v1": "language_contact_enabled",
    "feature/intergenerational-language-v1": (
        "intergenerational_language_enabled"),
    "feature/lexical-evolution-v1": "lexical_evolution_enabled",
    "feature/compositional-protolanguage-v1": (
        "compositional_protolanguage_enabled"),
    "feature/grammar-evolution-v1": "grammar_evolution_enabled",
    "feature/language-coevolution-v1": "language_coevolution_enabled",
    "feature/language-research-readiness-v1": None,
}

MILESTONE_SLUG = re.compile(r"feature/[a-z-]+-v1")
PLANNED_CLAIM = re.compile(r"planned,?\s*not\s*implemented", re.IGNORECASE)
IMPLEMENTED_CLAIM = re.compile(r"\bimplemented\b", re.IGNORECASE)

KNOWN_STALE_DATA = (
    "qtable_pop_300_300.json",
    "pop_equilibrium_summary.json",
)

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REPOSITORY_PATH = re.compile(
    r"`((?:src|tests|docs|benchmarks|plugins)/"
    r"[A-Za-z0-9_.\-/]+(?:\.py|\.md|\.json|\.toml))"
)
ROOT_FILE = re.compile(
    r"`((?:run_experiments\.py|pyproject\.toml|AGENTS\.md|"
    r"CORE_REPLICATION_V2_PLAN\.md))(?:::[^`]*)?`"
)


def _markdown_files() -> list[Path]:
    return sorted(HANDBOOK_ROOT.rglob("*.md"))


def _relative(path: Path) -> str:
    return path.relative_to(HANDBOOK_ROOT).as_posix()


def _check_required_pages(errors: list[str]) -> None:
    actual = {_relative(path) for path in _markdown_files()}
    for missing in sorted(REQUIRED_PAGES - actual):
        errors.append(f"missing required page: {missing}")


def _check_page_content(errors: list[str]) -> None:
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        name = _relative(path)
        if len(text.strip()) < 200:
            errors.append(f"empty or placeholder-sized page: {name}")
        if not text.lstrip().startswith("#"):
            errors.append(f"page lacks a leading heading: {name}")
        if text.count("```mermaid") != len(
            re.findall(r"```mermaid\n(?:flowchart|graph|sequenceDiagram|stateDiagram)", text)
        ):
            errors.append(f"implausible Mermaid opening in: {name}")
        if text.count("```") % 2:
            errors.append(f"unbalanced fenced code block: {name}")
        if ".-x" in text or "-." in text and ".-x" in text:
            errors.append(f"unsupported Mermaid edge form: {name}")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.rstrip() != line:
                errors.append(f"trailing whitespace: {name}:{line_number}")


def _check_links(errors: list[str]) -> None:
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            target = target.split("#", 1)[0]
            if not target or re.match(r"^(?:https?|mailto):", target):
                continue
            resolved = (path.parent / unquote(target)).resolve()
            if not resolved.exists():
                errors.append(
                    f"broken internal link: {_relative(path)} -> {raw_target}"
                )


def _check_referenced_repository_paths(errors: list[str]) -> None:
    for path in _markdown_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            references = set(REPOSITORY_PATH.findall(line))
            references.update(ROOT_FILE.findall(line))
            for reference in sorted(references):
                if (REPOSITORY_ROOT / reference).exists():
                    continue
                if re.search(r"\b(?:there is no|no focused|not present)\b", line, re.I):
                    continue
                errors.append(
                    f"missing referenced repository path: {_relative(path)} -> "
                    f"{reference}"
                )


def _check_index(errors: list[str]) -> None:
    index_path = HANDBOOK_ROOT / "README.md"
    if not index_path.exists():
        return
    targets: set[str] = set()
    text = index_path.read_text(encoding="utf-8")
    for raw_target in MARKDOWN_LINK.findall(text):
        target = raw_target.strip().split("#", 1)[0]
        if not target or re.match(r"^(?:https?|mailto):", target):
            continue
        resolved = (index_path.parent / unquote(target)).resolve()
        if resolved.suffix == ".md" and resolved.exists():
            targets.add(_relative(resolved))
    for page in sorted(REQUIRED_PAGES - {"README.md"} - targets):
        errors.append(f"handbook index does not link required page: {page}")


def _check_status_and_plans(errors: list[str]) -> None:
    for required in ("README.md", "HANDBOOK_STATUS.md"):
        path = HANDBOOK_ROOT / required
        if path.exists() and DOCUMENTED_COMMIT not in path.read_text(encoding="utf-8"):
            errors.append(f"documented commit missing from {required}")

    for path in _markdown_files():
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for stale_name in KNOWN_STALE_DATA:
                if stale_name in line and not re.search(
                    r"stale|historical|deprecated|nonauthoritative|non-authoritative|"
                    r"must not",
                    line,
                    re.IGNORECASE,
                ):
                    errors.append(
                        f"stale data lacks warning on same line: {_relative(path)}:"
                        f"{line_number}: {stale_name}"
                    )


def _implemented_gates() -> set[str]:
    """Return the configuration gates that actually exist in source."""
    sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
    try:
        from thalren_vale.config import SimulationConfig
    finally:
        sys.path.pop(0)
    return {
        name for name in SimulationConfig.__dataclass_fields__
        if name.endswith("_enabled")
    }


def _check_milestone_status_claims(errors: list[str]) -> None:
    """Check documented milestone status against source and for self-consistency.

    Two independent failures are caught. A page may contradict another page,
    which is what happens when a milestone lands and only some pages are
    swept. Or every page may agree on a status that source disproves, which a
    consistency check alone cannot see.
    """
    gates = _implemented_gates()
    for milestone, gate in MILESTONE_GATES.items():
        if gate is not None and gate not in gates:
            errors.append(
                f"milestone gate is absent from SimulationConfig: "
                f"{milestone} -> {gate}"
            )

    claims: dict[str, list[tuple[str, str]]] = {}
    for path in _markdown_files():
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for milestone in set(MILESTONE_SLUG.findall(line)):
                if milestone not in MILESTONE_GATES:
                    errors.append(
                        f"undeclared milestone: {_relative(path)}:"
                        f"{line_number}: {milestone}"
                    )
                    continue
                if PLANNED_CLAIM.search(line):
                    kind = "planned"
                elif IMPLEMENTED_CLAIM.search(line):
                    kind = "implemented"
                else:
                    continue
                claims.setdefault(milestone, []).append(
                    (kind, f"{_relative(path)}:{line_number}")
                )

    for milestone, entries in sorted(claims.items()):
        kinds = {kind for kind, _ in entries}
        if len(kinds) > 1:
            locations = ", ".join(
                f"{kind} at {where}" for kind, where in entries)
            errors.append(
                f"contradictory milestone status: {milestone}: {locations}"
            )
        gate = MILESTONE_GATES[milestone]
        implemented = gate is None or gate in gates
        if implemented and "planned" in kinds:
            planned = ", ".join(
                where for kind, where in entries if kind == "planned")
            errors.append(
                f"milestone is implemented in source but documented as "
                f"planned: {milestone}: {planned}"
            )


def _check_commands_and_generated_data(errors: list[str]) -> None:
    generated_suffixes = {".csv", ".json", ".jsonl", ".zst", ".log", ".png"}
    for path in sorted(HANDBOOK_ROOT.rglob("*")):
        if path.is_file() and path.suffix.lower() in generated_suffixes:
            errors.append(f"generated run/data artifact under handbook: {_relative(path)}")

    command_path = re.compile(
        r"(?:python|streamlit run)\s+((?:src|docs|tests)/[^\s\\]+\.py|"
        r"run_experiments\.py)"
    )
    for path in _markdown_files():
        for command_reference in command_path.findall(
            path.read_text(encoding="utf-8")
        ):
            if not (REPOSITORY_ROOT / command_reference).exists():
                errors.append(
                    f"command references missing entry point: {_relative(path)} -> "
                    f"{command_reference}"
                )


def main() -> int:
    errors: list[str] = []
    _check_required_pages(errors)
    _check_page_content(errors)
    _check_links(errors)
    _check_referenced_repository_paths(errors)
    _check_index(errors)
    _check_status_and_plans(errors)
    _check_milestone_status_claims(errors)
    _check_commands_and_generated_data(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Handbook validation failed with {len(errors)} issue(s).")
        return 1
    print(
        f"Handbook validation passed: {len(_markdown_files())} Markdown pages, "
        "all required links and repository references resolved."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
