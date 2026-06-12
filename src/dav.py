from email.utils import formatdate
from html import escape
from urllib.parse import unquote


DAV_NS = "DAV:"


def http_date(timestamp):
    if not timestamp:
        return formatdate(usegmt=True)
    if hasattr(timestamp, "timestamp"):
        return formatdate(timestamp.timestamp(), usegmt=True)
    return formatdate(usegmt=True)


def etag_from_object(obj):
    http_etag = getattr(obj, "httpEtag", None)
    etag = getattr(obj, "etag", None)
    return http_etag or (f'"{etag}"' if etag else None)


def xml_escape(value):
    return escape(str(value or ""), quote=True)


def build_prop_response(href, is_dir, size=0, modified=None, etag=None):
    display_name = "" if href == "/" else unquote(href.rstrip("/").rsplit("/", 1)[-1])
    resource_type = "<D:resourcetype><D:collection /></D:resourcetype>" if is_dir else "<D:resourcetype />"
    content_props = ""
    if not is_dir:
        content_props = f"<D:getcontentlength>{int(size or 0)}</D:getcontentlength>"
        if etag:
            content_props += f"<D:getetag>{xml_escape(etag)}</D:getetag>"

    return f"""<D:response>
  <D:href>{xml_escape(href)}</D:href>
  <D:propstat>
    <D:prop>
      <D:displayname>{xml_escape(display_name)}</D:displayname>
      <D:creationdate>{xml_escape(http_date(modified))}</D:creationdate>
      <D:getlastmodified>{xml_escape(http_date(modified))}</D:getlastmodified>
      {resource_type}
      {content_props}
    </D:prop>
    <D:status>HTTP/1.1 200 OK</D:status>
  </D:propstat>
</D:response>"""


def multistatus(responses):
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<D:multistatus xmlns:D="{DAV_NS}">'
        + "".join(responses)
        + "</D:multistatus>"
    )
