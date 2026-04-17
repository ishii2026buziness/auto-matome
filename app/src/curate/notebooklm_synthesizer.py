"""NotebookLM multi-turn synthesis pipeline.

Flow:
  1. Create daily temp notebook
  2. Add article URLs as sources
  3. Wait for processing
  4. Ask top-level: "今日は大きく何トピック？"
  5. For each topic, ask deep-dive with --json (parallel → get citations)
  6. Map citation source_ids back to original URLs
  7. Return list of TopicInsight (one per article)
  8. Caller is responsible for cleanup via cleanup_notebook()
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date


@dataclass
class TopicInsight:
    title: str
    insights: str             # deep-dive answer from NotebookLM
    source_urls: list[str] = field(default_factory=list)   # cited article URLs
    source_titles: list[str] = field(default_factory=list) # cited article titles


@dataclass
class NotebookLMAnalysis:
    topics: list[TopicInsight]
    notebook_id: str


_TOP_LEVEL_QUERY = """\
追加した記事群を読んで、今日の大きなトピックを3〜6個に分類してください。

以下のJSON配列だけを出力してください（引用番号[1]や[1-3]はタイトルに含めない）:
[
  {"title": "トピックタイトル（日本語・20字以内）", "summary": "1行の概要"},
  ...
]
"""

_DEEP_DIVE_QUERY = """\
「{topic}」について詳しく教えてください。

- 何が起きているか（事実・数値があれば）
- なぜ今話題なのか
- 面白い視点・意外な接続や対比
- ツッコミどころ・皮肉・笑えるポイント
- 今後ありそうな展開

