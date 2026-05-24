"""ChatGPT image-gen automation, ported from the extension's content.js."""

import asyncio
import datetime as _dt
import json
import os
import time
import uuid
from pathlib import Path

import httpx

from prompts import slugify


class RateLimited(Exception):
    pass


class GenerationFailed(Exception):
    pass


class ContentDenied(Exception):
    pass


LOADING_SELECTOR = '[data-testid="image-gen-loading-state-dots"]'
SEND_BUTTON = '[data-testid="send-button"]'
COMPOSER = '#prompt-textarea[contenteditable="true"]'


def log(msg: str, level: str = "info"):
    prefix = {"info": "[info]", "success": "[ ok ]", "error": "[err ]"}.get(
        level, "[info]"
    )
    print(f"{prefix} {msg}", flush=True)


async def _count_generated(page) -> int:
    return await page.evaluate(
        "() => document.querySelectorAll('img[alt^=\"Generated image:\"]').length"
    )


async def _last_image_src(page):
    return await page.evaluate(
        """() => {
            const imgs = document.querySelectorAll('img[alt^="Generated image:"]');
            return imgs.length ? imgs[imgs.length - 1].src : null;
        }"""
    )


async def _last_assistant_text(page) -> str:
    """Full innerText of the most recent conversation turn (assistant reply).

    Used to capture refusal / denial text when we don't get an image, so we
    can build a corpus of denial phrasings across runs.
    """
    try:
        return await page.evaluate(
            """() => {
                const turns = document.querySelectorAll('[data-testid^="conversation-turn-"]');
                if (turns.length === 0) return '';
                const last = turns[turns.length - 1];
                return (last.innerText || '').trim();
            }"""
        )
    except Exception:
        return ""


def log_no_image_response(
    output_dir: Path,
    prompt: str,
    error_type: str,
    error_msg: str,
    response_text: str,
) -> None:
    """Append a row to no_image_log.jsonl capturing what ChatGPT said instead
    of generating an image. Builds a corpus of refusal/denial variations
    that future detection rules can target.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _dt.datetime.now().isoformat(timespec="seconds"),
        "error_type": error_type,
        "error_msg": error_msg,
        "prompt": prompt,
        "response_text": response_text,
    }
    log_path = output_dir / "no_image_log.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


async def _check_for_errors(page):
    text = await page.evaluate(
        """() => {
            const turns = document.querySelectorAll('[data-testid^="conversation-turn-"]');
            if (turns.length === 0) return '';
            const last = turns[turns.length - 1];
            const ps = last.querySelectorAll('p[data-is-last-node], p');
            let out = '';
            ps.forEach(p => { out += p.textContent + '\\n'; });
            return out;
        }"""
    )
    if "hit the team plan limit" in text or "hit the limit for image generation" in text:
        raise RateLimited("image generation cap reached")
    if "experienced an error when generating" in text:
        raise GenerationFailed("model errored during generation")
    if (
        "violate our guardrails" in text
        or "content policy" in text
        or "unable to generate" in text
    ):
        raise ContentDenied("prompt rejected by content policy")


async def start_new_chat(page):
    await page.goto("https://chatgpt.com/", wait_until="domcontentloaded")
    await page.wait_for_selector(COMPOSER, timeout=30000)


async def type_prompt(page, text: str):
    await page.wait_for_selector(COMPOSER, timeout=15000)
    await page.evaluate(
        """(text) => {
            const el = document.querySelector('#prompt-textarea[contenteditable="true"]');
            el.focus();
            el.innerHTML = '<p>' + text.replace(/</g, '&lt;') + '</p>';
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        text,
    )


async def submit_prompt(page):
    await page.wait_for_selector(SEND_BUTTON, timeout=15000)
    await page.click(SEND_BUTTON)


