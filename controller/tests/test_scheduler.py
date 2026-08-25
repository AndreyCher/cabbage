from types import SimpleNamespace

from app.scheduler import eligible_runs


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
