"""Shared agent utilities."""
from __future__ import annotations

import json
import re
from typing import Any, Dict


def parse_json_block(text: str) -> Dict[str, Any]:
    """
    Extract the first JSON object from an LLM response, tolerating prose or
    ```json fences around it. Returns {} if nothing parseable is found.
    """
    if not text:
        return {}
    # Strip code fences if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        # Fall back to the first balanced-looking {...} span.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
    if not candidate:
        return {}
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {}
