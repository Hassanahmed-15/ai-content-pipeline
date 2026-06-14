"""Agent 3 — Editor / fact-checker. Polishes the draft and flags issues."""
from __future__ import annotations

from typing import Any, Dict

from ..llm import LLMClient
from .base import parse_json_block

SYSTEM = (
    "You are a rigorous editor and fact-checker. Improve clarity, fix grammar, "
    "tighten prose, and flag any claim that seems unsupported. Preserve the "
    "author's structure and markdown. Respond with ONLY a JSON object."
)

PROMPT_TEMPLATE = """\
Edit and fact-check the following draft.

TOPIC: {topic}

DRAFT:
{draft}

Return ONLY JSON with this exact shape:
{{
  "edited_markdown": "the improved full markdown article",
  "issues_found": [{{"type": "grammar|clarity|structure|fact", "note": "...", "severity": "low|med|high"}}],
  "fact_check": [{{"claim": "...", "verdict": "supported|plausible|unsupported", "note": "..."}}],
  "readability_score": 0
}}
"""


def run(llm: LLMClient, topic: str, draft_markdown: str) -> Dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(topic=topic, draft=draft_markdown)
    result = llm.complete(SYSTEM, prompt, max_tokens=3500, temperature=0.3, agent="editor")
    data = parse_json_block(result.text)
    if not data or "edited_markdown" not in data:
        # If the model didn't return JSON, treat its whole output as the edit.
        data = {
            "edited_markdown": result.text.strip() or draft_markdown,
            "issues_found": [],
            "fact_check": [],
            "readability_score": None,
        }
    data["_meta"] = {"model": result.model, "live": result.live,
                     "tokens": [result.input_tokens, result.output_tokens]}
    return data