日本語で答えてください。
"""


from common.logger import get_logger as _get_logger
_log = _get_logger("auto_matome.curate.notebooklm")


def _run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError as exc:
        # notebooklm CLI not installed — caller treats rc!=0 as failure and falls back
        return 1, "", str(exc)


async def _run_async(cmd: list[str]) -> tuple[int, str, str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run, cmd)


async def analyze_with_notebooklm(
    stories: list[dict],
    *,
    run_date: date | None = None,
) -> NotebookLMAnalysis | None:
    """Full multi-turn NotebookLM analysis. Returns None on failure."""
    urls = [s["url"] for s in stories if s.get("url")]
    if len(urls) < 3:
        _log.warning("not enough URLs for NotebookLM", extra={"count": len(urls)})
        return None

    today = (run_date or date.today()).isoformat()
    notebook_id = await _create_notebook(f"auto-matome-daily-{today}")
    if not notebook_id:
        _log.error("failed to create notebook")
        return None
    _log.info("notebook created", extra={"notebook_id": notebook_id[:8]})

    # Add URLs → collect {source_id: url} map
    source_map = await _add_sources(notebook_id, urls[:30])
    _log.info("sources added", extra={"added": len(source_map), "attempted": min(len(urls), 30)})
    if not source_map:
        _log.error("no sources added successfully")
        _run(["notebooklm", "notebook", "delete", notebook_id])
        return None

    # Wait for sources to be ready
    await _wait_sources_ready(notebook_id, len(source_map), timeout=120)

    # Step 1: top-level topic list
    topics_raw = await _ask(notebook_id, _TOP_LEVEL_QUERY, new=True)
    _log.info("topic list response", extra={"length": len(topics_raw), "preview": topics_raw[:200]})
    topic_items = _parse_topic_list(topics_raw)
    _log.info("parsed topics", extra={"count": len(topic_items), "topics": [t.get("title") for t in topic_items]})
    if not topic_items:
        _log.error("failed to parse topic list from NotebookLM response")
        _run(["notebooklm", "notebook", "delete", notebook_id])
        return None

    # Step 2: deep-dive per topic (parallel)
    deep_tasks = [
        _deep_dive(notebook_id, item["title"], source_map)
        for item in topic_items
    ]
    topic_insights = await asyncio.gather(*deep_tasks)

    # Filter out failures
    valid = [t for t in topic_insights if t is not None]
    if not valid:
        _run(["notebooklm", "notebook", "delete", notebook_id])
        return None

    return NotebookLMAnalysis(topics=valid, notebook_id=notebook_id)


async def _create_notebook(title: str) -> str | None:
    rc, out, _ = await _run_async(["notebooklm", "create", title, "--json"])
    if rc != 0:
        return None
    try:
        data = json.loads(out)
        # {"notebook": {"id": "..."}} or {"id": "..."}
        return data.get("notebook", data)["id"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


async def _add_sources(notebook_id: str, urls: list[str]) -> dict[str, str]:
    """Add URLs and return {source_id: url} map."""
    source_map: dict[str, str] = {}
    for url in urls:
        rc, out, _ = await _run_async([
            "notebooklm", "source", "add", url,
            "-n", notebook_id, "--json"
        ])
        if rc == 0:
            try:
                data = json.loads(out)
                # {"source": {"id": "..."}} or {"source_id": "..."} or {"id": "..."}
                src = data.get("source", data)
                sid = src.get("id") or src.get("source_id", "")
                if sid:
                    source_map[sid] = url
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        await asyncio.sleep(0.2)
    return source_map


async def _wait_sources_ready(notebook_id: str, total: int, timeout: int = 120) -> None:
    for _ in range(timeout // 5):
        await asyncio.sleep(5)
        rc, out, _ = await _run_async([
            "notebooklm", "source", "list",
            "-n", notebook_id, "--json"
        ])
        if rc != 0:
            break
        try:
            # strip "Matched: ..." prefix lines (CLI outputs before the JSON block)
            brace_idx = out.find("{")
            if brace_idx < 0:
                continue
            sources = json.loads(out[brace_idx:]).get("sources", [])
            ready = sum(1 for s in sources if s.get("status") == "ready")
            _log.info("waiting for sources", extra={"ready": ready, "total": total})
            if ready >= total * 0.7:
                break
        except (json.JSONDecodeError, KeyError):
            continue


async def _ask(notebook_id: str, query: str, new: bool = False) -> str:
    cmd = ["notebooklm", "ask", query, "-n", notebook_id]
    rc, out, err = await _run_async(cmd)
    _log.info("ask result", extra={"rc": rc, "out_len": len(out), "err_len": len(err), "out_preview": out[:100], "err_preview": err[:100]})
    return out if rc == 0 else ""


async def _ask_json(notebook_id: str, query: str) -> dict:
    cmd = ["notebooklm", "ask", query, "-n", notebook_id, "--json"]
    rc, out, _ = await _run_async(cmd)
    if rc != 0 or not out:
        return {}
    try:
        brace_idx = out.find("{")
        if brace_idx < 0:
            return {}
        return json.loads(out[brace_idx:])
    except json.JSONDecodeError:
        return {}


async def _deep_dive(
    notebook_id: str,
    topic_title: str,
    source_map: dict[str, str],
) -> TopicInsight | None:
    query = _DEEP_DIVE_QUERY.format(topic=topic_title)
    result = await _ask_json(notebook_id, query)
    if not result:
        return None

    answer = result.get("answer", "")
    references = result.get("references", [])

    # Map source_ids back to URLs
    source_urls: list[str] = []
    source_titles: list[str] = []
    seen: set[str] = set()
    for ref in references:
        sid = ref.get("source_id", "")
        url = source_map.get(sid, "")
        if url and url not in seen:
            seen.add(url)
            source_urls.append(url)
            source_titles.append(ref.get("cited_text", "")[:80])

    return TopicInsight(
        title=topic_title,
        insights=answer,
        source_urls=source_urls,
        source_titles=source_titles,
    )


def _fix_json_newlines(s: str) -> str:
    """Replace literal newlines inside JSON string values with spaces."""
    result = []
    in_string = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and in_string and i + 1 < len(s):
            result.append(c)
            i += 1
            result.append(s[i])
        elif c == '"':
            in_string = not in_string
            result.append(c)
        elif c == "\n" and in_string:
            result.append(" ")
        else:
            result.append(c)
        i += 1
    return "".join(result)


def _parse_topic_list(raw: str) -> list[dict]:
    """Parse JSON topic list from NotebookLM response.

    Handles: preamble text, ```json fences, citation markers [1-3],
    and literal newlines inside JSON string values.
    """
    # Remove citation markers like [1], [1-3], [1, 2]
    text = re.sub(r"\s*\[\d+(?:[,\-]\s*\d+)*\]", "", raw)
    # Extract JSON array
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    # Fix literal newlines inside string values
    fixed = _fix_json_newlines(m.group(0))
    try:
        data = json.loads(fixed)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict) and d.get("title")]
    except (json.JSONDecodeError, ValueError):
        pass
    return []


def cleanup_notebook(notebook_id: str) -> None:
    _run(["notebooklm", "delete", "-n", notebook_id, "-y"])
