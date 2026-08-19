"""Minimal maintenance listener used only during Render Free startup bootstrap.

The listener prevents Render's web-service port scan from timing out while a
fresh production database is applying long-running Django migrations.

It deliberately serves no project files and exposes no application data.
All requests receive HTTP 503 until the real Gunicorn process takes over.
"""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))


class MaintenanceHandler(BaseHTTPRequestHandler):
    server_version = "Build360Bootstrap/1.0"
    sys_version = ""

    def _respond(self) -> None:
        body = b"Build360 deployment bootstrap in progress.\n"
        self.send_response(503)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Retry-After", "30")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        self._respond()

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler API
        self._respond()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        self._respond()

    def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
        self._respond()

    def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler API
        self._respond()

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API
        self._respond()

    def log_message(self, format: str, *args: object) -> None:
        # Keep bootstrap logs concise and avoid echoing request details.
        return


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    print(
        f"[R45] Maintenance listener active on {HOST}:{PORT} "
        "(HTTP 503 until Gunicorn takeover).",
        flush=True,
    )
    server = ReusableThreadingHTTPServer((HOST, PORT), MaintenanceHandler)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
