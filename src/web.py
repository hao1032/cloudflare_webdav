from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import PurePosixPath
from re import DOTALL, MULTILINE, sub


TEXT_EXTENSIONS = {
    ".txt",
    ".log",
    ".csv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".env",
}
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".css",
    ".html",
    ".sh",
    ".ps1",
    ".bat",
    ".sql",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
}
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".avif"}


def file_extension(path):
    return PurePosixPath(path).suffix.lower()


def preview_kind(path, content_type=""):
    extension = file_extension(path)
    content_type = (content_type or "").lower()
    if content_type.startswith("image/") or extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in MARKDOWN_EXTENSIONS:
        return "markdown"
    if extension in CODE_EXTENSIONS:
        return "code"
    if content_type.startswith("text/") or extension in TEXT_EXTENSIONS:
        return "text"
    return None


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
        return datetime.fromtimestamp(timestamp.timestamp(), beijing_tz).strftime("%Y-%m-%d %H:%M")
    if hasattr(timestamp, "getTime"):
        return datetime.fromtimestamp(timestamp.getTime() / 1000, beijing_tz).strftime("%Y-%m-%d %H:%M")
    if hasattr(timestamp, "strftime"):
        return timestamp.strftime("%Y-%m-%d %H:%M")
    return str(timestamp)


