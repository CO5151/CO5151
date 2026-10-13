#!/usr/bin/env python3
"""
CO5151 Seminar S1-7: Local Web Server for Agent Design Demo
Launches a lightweight HTTP server on localhost:8080 serving demo_web/
"""

import http.server
import os
import socketserver
import sys
import webbrowser

PORT = 8080
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(CURRENT_DIR, "web")):
    DEMO_DIR = os.path.join(CURRENT_DIR, "web")
else:
    DEMO_DIR = os.path.join(CURRENT_DIR, "demo_web")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DEMO_DIR, **kwargs)

def main():
    os.chdir(DEMO_DIR)
    global PORT
    for port in [8080, 8088, 8765, 8888, 9000]:
        try:
            httpd = socketserver.TCPServer(("", port), Handler)
            PORT = port
            break
        except OSError:
            continue
    else:
        print("Could not bind to any available port.")
        sys.exit(1)

    with httpd:
        url = f"http://localhost:{PORT}"
        print(f"\n" + "=" * 70)
        print(f"🚀 CO5151 Seminar S1-7: Agent Design Workbench for Law Graph")
        print(f"📡 Server running at: {url}")
        print(f"📂 Serving directory: {DEMO_DIR}")
        print(f"Press Ctrl+C to stop the server.")
        print("=" * 70 + "\n")
        
        # Try to open browser automatically if not headless
        try:
            webbrowser.open(url)
        except Exception:
            pass

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped cleanly.")

if __name__ == "__main__":
    main()
