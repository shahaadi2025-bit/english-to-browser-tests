"""Rule-based 'brain': understands simple plain-English steps with NO model, NO download, NO key.

It is a fallback for when no AI model is available. It reads the same page snapshot as the AI brains and
returns the same JSON-style actions, so the runner, safety checks and reports are identical.
Understood steps (case-insensitive, joined by 'and', 'then', commas, full stops or new lines):
  open/go to/visit <url>        click/press/tap <button or link text>      press Enter|Tab|Escape
  type/enter/fill "<text>" in <field>      enter <field> "<text>"        select "<option>" from <dropdown>
  log in with email X and password Y       wait N seconds
  verify/check/ensure/confirm ... "<text>" | <phrase> | url contains X | title contains X | ... not shown
"""
import json, re

VERBS = r"open|go|visit|navigate|click|press|tap|type|enter|fill|input|select|choose|verify|check|assert|ensure|confirm|expect|validate|make|log|login|sign|wait"
SPLIT = re.compile(r"\s*(?:,\s*)?(?:\band then\b|\bthen\b|\band\b(?=\s+(?:" + VERBS + r")\b)|;|\n|\.\s+)\s*"
                   r"|\s*,\s*(?=(?:" + VERBS + r")\b)", re.I)
Q = r"[\"'“‘](.+?)[\"'”’]"
STOP = set("the a an is are be was of to in on for and or that this these those page screen site shown displayed visible present showing "
           "appears appear there it with has have contains contain shows show displays display says say text some any should user "
           "successfully correctly properly".split())
ELEM_WORDS = {"form": ("input", "textarea", "select"), "button": ("button",), "link": ("a",),
              "field": ("input", "textarea"), "input": ("input", "textarea"), "box": ("input", "textarea"),
              "textbox": ("input", "textarea"), "dropdown": ("select",)}


def _words(s):
    return re.findall(r"[a-z0-9@._-]+", s.lower())


def split_steps(case):
    case = case.strip()
    parts, out = [], []
    # keep quoted text and URLs intact while splitting
    protected, n = {}, [0]

    def keep(m):
        n[0] += 1
        k = f"\u0000{n[0]}\u0000"
        protected[k] = m.group(0)
        return k
    tmp = re.sub(Q + r"|https?://\S+|\b[\w-]+(?:\.[\w-]+)+\.[a-z]{2,}\S*", keep, case)
    for p in SPLIT.split(tmp):
        p = p.strip(" .")
        for k, v in protected.items():
            p = p.replace(k, v)
        if p:
            out.append(p)
    return out


def _url_in(s):
    m = re.search(r"https?://[^\s\"']+|\b(?:[\w-]+\.)+[a-z]{2,}(?:/[^\s\"']*)?", s, re.I)
    return m.group(0).rstrip(".,;)") if m else None


def expand(step):
    """One English step -> list of primitive steps (dicts)."""
    s, low = step.strip(), step.strip().lower()
    m = re.match(r"(?:open|go to|visit|navigate to|browse to)\s+(.+)", s, re.I)
    if m:
        u = _url_in(m.group(1))
        return [{"k": "goto", "url": u}] if u else [{"k": "bad", "why": f"no URL in step: {step}"}]
    if re.match(r"(?:log ?in|sign ?in)\b", low):
        em = re.search(r"(?:email|e-mail|username|user name|user)\s*(?:is|=|:)?\s*[\"']?([^\s\"',]+)", s, re.I)
        pw = re.search(r"password\s*(?:is|=|:)?\s*[\"']?([^\s\"',]+)", s, re.I)
        if not (em and pw):
            return [{"k": "blocked", "why": "login step has no credentials (write: log in with email X and password Y)"}]
        return [{"k": "type", "target": "email", "alt": ["username", "user", "login"], "text": em.group(1)},
                {"k": "type", "target": "password", "text": pw.group(1)},
                {"k": "click", "target": "sign in", "alt": ["log in", "login", "submit"]}]
    m = re.match(r"wait(?: for)?\s+(\d+)", low)
    if m:
        return [{"k": "wait", "seconds": int(m.group(1))}]
    m = re.match(r"press\s+(?:the\s+)?(enter|return|tab|escape|esc)(?:\s+key)?$", low)
    if m:
        return [{"k": "press", "key": {"return": "Enter", "esc": "Escape"}.get(m.group(1), m.group(1).capitalize())}]
    m = re.match(r"(?:select|choose|pick)\s+" + Q + r"\s+(?:from|in|on)\s+(?:the\s+)?(.+?)(?:\s+(?:dropdown|list|menu|field))?$", s, re.I)
    if m:
        return [{"k": "select", "option": m.group(1), "target": m.group(2)}]
    m = re.match(r"(?:type|enter|fill(?: in)?|input|write)\s+" + Q + r"\s+(?:in|into|as|on)\s+(?:the\s+)?(.+?)(?:\s+(?:field|box|input|textbox|bar))?$", s, re.I)
    if m:
        return [{"k": "type", "text": m.group(1), "target": m.group(2), "enter": False}]
    m = re.match(r"(?:type|enter|fill(?: in)?|input|set)\s+(?:the\s+)?(.+?)(?:\s+(?:field|box|input))?\s+(?:with|as|to|=)\s+" + Q + r"$", s, re.I)
    if m:
        return [{"k": "type", "text": m.group(2), "target": m.group(1)}]
    m = re.match(r"(?:click|press|tap|hit|select|choose)(?:\s+on)?\s+(?:the\s+)?(.+?)(?:\s+(?:button|link|tab|menu|option|icon))?$", s, re.I)
    if m:
        return [{"k": "click", "target": m.group(1).strip("\"'“”")}]
    m = re.match(r"(?:verify|check|assert|ensure|confirm|expect|validate|make sure)(?:\s+that)?\s+(.+)", s, re.I)
    if m:
        return [{"k": "verify", "what": m.group(1)}]
    return [{"k": "bad", "why": f"cannot understand step: {step!r}"}]


