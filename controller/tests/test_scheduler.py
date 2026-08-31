from types import SimpleNamespace

from datetime import datetime, timedelta, timezone

from app.scheduler import elapsed_seconds, eligible_runs


def run(identity: str):
    return SimpleNamespace(identity=identity)


def test_eligible_runs_serialize_each_identity_and_fill_global_slots():
    queued = [run("busy"), run("busy"), run("alpha"), run("alpha"), run("beta")]

    selected = eligible_runs(queued, {"busy"}, free_slots=2)

    assert [item.identity for item in selected] == ["alpha", "beta"]


def test_eligible_runs_keep_global_order_for_distinct_identities():
    queued = [run("high"), run("medium"), run("low")]

    selected = eligible_runs(queued, set(), free_slots=2)

    assert [item.identity for item in selected] == ["high", "medium"]


def test_elapsed_seconds_supports_aware_and_legacy_naive_datetimes():
    now = datetime.now(timezone.utc)
    assert 9.9 <= elapsed_seconds(now - timedelta(seconds=10), now) <= 10.1
    naive = (now - timedelta(seconds=5)).replace(tzinfo=None)
    assert 4.9 <= elapsed_seconds(naive, now) <= 5.1
