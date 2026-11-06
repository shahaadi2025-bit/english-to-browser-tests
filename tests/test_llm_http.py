"""Tests the real HTTP/JSON path with a fake Ollama and a fake OpenAI-compatible server (no model, no internet)."""
import json, os, re, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl_tester.llm import OllamaBrain, OpenAICompatBrain, parse_action
from nl_tester.runner import run_test

URL = "file://" + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_site", "login.html")
calls = {"n": 0}


def sid(text, label):
    return int(re.search(r"\[(\d+)\][^\n]*" + label, text).group(1))


def decide(last):
    calls["n"] += 1
    n = calls["n"]
    if n == 1:  return "Sure! ```json\n" + json.dumps({"action": "type", "id": sid(last, "Email"), "text": "customer@demo.test"}) + "\n```"  # fenced
    if n == 2:  return "I will now log in"                                                                                                 # invalid -> must recover
    if n == 3:  return json.dumps({"action": "type", "id": str(sid(last, "Password")), "text": "secret"})                                 # id as string
    if n == 4:  return json.dumps({"tool": "click", "arguments": {"id": sid(last, "Sign in")}})                                          # alt key names
    return json.dumps({"action": "finish", "verdict": "pass", "reason": "dashboard visible", "evidence": "Customer Dashboard"})


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({"models": [{"name": "qwen2.5:7b-instruct"}]}).encode())
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert body["messages"][0]["role"] == "system"
        text = decide(body["messages"][-1]["content"])
        out = {"message": {"content": text}} if self.path.endswith("/api/chat") else {"choices": [{"message": {"content": text}}]}
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(out).encode())


srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_port}"

assert parse_action('x {"action":"click","id":"4"} y') == ("click", {"id": 4})
assert parse_action("no json")[0] == "error"
assert parse_action('{"action":"hack"}')[0] == "error"
assert parse_action('{"action":"finish","verdict":"maybe","reason":"r"}')[0] == "error"

for name, brain in [("ollama", OllamaBrain("qwen2.5:7b-instruct", base)), ("openai", OpenAICompatBrain("m", base + "/v1", "k"))]:
    calls["n"] = 0
    if name == "ollama": brain.check()
    r = run_test("login", brain, URL, log=lambda *_: None)
    print(name, r["verdict"], r["reason"], "| steps:", [s["action"] for s in r["steps"]])
    assert r["verdict"] == "PASS", r
    assert any(s["action"] == "error" and "ACTION FAILED" in s.get("note", "") for s in r["steps"]), "bad reply was not reported back"
print("llm http OK")
