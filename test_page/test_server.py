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

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def translate_path(self, path):
        clean = path.split('?', 1)[0].split('#', 1)[0]
        repo_root = os.path.dirname(DIRECTORY)
        if clean.startswith('/extension/'):
            rel = clean[len('/extension/'):].lstrip('/')
            return os.path.join(repo_root, 'extension', rel)
        if clean in ('/vault_window.html', '/vault_window.js', '/vault.html', '/vault'):
            target = 'vault_window.html' if not clean.endswith('.js') else 'vault_window.js'
            return os.path.join(DIRECTORY, target)
        return super().translate_path(path)


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def run_server():
    with ReusableTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Serving WebVeil test page at http://127.0.0.1:{PORT}/")
        httpd.serve_forever()


if __name__ == "__main__":
    run_server()
