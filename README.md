# Plain-English test cases -> automated browser tests (100% free tools)

Give it a test case in plain English; it drives a real browser (Playwright) with a free AI model and reports **PASS / FAIL / BLOCKED**.

    python run_test.py "Open https://phptravels.com/demo and verify the page has a form asking for a name and email"

## Tech stack
Python 3 · Playwright (Chromium) · **Ollama** running a free open-source model locally, with a built-in **rules engine** as an automatic no-download fallback. No API key, no account, no paid service, no extra Python packages beyond Playwright.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

**Local model (free, no key)**
1. Install Ollama: https://ollama.com (Windows: `winget install Ollama.Ollama`)
2. `ollama pull qwen2.5:7b-instruct` (about 4.7 GB; on a weak laptop use `llama3.2:3b` and pass `--model llama3.2:3b`)

Advanced: any other local server that speaks the OpenAI chat format and needs no key (for example LM Studio) works with `--provider openai --base-url http://localhost:1234/v1 --model <name>`.

## Modes (`--provider`)

| Mode | What it uses | When |
|---|---|---|
| `auto` (default) | Local Ollama model if it is running and downloaded, otherwise the rules engine (a note is printed) | normal use |
| `ollama` | Local AI model only (errors if unavailable) | free-form test sentences |
| `rules` | No model at all, built-in parser | no download possible, fast, repeatable |

**Rules engine** understands simple steps joined by "and", "then", commas or new lines: `open <url>`, `click <button/link text>`, `type "<text>" in <field>`, `enter <field> "<text>"`, `select "<option>" from <dropdown>`, `log in with email X and password Y`, `press Enter`, `wait 3 seconds`, and checks such as `verify "<exact text>" is shown`, `verify the dashboard is not shown`, `verify the url contains X`, `verify the title contains "X"`. It refuses (BLOCKED) steps it cannot understand or checks that are too complex to judge by keywords, instead of guessing. It cannot invent credentials, so "log in as a customer" needs an AI model or explicit credentials.

If `ollama pull` fails with a network/DNS error: retry, run `ipconfig /flushdns`, switch Windows DNS to 1.1.1.1 / 8.8.8.8, or use a mobile hotspot. Meanwhile `auto` keeps working through the rules engine.

## Run

```bash
python run_test.py "Log in as a customer and verify the dashboard is shown" --url https://example.com
python run_test.py --file tests/sample_tests.txt --allowed-domains phptravels.com --headed
python run_test.py "..." --model llama3.2:3b --max-steps 30
```
Output: live step log, verdict per test, `report.html` (steps + screenshots), `report.json`, screenshots in `artifacts/`. Exit code 0 only if all tests PASS. Credentials a test needs must be written in the test case.

Self-tests (no model, no internet): `python tests/test_plumbing.py`, `python tests/test_llm_http.py`, `python tests/test_rules.py`.

## How it works

1. Playwright opens the start URL (`--url`, or the model uses `goto` with a URL from the test text).
2. A JS snapshot lists every visible interactive element with a number (`[7] <input> 'Email'`) in the page and up to 4 iframes, plus headings and visible text. Nothing is site-specific.
3. The model sees the test case + snapshot and replies with ONE JSON action (`click`, `type`, `select`, `press`, `scroll`, `wait`, `goto`, or `finish`). Plain JSON means any chat model works, tool-calling support is not needed. Malformed replies are reported back to the model so it can correct itself.
4. The action runs, a fresh snapshot is sent back, repeat (max 25 steps, 300 s).
5. **Anti-fake-PASS check:** a PASS must quote text that is on the page; the runner re-reads the page and downgrades the verdict to FAIL otherwise.

## Docker (extra isolation)
```bash
docker build -t nl-tester .
docker run --rm -e OLLAMA_HOST=http://host.docker.internal:11434 nl-tester "Verify the page has a demo form" --url https://phptravels.com/demo --allowed-domains phptravels.com
```
CI (`.github/workflows/ci.yml`) runs the offline self-tests on every push.

## Security

* No keys or secrets are needed: the model runs on your machine and page text never leaves it. (`.gitignore` still covers `.env` and key files as a precaution.)
* `--allowed-domains a.com,b.com` blocks the model's `goto` *and* any page-driven navigation to other sites. Without it, navigation is limited to http(s) and refuses localhost, private/link-local addresses and `javascript:`/`file:`/`data:` schemes.
* Passwords typed by the model are masked in logs and reports; password fields are not echoed in snapshots.
* Page text is untrusted: the model only has browser actions (no files, no shell), a PASS needs on-page evidence, and runs have step/time limits. Prompt injection is reduced, not eliminated: use `--allowed-domains` and test accounts only.
* Browser context: downloads off, no permissions, service workers blocked. Screenshots may contain page content, so don't publish `artifacts/` after testing private data.

## Limitations

* Rules mode is keyword-based: it can be fooled by unusual wording and only checks what is visible as text; use quoted exact text for dependable checks.
* Free/small models are less reliable than large ones: vague tests, long pages or complex flows can give wrong verdicts or wander. Use clear test steps; try a larger local model (for example `ollama pull llama3.1:8b`) if a small one struggles. The evidence check catches invented proof, not a wrong interpretation.
* Non-deterministic and slow on CPU (a step can take several seconds locally).
* Not handled: CAPTCHA/2FA (reported as BLOCKED), file upload, drag-and-drop, closed shadow DOM, more than 4 iframes, very long pages (snapshot is truncated).
* Test data must be in the test case.
