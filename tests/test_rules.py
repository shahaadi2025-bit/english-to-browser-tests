"""Tests the no-model rules engine on local pages: python tests/test_rules.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nl_tester.rules import RulesBrain, split_steps
from nl_tester.runner import run_test

LOGIN = "file://" + os.path.join(ROOT, "demo_site", "login.html")
FRAME = "file://" + os.path.join(ROOT, "demo_site", "iframe.html")

assert split_steps('Open https://phptravels.com/demo and verify the page has a form') == \
    ['Open https://phptravels.com/demo', 'verify the page has a form']
assert len(split_steps('Log in with email a@b.com and password xyz, then verify the dashboard is shown')) == 2

CASES = [
    ("Log in with email customer@demo.test and password secret and verify the dashboard is shown", LOGIN, "PASS"),
    ('Type "customer@demo.test" in the email field, type "secret" in the password field, click Sign in, verify "Welcome back" is shown', LOGIN, "PASS"),
    ("Log in with email customer@demo.test and password WRONG and verify the dashboard is shown", LOGIN, "FAIL"),
    ('Click Sign in and verify "Invalid credentials" is displayed', LOGIN, "PASS"),
    ("Verify the dashboard is not shown", LOGIN, "PASS"),
    ("Verify the page shows a checkout button", LOGIN, "FAIL"),
    ("Click the Pay now button and verify the order is confirmed", LOGIN, "FAIL"),
    ("Log in as a customer and verify the dashboard is shown", LOGIN, "BLOCKED"),
    ("Do something clever with the page", LOGIN, "BLOCKED"),
    ("Verify that submitting the form with all fields empty does not succeed and shows validation", LOGIN, "BLOCKED"),
    ("Verify the user can complete the whole booking flow and receives a confirmation email with the invoice attached", LOGIN, "BLOCKED"),
    ('Enter "a@b.co" in the email field, click Send and verify "Frame submitted" is shown', FRAME, "PASS"),
]
bad = 0
for case, url, want in CASES:
    r = run_test(case, RulesBrain(), url, log=lambda *_: None)
    ok = r["verdict"] == want
    bad += not ok
    print(("ok  " if ok else "BAD ") + f"{want:<7} got {r['verdict']:<7} | {case[:60]}  -> {r['reason'][:70]}")
# regression: ONE brain object reused for several tests (as run_test.py does) must not leak state
shared = RulesBrain()
for case, want in [('Verify "Demo Shop" is shown', "PASS"), ('Verify "Demo Shop" is shown', "PASS"),
                   ("Verify the page shows a checkout button", "FAIL"), ('Verify "Demo Shop" is shown', "PASS")]:
    r = run_test(case, shared, LOGIN, log=lambda *_: None)
    assert r["verdict"] == want, (case, r["verdict"], r["reason"])
print("shared-brain OK")
assert not bad, f"{bad} rules test(s) failed"
print("rules OK")

from nl_tester.llm import make_brain
b = make_brain("auto", None, "http://127.0.0.1:9", log=lambda *_: None)   # nothing listens there -> must fall back
assert b.__class__.__name__ == "RulesBrain", b
print("auto fallback OK")