class RulesBrain:
    name = "rules"

    def __init__(self):
        self.queue, self.snap, self.tries, self.n = None, None, 0, 0

    def observe(self, snap):
        self.snap = snap

    # ---- element matching ----
    def _find(self, target, alt, kinds):
        words = [target] + list(alt or [])
        best, best_score = None, 0
        for it in self.snap["items"]:
            hay = " ".join(str(it.get(k, "")) for k in ("text", "name", "type", "href")).lower()
            score = 0
            for w in words:
                w = w.lower().strip()
                if not w:
                    continue
                if it["text"].lower() == w:
                    score = max(score, 10)
                elif w in hay:
                    score = max(score, 6)
                else:
                    tw = [t for t in _words(w) if t not in STOP]
                    if tw and all(t in hay for t in tw):
                        score = max(score, 5)
                    elif tw:
                        score = max(score, 4 * sum(t in hay for t in tw) / len(tw) - 2)
            if score and it["tag"] in kinds:
                score += 2
            if kinds and it["tag"] not in kinds and not (it["tag"] == "input" and "input" in kinds):
                score -= 3
            if it.get("disabled"):
                score -= 4
            if score > best_score:
                best, best_score = it, score
        return best if best_score >= 4 else None

    def _present(self, phrase):
        """Heuristic: >=60% of significant words appear on the page (or a matching element exists)."""
        s = self.snap
        hay = " ".join([s["text"], s["title"], s["url"], *s["headings"],
                        *[f"{x['text']} {x.get('name', '')}" for x in s["items"]]]).lower()
        words = [w for w in _words(phrase) if w not in STOP]
        if not words:
            return False, ""
        hits, ev = 0, ""
        for w in words:
            ok = w in hay
            if not ok and w in ELEM_WORDS:
                ok = any(i["tag"] in ELEM_WORDS[w] for i in s["items"])
            if ok:
                hits += 1
                if not ev and w in hay:
                    ev = w
        return hits / len(words) >= 0.6, ev or (s["title"] or s["url"])

    def _verify(self, what):
        s = self.snap
        neg = re.search(r"\b(not|no longer|doesn't|does not|isn't|is not|without|never)\b", what, re.I)
        m = re.search(r"\burl\s+(?:contains|has|includes|is|equals|ends with|starts with)\s+[\"']?([^\s\"']+)", what, re.I)
        if m and not neg:
            ok = m.group(1).lower() in s["url"].lower()
            return ok, s["url"], f"URL {'contains' if ok else 'does not contain'} {m.group(1)!r} (url: {s['url']})"
        m = re.search(r"\btitle\s+(?:contains|has|includes|is|equals)\s+" + Q, what, re.I) or \
            re.search(r"\btitle\s+(?:contains|has|includes|is|equals)\s+(.+)$", what, re.I)
        if m and not neg:
            ok = m.group(1).strip().lower() in s["title"].lower()
            return ok, s["title"], f"title {'matches' if ok else 'does not match'} {m.group(1)!r} (title: {s['title']!r})"
        q = re.search(Q, what)
        phrase = q.group(1) if q else re.sub(
            r"^(?:the\s+)?(?:page|screen|site|app)?\s*(?:should\s+)?(?:now\s+)?(?:shows?|displays?|contains?|has|have|says|include[s]?)?\s*", "", what, flags=re.I)
        phrase = re.sub(r"\b(?:is|are|was|were)\s+(?:not\s+)?(?:shown|displayed|visible|present|showing|loaded|available)\b.*$", "", phrase, flags=re.I)
        phrase = re.sub(r"\b(?:does not|doesn't|is not|isn't|not|no longer|without|never)\b", "", phrase, flags=re.I).strip()
        nwords = len([w for w in _words(phrase) if w not in STOP])
        if not q and (nwords > 6 or (neg and nwords > 4)):
            return None      # too complex for keyword matching: refuse instead of guessing
        if q:
            ok = q.group(1).lower() in " ".join([s["text"], s["title"], *s["headings"],
                                                  *[x["text"] for x in s["items"]]]).lower()
            ev = q.group(1)
        else:
            ok, ev = self._present(phrase)
        if neg:
            return (not ok), (s["title"] or s["url"]), f"{phrase!r} is {'absent' if not ok else 'still present'} on the page"
        return ok, ev, f"{phrase!r} {'found' if ok else 'not found'} on the page"

    # ---- brain interface ----
    def next_step(self, messages):
        self.n += 1
        if self.queue is None:
            case = messages[0]["content"].split("TEST CASE:\n", 1)[-1].split("\n\nThe browser", 1)[0].split("\n\nNo start URL", 1)[0]
            self.queue = [p for st in split_steps(case) for p in expand(st)]
        last = messages[-1]["content"] if isinstance(messages[-1]["content"], str) else ""
        act = self._decide(last)
        name, args = act
        return json.dumps({"action": name, **args}), [(f"r{self.n}", name, args)]

    def _finish(self, verdict, reason, evidence=""):
        return "finish", {"verdict": verdict, "reason": reason, "evidence": evidence}

    def _decide(self, last):
        if "ACTION FAILED" in last:
            return self._finish("FAIL", "A step could not be performed: " + last.split("ACTION FAILED:")[1].split("\n")[0].strip())
        if not self.queue:
            return self._finish("BLOCKED", "The test case has no verification step (use: verify ... / check ... / ensure ...).")
        st = self.queue[0]
        k = st["k"]
        retry = lambda msg: (self._wait_or(msg))
        if k == "bad":
            return self._finish("BLOCKED", st["why"] + " (rules mode understands simple steps; use an AI model for free-form text)")
        if k == "blocked":
            return self._finish("BLOCKED", st["why"])
        if k in ("goto", "wait", "press"):
            self.queue.pop(0); self.tries = 0
            return {"goto": ("goto", {"url": st.get("url")}), "wait": ("wait", {"seconds": st.get("seconds", 1)}),
                    "press": ("press", {"key": st.get("key")})}[k]
        if k in ("click", "type", "select"):
            kinds = {"click": ("button", "a", "input", "summary"), "type": ("input", "textarea"), "select": ("select",)}[k]
            it = self._find(st["target"], st.get("alt"), kinds)
            if not it:
                return retry(f"could not find an element matching {st['target']!r}")
            self.queue.pop(0); self.tries = 0
            if k == "click":
                return "click", {"id": it["id"]}
            if k == "type":
                return "type", {"id": it["id"], "text": st["text"], "press_enter": False}
            return "select", {"id": it["id"], "option": st["option"]}
        if k == "verify":
            res = self._verify(st["what"])
            if res is None:
                return self._finish("BLOCKED", f"cannot judge this check with simple rules (too complex): {st['what']!r}. "
                                    "Quote the exact text to look for, e.g. verify \"Welcome\" is shown, or use an AI model.")
            ok, ev, why = res
            if not ok and self.tries < 2:
                self.tries += 1
                return "wait", {"seconds": 1.5}
            self.queue.pop(0); self.tries = 0
            if not ok:
                return self._finish("FAIL", why)
            if any(x["k"] == "verify" for x in self.queue):
                return "wait", {"seconds": 0.2}         # more checks follow: re-read the page, then continue
            return self._finish("PASS", why, ev)
        return self._finish("BLOCKED", "internal: unknown step")

    def _wait_or(self, msg):
        if self.tries < 2:
            self.tries += 1
            return "wait", {"seconds": 1.5}
        return self._finish("FAIL", msg)
