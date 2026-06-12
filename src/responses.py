from datetime import datetime, timedelta, timezone
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


def format_modified(timestamp):
    if not timestamp:
        return ""
    beijing_tz = timezone(timedelta(hours=8))
    if hasattr(timestamp, "timestamp"):
        return datetime.fromtimestamp(timestamp.timestamp(), beijing_tz).strftime("%Y-%m-%d %H:%M CST")
    if hasattr(timestamp, "getTime"):
        return datetime.fromtimestamp(timestamp.getTime() / 1000, beijing_tz).strftime("%Y-%m-%d %H:%M")
    if hasattr(timestamp, "strftime"):
        return timestamp.strftime("%Y-%m-%d %H:%M")
    return str(timestamp)


def html_page(title, rows):
    body_rows = "\n".join(rows) or '<tr><td colspan="3" class="empty">Empty directory</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --border: color-mix(in srgb, currentColor 14%, transparent);
      --muted: color-mix(in srgb, currentColor 58%, transparent);
      --row: color-mix(in srgb, currentColor 4%, transparent);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      line-height: 1.45;
      background: Canvas;
      color: CanvasText;
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 32px 20px;
    }}
    header {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }}
    h1 {{
      font-size: clamp(1.25rem, 2vw, 1.75rem);
      margin: 0;
      word-break: break-word;
      letter-spacing: 0;
    }}
    .summary {{
      color: var(--muted);
      font-size: .9rem;
      white-space: nowrap;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 10px 14px;
      text-align: left;
      vertical-align: middle;
    }}
    th {{
      color: var(--muted);
      font-size: .78rem;
      font-weight: 650;
      text-transform: uppercase;
    }}
    tbody tr:hover {{ background: var(--row); }}
    tbody tr:last-child td {{ border-bottom: 0; }}
    th.size, td.size {{ text-align: right; white-space: nowrap; width: 8rem; }}
    th.modified, td.modified {{ white-space: nowrap; width: 13rem; }}
    td.modified, td.size {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
    a {{
      color: inherit;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: .5rem;
      max-width: 100%;
    }}
    a:hover {{ text-decoration: underline; }}
    .name {{ overflow-wrap: anywhere; }}
    svg.icon {{
      width: 1rem;
      height: 1rem;
      flex: 0 0 auto;
      stroke-width: 1.8;
      color: var(--muted);
    }}
    svg.icon.dir {{ color: #2563eb; }}
    .empty {{ color: var(--muted); text-align: center; padding: 28px 14px; }}
    @media (max-width: 680px) {{
      main {{ padding: 22px 12px; }}
      header {{ display: block; }}
      .summary {{ margin-top: 4px; }}
      th.modified, td.modified {{ display: none; }}
      th, td {{ padding: 10px 9px; }}
      th.size, td.size {{ width: 6rem; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{escape(title)}</h1>
      <div class="summary">R2 WebDAV directory</div>
    </header>
    <table>
      <thead><tr><th>Name</th><th class="size">Size</th><th class="modified">Modified</th></tr></thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </main>
</body>
</html>"""


def directory_row(name, href, size="", modified="", is_dir=False):
    label = f"{name}/" if is_dir else name
    icon = (
        '<svg class="icon dir" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor">'
        '<path d="M3 7.5h6l2 2h10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />'
        '<path d="M3 7.5V5a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v2.5" />'
        "</svg>"
        if is_dir
        else '<svg class="icon file" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor"><path d="M6 2.5h8l4 4v15H6z" /><path d="M14 2.5v4h4" /></svg>'
    )
    return (
        "<tr>"
        f'<td><a href="{escape(href, quote=True)}">{icon}'
        f'<span class="name">{escape(label)}</span></a></td>'
        f'<td class="size">{escape(size)}</td>'
        f'<td class="modified">{escape(modified)}</td>'
        "</tr>"
    )
