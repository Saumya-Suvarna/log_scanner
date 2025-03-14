"""Module providing all network configuration utilities"""

import os
import json
import asyncio
import logging
import aiofiles
import websockets
import aiohttp

from constants import (
    HOSTNAME,
    LOG_DIR,
    SECONDARY_SERVERS,
)

from utils import get_response


async def start_websocket_server(ws_port):
    """Starts WebSocket server."""

    async def websocket_log_stream(websocket):
        """Handles dynamic log streaming via WebSockets"""
        try:
            filename = await websocket.recv()
            logging.debug("Received filename: %s", filename)

            file_path = os.path.join(LOG_DIR, filename)

            if not os.path.exists(file_path) or not os.access(file_path, os.R_OK):
                await websocket.send(json.dumps({"error": "File not accessible"}))
                return

            last_position = os.path.getsize(file_path)  # Start at the end of file

            while True:
                await asyncio.sleep(1)  # Check for updates every 1 second

                # Open the file asynchronously and read new lines
                async with aiofiles.open(file_path, "r") as f:
                    await f.seek(last_position)  # Move to last known position
                    new_lines = await f.read()

                    if new_lines.strip():  # If new data exists, send to WebSocket
                        last_position += len(new_lines)
                        await websocket.send(
                            json.dumps(
                                {
                                    "log": new_lines.strip(),
                                    "source": f"{HOSTNAME}:{ws_port}",
                                    "file": str(file_path),
                                }
                            )
                        )  # Send new logs

        except websockets.exceptions.ConnectionClosedError:
            logging.error("WebSocket connection closed by the client")
        except Exception as e:
            logging.error("WebSocket Error: %s", e)
            await websocket.send(json.dumps({"error": f"Internal server error: {e}"}))
        finally:
            logging.error("WebSocket client disconnected")

    server = await websockets.serve(websocket_log_stream, HOSTNAME, ws_port)
    logging.error("WebSocket Server running on port : %d ", ws_port)
    await server.wait_closed()


def handle_external_logs():
    """Fetches logs only from secondary servers when manually triggered."""
    logs_from_secondary = fetch_logs_from_secondary_servers()

    response = get_response(
        limit=None,
        offset=None,
        entries=logs_from_secondary,
    )
    return response


def fetch_logs_from_secondary_servers():
    """Fetches logs from secondary servers asynchronously."""
    logs = []

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(fetch_from_servers())

    for result in results:
        if result:
            logs.extend(result)

    return logs


async def fetch_from_servers():
    """Asynchronously fetch logs from secondary servers"""
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_log(
                session,
                f"{server}/logs",
            )
            for server in SECONDARY_SERVERS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [res for res in results if isinstance(res, list)]


async def fetch_log(session, url):
    """Fetch logs from a single secondary server"""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("entries", [])
            return []
    except Exception as e:
        logging.info("Failed to fetch logs from %s: %e", url, e)
        return []
