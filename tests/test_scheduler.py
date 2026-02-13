from openclaw_automation.scheduler import RunQueue, RunRequest


def test_queue_defaults_to_single_concurrency() -> None:
    q = RunQueue(max_concurrent_runs=1)
    q.enqueue(RunRequest(run_id="r1", script_id="a", required_locks=["site:united.com"]))
    q.enqueue(RunRequest(run_id="r2", script_id="b", required_locks=["site:united.com"]))

    started = q.tick()
    assert [r.run_id for r in started] == ["r1"]
    assert q.snapshot()["queued"] == ["r2"]

    q.complete("r1")
    started2 = q.tick()
    assert [r.run_id for r in started2] == ["r2"]


def test_parallel_with_non_conflicting_locks() -> None:
    q = RunQueue(max_concurrent_runs=2)
    q.enqueue(RunRequest(run_id="r1", script_id="a", required_locks=["site:united.com"]))
    q.enqueue(RunRequest(run_id="r2", script_id="b", required_locks=["site:singaporeair.com"]))

    started = q.tick()
    assert {r.run_id for r in started} == {"r1", "r2"}


def test_lock_conflict_blocks_second_run() -> None:
    q = RunQueue(max_concurrent_runs=2)
    q.enqueue(RunRequest(run_id="r1", script_id="a", required_locks=["browser_profile:default"]))
    q.enqueue(RunRequest(run_id="r2", script_id="b", required_locks=["browser_profile:default"]))

    started = q.tick()
    assert [r.run_id for r in started] == ["r1"]
    assert q.snapshot()["queued"] == ["r2"]

