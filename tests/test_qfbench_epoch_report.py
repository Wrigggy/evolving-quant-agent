import json
from datetime import datetime, timedelta, timezone


def _audit_record(*, cost="0.01", latency_ms=100):
    return {
        "schema_version": 1,
        "request_identity_sha256": "a" * 64,
        "model": "deepseek/deepseek-v4-flash",
        "started_at": "2026-08-03T00:00:00+00:00",
        "finished_at": "2026-08-03T00:00:01+00:00",
        "latency_ms": latency_ms,
        "request_state": "completed",
        "upstream_status_code": 200,
        "provider_request_id": "request-1",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "provider_cost_usd": cost,
        "failure_class": None,
    }


def _write_attempt(run_dir, repetition, *, reward, timeout=False):
    attempt_id = f"attempt-{repetition}"
    attempt_dir = run_dir / "attempts" / attempt_id
    attempt_dir.mkdir(parents=True)
    task_id = f"task-{repetition}"
    (attempt_dir / "attempt.json").write_text(
        json.dumps(
            {
                "attempt_id": attempt_id,
                "run_id": run_dir.name,
                "benchmark_commit": "0" * 40,
                "task_id": task_id,
                "split": "baseline_primary",
                "checkpoint": f"repetition-{repetition:02d}-primary",
                "worker_digest": "1" * 64,
            }
        )
    )
    (attempt_dir / "completed-score.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "domain": "domain-a",
                "reward": reward,
                "diagnostic_tags": ["timeout"] if timeout else [],
            }
        )
    )
    record = _audit_record(cost=f"0.0{repetition}", latency_ms=100 * repetition)
    record["request_identity_sha256"] = f"{repetition:x}" * 64
    (attempt_dir / "proxy-audit.jsonl").write_text(json.dumps(record) + "\n")
    lifecycle = run_dir / "lifecycles" / run_dir.name / attempt_id
    lifecycle.mkdir(parents=True)
    started = datetime(2026, 8, 3, repetition, tzinfo=timezone.utc)
    (lifecycle / "worker-sandbox-lifecycle-v2.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "role": "worker",
                "run_id": run_dir.name,
                "attempt_id": attempt_id,
                "started_at": started.isoformat(),
                "finished_at": (started + timedelta(minutes=1)).isoformat(),
                "cleaned_up": True,
            }
        )
    )


def test_max_worker_overlap_measures_twelve_and_rejects_eleven():
    from qea.qfbench_epoch_report import max_worker_overlap

    base = datetime(2026, 8, 3, tzinfo=timezone.utc)
    twelve = [
        {
            "role": "worker",
            "started_at": base.isoformat(),
            "finished_at": (base + timedelta(seconds=30 + index)).isoformat(),
        }
        for index in range(12)
    ]
    eleven = [
        {
            "role": "worker",
            "started_at": (base + timedelta(seconds=index * 2)).isoformat(),
            "finished_at": (base + timedelta(seconds=index * 2 + 21)).isoformat(),
        }
        for index in range(12)
    ]

    assert max_worker_overlap(twelve) == 12
    assert max_worker_overlap(eleven) == 11


def test_scheduler_epoch_report_separates_epochs_and_preserves_combined_result(
    tmp_path,
):
    from qea.qfbench_epoch_report import summarize_scheduler_epochs

    run_dir = tmp_path / "formal-run"
    for repetition, reward in enumerate((1.0, 0.0, 0.5, 1.0, 0.5), start=1):
        _write_attempt(
            run_dir,
            repetition,
            reward=reward,
            timeout=repetition == 2,
        )

    report = summarize_scheduler_epochs(run_dir)

    epoch_one = report["epochs"]["scheduler_epoch_1"]
    epoch_two = report["epochs"]["scheduler_epoch_2"]
    assert epoch_one["repetitions"] == [1]
    assert epoch_one["worker_concurrency"] == 4
    assert epoch_one["official_reward_mean"] == 1.0
    assert epoch_two["repetitions"] == [2, 3, 4, 5]
    assert epoch_two["worker_concurrency"] == 12
    assert epoch_two["timeout_count"] == 1
    assert epoch_two["request_count"] == 4
    assert report["combined"]["attempt_count"] == 5
    assert report["combined"]["official_reward_mean"] == 0.6
    assert report["combined"]["provider_cost_usd"] == "0.15"
    assert report["scheduler_epoch_batch_effect_warning"] is True
