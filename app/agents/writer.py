"""Agent 2 — Writer. Turns the research brief into a full markdown draft."""
from __future__ import annotations

import json
from typing import Any, Dict

from ..llm import LLMClient

SYSTEM = (
    "You are an expert content writer. Write clear, engaging, well-structured "
    "markdown articles. Use headings, short paragraphs, and concrete examples. "
    "Ground every claim in the provided research. Output ONLY the markdown article."
)

PROMPT_TEMPLATE = """\
Write a complete article in markdown.

TOPIC: {topic}
AUDIENCE: {audience}
TARGET LENGTH: ~{words} words
TONE: {tone}

RESEARCH BRIEF (JSON):
{brief}

Requirements:
- Start with an H1 title.
- Include an intro, 3-5 body sections with H2 headings, and a conclusion.
- Weave in the research key_points and stats naturally.
- Do not include any commentary outside the article itself.
"""


def run(llm: LLMClient, topic: str, audience: str, tone: str, words: int,
        brief: Dict[str, Any]) -> Dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(
        topic=topic, audience=audience, words=words, tone=tone,
        brief=json.dumps({k: v for k, v in brief.items() if k != "_meta"}, indent=2),
    )
    result = llm.complete(SYSTEM, prompt, max_tokens=3000, temperature=0.7, agent="writer")
    return {
        "markdown": result.text.strip(),
        "_meta": {"model": result.model, "live": result.live,
                  "tokens": [result.input_tokens, result.output_tokens]},
    }
