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

PLANNED_LANGUAGE_MILESTONES = (
    "feature/language-coevolution-v1",
    "feature/language-research-readiness-v1",
)

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
            for milestone in PLANNED_LANGUAGE_MILESTONES:
                if milestone in line and "Planned, not implemented" not in line:
                    errors.append(
                        f"planned milestone lacks exact status: {_relative(path)}:"
                        f"{line_number}: {milestone}"
                    )
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