def page_shell(title, body):
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
      --accent: #2563eb;
      --code-bg: color-mix(in srgb, currentColor 5%, transparent);
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
    .summary, .meta {{
      color: var(--muted);
      font-size: .9rem;
      white-space: nowrap;
    }}
    a {{ color: inherit; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .actions {{ display: flex; gap: 12px; align-items: center; }}
    .button {{
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 10px;
      color: CanvasText;
      background: Canvas;
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
    th.modified, td.modified {{ white-space: nowrap; width: 11rem; }}
    td.modified, td.size {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
    .file-link {{
      display: inline-flex;
      align-items: center;
      gap: .5rem;
      max-width: 100%;
    }}
    .name {{ overflow-wrap: anywhere; }}
    svg.icon {{
      width: 1rem;
      height: 1rem;
      flex: 0 0 auto;
      stroke-width: 1.8;
      color: var(--muted);
    }}
    svg.icon.dir {{ color: var(--accent); }}
    .empty {{ color: var(--muted); text-align: center; padding: 28px 14px; }}
    .preview {{
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      background: Canvas;
    }}
    pre {{
      margin: 0;
      padding: 16px;
      overflow: auto;
      background: var(--code-bg);
      font: 13px/1.55 ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      tab-size: 2;
    }}
    code {{ font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; }}
    .markdown {{
      padding: 22px;
      max-width: 860px;
    }}
    .markdown h1, .markdown h2, .markdown h3 {{ margin: 1.1em 0 .45em; }}
    .markdown h1:first-child, .markdown h2:first-child, .markdown h3:first-child {{ margin-top: 0; }}
    .markdown p {{ margin: .75em 0; }}
    .markdown code {{ background: var(--code-bg); border-radius: 4px; padding: .1rem .25rem; }}
    .markdown pre code {{ background: transparent; padding: 0; }}
    .kw {{ color: #7c3aed; }}
    .str {{ color: #047857; }}
    .com {{ color: #6b7280; }}
    .num {{ color: #b45309; }}
    .image-preview {{
      display: block;
      max-width: 100%;
      max-height: 76vh;
      margin: 0 auto;
      background: color-mix(in srgb, currentColor 4%, transparent);
    }}
    @media (max-width: 680px) {{
      main {{ padding: 22px 12px; }}
      header {{ display: block; }}
      .summary, .actions {{ margin-top: 6px; }}
      th.modified, td.modified {{ display: none; }}
      th, td {{ padding: 10px 9px; }}
      th.size, td.size {{ width: 6rem; }}
    }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>"""


def icon_svg(is_dir):
    if is_dir:
        return (
            '<svg class="icon dir" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor">'
            '<path d="M3 7.5h6l2 2h10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />'
            '<path d="M3 7.5V5a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v2.5" />'
            "</svg>"
        )
    return (
        '<svg class="icon file" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor">'
        '<path d="M6 2.5h8l4 4v15H6z" /><path d="M14 2.5v4h4" /></svg>'
    )


def directory_row(name, href, size="", modified="", is_dir=False):
    label = f"{name}/" if is_dir else name
    return (
        "<tr>"
        f'<td><a class="file-link" href="{escape(href, quote=True)}">{icon_svg(is_dir)}'
        f'<span class="name">{escape(label)}</span></a></td>'
        f'<td class="size">{escape(size)}</td>'
        f'<td class="modified">{escape(modified)}</td>'
        "</tr>"
    )


def directory_page(title, rows):
    body_rows = "\n".join(rows) or '<tr><td colspan="3" class="empty">Empty directory</td></tr>'
    body = f"""
    <header>
      <h1>{escape(title)}</h1>
      <div class="summary">R2 WebDAV directory</div>
    </header>
    <table>
      <thead><tr><th>Name</th><th class="size">Size</th><th class="modified">Modified</th></tr></thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>"""
    return page_shell(title, body)


def highlight_code(text):
    escaped = escape(text)
    escaped = sub(r"(&quot;.*?&quot;|'.*?')", r'<span class="str">\1</span>', escaped)
    escaped = sub(r"\b(def|class|import|from|return|if|else|elif|for|while|try|except|async|await|const|let|var|function|type|interface|public|private|static|new)\b", r'<span class="kw">\1</span>', escaped)
    escaped = sub(r"\b(\d+(?:\.\d+)?)\b", r'<span class="num">\1</span>', escaped)
    escaped = sub(r"(^|\s)(#.*?$|//.*?$)", r'\1<span class="com">\2</span>', escaped, flags=MULTILINE)
    return escaped


def markdown_to_html(text):
    text = text.replace("\r\n", "\n")
    code_blocks = []

    def store_code(match):
        code_blocks.append(f"<pre><code>{highlight_code(match.group(2))}</code></pre>")
        return f"\n@@CODEBLOCK{len(code_blocks) - 1}@@\n"

    text = sub(r"```(\w+)?\n(.*?)```", store_code, text, flags=DOTALL)
    lines = []
    for line in text.split("\n"):
        if line.startswith("### "):
            lines.append(f"<h3>{escape(line[4:])}</h3>")
        elif line.startswith("## "):
            lines.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("# "):
            lines.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("- "):
            lines.append(f"<p>• {escape(line[2:])}</p>")
        elif line.strip():
            line = escape(line)
            line = sub(r"`([^`]+)`", r"<code>\1</code>", line)
            line = sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", line)
            lines.append(f"<p>{line}</p>")
        else:
            lines.append("")
    html = "\n".join(lines)
    for index, block in enumerate(code_blocks):
        html = html.replace(f"@@CODEBLOCK{index}@@", block)
    return html


def preview_page(path, kind, body, raw_href, size="", modified=""):
    title = PurePosixPath(path).name or path
    meta = " · ".join(part for part in (size, modified) if part)
    if kind == "image":
        preview = f'<div class="preview"><img class="image-preview" src="{escape(raw_href, quote=True)}" alt="{escape(title, quote=True)}"></div>'
    elif kind == "markdown":
        preview = f'<article class="preview markdown">{markdown_to_html(body)}</article>'
    elif kind == "code":
        preview = f'<div class="preview"><pre><code>{highlight_code(body)}</code></pre></div>'
    else:
        preview = f'<div class="preview"><pre>{escape(body)}</pre></div>'
    html = f"""
    <header>
      <div>
        <h1>{escape(title)}</h1>
        <div class="meta">{escape(meta)}</div>
      </div>
      <div class="actions"><a class="button" href="{escape(raw_href, quote=True)}">Raw</a></div>
    </header>
    {preview}"""
    return page_shell(title, html)
