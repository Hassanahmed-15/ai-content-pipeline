"""
LLM client with real OpenAI and Claude backends plus a deterministic offline stub.

Design goal: the whole pipeline runs end-to-end *right now* with no API key
(returning structured stub output), and goes fully live the moment you set an
API key -- with zero code changes anywhere else.

Provider is chosen by the LLM_PROVIDER env var ("openai" default, or "anthropic").
Keys are read from the environment / .env only; they are never hardcoded.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

# Provider + per-provider default models. Override any of these via env.
PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")


@dataclass
class LLMResult:
    text: str
    model: str
    live: bool          # True if a real provider call was made
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient:
    """Single entry point used by every agent. Backend chosen by LLM_PROVIDER."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = (provider or PROVIDER).lower()
        self._client = None

        if self.provider == "anthropic":
            self.api_key = api_key if api_key is not None else os.getenv("ANTHROPIC_API_KEY")
            self.model = model or CLAUDE_MODEL
            if self.api_key:
                try:
                    import anthropic  # lazy import so the stub path needs no deps
                    self._client = anthropic.Anthropic(api_key=self.api_key)
                except Exception as exc:  # pragma: no cover
                    print(f"[llm] anthropic SDK unavailable ({exc}); falling back to stub")
        else:  # default: openai
            self.provider = "openai"
            self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
            self.model = model or OPENAI_MODEL
            if self.api_key:
                try:
                    from openai import OpenAI  # lazy import
                    self._client = OpenAI(api_key=self.api_key)
                except Exception as exc:  # pragma: no cover
                    print(f"[llm] openai SDK unavailable ({exc}); falling back to stub")

    @property
    def is_live(self) -> bool:
        return self._client is not None

    def complete(
        self,
        system: str,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        agent: str = "agent",
    ) -> LLMResult:
        if self._client is not None:
            if self.provider == "anthropic":
                return self._complete_anthropic(system, prompt, max_tokens, temperature)
            return self._complete_openai(system, prompt, max_tokens, temperature)
        return self._complete_stub(system, prompt, agent)

    # --------------------------------------------------------------- openai
    def _complete_openai(self, system, prompt, max_tokens, temperature) -> LLMResult:
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        return LLMResult(
            text=text,
            model=self.model,
            live=True,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )

    # ------------------------------------------------------------ anthropic
    def _complete_anthropic(self, system, prompt, max_tokens, temperature) -> LLMResult:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return LLMResult(
            text=text,
            model=self.model,
            live=True,
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
        )

    # ------------------------------------------------------------------ stub
    def _complete_stub(self, system, prompt, agent) -> LLMResult:
        """
        Deterministic, structurally-correct fake output so the pipeline is
        fully testable offline. Each agent gets a shape it knows how to parse.
        """
        topic = _extract_topic(prompt)
        text = _STUB_BUILDERS.get(agent, _stub_generic)(topic, prompt)
        return LLMResult(text=text, model="stub", live=False)


# --------------------------------------------------------------------------- #
# Helpers + stub content builders
# --------------------------------------------------------------------------- #
def _extract_topic(prompt: str) -> str:
    m = re.search(r"TOPIC:\s*(.+)", prompt)
    if m:
        return m.group(1).strip().splitlines()[0].strip()
    return "the requested topic"


def _stub_research(topic: str, prompt: str) -> str:
    return json.dumps(
        {
            "summary": f"Stub research brief on '{topic}'. (Set ANTHROPIC_API_KEY for real research.)",
            "key_points": [
                f"{topic} is growing in adoption across the industry.",
                f"Three common challenges relate to cost, accuracy, and integration in {topic}.",
                f"Best practice is to start small and measure outcomes when applying {topic}.",
            ],
            "stats": [
                {"claim": f"Adoption of {topic} rose notably year over year.", "source": "stub://industry-report"},
            ],
            "angles": ["beginner guide", "ROI / business value", "common pitfalls"],
        },
        indent=2,
    )


def _stub_writer(topic: str, prompt: str) -> str:
    return (
        f"# {topic.title()}: A Practical Guide\n\n"
        f"## Introduction\n"
        f"{topic.capitalize()} has become essential for modern teams. "
        f"This guide breaks down what it is, why it matters, and how to start.\n\n"
        f"## Why It Matters\n"
        f"Organizations adopting {topic} report faster workflows and clearer outcomes. "
        f"The value comes from automating repetitive work and surfacing insight earlier.\n\n"
        f"## How To Get Started\n"
        f"1. Define a small, measurable use case.\n"
        f"2. Pilot it with one team.\n"
        f"3. Measure results and iterate before scaling.\n\n"
        f"## Common Pitfalls\n"
        f"Avoid over-engineering early. Focus on data quality and a tight feedback loop.\n\n"
        f"## Conclusion\n"
        f"Start small, measure honestly, and expand what works. {topic.capitalize()} rewards iteration."
    )


def _stub_editor(topic: str, prompt: str) -> str:
    return json.dumps(
        {
            "edited_markdown": _extract_draft(prompt)
            or f"# {topic.title()}\n\n(Edited stub copy.)",
            "issues_found": [
                {"type": "clarity", "note": "Intro tightened for readability.", "severity": "low"},
            ],
            "fact_check": [
                {"claim": f"Adoption of {topic} is rising.", "verdict": "plausible", "note": "stub check"},
            ],
            "readability_score": 72,
        },
        indent=2,
    )


def _stub_seo(topic: str, prompt: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return json.dumps(
        {
            "title": f"{topic.title()}: A Practical Guide (2026)",
            "meta_description": f"Learn {topic} the practical way: why it matters, how to start, "
            f"and the pitfalls to avoid. A clear, actionable guide.",
            "slug": slug or "guide",
            "keywords": [topic, f"{topic} guide", f"how to use {topic}", f"{topic} best practices"],
            "social_caption": f"New guide: getting real value from {topic}. Start small, measure, scale. 🚀",
        },
        indent=2,
    )


def _stub_generic(topic: str, prompt: str) -> str:
    return f"Stub response about {topic}."


def _extract_draft(prompt: str) -> str:
    # Grab everything between "DRAFT:" and the trailing "Return ONLY JSON"
    # instruction block so the stub edit doesn't echo prompt scaffolding.
    m = re.search(r"DRAFT:\s*(.+?)\n\nReturn ONLY JSON", prompt, re.DOTALL)
    if not m:
        m = re.search(r"DRAFT:\s*(.+)", prompt, re.DOTALL)
    return m.group(1).strip() if m else ""


_STUB_BUILDERS = {
    "research": _stub_research,
    "writer": _stub_writer,
    "editor": _stub_editor,
    "seo": _stub_seo,
}
