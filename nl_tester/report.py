import html, os

COLORS = {"PASS": "#1e9a4b", "FAIL": "#c8372d", "BLOCKED": "#b07a00", "ERROR": "#6b7280"}


def write_html(results, path="report.html"):
    rows = []
    for n, r in enumerate(results, 1):
        c = COLORS.get(r["verdict"], "#6b7280")
        steps = "".join(
            f"<tr><td>{x['n']}</td><td>{html.escape(x['action'])}</td>"
            f"<td><code>{html.escape(str(x['args']))}</code></td><td>{html.escape(str(x.get('note', '')))}</td></tr>"
            for x in r["steps"])
        shot = f"artifacts/test{n}/final.png"
        img = f'<p><img src="{shot}" style="max-width:100%;border:1px solid #ccc"></p>' if os.path.exists(shot) else ""
        rows.append(f"""<section><h2>Test {n}: <span style="color:{c}">{r['verdict']}</span></h2>
<p><b>{html.escape(r['test'])}</b></p><p>{html.escape(r['reason'])}</p>
{('<p>Evidence: <q>' + html.escape(r['evidence']) + '</q></p>') if r['evidence'] else ''}
<p>{r.get('seconds', '?')} s</p>
<table><tr><th>#</th><th>Action</th><th>Arguments</th><th>Result</th></tr>{steps}</table>{img}</section>""")
    doc = ("<!doctype html><meta charset=utf-8><title>Test report</title><style>body{font:14px Arial;max-width:960px;"
           "margin:24px auto;padding:0 12px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;"
           "padding:4px 6px;text-align:left}section{margin-bottom:36px}</style><h1>Test report</h1>" + "".join(rows))
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path
