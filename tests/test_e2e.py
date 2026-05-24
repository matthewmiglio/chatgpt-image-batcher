"""End-to-end test: runs the real `generate` flow against ChatGPT.

When this passes, the program's complete pipeline is verified:
  load prompts -> launch browser -> auth check -> type/submit prompt ->
  wait for image -> download to output dir.

Requires a one-time `python image_gen.py auth` first (persistent profile).
Skips automatically if not logged in.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from browser import launch_browser, check_login_status  # noqa: E402
from chatgpt import generate_batch  # noqa: E402
from prompts import load_prompts  # noqa: E402

import image_gen  # noqa: E402


pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("e2e_output")


@pytest.fixture(scope="module")
def prompts_file(tmp_path_factory) -> Path:
    """Single prompt file in the exact format from the spec."""
    p = tmp_path_factory.mktemp("e2e_prompts") / "prompts.json"
    p.write_text(
        json.dumps({"prompt1": "a single small red apple on a white background"})
    )
    return p


async def _ensure_logged_in() -> bool:
    pw, context, page = await launch_browser(headless=False)
    try:
        await page.goto("https://chatgpt.com/", wait_until="domcontentloaded")
        return await check_login_status(page)
    finally:
        try:
            await context.close()
        except Exception:
            pass
        await pw.stop()


def test_logged_in_or_skip():
    """Gate: every following e2e test depends on a live session."""
    logged_in = asyncio.run(_ensure_logged_in())
    if not logged_in:
        pytest.skip("not logged in — run: python image_gen.py auth")


def test_load_prompts_from_spec_format(prompts_file):
    """The spec's example JSON shape must work."""
    prompts = load_prompts(str(prompts_file))
    assert len(prompts) == 1
    assert "apple" in prompts[0]


def test_generate_downloads_image_end_to_end(prompts_file, output_dir):
    """The full pipeline — when this passes, the program works end-to-end."""
    rc = image_gen.main(
        [
            "generate",
            "--prompts",
            str(prompts_file),
            "--output",
            str(output_dir),
        ]
    )
    assert rc == 0, "generate command returned non-zero"

    images = [
        p
        for p in output_dir.iterdir()
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    assert images, f"no image files written to {output_dir}"
    assert images[0].stat().st_size > 1000, "downloaded image is suspiciously small"

    results = json.loads((output_dir / "results.json").read_text())
    assert results and results[0]["ok"], f"results.json says failure: {results}"
    assert Path(results[0]["path"]).exists()