async def wait_for_image_generation(page, prev_count: int, timeout_s: int = 360):
    """Wait until a new generated image appears in the conversation."""
    # Wait for loading indicator (best-effort)
    try:
        await page.wait_for_selector(LOADING_SELECTOR, timeout=30000)
        log("image generation in progress...")
    except Exception:
        log("loading indicator not found, checking for image directly...")

    poll = 0.25
    deadline = time.time() + min(300, timeout_s)
    while time.time() < deadline:
        await _check_for_errors(page)
        present = await page.evaluate(
            f"() => !!document.querySelector('{LOADING_SELECTOR}')"
        )
        if not present:
            break
        await asyncio.sleep(poll)

    # Now wait for the image element
    double_handled = False
    img_deadline = time.time() + 60
    while time.time() < img_deadline:
        await _check_for_errors(page)
        if await _count_generated(page) > prev_count:
            log("image generated", "success")
            return
        if not double_handled:
            multigen = await page.query_selector(
                '[data-testid="image-paragen-multigen"]'
            )
            if multigen:
                log("double-render detected — picking image 1...")
                clicked = await page.evaluate(
                    """() => {
                        const mg = document.querySelector('[data-testid="image-paragen-multigen"]');
                        if (!mg) return false;
                        for (const b of mg.querySelectorAll('button')) {
                            if (b.textContent.includes('Image 1')) { b.click(); return true; }
                        }
                        return false;
                    }"""
                )
                double_handled = bool(clicked)
        await asyncio.sleep(poll)

    raise GenerationFailed("timed out waiting for image to render")


async def download_image(page, prompt: str, output_dir: Path) -> Path:
    src = await _last_image_src(page)
    if not src:
        raise GenerationFailed("no generated image found in DOM")

    # Forward ChatGPT cookies to httpx so the image URL is fetchable
    cookies = await page.context.cookies()
    jar = {c["name"]: c["value"] for c in cookies}

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(prompt)
    ext = ".png"
    lower = src.split("?")[0].lower()
    for candidate in (".png", ".jpg", ".jpeg", ".webp"):
        if lower.endswith(candidate):
            ext = candidate
            break

    # uuid4 already makes collisions astronomically unlikely, but guard
    # anyway so a re-run into an existing dir can never overwrite a file.
    while True:
        fpath = output_dir / f"{slug}-{uuid.uuid4()}{ext}"
        if not fpath.exists():
            break

    async with httpx.AsyncClient(
        cookies=jar,
        timeout=60.0,
        headers={"User-Agent": "Mozilla/5.0 (chatgpt-image-generator)"},
    ) as client:
        resp = await client.get(src)
        resp.raise_for_status()
        fpath.write_bytes(resp.content)

    log(f"downloaded -> {fpath.name}", "success")
    return fpath


async def generate_one(page, prompt: str, output_dir: Path) -> Path:
    prev = await _count_generated(page)
    await type_prompt(page, prompt)
    await submit_prompt(page)
    await wait_for_image_generation(page, prev)
    return await download_image(page, prompt, output_dir)


async def _record_no_image(page, output_dir: Path, prompt: str, exc: Exception):
    """Capture the assistant's text reply when generation produced no image."""
    text = await _last_assistant_text(page)
    log_no_image_response(
        output_dir, prompt, type(exc).__name__, str(exc), text
    )


async def generate_batch(page, prompts, output_dir: Path):
    """Generate images for every prompt. Yields (index, prompt, result_path_or_error)."""
    await start_new_chat(page)
    results = []
    for i, prompt in enumerate(prompts):
        log(f"[{i + 1}/{len(prompts)}] {prompt[:70]}")
        try:
            path = await generate_one(page, prompt, output_dir)
            results.append({"prompt": prompt, "ok": True, "path": str(path)})
        except RateLimited as e:
            await _record_no_image(page, output_dir, prompt, e)
            log(f"rate limited — stopping: {e}", "error")
            results.append({"prompt": prompt, "ok": False, "error": "rate_limited"})
            break
        except ContentDenied as e:
            await _record_no_image(page, output_dir, prompt, e)
            log(f"content denied: {e}", "error")
            results.append({"prompt": prompt, "ok": False, "error": "content_denied"})
            await asyncio.sleep(5)
        except GenerationFailed as e:
            await _record_no_image(page, output_dir, prompt, e)
            log(f"generation failed: {e}", "error")
            results.append({"prompt": prompt, "ok": False, "error": str(e)})
            await asyncio.sleep(30)
        except Exception as e:
            try:
                await _record_no_image(page, output_dir, prompt, e)
            except Exception:
                pass
            log(f"unexpected error: {e}", "error")
            results.append({"prompt": prompt, "ok": False, "error": str(e)})
            await asyncio.sleep(10)
    return results
