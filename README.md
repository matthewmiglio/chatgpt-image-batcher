# chatgpt-image-batcher

<p align="center">
  <img src="docs/images/hero.png" alt="A robot in a beret painting a confused chef-hatted cat while a tiny dragon photobombs" width="640">
</p>

Playwright-driven CLI that batch-feeds prompts to ChatGPT's image
generator and dumps the results into a folder. No OpenAI API key — it
drives the real `chatgpt.com` web UI with a persistent browser profile.

JSON in. PNGs out. Runs headless.

This is the grown-up successor to a [Chrome
extension](https://chrome.google.com/webstore) I'd been running — same
flow, now a proper Python app with tests.

## Setup

```bash
poetry install
poetry run playwright install chromium
```

## 1. One-time login

```bash
python image_gen.py auth
```

A Chromium window opens. Log into ChatGPT, then **close the window** —
your session is saved to `data/browser_profile/` and reused on every run.

## 2. Drop your prompts in a JSON file

Either a dict (key names are ignored, values are used in order):

```json
{
  "prompt1": "a cat doing a backflip over a stack of pancakes",
  "prompt2": "a corgi astronaut planting a flag on the moon",
  "prompt3": "a robot painting a sunset, oil on canvas"
}
```

Or a plain list:

```json
["a cat doing a backflip", "a corgi astronaut", "a robot painting"]
```

A sample sits at [`examples/prompts.json`](examples/prompts.json).

## 3. Generate

```bash
python image_gen.py generate --prompts "C:/prompts.json" --output "C:/where/you/want/them"
```

Shorthand (positional prompts path):

```bash
python image_gen.py generate "C:/prompts.json"
```

Each image is saved as `<slug-of-prompt>-<uuid>.png`. A `results.json` log
is written alongside the images.

### Flags

| flag                  | default          | meaning                                |
| --------------------- | ---------------- | -------------------------------------- |
| `--prompts <path>`    | (required)       | JSON file of prompts                   |
| `--output <dir>`      | `data/output/`   | where images land                      |
| `--headful`           | off              | show the browser window                |

## How it works

It's a faithful port of my old Chrome extension's `content.js`:

1. Open `chatgpt.com` in a Playwright-driven Chromium with a persistent profile.
2. For each prompt: type into the composer, click send, wait for the loading dots to disappear, wait for the new `<img alt="Generated image: ...">` to appear, handle the "Image 1 / Image 2" double-render picker if it shows up.
3. Fetch the image URL using the browser's session cookies and write the bytes to disk.

Failure modes the extension hit, all preserved here: rate-limit detection
(stops the batch), content-policy denials (skips and continues),
generation errors (waits 30s and continues).

## Tests

```bash
poetry run pytest                # unit tests (15 of them, ~2s)
poetry run pytest -m e2e         # real end-to-end run against ChatGPT
poetry run pytest -m "not e2e"   # everything except e2e
```

The e2e test runs the full pipeline — submits a real prompt, waits for
ChatGPT to render an image, downloads it, and asserts the file exists
and is a valid PNG. When all 18 tests pass, the whole thing works
end-to-end.

## Project layout

```
image_gen.py              # CLI entry point
src/
  browser.py              # Playwright launch + persistent profile + auth
  chatgpt.py              # type / submit / wait / download
  prompts.py              # JSON loader + slugify
tests/
  test_prompts.py         # prompts.json shapes, slugify edge cases
  test_cli.py             # argparse contract
  test_e2e.py             # full pipeline against real ChatGPT
docs/images/hero.png      # the silly robot above
examples/prompts.json     # sample input file
```

## Notes

- Needs a ChatGPT account with image-gen access (Plus/Pro/Team).
- The persistent profile lives in `data/browser_profile/` — gitignored.
  Re-run `auth` if your cookies expire.
- ChatGPT changes their DOM selectors constantly. If a run hangs on
  `Timeout waiting for: [data-testid="..."]`, the selectors in
  `src/chatgpt.py` probably need a tweak.
