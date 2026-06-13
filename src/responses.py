from workers import Response


def response(body="", status=200, headers=None):
    # Status codes 204 (No Content), 304 (Not Modified), and 1xx
    # MUST have a null body per the Fetch API spec.
    if body == "" and (status in (204, 304) or 100 <= status < 200):
        body = None
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
