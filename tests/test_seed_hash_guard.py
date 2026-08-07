"""PYTHONHASHSEED=0 re-exec guard for every accepted --seed spelling.

The guard in ``src/thalren_vale/__main__.py`` is defence in depth: it pins hash
ordering before the interpreter starts so dict/set iteration cannot vary between
processes. These tests pin the *detection* surface, which previously used exact
list membership (``"--seed" not in sys.argv``) and therefore skipped the re-exec
for the ``--seed=42`` spelling argparse also accepts, and for the installed
console script, which bypassed this module entirely.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from thalren_vale import __main__ as entry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


@pytest.mark.parametrize(
    "argv",
    (
        pytest.param(["--seed", "42"], id="two-token"),
        pytest.param(["--seed=42"], id="joined"),
        pytest.param(["--ticks", "3", "--seed=0"], id="joined-after-other"),
        pytest.param(["--seed", "42", "--ticks", "3"], id="two-token-first"),
        pytest.param(["--seed=42", "--condition", "x"], id="joined-first"),
    ),
)
def test_every_accepted_seed_spelling_is_detected(argv):
    assert entry._seed_argument_present(argv) is True


@pytest.mark.parametrize(
    "argv",
    (
        pytest.param([], id="empty"),
        pytest.param(["--ticks", "3"], id="no-seed"),
        pytest.param(["--condition", "baseline"], id="other-option"),
        # The batch runner's --seeds must not be mistaken for a simulator seed.
        pytest.param(["--seeds", "1-5"], id="runner-seeds"),
        pytest.param(["--seeds=1-5"], id="runner-seeds-joined"),
        pytest.param(["--seed-file"], id="prefix-only"),
    ),
)
def test_unrelated_arguments_do_not_trigger_the_guard(argv):
    assert entry._seed_argument_present(argv) is False


def _stub_reexec(monkeypatch, argv, hash_seed):
    """Run the guard with subprocess.run stubbed; return the recorded call."""
    recorded = {}

    class _Result:
        returncode = 0

    def _fake_run(command, env=None, **kwargs):
        recorded["command"] = list(command)
        recorded["env"] = dict(env or {})
        return _Result()

    monkeypatch.setattr(sys, "argv", ["prog", *argv])
    monkeypatch.setattr(subprocess, "run", _fake_run)
    if hash_seed is None:
        monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    else:
        monkeypatch.setenv("PYTHONHASHSEED", hash_seed)
    return recorded


@pytest.mark.parametrize(
    "argv",
    (
        pytest.param(["--seed", "42", "--ticks", "1"], id="two-token"),
        pytest.param(["--seed=42", "--ticks", "1"], id="joined"),
    ),
)
def test_guard_reexecs_with_hash_seed_zero_for_each_spelling(monkeypatch, argv):
    recorded = _stub_reexec(monkeypatch, argv, None)

    with pytest.raises(SystemExit) as exit_info:
        entry._ensure_hash_seed()

    assert exit_info.value.code == 0
    assert recorded["env"]["PYTHONHASHSEED"] == "0"
    # The argument tail must be forwarded byte-for-byte so the child parses the
    # exact spelling the caller used.
    assert recorded["command"] == [sys.executable, "-m", "thalren_vale", *argv]


def test_guard_does_not_reexec_without_a_seed(monkeypatch):
    recorded = _stub_reexec(monkeypatch, ["--ticks", "1"], None)

    entry._ensure_hash_seed()

    assert recorded == {}


@pytest.mark.parametrize(
    "argv",
    (
        pytest.param(["--seed", "42"], id="two-token"),
        pytest.param(["--seed=42"], id="joined"),
    ),
)
def test_guard_does_not_reexec_when_already_deterministic(monkeypatch, argv):
    recorded = _stub_reexec(monkeypatch, argv, "0")

    entry._ensure_hash_seed()

    assert recorded == {}


def test_console_script_entry_point_routes_through_the_guard():
    """The installed thalren-vale script must not bypass __main__.py.

    Pointing it at ``sim:run`` skipped ``_ensure_hash_seed()`` entirely, so an
    explicit --seed got no hash-seed pin on that path.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    scripts = re.search(
        r"^\[project\.scripts\]$(.*?)(?=^\[|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert scripts is not None, "pyproject.toml has no [project.scripts] table"
    target = re.search(
        r"^thalren-vale\s*=\s*[\"'](?P<target>[^\"']+)[\"']",
        scripts.group(1),
        flags=re.MULTILINE,
    )
    assert target is not None, "pyproject.toml declares no thalren-vale script"
    assert target.group("target") == "thalren_vale.__main__:main"
    assert callable(entry.main)


@pytest.mark.parametrize(
    "argv",
    (
        pytest.param(["--seed", "42"], id="two-token"),
        pytest.param(["--seed=42"], id="joined"),
    ),
)
def test_importing_the_module_runs_the_guard_like_a_console_script(
    tmp_path, argv,
):
    """Importing thalren_vale.__main__ is exactly what the console script does.

    The child stubs subprocess.run before the import so no simulation starts; it
    then records the command and PYTHONHASHSEED the guard would have used.
    """
    report = tmp_path / "guard.json"
    child = "\n".join(
        (
            "import json, subprocess, sys",
            f"sys.argv = ['thalren-vale', *{argv!r}]",
            "captured = {}",
            "class _Result:",
            "    returncode = 0",
            "def _fake_run(command, env=None, **kwargs):",
            "    captured['command'] = list(command)",
            "    captured['hash_seed'] = (env or {}).get('PYTHONHASHSEED')",
            "    return _Result()",
            "subprocess.run = _fake_run",
            "try:",
            "    import thalren_vale.__main__",
            "except SystemExit:",
            "    pass",
            f"open({str(report)!r}, 'w', encoding='utf-8')"
            ".write(json.dumps(captured))",
        )
    )
    environment = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT / "src"))
    environment.pop("PYTHONHASHSEED", None)
    completed = subprocess.run(
        [sys.executable, "-c", child],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
    captured = json.loads(report.read_text(encoding="utf-8"))
    assert captured["hash_seed"] == "0"
    assert captured["command"][1:] == ["-m", "thalren_vale", *argv]
