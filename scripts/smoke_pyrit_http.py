"""Local-only smoke test for the optional PyRIT HTTP adapter.

Run this script with the PyRIT project venv. It starts a loopback HTTP server,
so it never contacts an external target.
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from redteam_memory.models import Case  # noqa: E402
from redteam_memory.runner import run_once  # noqa: E402
from redteam_memory.store import MemoryStore  # noqa: E402
from redteam_memory.targets import PyRITHTTPTarget  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length))
        response = json.dumps({"answer": f"echo:{body['prompt']}"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_args: object) -> None:
        return


async def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    raw_request = (
        f'POST http://127.0.0.1:{port}/chat HTTP/1.1\n'
        f'Host: 127.0.0.1:{port}\n'
        "Content-Type: application/json\n\n"
        '{"prompt": "{PROMPT}"}'
    )
    db_path = PROJECT / "data" / "pyrit_smoke.sqlite3"
    try:
        with MemoryStore(db_path) as store:
            case = store.save_case(Case(title="local PyRIT adapter smoke"))
            target = PyRITHTTPTarget(
                raw_http_request=raw_request,
                response_key="answer",
                prompt_encoding="json",
                use_tls=False,
            )
            result = await run_once(
                store,
                case_id=case.case_id,
                target=target,
                prompt='quote "and newline\\nvalue',
                mechanism="adapter-smoke",
                conversation_id="loopback",
            )
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    finally:
        server.shutdown()
        server.server_close()
        if db_path.exists():
            db_path.unlink()


if __name__ == "__main__":
    asyncio.run(main())

