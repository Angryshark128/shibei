import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from web import webhook


class _Receiver:
    """本地最小接收端：固定返回给定状态码与响应体，退出时关闭。"""

    def __init__(self, status: int = 200, body: bytes = b'{"ok": true}'):
        self.status = status
        self.body = body
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                self.send_response(receiver.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(receiver.body)))
                self.end_headers()
                self.wfile.write(receiver.body)

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/hook"

    def __enter__(self) -> "_Receiver":
        return self

    def __exit__(self, *exc) -> bool:
        self.httpd.shutdown()
        self.httpd.server_close()
        return False


# ---------- _headers ----------


def test_headers_without_token_adds_no_auth():
    assert webhook._headers({"header_key": "Authorization", "token": "  "}) == {"Content-Type": "application/json"}


def test_headers_default_to_authorization():
    # 只填 Token 不填 Header 名称：按惯例走 Authorization，不要静默丢掉 Token
    assert webhook._headers({"token": "abc"})["Authorization"] == "abc"


def test_headers_use_custom_key_and_strip_token():
    # 粘贴的 Token 常带换行，http.client 会因非法请求头直接抛错
    assert webhook._headers({"header_key": " X-Token ", "token": "abc\n"})["X-Token"] == "abc"


# ---------- _post ----------


def test_post_success_has_no_detail():
    with _Receiver(200) as r:
        assert webhook._post({"url": r.url}, {"event": "test"}) == (True, "")


def test_post_http_error_keeps_receiver_message():
    with _Receiver(401, b'{"ok": false, "error": "bad signature"}') as r:
        ok, detail = webhook._post({"url": r.url}, {"event": "test"})
    assert not ok
    assert "401" in detail and "bad signature" in detail


def test_post_connection_error_returns_reason():
    # 127.0.0.1:1 不会有服务监听
    ok, detail = webhook._post({"url": "http://127.0.0.1:1/hook"}, {"event": "test"})
    assert not ok
    assert detail


def test_post_without_url_returns_reason():
    ok, detail = webhook._post({"url": ""}, {"event": "test"})
    assert not ok
    assert detail
