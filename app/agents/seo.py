"""Agent 4 — SEO + packaging. Produces title, meta, slug, keywords, social copy."""
from __future__ import annotations

import re
from typing import Any, Dict

from ..llm import LLMClient
from .base import parse_json_block

SYSTEM = (
    "You are an SEO specialist. Given an article, produce optimized metadata. "
    "Titles under 60 chars, meta descriptions under 160 chars. "
    "Respond with ONLY a JSON object."
)

PROMPT_TEMPLATE = """\
Generate SEO metadata for this article.

TOPIC: {topic}

ARTICLE:
{article}

Return ONLY JSON with this exact shape:
{{
  "title": "SEO title under 60 chars",
  "meta_description": "compelling description under 160 chars",
  "slug": "url-friendly-slug",
  "keywords": ["kw", "..."],
  "social_caption": "short social post with one emoji"
}}
"""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "article"


def run(llm: LLMClient, topic: str, article_markdown: str) -> Dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(topic=topic, article=article_markdown[:4000])
    result = llm.complete(SYSTEM, prompt, max_tokens=800, temperature=0.5, agent="seo")
    data = parse_json_block(result.text)
    if not data:
        data = {}
    # Guarantee required fields exist and are sane.
    data.setdefault("title", topic.title())
    data.setdefault("meta_description", "")
    data["slug"] = _slugify(data.get("slug") or topic)
    data.setdefault("keywords", [])
    data.setdefault("social_caption", "")
    data["_meta"] = {"model": result.model, "live": result.live,
                     "tokens": [result.input_tokens, result.output_tokens]}
    return data
