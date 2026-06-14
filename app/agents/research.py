"""Agent 1 — Research. Produces a structured brief the writer can build on."""
from __future__ import annotations

from typing import Any, Dict

from ..llm import LLMClient
from .base import parse_json_block

SYSTEM = (
    "You are a meticulous research analyst. Given a topic, produce a tight, "
    "factual research brief. Be concrete, avoid fluff, and never invent precise "
    "statistics you cannot reasonably support. Respond with ONLY a JSON object."
)

PROMPT_TEMPLATE = """\
Produce a research brief for an article.

TOPIC: {topic}
AUDIENCE: {audience}
GOAL: {goal}

Return ONLY JSON with this exact shape:
{{
  "summary": "2-3 sentence overview",
  "key_points": ["point", "..."],
  "stats": [{{"claim": "...", "source": "..."}}],
  "angles": ["angle", "..."]
}}
"""


def run(llm: LLMClient, topic: str, audience: str, goal: str) -> Dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(topic=topic, audience=audience, goal=goal)
    result = llm.complete(SYSTEM, prompt, max_tokens=1500, temperature=0.4, agent="research")
    data = parse_json_block(result.text)
    if not data:
        # Defensive default so downstream agents always have something to chew on.
        data = {"summary": result.text.strip()[:500], "key_points": [], "stats": [], "angles": []}
    data["_meta"] = {"model": result.model, "live": result.live,
                     "tokens": [result.input_tokens, result.output_tokens]}
    return data
