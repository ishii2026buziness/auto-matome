"""Auto Matome pipeline — config-driven multi-source fetch."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
COMMON_SRC = ROOT.parent / "common" / "src"

# The installed common package (from packages/common) is shadowed by src/common/
# when src/ is in sys.path. Python auto-adds the script's directory to sys.path[0].
# Fix: remove it, import common from sibling package source, then re-add for local imports.
_src_str = str(SRC)
if _src_str in sys.path:
    sys.path.remove(_src_str)

sys.path.insert(0, str(COMMON_SRC))
from common.artifacts import ArtifactStore
from common.contract_validation import save_validated_job_result
from common.contracts import FailureCode, JobResult, JobStatus, StageResult, StageStatus
from common.job_metrics import export_job_result_metrics_from_env
from common.logger import get_logger

# Now add src/ back for local imports (ingest, curate, etc.)
sys.path.insert(0, _src_str)

from ingest import fetch_all
from curate.dedup import dedup_stories
from curate.quality_gate import AutoMatomeQualityGate
from curate.matome_converter import convert_to_matome, has_meaningful_body

log = get_logger("auto_matome.pipeline")
_gate = AutoMatomeQualityGate()


@dataclass(frozen=True)
class RunContext:
    run_date: date
    root: Path = ROOT

    @property
    def run_id(self) -> str:
        return self.run_date.isoformat()

    @property
    def artifact_store(self) -> ArtifactStore:
        return ArtifactStore(self.root / "artifacts", "auto-matome", run_id=self.run_id)

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def output_path(self) -> Path:
        return self.output_dir / f"{self.run_id}.md"


def _resolve_run_context(run_date: date | None = None, *, root: Path | None = None) -> RunContext:
    return RunContext(run_date=run_date or date.today(), root=root or ROOT)


def _persist_result(result: JobResult, store: ArtifactStore) -> JobResult:
    save_validated_job_result(result, store.summary_path())
    export_job_result_metrics_from_env(result, artifact_root=store.run_dir)
    return result


def _should_skip_conversion(output_exists: bool, new_story_count: int) -> bool:
    return new_story_count == 0 or (output_exists and new_story_count < 5)


def _run_site_command(script_name: str) -> None:
    log.info("running site command", extra={"script": script_name})
    subprocess.run(
        ["npm", "run", script_name],
        cwd=ROOT,
        check=True,
    )


def build_site() -> None:
    if os.environ.get("AUTO_MATOME_SKIP_SITE_BUILD") == "1":
        log.info("site build skipped")
        return
    _run_site_command("site:build")


def deploy_site_if_enabled() -> None:
    if os.environ.get("AUTO_MATOME_DEPLOY_SITE") != "1":
        log.info("site deploy skipped")
        return
    _run_site_command("site:deploy")


def push_content_to_branch(output_path: Path) -> None:
    """生成コンテンツ（output/YYYY-MM-DD.md）を content-data ブランチに git push する。

    必要な環境変数:
      - GITHUB_TOKEN : git push に使用するPersonal Access Token
      - GIT_USER_EMAIL / GIT_USER_NAME : コミット用（省略可）

    tmpdir に bare clone を作って操作する。ROOT が output/ シンボリックリンクを
    含むため、同ディレクトリで branch checkout すると "untracked files would be
    overwritten" エラーになるのを回避するため。
    """
    import shutil, tempfile

    if os.environ.get("AUTO_MATOME_PUSH_CONTENT") != "1":
        log.info("content push skipped (AUTO_MATOME_PUSH_CONTENT != 1)")
        return

    if not output_path.exists():
        log.warning("content push skipped: output file does not exist", extra={"path": str(output_path)})
        return

    git_email = os.environ.get("GIT_USER_EMAIL", "auto-matome-bot@example.com")
    git_name = os.environ.get("GIT_USER_NAME", "auto-matome-bot")
    github_token = os.environ.get("GITHUB_TOKEN", "")

    # リモートURLを組み立て（GITHUB_TOKEN があれば認証URL）
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=ROOT, capture_output=True, text=True,
    )
    origin_url = result.stdout.strip()
    if github_token and origin_url.startswith("https://github.com/"):
        repo_path = origin_url.removeprefix("https://github.com/")
        push_url = f"https://x-access-token:{github_token}@github.com/{repo_path}"
    else:
        push_url = origin_url

    log.info("pushing content to content-data branch", extra={"output_path": str(output_path)})

    env = {**os.environ, "GIT_AUTHOR_EMAIL": git_email, "GIT_AUTHOR_NAME": git_name,
           "GIT_COMMITTER_EMAIL": git_email, "GIT_COMMITTER_NAME": git_name}

    tmpdir = tempfile.mkdtemp(prefix="auto-matome-push-")
    try:
        # tmpdir で新しいリポジトリを作成し、content-data を取得
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", push_url], cwd=tmpdir, check=True, capture_output=True)

        fetch_result = subprocess.run(
            ["git", "fetch", "origin", "content-data:content-data"],
            cwd=tmpdir, capture_output=True,
        )
        if fetch_result.returncode == 0:
            subprocess.run(["git", "checkout", "content-data"], cwd=tmpdir, check=True, capture_output=True)
        else:
            subprocess.run(["git", "checkout", "--orphan", "content-data"], cwd=tmpdir, env=env, check=True, capture_output=True)

        # output ファイルをコピーして add
        out_dir = Path(tmpdir) / "output"
        out_dir.mkdir(exist_ok=True)
        shutil.copy2(output_path, out_dir / output_path.name)
        subprocess.run(["git", "add", str(out_dir / output_path.name)], cwd=tmpdir, env=env, check=True)

        commit_result = subprocess.run(
            ["git", "commit", "-m", f"content: add {output_path.name}"],
            cwd=tmpdir, env=env, capture_output=True, text=True,
        )
        if commit_result.returncode != 0 and "nothing to commit" in commit_result.stdout + commit_result.stderr:
            log.info("content push: nothing new to commit")
        else:
            commit_result.check_returncode()
            subprocess.run(["git", "push", "origin", "content-data"], cwd=tmpdir, env=env, check=True)
            log.info("content pushed to content-data branch")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _duration_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _stage_success(
    stage: str,
    start: float,
    *,
    input_count: int = 0,
    output_count: int = 0,
    artifact_paths: list[Path] | None = None,
    warnings: list[str] | None = None,
) -> StageResult:
    return StageResult(
        status=StageStatus.SUCCESS,
        stage=stage,
        input_count=input_count,
        output_count=output_count,
        artifact_paths=artifact_paths or [],
        warnings=warnings or [],
        duration_ms=_duration_ms(start),
    )


def _stage_skipped(
    stage: str,
    start: float,
    *,
    input_count: int = 0,
    output_count: int = 0,
    artifact_paths: list[Path] | None = None,
    warnings: list[str] | None = None,
) -> StageResult:
    return StageResult(
        status=StageStatus.SKIPPED,
        stage=stage,
        input_count=input_count,
        output_count=output_count,
        artifact_paths=artifact_paths or [],
        warnings=warnings or [],
        duration_ms=_duration_ms(start),
    )


def _stage_failed(
    stage: str,
    start: float,
    failure_code: FailureCode,
    *,
    input_count: int = 0,
    output_count: int = 0,
    artifact_paths: list[Path] | None = None,
    warnings: list[str] | None = None,
) -> StageResult:
    return StageResult(
        status=StageStatus.FAILED,
        stage=stage,
        input_count=input_count,
        output_count=output_count,
        artifact_paths=artifact_paths or [],
        warnings=warnings or [],
        failure_code=failure_code,
        duration_ms=_duration_ms(start),
    )


async def run_pipeline(*, run_date: date | None = None) -> JobResult:
    log.info("starting combined pipeline")
    job_start = time.perf_counter()
    context = _resolve_run_context(run_date)
    run_id = context.run_id
    store = context.artifact_store
    stages: list[StageResult] = []
    current_stage = "collect"
    current_stage_start = job_start
    current_artifact_paths: list[Path] = []
    current_input_count = 0
    current_output_count = 0
    output_dir = context.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = context.output_path
    try:
        # Fetch all enabled sources from config/sources.yaml (parallel)
        current_stage = "collect"
        collect_start = time.perf_counter()
        current_stage_start = collect_start
        current_artifact_paths = []
        all_stories = await fetch_all()
        collected_path = store.write_json("collect", "stories.json", all_stories)
        current_artifact_paths = [collected_path]
        current_output_count = len(all_stories)
        stages.append(
            _stage_success(
                "collect",
                collect_start,
                output_count=len(all_stories),
                artifact_paths=[collected_path],
            )
        )

        # Quality gate
        current_stage = "select"
        select_start = time.perf_counter()
        current_stage_start = select_start
        before = len(all_stories)
        current_input_count = before
        all_stories = [s for s in all_stories if _gate.evaluate(s).passed]
        log.info("quality gate applied", extra={"before": before, "after": len(all_stories)})

        # Dedup across sources and across runs
        unique = dedup_stories(all_stories, current_date=context.run_date)
        log.info("dedup applied", extra={"before": len(all_stories), "after": len(unique)})
        selected_path = store.write_json("select", "selected-stories.json", unique)
        current_artifact_paths = [selected_path]
        current_output_count = len(unique)
        select_warnings = ["No unique stories were selected."] if len(unique) == 0 else []
        stages.append(
            _stage_success(
                "select",
                select_start,
                input_count=before,
                output_count=len(unique),
                artifact_paths=[selected_path],
                warnings=select_warnings,
            )
        )

        # Split by source for converter
        def _by_source(src: str) -> list[dict]:
            return [{k: v for k, v in s.items() if k != "_source"} for s in unique if s["_source"] == src]

        hn_stories = _by_source("hn")
        indieweb_stories = _by_source("indieweb") + _by_source("rss")
        reddit_stories = _by_source("reddit")

        # 新規記事が無い日、または既存出力があり増分が少ない日は空記事を作らずスキップ
        if _should_skip_conversion(output_path.exists(), len(unique)):
            reason = "no new unique stories" if len(unique) == 0 else "today's output already exists and few new stories"
            log.info(
                "skipping conversion",
                extra={
                    "reason": reason,
                    "existing": str(output_path),
                    "new_stories": len(unique),
                },
            )
            current_stage = "synthesize"
            synth_start = time.perf_counter()
            current_stage_start = synth_start
            current_artifact_paths = [selected_path]
            current_input_count = len(unique)
            current_output_count = 0
            stages.append(
                _stage_skipped(
                    "synthesize",
                    synth_start,
                    input_count=len(unique),
                    output_count=0,
                    artifact_paths=[selected_path],
                    warnings=[reason],
                )
            )
            current_stage = "render"
            render_start = time.perf_counter()
            current_stage_start = render_start
            stages.append(
                _stage_skipped(
                    "render",
                    render_start,
                    artifact_paths=[output_path] if output_path.exists() else [],
                    warnings=["No content rendered."] if not output_path.exists() else ["Existing daily output left unchanged."],
                )
            )
            current_stage = "publish"
            publish_start = time.perf_counter()
            current_stage_start = publish_start
            stages.append(
                _stage_skipped(
                    stage="publish",
                    artifact_paths=[output_path] if output_path.exists() else [],
                    warnings=["No publish attempted."],
                    start=publish_start,
                )
            )
            result = JobResult(
                status=JobStatus.SUCCESS,
                job_name="auto-matome",
                run_id=run_id,
                stages=stages,
                artifact_root=store.run_dir,
                warnings=[reason],
                duration_ms=_duration_ms(job_start),
            )
            return _persist_result(result, store)

        log.info("converting to 2ch-style matome via Claude Code")
        current_stage = "synthesize"
        synth_start = time.perf_counter()
        current_stage_start = synth_start
        current_input_count = len(unique)
        current_output_count = 0
        current_artifact_paths = []
        matome_md = await convert_to_matome(
            hn_stories,
            indieweb_stories,
            reddit_stories,
            run_date=context.run_date,
        )
        synthesized_path = store.write_text("synthesize", "matome.md", matome_md)
        current_artifact_paths = [synthesized_path]

        if not has_meaningful_body(matome_md):
            stages.append(
                _stage_failed(
                    "synthesize",
                    synth_start,
                    FailureCode.OUTPUT_EMPTY,
                    input_count=len(unique),
                    artifact_paths=[synthesized_path],
                    warnings=["Converter returned placeholder-only or empty content."],
                )
            )
            log.warning(
                "converter returned empty content; keeping existing output",
                extra={"output_path": str(output_path), "new_stories": len(unique)},
            )
            if output_path.exists():
                current_stage = "render"
                render_start = time.perf_counter()
                current_stage_start = render_start
                build_site()
                stages.append(
                    _stage_success(
                        "render",
                        render_start,
                        artifact_paths=[output_path],
                        warnings=["Reused existing daily output after empty synthesis output."],
                    )
                )
                current_stage = "publish"
                publish_start = time.perf_counter()
                current_stage_start = publish_start
                deploy_site_if_enabled()
                push_content_to_branch(output_path)
                publish_status = StageStatus.SUCCESS if os.environ.get("AUTO_MATOME_DEPLOY_SITE") == "1" else StageStatus.SKIPPED
                stages.append(
                    StageResult(
                        status=publish_status,
                        stage="publish",
                        artifact_paths=[output_path],
                        warnings=["Site deploy skipped by configuration."] if publish_status == StageStatus.SKIPPED else [],
                        duration_ms=_duration_ms(publish_start),
                    )
                )
                result = JobResult(
                    status=JobStatus.PARTIAL,
                    job_name="auto-matome",
                    run_id=run_id,
                    stages=stages,
                    artifact_root=store.run_dir,
                    warnings=["Synthesis output was empty; existing output was preserved."],
                    failure_code=FailureCode.OUTPUT_EMPTY,
                    duration_ms=_duration_ms(job_start),
                )
                return _persist_result(result, store)
            result = JobResult(
                status=JobStatus.FAILED,
                job_name="auto-matome",
                run_id=run_id,
                stages=stages,
                artifact_root=store.run_dir,
                warnings=["No existing daily output is available after empty synthesis output."],
                failure_code=FailureCode.OUTPUT_EMPTY,
                duration_ms=_duration_ms(job_start),
            )
            return _persist_result(result, store)

        output_path.write_text(matome_md, encoding="utf-8")
        current_output_count = 1
        stages.append(
            _stage_success(
                "synthesize",
                synth_start,
                input_count=len(unique),
                output_count=1,
                artifact_paths=[synthesized_path],
            )
        )

        log.info(f"wrote {output_path}")
        current_stage = "render"
        render_start = time.perf_counter()
        current_stage_start = render_start
        current_artifact_paths = [output_path]
        current_input_count = 1
        current_output_count = 1
        build_site()
        stages.append(
            _stage_success(
                "render",
                render_start,
                input_count=1,
                output_count=1,
                artifact_paths=[output_path],
            )
        )
        current_stage = "publish"
        publish_start = time.perf_counter()
        current_stage_start = publish_start
        deploy_site_if_enabled()
        push_content_to_branch(output_path)
        publish_status = StageStatus.SUCCESS if os.environ.get("AUTO_MATOME_DEPLOY_SITE") == "1" else StageStatus.SKIPPED
        stages.append(
            StageResult(
                status=publish_status,
                stage="publish",
                input_count=1,
                output_count=1 if publish_status == StageStatus.SUCCESS else 0,
                artifact_paths=[output_path],
                warnings=["Site deploy skipped by configuration."] if publish_status == StageStatus.SKIPPED else [],
                duration_ms=_duration_ms(publish_start),
            )
        )
        result = JobResult(
            status=JobStatus.SUCCESS,
            job_name="auto-matome",
            run_id=run_id,
            stages=stages,
            artifact_root=store.run_dir,
            duration_ms=_duration_ms(job_start),
        )
        return _persist_result(result, store)
    except Exception as exc:
        if not stages or stages[-1].stage != current_stage:
            stages.append(
                _stage_failed(
                    current_stage,
                    current_stage_start,
                    FailureCode.UNEXPECTED_ERROR,
                    input_count=current_input_count,
                    output_count=current_output_count,
                    artifact_paths=current_artifact_paths,
                    warnings=[str(exc)],
                )
            )
        result = JobResult(
            status=JobStatus.FAILED,
            job_name="auto-matome",
            run_id=run_id,
            stages=stages,
            artifact_root=store.run_dir,
            warnings=[f"Unexpected error in stage '{current_stage}': {exc}"],
            failure_code=FailureCode.UNEXPECTED_ERROR,
            duration_ms=_duration_ms(job_start),
        )
        return _persist_result(result, store)


async def main(*, run_date: date | None = None) -> Path:
    context = _resolve_run_context(run_date)
    result = await run_pipeline(run_date=context.run_date)
    if result.status == JobStatus.FAILED:
        raise RuntimeError(result.failure_code or "auto-matome pipeline failed")
    render_stage = result.stage("render")
    if render_stage and render_stage.artifact_paths:
        return Path(render_stage.artifact_paths[0])
    return context.output_path


if __name__ == "__main__":
    path = asyncio.run(main())
    print(f"Output: {path}")
