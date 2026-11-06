#!/usr/bin/env python3
"""Run plain-English test cases in a browser.  See README.md."""
import argparse, json, os, sys
from nl_tester.llm import make_brain
from nl_tester.report import write_html
from nl_tester.runner import run_test


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("test", nargs="?", help="test case in plain English (or use --file)")
    ap.add_argument("--file", help="text file with one test case per line (blank lines and # comments ignored)")
    ap.add_argument("--url", help="start URL (optional if the test case mentions one)")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--max-steps", type=int, default=25)
    ap.add_argument("--provider", choices=["auto", "ollama", "rules", "openai"], default=os.environ.get("NLT_PROVIDER", "auto"),
                    help="auto (default) = local Ollama model if available, else built-in rules engine; ollama; rules = no model at all; openai = any key-less OpenAI-compatible local server")
    ap.add_argument("--model", help="model name (default qwen2.5:7b-instruct for ollama)")
    ap.add_argument("--base-url", help="ollama host (default http://localhost:11434) or the OpenAI-compatible base URL")
    ap.add_argument("--allowed-domains", help="comma-separated; the browser may only visit these sites (recommended)")
    ap.add_argument("--max-seconds", type=int, default=300, help="time limit per test")
    ap.add_argument("--report", default="report.json", help="where to write the JSON report")
    a = ap.parse_args()

    cases = []
    if a.file:
        cases += [l.strip() for l in open(a.file, encoding="utf-8") if l.strip() and not l.startswith("#")]
    if a.test:
        cases.append(a.test)
    if not cases:
        ap.error("give a test case or --file")

    allowed = [d.strip().lower() for d in a.allowed_domains.split(",") if d.strip()] if a.allowed_domains else None
    if a.url and not a.url.startswith(("http://", "https://", "file://")) and "://" in a.url:
        sys.exit("--url must be http(s)")
    brain = make_brain(a.provider, a.model, a.base_url)
    results = []
    for n, case in enumerate(cases, 1):
        print(f"\n=== Test {n}/{len(cases)}: {case}")
        r = run_test(case, brain, a.url, a.headed, a.max_steps, shots_dir=f"artifacts/test{n}",
                     allowed_domains=allowed, max_seconds=a.max_seconds)
        results.append(r)
        print(f"{r['verdict']}: {r['reason']}" + (f"\n  evidence: {r['evidence']!r}" if r["evidence"] else ""))
    json.dump(results, open(a.report, "w"), indent=2)
    print("HTML report:", write_html(results))
    print("\n==== SUMMARY ====")
    for r in results:
        print(f"{r['verdict']:<8} {r['test'][:90]}")
    sys.exit(0 if all(r["verdict"] == "PASS" for r in results) else 1)


if __name__ == "__main__":
    main()
