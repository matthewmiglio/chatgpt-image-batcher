"""chatgpt-image-generator CLI entry point.

Examples:
    python image_gen.py auth
    python image_gen.py generate --prompts C:/prompts.json --output C:/out
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

from browser import launch_browser, login_session, check_login_status  # noqa: E402
from chatgpt import generate_batch  # noqa: E402
from prompts import load_prompts  # noqa: E402


async def cmd_auth(_args) -> int:
    await login_session()
    return 0


async def cmd_generate(args) -> int:
    prompts = load_prompts(args.prompts)
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded {len(prompts)} prompts from {args.prompts}")
    print(f"Output dir: {output_dir}")

    pw, context, page = await launch_browser(headless=not args.headful)
    try:
        await page.goto("https://chatgpt.com/", wait_until="domcontentloaded")
        if not await check_login_status(page):
            print(
                "Not logged in. Run:  python image_gen.py auth",
                file=sys.stderr,
            )
            return 2
        results = await generate_batch(page, prompts, output_dir)
    finally:
        try:
            await context.close()
        except Exception:
            pass
        await pw.stop()

    log_path = output_dir / "results.json"
    log_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    ok = sum(1 for r in results if r["ok"])
    print(f"\nDone: {ok}/{len(prompts)} downloaded -> {output_dir}")
    return 0 if ok > 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="image_gen")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("auth", help="interactive one-time login to ChatGPT")

    g = sub.add_parser("generate", help="generate images from a prompts JSON file")
    g.add_argument("prompts_positional", nargs="?", help="optional prompts.json path")
    g.add_argument("--prompts", help="path to prompts JSON file")
    g.add_argument(
        "--output",
        default=os.path.join(HERE, "data", "output"),
        help="output directory for generated images",
    )
    g.add_argument(
        "--headful",
        action="store_true",
        help="show the browser window (default: headless)",
    )

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate":
        # Allow `generate "C:/prompts.json"` shorthand
        if not args.prompts and args.prompts_positional:
            args.prompts = args.prompts_positional
        if not args.prompts:
            parser.error("generate requires --prompts <path> (or a positional path)")
        return asyncio.run(cmd_generate(args))

    if args.command == "auth":
        return asyncio.run(cmd_auth(args))

    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
