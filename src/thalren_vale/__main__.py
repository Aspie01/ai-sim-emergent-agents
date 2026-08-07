# (c) 2026 (KriaetvAspie / AspieTheBard)
# Licensed under the Polyform Noncommercial License 1.0.0
"""Entry point for: python -m thalren_vale, and for the thalren-vale script."""

import os
import sys
from collections.abc import Sequence


def _seed_argument_present(argv: Sequence[str]) -> bool:
    """Report whether argv carries a --seed spelling that argparse accepts.

    ``sim.run()`` builds its parser with ``allow_abbrev=False``, so exactly two
    spellings reach it: the two-token ``--seed 42`` and the joined ``--seed=42``.
    A plain ``"--seed" in argv`` membership test only matches the first, so the
    joined form skipped the re-exec below.  Match ``--seed=`` by prefix rather
    than by ``startswith("--seed")`` so unrelated options that merely share the
    prefix (for example the runner's ``--seeds``) still do not trigger a re-exec.
    """
    return any(
        argument == "--seed" or argument.startswith("--seed=")
        for argument in argv
    )


def _ensure_hash_seed() -> None:
    """Re-exec with PYTHONHASHSEED=0 when a --seed argument is present.

    Python randomises the hash seed between process invocations by default,
    making dict/set iteration order non-deterministic.  Setting PYTHONHASHSEED=0
    before the interpreter starts guarantees identical ordering across runs with
    the same --seed value, which is required for reproducible experiments.

    Uses subprocess.run() rather than os.execve() so that stdout/stderr are
    correctly inherited on Windows (os.execve does not forward I/O handles
    through PowerShell pipelines on Windows).
    """
    if not _seed_argument_present(sys.argv[1:]):
        return
    if os.environ.get("PYTHONHASHSEED") == "0":
        return  # already in a deterministic-hash process
    import subprocess
    env = dict(os.environ, PYTHONHASHSEED="0")
    pkg = __package__ or "thalren_vale"
    result = subprocess.run(
        [sys.executable, "-m", pkg] + sys.argv[1:],
        env=env,
        # Inherit stdin/stdout/stderr from the parent so all output is visible.
    )
    sys.exit(result.returncode)


_ensure_hash_seed()

from .sim import run  # noqa: E402 – import must come after re-exec guard


def main() -> None:
    """Console-script entry point for ``thalren-vale``.

    The pyproject console script points here rather than at ``sim:run`` so the
    installed command goes through the same guard as ``python -m thalren_vale``.
    Importing this module has already run ``_ensure_hash_seed()`` above, so by
    the time this function is called the process either has PYTHONHASHSEED=0 or
    no explicit --seed was requested.
    """
    run()


if __name__ == "__main__":
    main()
