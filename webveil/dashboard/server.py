"""
WebVeil Dashboard WebSocket Server.
Tiny HTTP + WebSocket server that streams agent events to the web dashboard.
"""

import json
import logging
import threading
import http.server
import os
from typing import List

logger = logging.getLogger("WebVeilDashboard")

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))


class DashboardHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the dashboard HTML file."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress HTTP request logging


def start_dashboard_server(port: int, events: List[dict], event_lock: threading.Lock):
    """
    Start the dashboard HTTP server and WebSocket event streamer.
    Uses simple HTTP with polling endpoint (avoids websockets dependency issues).
    """
    import socketserver

    class JsonAPIHandler(DashboardHTTPHandler):
        """Serves both static files and a JSON events API."""

        def do_GET(self):
            if self.path == "/api/events":
                # Return all events as JSON
                with event_lock:
                    data = json.dumps(events[-200:], default=str)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data.encode("utf-8"))
            elif self.path == "/api/events/count":
                with event_lock:
                    count = len(events)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"count": count}).encode("utf-8"))
            else:
                super().do_GET()

    with socketserver.TCPServer(("127.0.0.1", port), JsonAPIHandler) as httpd:
        logger.info(f"[Dashboard] Serving at http://127.0.0.1:{port}")
        httpd.serve_forever()
