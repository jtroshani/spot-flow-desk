"""Serve the dashboard locally and refresh data.js every hour.

Run: python3 serve.py   then open http://localhost:8000
"""
import functools
import http.server
import os
import subprocess
import sys
import threading
import time

PORT = int(os.environ.get("PORT", 8000))
HERE = os.path.dirname(os.path.abspath(__file__))
HOUR = 3600


def refresh_forever():
    while True:
        print(time.strftime("[%H:%M:%S]"), "Checking for new flows...", flush=True)
        result = subprocess.run([sys.executable, os.path.join(HERE, "update_data.py")], capture_output=True, text=True)
        print((result.stdout or result.stderr).strip().splitlines()[-1], flush=True)
        time.sleep(HOUR)


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=refresh_forever, daemon=True).start()
    handler = functools.partial(NoCache, directory=HERE)
    print(f"Spot Flow Desk running at http://localhost:{PORT}  (Ctrl+C to stop)", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler).serve_forever()
