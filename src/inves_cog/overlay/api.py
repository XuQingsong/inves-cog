"""Read-only HTTP delivery; no endpoint can alter an overlay or order."""

import argparse
import json
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, HTTPException

from inves_cog.overlay.delivery import FileDelivery


def create_app(delivery):
    app = FastAPI()

    @app.get("/api/linkage/overlay")
    def overlay(date: date):
        payload = delivery.read(date.isoformat())
        if payload is None:
            raise HTTPException(status_code=404, detail="覆盖层未接通")
        return payload

    return app


def main():
    parser = argparse.ArgumentParser(description="Serve the read-only M9 overlay contract without new dependencies")
    parser.add_argument("--directory", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    delivery = FileDelivery(args.directory)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path != "/api/linkage/overlay":
                self.send_error(404)
                return
            try:
                day = date.fromisoformat(parse_qs(parsed.query).get("date", [""])[0])
                payload = delivery.read(day.isoformat())
                status = 200 if payload is not None else 404
                result = payload if payload is not None else {"detail": "覆盖层未接通"}
            except (ValueError, OSError):
                status, result = 400, {"detail": "日期无效或覆盖层暂不可用"}
            blob = json.dumps(result, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

        def log_message(self, format, *args):
            return None

    with HTTPServer((args.host, args.port), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
