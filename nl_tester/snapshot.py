"""Turns the live page into a compact, numbered list of interactive elements for the model."""

SNAPSHOT_JS = r"""
(start) => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const visible = e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  document.querySelectorAll('[data-nlt]').forEach(e => e.removeAttribute('data-nlt'));
  const sel = 'a[href],button,input,select,textarea,summary,[role=button],[role=link],[role=tab],' +
              '[role=menuitem],[role=checkbox],[role=radio],[role=option],[onclick],[contenteditable=true]';
  const items = [];
  let n = start || 0;
  const walk = root => {
    root.querySelectorAll(sel).forEach(e => {
      if (!visible(e) || e.type === 'hidden') return;
      const id = ++n;
      e.setAttribute('data-nlt', id);
      let label = clean(e.getAttribute('aria-label')) ||
        (e.labels && e.labels[0] ? clean(e.labels[0].textContent) : '') ||
        clean(e.getAttribute('placeholder')) || clean(e.innerText || e.value) ||
        clean(e.getAttribute('title')) || clean(e.getAttribute('alt'));
      const o = { id, tag: e.tagName.toLowerCase(), text: label.slice(0, 80) };
      if (e.type && e.tagName === 'INPUT') o.type = e.type;
      if (e.name) o.name = e.name;
      if (e.tagName === 'A' && e.getAttribute('href')) o.href = e.getAttribute('href').slice(0, 80);
      if (['INPUT','TEXTAREA'].includes(e.tagName) && !['checkbox','radio','password'].includes(e.type) && e.value) o.value = e.value.slice(0, 40);
      if (e.type === 'checkbox' || e.type === 'radio') o.checked = e.checked;
      if (e.tagName === 'SELECT') o.options = Array.from(e.options).map(x => clean(x.text)).slice(0, 30), o.selected = clean(e.options[e.selectedIndex]?.text);
      if (e.disabled) o.disabled = true;
      items.push(o);
    });
    root.querySelectorAll('*').forEach(h => { if (h.shadowRoot) walk(h.shadowRoot); });
  };
  walk(document);
  const headings = Array.from(document.querySelectorAll('h1,h2,h3')).filter(visible).map(h => clean(h.innerText)).slice(0, 12);
  return { url: location.href, title: document.title, headings, items, next: n,
           text: clean(document.body ? document.body.innerText : '').slice(0, 2500) };
}
"""


def take_snapshot(page):
    """Snapshot of the main frame plus up to 4 child iframes (ids are unique across frames)."""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    main = page.main_frame
    snap = main.evaluate(SNAPSHOT_JS, 0)
    nxt = snap.pop("next")
    snap["items"] = snap["items"][:150]
    for idx, fr in enumerate([f for f in page.frames if f != main][:4], start=1):
        try:
            if fr.is_detached():
                continue
            sub = fr.evaluate(SNAPSHOT_JS, nxt)
        except Exception:
            continue
        nxt = sub["next"]
        for it in sub["items"]:
            it["frame"] = idx
            snap["items"].append(it)
        if sub["text"]:
            snap["text"] += f" [iframe {idx}] " + sub["text"][:800]
    snap["items"] = snap["items"][:200]
    return snap


def render(snap) -> str:
    lines = [f"URL: {snap['url']}", f"TITLE: {snap['title']}"]
    if snap["headings"]:
        lines.append("HEADINGS: " + " | ".join(snap["headings"]))
    lines.append("INTERACTIVE ELEMENTS:")
    for it in snap["items"]:
        extra = " ".join(f"{k}={v!r}" for k, v in it.items() if k not in ("id", "tag", "text"))
        lines.append(f"[{it['id']}] <{it['tag']}> {it['text']!r} {extra}".rstrip())
    lines.append("VISIBLE TEXT (truncated): " + snap["text"])
    return "\n".join(lines)
