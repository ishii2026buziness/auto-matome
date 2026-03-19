from __future__ import annotations

import json

import pytest

from datetime import date

from common.contracts import FailureCode, JobStatus
from src.pipeline import _should_skip_conversion
from src import pipeline


def test_should_skip_conversion_when_no_new_stories():
    assert _should_skip_conversion(output_exists=False, new_story_count=0) is True


def test_should_skip_conversion_when_existing_output_and_few_new_stories():
    assert _should_skip_conversion(output_exists=True, new_story_count=4) is True


def test_should_not_skip_conversion_for_first_meaningful_run():
    assert _should_skip_conversion(output_exists=False, new_story_count=4) is False


@pytest.mark.asyncio
async def test_run_pipeline_returns_success_when_no_new_stories(monkeypatch, tmp_path):
    async def fake_fetch_all():
        return []

    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pipeline, "dedup_stories", lambda stories, **kwargs: [])
    monkeypatch.setattr(pipeline, "build_site", lambda: None)
    monkeypatch.setattr(pipeline, "deploy_site_if_enabled", lambda: None)

    result = await pipeline.run_pipeline()

    assert result.status == JobStatus.SUCCESS
    assert result.failure_code is None
    assert result.stage("select") is not None
    assert result.stage("select").output_count == 0
    assert result.stage("synthesize").status == "skipped"
    assert result.stage("render").status == "skipped"
    assert result.stage("publish").status == "skipped"
    summary = json.loads((result.artifact_root / "job-result.json").read_text(encoding="utf-8"))
    assert summary["failure_code"] is None


@pytest.mark.asyncio
async def test_run_pipeline_returns_success_when_existing_output_and_few_new_stories(monkeypatch, tmp_path):
    stories = [
        {"_source": "hn", "title": "Story", "url": "https://example.com", "summary": "sum"},
    ]

    async def fake_fetch_all():
        return stories

    build_called = False
    deploy_called = False

    def fake_build_site():
        nonlocal build_called
        build_called = True

    def fake_deploy_site():
        nonlocal deploy_called
        deploy_called = True

    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pipeline, "dedup_stories", lambda selected, **kwargs: selected)
    monkeypatch.setattr(pipeline, "build_site", fake_build_site)
    monkeypatch.setattr(pipeline, "deploy_site_if_enabled", fake_deploy_site)

    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "2026-03-16.md").write_text("existing", encoding="utf-8")

    result = await pipeline.run_pipeline(run_date=date(2026, 3, 16))

    assert result.status == JobStatus.SUCCESS
    assert result.failure_code is None
    assert result.stage("synthesize").status == "skipped"
    assert result.stage("render").status == "skipped"
    assert result.stage("publish").status == "skipped"
    assert build_called is False
    assert deploy_called is False


@pytest.mark.asyncio
async def test_run_pipeline_returns_success_and_writes_artifacts(monkeypatch, tmp_path):
    stories = [
        {"_source": "hn", "title": "Story", "url": "https://example.com", "summary": "sum"},
    ]

    async def fake_fetch_all():
        return stories

    async def fake_convert(*_args, **_kwargs):
        return "# Title\n\nbody"

    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pipeline, "dedup_stories", lambda selected, **kwargs: selected)
    monkeypatch.setattr(pipeline, "convert_to_matome", fake_convert)
    monkeypatch.setattr(pipeline, "has_meaningful_body", lambda markdown: True)
    monkeypatch.setattr(pipeline, "build_site", lambda: None)
    monkeypatch.setattr(pipeline, "deploy_site_if_enabled", lambda: None)

    result = await pipeline.run_pipeline()

    assert result.status == JobStatus.SUCCESS
    assert result.stage("collect") is not None
    assert result.stage("synthesize") is not None
    assert (tmp_path / "output").exists()


@pytest.mark.asyncio
async def test_run_pipeline_honors_explicit_run_date(monkeypatch, tmp_path):
    stories = [
        {"_source": "hn", "title": "Story", "url": "https://example.com", "summary": "sum"},
    ]

    async def fake_fetch_all():
        return stories

    async def fake_convert(*_args, **_kwargs):
        return "# Title\n\nbody"

    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pipeline, "dedup_stories", lambda selected, **kwargs: selected)
    monkeypatch.setattr(pipeline, "convert_to_matome", fake_convert)
    monkeypatch.setattr(pipeline, "has_meaningful_body", lambda markdown: True)
    monkeypatch.setattr(pipeline, "build_site", lambda: None)
    monkeypatch.setattr(pipeline, "deploy_site_if_enabled", lambda: None)

    result = await pipeline.run_pipeline(run_date=date(2026, 3, 5))

    assert result.run_id == "2026-03-05"
    assert result.artifact_root.name == "2026-03-05"
    assert (tmp_path / "output" / "2026-03-05.md").exists()


@pytest.mark.asyncio
async def test_run_pipeline_persists_job_result_on_unexpected_error(monkeypatch, tmp_path):
    stories = [
        {"_source": "hn", "title": "Story", "url": "https://example.com", "summary": "sum"},
    ]

    async def fake_fetch_all():
        return stories

    async def exploding_convert(*_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pipeline, "dedup_stories", lambda selected, **kwargs: selected)
    monkeypatch.setattr(pipeline, "convert_to_matome", exploding_convert)
    monkeypatch.setattr(pipeline, "build_site", lambda: None)
    monkeypatch.setattr(pipeline, "deploy_site_if_enabled", lambda: None)

    result = await pipeline.run_pipeline()

    assert result.status == JobStatus.FAILED
    assert result.failure_code == FailureCode.UNEXPECTED_ERROR
    assert result.stage("synthesize") is not None
    assert (result.artifact_root / "job-result.json").exists()
    assert (result.artifact_root / "job-metrics.prom").exists()
