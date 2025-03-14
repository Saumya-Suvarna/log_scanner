"""Main Module with initializiation of servers"""

import json
import os
import argparse
import asyncio
import logging

import http.server
import urllib.parse
import threading
from http import HTTPStatus

from network_utils import handle_external_logs, start_websocket_server
from constants import (
    HOSTNAME,
    DEFAULT_PRIMARY_PORT,
    DEFAULT_SECONDARY_PORT,
    WS_PORT,
)
from utils import read_logs_reverse, get_file_path, get_response, get_next_url

# set up logger
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class LogRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Handles HTTP requests for log retrieval (for both primary and secondary servers)"""

    def do_GET(self):
        """Handles GET requests."""
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == "/logs":
            self.handle_logs(parsed_path.query)
        elif parsed_path.path == "/fetch_external_logs":
            self.send_response_json(HTTPStatus.OK, handle_external_logs())
        else:
            self.send_response_json(HTTPStatus.NOT_FOUND, "Endpoint Not Found")

    def handle_logs(self, query):
        """Handles log retrieval with filtering & pagination."""
        params = urllib.parse.parse_qs(query)
        filename = params.get("filename", [None])[0]
        is_regex = bool(params.get("is_regex", [False])[0])
        filter_text = params.get("filter", [None])[0]
        offset = int(params.get("offset", [0])[0]) if params.get("offset") else None
        limit = int(params.get("limit", [100])[0])

        file_path, error_code, error_str = get_file_path(filename, is_regex)
        if error_code != HTTPStatus.OK:
            self.send_response_json(error_code, error_str)

        # If the file is empty return empty response
        if os.path.getsize(file_path) == 0:
            resp = get_response(limit=limit, entries=[])
            self.send_response_json(HTTPStatus.OK, resp)
            return

        try:
            # Get the logs
            logs, next_offset = read_logs_reverse(
                file_path, filter_text, offset, limit, HOSTNAME, self.server_port
            )
            # Get the next url if it exists
            next_url = get_next_url(filename, next_offset, limit, filter_text)

            response = get_response(
                offset=next_offset,
                limit=limit,
                has_next=next_offset is not None,
                next_link=next_url,
                entries=logs,
            )
            self.send_response_json(HTTPStatus.OK, response)
        except Exception as e:
            self.send_response_json(
                HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading logs: {str(e)}"
            )

    def send_response_json(self, code, data):
        """Sends JSON response with CORS headers."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self' ws: wss:; connect-src 'self' ws: wss:",
        )
        self.end_headers()
        if code != HTTPStatus.OK:
            data = {"error": {"code": code, "message": data}}
        self.wfile.write(json.dumps(data, indent=4).encode("utf-8"))


def init_http_server(http_port, mode):
    """Runs the HTTP server."""
    server_address = ("", http_port)
    handler = LogRequestHandler
    handler.server_mode = mode
    handler.server_port = http_port
    httpd = http.server.HTTPServer(server_address, handler)
    logging.info("%s Server running on port %d", mode.capitalize(), http_port)
    httpd.serve_forever()


def init_servers(http_port, ws_port, mode):
    """initializes the servers"""
    # Initialize HTTP server
    http_thread = threading.Thread(
        target=init_http_server, args=(http_port, mode), daemon=True
    )
    http_thread.start()

    # Initialize WebSocket server
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_websocket_server(ws_port))
    loop.run_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["primary", "secondary"], default="primary")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--wsport", type=int, default=None)
    args = parser.parse_args()
    # Get ports
    port = args.port or (
        DEFAULT_PRIMARY_PORT if args.mode == "primary" else DEFAULT_SECONDARY_PORT
    )
    wsport = args.wsport or (WS_PORT)
    # Initialize servers
    init_servers(port, wsport, args.mode)
