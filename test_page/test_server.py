"""
Local HTTP Server for WebVeil Test Webpage.
"""

import http.server
import socketserver
import os
import sys

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)


def run_server():
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Serving WebVeil test page at http://127.0.0.1:{PORT}/")
        httpd.serve_forever()


if __name__ == "__main__":
    run_server()
