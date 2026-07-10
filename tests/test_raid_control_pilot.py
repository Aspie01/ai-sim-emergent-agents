"""Unit coverage for the bounded raid-control pilot matrix."""

from run_raid_control_pilot import CONDITIONS, summarize


def test_pilot_conditions_form_complete_combat_raid_matrix():
    matrix = {
        (condition["combat_enabled"], condition["raids_enabled"])
        for condition in CONDITIONS
    }

    assert matrix == {
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    }


def test_pilot_summary_aggregates_only_completed_rows():
    base = {
        "experiment_id": "raid-control-pilot-v1",
        "condition": "combat_off_raids_on",
        "combat_enabled": False,
        "raids_enabled": True,
        "ticks": 100,
        "status": "completed",
        "elapsed_seconds": 10,
        "output_bytes": 1000,
        "structured_event_count": 20,
        "raid_event_count": 15,
        "final_population": 200,
        "peak_population": 210,
        "final_factions": 50,
        "peak_factions": 55,
        "total_wars": 0,
        "total_deaths": 3,
        "peak_ram_mb": 12,
    }
    rows = [
        {**base, "seed": 1},
        {**base, "seed": 2, "elapsed_seconds": 20, "raid_event_count": 5},
        {**base, "seed": 3, "status": "invalid_output"},
    ]

    result = summarize(rows)[0]

    assert result["requested_runs"] == 3
    assert result["completed_runs"] == 2
    assert result["mean_elapsed_seconds"] == 15
    assert result["mean_raid_events"] == 10
    assert result["aggregate_raid_share"] == 0.5
