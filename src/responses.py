from html import escape

from workers import Response


def response(body="", status=200, headers=None):
    return Response(body, status=status, headers=headers or {})


def text_response(body, status=200, extra_headers=None):
    headers = {"content-type": "text/plain; charset=utf-8"}
    if extra_headers:
        headers.update(extra_headers)
    return response(body, status=status, headers=headers)


def dav_response(xml_body, status=207):
    return response(
        xml_body,
        status=status,
        headers={"content-type": 'application/xml; charset="utf-8"'},
    )


def html_response(html_body, status=200, extra_headers=None):
    headers = {"content-type": "text/html; charset=utf-8"}
    if extra_headers:
        headers.update(extra_headers)
    return response(html_body, status=status, headers=headers)


def format_size(size):
    value = float(size or 0)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def html_page(title, rows):
    body_rows = "\n".join(rows) or '<tr><td colspan="3" class="empty">Empty directory</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; line-height: 1.45; }}
    main {{ max-width: 960px; margin: 0 auto; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 1rem; word-break: break-word; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid color-mix(in srgb, currentColor 18%, transparent); padding: .65rem .5rem; text-align: left; }}
    th.size, td.size {{ text-align: right; white-space: nowrap; }}
    td.modified {{ white-space: nowrap; opacity: .75; }}
    a {{ color: inherit; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .empty {{ opacity: .7; text-align: center; }}
  </style>
</head>
<body>
  <main>
    <h1>{escape(title)}</h1>
    <table>
      <thead><tr><th>Name</th><th class="size">Size</th><th>Modified</th></tr></thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </main>
</body>
</html>"""


def directory_row(name, href, size="", modified="", is_dir=False):
    label = f"{name}/" if is_dir else name
    icon = "[DIR] " if is_dir else ""
    return (
        "<tr>"
        f'<td><a href="{escape(href, quote=True)}">{escape(icon + label)}</a></td>'
        f'<td class="size">{escape(size)}</td>'
        f'<td class="modified">{escape(modified)}</td>'
        "</tr>"
    )
