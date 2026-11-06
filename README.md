# Task 2 – Plain-English test cases -> automated browser tests

Give it a test case in plain English; it drives a real browser (Playwright) and reports **PASS / FAIL / BLOCKED**.

    python run_test.py "Open https://phptravels.com/demo and verify the page has a form asking for a name and email"

## Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
export ANTHROPIC_API_KEY=sk-ant-...                     # Windows: set ANTHROPIC_API_KEY=...
```

## Run

```bash
python run_test.py "Log in as a customer and verify the dashboard is shown" --url https://example.com
python run_test.py --file tests/sample_tests.txt          # one test per line
python run_test.py "..." --headed                         # watch the browser (good for the screen recording)
python run_test.py "..." --model claude-opus-5-5 --max-steps 30
```
Output: live step log, `report.html` (steps + screenshots),  verdict per test, `report.json`, and a final screenshot in `artifacts/`. Exit code 0 only if all tests PASS.
Credentials or data the test needs must be written in the test case, e.g. "log in with email a@b.com and password xyz".

Offline self-check of the browser plumbing (no API key): `python tests/test_plumbing.py` (uses `demo_site/login.html` and a scripted stand-in for the model).

## Docker (extra isolation)

```bash
docker build -t nl-tester .
docker run --rm -e ANTHROPIC_API_KEY nl-tester "Verify the page has a demo request form" --url https://phptravels.com/demo --allowed-domains phptravels.com
```
CI (`.github/workflows/ci.yml`) runs the offline self-test on every push.

## How it works

1. Playwright opens the start URL (`--url`, or the model calls `goto` using a URL in the test text).
2. Each step, a JS snapshot lists every visible interactive element with a number (`[7] <input> 'Email' type=email`) plus headings and visible text. Nothing site-specific, no selectors.
3. The model (Claude, tool use) reads the test case + snapshot and calls ONE tool: `click`, `type`, `select`, `press`, `scroll`, `wait`, `goto`, or `finish(verdict, reason, evidence)`.
4. The action runs, a fresh snapshot is sent back, repeat (max 25 steps).
5. **Anti-hallucination check:** a PASS must include an `evidence` quote; the runner re-reads the page and downgrades PASS to FAIL if that text is not actually there.

Because the page is re-read every step, it works on any site and survives UI changes.

## Security

* **API key** is read only from `ANTHROPIC_API_KEY`; never written to files or logs. Don't commit it (`.gitignore` excludes reports/artifacts).
* **Restrict where the browser may go:** `--allowed-domains example.com,phptravels.com` blocks the model's `goto` *and* any page-driven navigation to other sites. Without it, model navigation is still limited to http(s) and refuses localhost / private / link-local addresses and `javascript:`, `file:`, `data:` schemes.
* **Passwords** typed by the model are masked in logs and `report.json`; password fields are never echoed back in page snapshots.
* **Prompt injection:** page text is treated as untrusted data; the model has no tools beyond browser actions; no file/shell access; PASS needs on-page evidence. Use `--allowed-domains` and test accounts, never real credentials or production data.
* Browser context: downloads off, no permissions granted, service workers blocked, per-test time limit (`--max-seconds`, default 300) and step limit.
* Screenshots in `artifacts/` can contain page content: don't publish them if a test touched private data.

## Limitations

* The final verdict is still a model judgement; the evidence check catches invented proof, not a wrong interpretation. Vague test cases give vague results.
* Non-deterministic: the same test may take different paths run to run. Costs API tokens per step.
* Not handled: CAPTCHA/2FA (reported as BLOCKED), file upload, drag-and-drop, closed shadow DOM, more than 4 iframes, very long pages (only first 150 elements / 2500 chars of text shown).
* Test data must be in the test case; the model won't know passwords. Demo sites with a public credential on the page may be used.
* Page text is untrusted; the prompt tells the model to ignore instructions found in pages, but prompt injection is not fully solved.
