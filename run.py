#!/usr/bin/env python3
"""
Polished CLI runner for the multi-agent content pipeline.

Usage:
    python run.py "Your topic here"
    python run.py "AI agents for fintech" --words 600 --tone witty --no-publish

Runs fully offline (stub LLM) unless an API key is configured in .env, in which
case it makes real OpenAI (or Claude) calls. Either way it runs end-to-end.
"""
import argparse
import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

from app.llm import LLMClient
from app.orchestrator import ContentPipeline

# ANSI colors (auto-disabled if not a TTY).
_TTY = sys.stdout.isatty()
def c(code, s): return f"\033[{code}m{s}\033[0m" if _TTY else s
BOLD=lambda s:c("1",s); DIM=lambda s:c("2",s); GREEN=lambda s:c("32",s)
CYAN=lambda s:c("36",s); YEL=lambda s:c("33",s); MAG=lambda s:c("35",s)

SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
ORDER = ["research", "writer", "editor", "seo", "publish"]


def main() -> int:
    p = argparse.ArgumentParser(description="Run the multi-agent content pipeline.")
    p.add_argument("topic", help="The article topic")
    p.add_argument("--audience", default="general business readers")
    p.add_argument("--goal", default="educate and drive engagement")
    p.add_argument("--tone", default="clear and professional")
    p.add_argument("--words", type=int, default=800)
    p.add_argument("--no-publish", action="store_true")
    args = p.parse_args()

    llm = LLMClient()
    pipeline = ContentPipeline(llm)

    mode = GREEN(f"LIVE · {llm.provider} · {llm.model}") if llm.is_live else YEL("STUB MODE (no API key)")
    print()
    print(BOLD(MAG("  🧠 AI Multi-Agent Content Pipeline")))
    print(f"  {DIM('mode:')} {mode}")
    print(f"  {DIM('topic:')} {BOLD(args.topic)}")
    print(DIM("  " + "─" * 60))

    done = {}
    def on_stage(name, info):
        mark = GREEN("✔")
        live = CYAN(" live") if info.get("live") else ""
        print(f"  {mark} {BOLD(name.ljust(9))} {DIM(str(info['seconds'])+'s')}{live}  {DIM(info['summary'])}")
        done[name] = info

    t0 = time.time()
    print(f"  {CYAN('▶')} running {len(ORDER)} agents…\n")
    result = pipeline.run(
        topic=args.topic, audience=args.audience, goal=args.goal,
        tone=args.tone, words=args.words, publish=not args.no_publish,
        on_stage=on_stage,
    )
    total = round(time.time() - t0, 2)

    print(DIM("  " + "─" * 60))
    print(f"  {BOLD('SEO title')} : {result.seo.get('title')}")
    print(f"  {BOLD('Slug')}      : {result.seo.get('slug')}")
    print(f"  {BOLD('Keywords')}  : {DIM(', '.join(result.seo.get('keywords', [])))}")
    if result.published_path:
        print(f"  {BOLD('Published')} : {GREEN(result.published_path)}")
    print(f"  {BOLD('Total')}     : {total}s")
    print(DIM("  " + "─" * 60))
    print(BOLD("  FINAL ARTICLE (preview):\n"))
    for line in result.final_markdown[:700].splitlines():
        print("   " + line)
    print(DIM("   …\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
