from __future__ import annotations

import json

from common.contracts import JobResult, JobStatus
from src import cli


def test_cli_run_passes_run_date(monkeypatch, capsys):
    captured: dict[str, object] = {}

    async def fake_run_pipeline(*, run_date=None):
        captured["run_date"] = run_date
        return JobResult(
            status=JobStatus.SUCCESS,
            job_name="auto-matome",
            run_id="2026-03-05",
            stages=[],
            artifact_root=cli.ROOT / "artifacts" / "auto-matome" / "2026-03-05",
            duration_ms=1,
        )

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    exit_code = cli.main(["run", "--run-date", "2026-03-05"])

    assert exit_code == 0
    assert str(captured["run_date"]) == "2026-03-05"
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "2026-03-05"
