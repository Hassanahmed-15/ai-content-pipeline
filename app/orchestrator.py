"""
Multi-agent orchestrator.

Chains: Research -> Writer -> Editor/Fact-check -> SEO -> Publish.
Each stage is timed and logged so a run is fully traceable -- the same
observability you'd want from a production agent workflow.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .agents import editor, research, seo, writer
from .llm import LLMClient

OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "..", "output"))


@dataclass
class StageLog:
    name: str
    seconds: float
    live: bool
    summary: str


@dataclass
class PipelineResult:
    run_id: str
    topic: str
    created_at: str
    live: bool
    final_markdown: str
    seo: Dict[str, Any]
    research: Dict[str, Any]
    editor_report: Dict[str, Any]
    published_path: Optional[str]
    stages: List[StageLog] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "topic": self.topic,
            "created_at": self.created_at,
            "live": self.live,
            "seo": {k: v for k, v in self.seo.items() if k != "_meta"},
            "research": {k: v for k, v in self.research.items() if k != "_meta"},
            "editor_report": {
                k: v for k, v in self.editor_report.items()
                if k not in ("_meta", "edited_markdown")
            },
            "final_markdown": self.final_markdown,
            "published_path": self.published_path,
            "stages": [vars(s) for s in self.stages],
        }


class ContentPipeline:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    def run(
        self,
        topic: str,
        audience: str = "general business readers",
        goal: str = "educate and drive engagement",
        tone: str = "clear and professional",
        words: int = 800,
        publish: bool = True,
        on_stage=None,
    ) -> PipelineResult:
        run_id = uuid.uuid4().hex[:12]
        stages: List[StageLog] = []

        def _time(name: str, fn):
            t0 = time.time()
            out = fn()
            dt = round(time.time() - t0, 3)
            live = bool(out.get("_meta", {}).get("live"))
            summary = _summ(name, out)
            stages.append(StageLog(name=name, seconds=dt, live=live, summary=summary))
            print(f"[pipeline {run_id}] {name:8s} done in {dt}s (live={live})")
            if on_stage:
                on_stage(name, {"seconds": dt, "live": live, "summary": summary})
            return out

        print(f"[pipeline {run_id}] START topic={topic!r} live_llm={self.llm.is_live}")

        brief = _time("research", lambda: research.run(self.llm, topic, audience, goal))
        draft = _time("writer", lambda: writer.run(self.llm, topic, audience, tone, words, brief))
        edited = _time("editor", lambda: editor.run(self.llm, topic, draft["markdown"]))
        final_md = edited.get("edited_markdown") or draft["markdown"]
        meta = _time("seo", lambda: seo.run(self.llm, topic, final_md))

        published_path = None
        if publish:
            published_path = self._publish(run_id, topic, final_md, meta, brief, edited)
            stages.append(StageLog("publish", 0.0, False, f"wrote {published_path}"))
            print(f"[pipeline {run_id}] publish done -> {published_path}")
            if on_stage:
                on_stage("publish", {"seconds": 0.0, "live": False,
                                     "summary": f"wrote {os.path.basename(published_path)}"})

        result = PipelineResult(
            run_id=run_id,
            topic=topic,
            created_at=datetime.now(timezone.utc).isoformat(),
            live=self.llm.is_live,
            final_markdown=final_md,
            seo=meta,
            research=brief,
            editor_report=edited,
            published_path=published_path,
            stages=stages,
        )
        print(f"[pipeline {run_id}] COMPLETE ({len(final_md)} chars of final content)")
        return result

    # ------------------------------------------------------------------ #
    def _publish(self, run_id, topic, final_md, meta, brief, edited) -> str:
        """'Publish' = write a front-matter markdown file + a JSON sidecar."""
        out_dir = os.path.abspath(OUTPUT_DIR)
        os.makedirs(out_dir, exist_ok=True)
        slug = meta.get("slug", "article")
        md_path = os.path.join(out_dir, f"{slug}-{run_id}.md")

        front_matter = (
            "---\n"
            f"title: {json.dumps(meta.get('title', topic))}\n"
            f"description: {json.dumps(meta.get('meta_description', ''))}\n"
            f"slug: {slug}\n"
            f"keywords: {json.dumps(meta.get('keywords', []))}\n"
            f"generated_at: {datetime.now(timezone.utc).isoformat()}\n"
            f"run_id: {run_id}\n"
            "---\n\n"
        )
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(front_matter + final_md + "\n")

        json_path = os.path.join(out_dir, f"{slug}-{run_id}.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "run_id": run_id,
                    "topic": topic,
                    "seo": {k: v for k, v in meta.items() if k != "_meta"},
                    "research": {k: v for k, v in brief.items() if k != "_meta"},
                    "editor_issues": edited.get("issues_found", []),
                    "fact_check": edited.get("fact_check", []),
                },
                fh,
                indent=2,
            )
        return md_path


def _summ(name: str, out: Dict[str, Any]) -> str:
    if name == "research":
        return f"{len(out.get('key_points', []))} key points, {len(out.get('stats', []))} stats"
    if name == "writer":
        return f"{len(out.get('markdown', ''))} chars drafted"
    if name == "editor":
        return f"{len(out.get('issues_found', []))} issues, {len(out.get('fact_check', []))} fact checks"
    if name == "seo":
        return f"title={out.get('title','')!r}, {len(out.get('keywords', []))} keywords"
    return ""
