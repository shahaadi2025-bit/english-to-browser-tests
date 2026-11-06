import json, os, re, time
from playwright.sync_api import sync_playwright
from .actions import run_action, host_allowed
from .snapshot import take_snapshot, render

BLANK = {"url": "about:blank", "title": "", "headings": [], "items": [], "text": ""}


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def _snap(page):
    return BLANK if page.url == "about:blank" else take_snapshot(page)


def _check_pass(page, evidence):
    """A PASS needs a quote that is really on the page right now (blocks hallucinated passes)."""
    s = _snap(page)
    hay = _norm(" ".join([s["text"], s["title"], s["url"], *s["headings"], *[x["text"] for x in s["items"]]]))
    return bool(evidence) and _norm(evidence) in hay


def run_test(case, brain, start_url=None, headed=False, max_steps=25, shots_dir=None, log=print,
             allowed_domains=None, max_seconds=300):
    """Returns dict(test, verdict, reason, evidence, steps, seconds). Verdict: PASS / FAIL / BLOCKED / ERROR."""
    t0, steps = time.time(), []
    result = {"test": case, "verdict": "ERROR", "reason": "", "evidence": "", "steps": steps}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=False,
                                  permissions=[], service_workers="block")
        if allowed_domains:   # hard guard: page-driven navigations may not leave the allowed sites
            from urllib.parse import urlparse

            def guard(route):
                req = route.request
                if req.is_navigation_request() and urlparse(req.url).scheme in ("http", "https") \
                        and not host_allowed(urlparse(req.url).hostname, allowed_domains):
                    return route.abort()
                return route.continue_()
            ctx.route("**/*", guard)
        page = ctx.new_page()
        items_by_id = {}
        try:
            if start_url:
                page.goto(start_url if "://" in start_url else "https://" + start_url,
                          wait_until="domcontentloaded", timeout=30000)
            intro = ("TEST CASE:\n" + case + "\n\n" +
                     ("The browser is already on the start page.\n\n" if start_url else
                      "No start URL was given: take it from the test case and use goto.\n\n"))
            snap0 = _snap(page)
            observe = getattr(brain, "observe", lambda _s: None)
            observe(snap0)
            items_by_id = {x["id"]: x for x in snap0["items"]}
            messages = [{"role": "user", "content": intro + "CURRENT PAGE:\n" + render(snap0)}]
            for i in range(1, max_steps + 1):
                if time.time() - t0 > max_seconds:
                    result.update(verdict="FAIL", reason=f"Time limit of {max_seconds}s exceeded.")
                    break
                if len(ctx.pages) > 1:          # a link opened a new tab: follow it
                    page = ctx.pages[-1]
                content, calls = brain.next_step(messages)
                messages.append({"role": "assistant", "content": content})
                if not calls:
                    result.update(reason="model made no tool call")
                    break
                tid, name, args = calls[0]
                shown = dict(args)
                if name == "type" and items_by_id.get(args.get("id"), {}).get("type") == "password":
                    shown["text"] = "********"          # never write secrets to logs/reports
                log(f"  step {i}: {name} {json.dumps(shown)[:120]}")
                steps.append({"n": i, "action": name, "args": shown, "url": page.url})
                if name == "finish":
                    verdict, reason = args.get("verdict", "FAIL"), args.get("reason", "")
                    ev = args.get("evidence", "") or ""
                    if verdict == "PASS" and not _check_pass(page, ev):
                        verdict = "FAIL"
                        reason = f"Model claimed PASS but its evidence {ev!r} is not on the page. Its reason: {reason}"
                    result.update(verdict=verdict, reason=reason, evidence=ev)
                    break
                try:
                    note = run_action(page, name, args, allowed_domains)
                    page.wait_for_timeout(800)
                except Exception as e:
                    note = "ACTION FAILED: " + str(e).splitlines()[0][:200]
                steps[-1]["note"] = note
                if shots_dir:
                    try:
                        os.makedirs(shots_dir, exist_ok=True)
                        page.screenshot(path=os.path.join(shots_dir, f"step{i:02d}.png"))
                    except Exception:
                        pass
                snap = _snap(page)
                observe(snap)
                items_by_id = {x["id"]: x for x in snap["items"]}
                messages.append({"role": "user", "content":
                                 f"Result of your last action: {note}\n\nCURRENT PAGE:\n{render(snap)}"})
            else:
                result.update(verdict="FAIL", reason=f"No verdict after {max_steps} steps.")
        except Exception as e:
            result.update(verdict="ERROR", reason=f"{type(e).__name__}: {str(e).splitlines()[0][:300]}")
        finally:
            if shots_dir:
                try:
                    os.makedirs(shots_dir, exist_ok=True)
                    page.screenshot(path=os.path.join(shots_dir, "final.png"))
                except Exception:
                    pass
            browser.close()
    result["seconds"] = round(time.time() - t0, 1)
    return result
