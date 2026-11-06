"""Executes one model-chosen action on the page. Never uses site-specific selectors."""


import ipaddress
from urllib.parse import urlparse


def host_allowed(host, allowed):
    host = (host or "").lower()
    return any(host == d or host.endswith("." + d) for d in allowed)


def check_url(url, allowed=None):
    """Model-chosen navigation: web URLs only; no local/private targets unless explicitly allowed."""
    import re
    if re.match(r"^\s*(javascript|data|file|blob|about|chrome|view-source|vbscript):", url, re.I):
        raise ValueError("blocked URL scheme")
    if "://" not in url:
        url = "https://" + url
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise ValueError(f"blocked URL scheme {u.scheme!r}")
    host = (u.hostname or "").lower()
    if allowed:
        if not host_allowed(host, allowed):
            raise ValueError(f"blocked: {host} is not in --allowed-domains")
    else:
        private = host == "localhost" or host.endswith(".local") or host.endswith(".internal")
        try:
            ip = ipaddress.ip_address(host)
            private = private or ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        except ValueError:
            pass
        if private:
            raise ValueError(f"blocked: {host} looks like a local/private address")
    return url


def _el(page, eid):
    for fr in page.frames:               # main frame and iframes
        loc = fr.locator(f'[data-nlt="{int(eid)}"]').first
        try:
            if loc.count():
                return loc
        except Exception:
            continue
    raise ValueError(f"element [{eid}] not found (page changed? use the latest snapshot)")


def run_action(page, name, args, allowed=None):
    t = 6000
    if name == "goto":
        url = check_url(args["url"], allowed)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return f"navigated to {page.url}"
    if name == "click":
        loc = _el(page, args["id"])
        try:
            loc.click(timeout=t)
        except Exception:
            loc.click(timeout=t, force=True)   # overlays / custom widgets
        return f"clicked [{args['id']}]"
    if name == "type":
        loc = _el(page, args["id"])
        loc.fill(args["text"], timeout=t)
        if args.get("press_enter"):
            loc.press("Enter")
        return f"typed into [{args['id']}]" + (" and pressed Enter" if args.get("press_enter") else "")
    if name == "select":
        loc = _el(page, args["id"])
        try:
            loc.select_option(label=args["option"], timeout=t)
        except Exception:
            loc.select_option(value=args["option"], timeout=t)
        return f"selected {args['option']!r} in [{args['id']}]"
    if name == "press":
        page.keyboard.press(args["key"])
        return f"pressed {args['key']}"
    if name == "scroll":
        page.mouse.wheel(0, 700 if args.get("direction", "down") == "down" else -700)
        return "scrolled"
    if name == "wait":
        page.wait_for_timeout(int(min(float(args.get("seconds", 1)), 10) * 1000))
        return "waited"
    raise ValueError(f"unknown action {name}")
