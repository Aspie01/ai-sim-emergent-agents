"""Contract test for the standalone benchmark harness."""

import csv
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_writes_json_and_csv(tmp_path):
    output = tmp_path / "benchmark.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "benchmarks" / "benchmark_simulation.py"),
            "--populations", "10",
            "--modes", "serial",
            "--ticks", "1",
            "--warmup", "0",
            "--output", str(output),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["benchmark"] == "inhabitants_layer_population_scaling"
    assert payload["results"][0]["population"] == 10
    assert payload["results"][0]["mode"] == "serial"
    with output.with_suffix(".csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["population"] == "10"
