#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.server
import socketserver
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve local automation artifacts (screenshots, traces).")
    parser.add_argument("--dir", default="browser_runs", help="Directory to serve")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    args = parser.parse_args()

    root = Path(args.dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    handler = lambda *h_args, **h_kwargs: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *h_args, directory=str(root), **h_kwargs
    )
    with socketserver.TCPServer(("0.0.0.0", args.port), handler) as httpd:
        print(f"Serving {root} at http://127.0.0.1:{args.port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
