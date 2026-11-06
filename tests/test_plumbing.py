"""Offline check of the browser plumbing with a scripted 'model' (no API key needed): python tests/test_plumbing.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl_tester.llm import Brain
from nl_tester.runner import run_test

URL = "file://" + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_site", "login.html")


class Scripted(Brain):
    def __init__(self, steps): self.steps, self.i = steps, 0
    def next_step(self, messages):
        name, args = self.steps[self.i]; self.i += 1
        if callable(args): args = args(messages[-1])
        blk = {"type": "tool_use", "id": f"t{self.i}", "name": name, "input": args}
        return [blk], [(f"t{self.i}", name, args)]


def find(msg, text):
    body = msg["content"] if isinstance(msg["content"], str) else msg["content"][0]["content"]
    for line in body.splitlines():
        if line.startswith("[") and text in line:
            return int(line[1:line.index("]")])
    raise AssertionError(f"{text} not in snapshot")


good = Scripted([
    ("type", lambda m: {"id": find(m, "Email"), "text": "customer@demo.test"}),
    ("type", lambda m: {"id": find(m, "Password"), "text": "secret"}),
    ("click", lambda m: {"id": find(m, "Sign in")}),
    ("finish", {"verdict": "PASS", "reason": "dashboard shown", "evidence": "Customer Dashboard"}),
])
r = run_test("login", good, URL, log=lambda *_: None); print(r["verdict"], r["reason"]); assert r["verdict"] == "PASS"

fake = Scripted([("finish", {"verdict": "PASS", "reason": "sure", "evidence": "Order confirmed"})])
r = run_test("x", fake, URL, log=lambda *_: None); print(r["verdict"], r["reason"][:70]); assert r["verdict"] == "FAIL"

bad = Scripted([
    ("type", lambda m: {"id": find(m, "Email"), "text": "wrong@demo.test"}),
    ("click", lambda m: {"id": find(m, "Sign in")}),
    ("finish", {"verdict": "FAIL", "reason": "error shown", "evidence": "Invalid credentials"}),
])
r = run_test("bad login", bad, URL, log=lambda *_: None); print(r["verdict"]); assert r["verdict"] == "FAIL"
print("plumbing OK")

# ---- security checks ----
from nl_tester.actions import check_url
for u in ["javascript:alert(1)", "file:///etc/passwd", "http://localhost:8000", "http://169.254.169.254/", "http://10.0.0.5", "ftp://x.com"]:
    try: check_url(u); raise SystemExit("NOT BLOCKED: " + u)
    except ValueError: pass
assert check_url("example.com") == "https://example.com"
try: check_url("https://evil.com", ["example.com"]); raise SystemExit("allowlist failed")
except ValueError: pass
assert check_url("https://www.example.com/x", ["example.com"])

logs = []
pw = Scripted([("type", lambda m: {"id": find(m, "Password"), "text": "TopSecret123"}),
               ("finish", {"verdict": "FAIL", "reason": "done"})])
r = run_test("pw", pw, URL, log=logs.append)
assert "TopSecret123" not in str(logs) + str(r), "password leaked"
print("security OK")

IFRAME = "file://" + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_site", "iframe.html")
fr = Scripted([("type", lambda m: {"id": find(m, "Email"), "text": "a@b.co"}),
               ("click", lambda m: {"id": find(m, "Send")}),
               ("finish", {"verdict": "PASS", "reason": "frame form works", "evidence": "Frame submitted"})])
r = run_test("iframe", fr, IFRAME, log=lambda *_: None); print(r["verdict"], r["reason"]); assert r["verdict"] == "PASS"
from nl_tester.report import write_html
import tempfile; write_html([r], os.path.join(tempfile.gettempdir(), "r.html")); print("iframe + report OK")
