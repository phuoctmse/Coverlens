"""Shared fixtures."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest


class FakeOllamaServer:
    """A local HTTP server that answers like Ollama, for offline tests."""

    def __init__(self) -> None:
        self.models: list[dict[str, str]] = [
            {"name": "llama3.1:8b", "digest": "abc123"}
        ]
        self.seen: list[dict[str, Any]] = []
        self.auth: list[str | None] = []  # Authorization header of every request
        self.status = 200
        self.body = json.dumps(
            {
                "message": {
                    "content": json.dumps(
                        {"status": "gap", "cited_case_ids": [], "rationale": "no"}
                    )
                },
                "prompt_eval_count": 1200,
                "eval_count": 45,
                "total_duration": 2_500_000_000,
            }
        )
        handler = self._handler()
        self._httpd = HTTPServer(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_port}"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def reply_with(self, body: str, status: int = 200) -> None:
        self.body, self.status = body, status

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, status: int, body: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))

            def do_GET(self) -> None:
                server.auth.append(self.headers.get("Authorization"))
                self._reply(200, json.dumps({"models": server.models}))

            def do_POST(self) -> None:
                server.auth.append(self.headers.get("Authorization"))
                length = int(self.headers["Content-Length"])
                server.seen.append(json.loads(self.rfile.read(length)))
                self._reply(server.status, server.body)

            def log_message(self, *_: Any) -> None:
                pass

        return Handler


@pytest.fixture
def fake_ollama() -> Iterator[FakeOllamaServer]:
    server = FakeOllamaServer()
    yield server
    server.close()
