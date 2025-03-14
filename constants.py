"""Module with all constant values used"""

from pathlib import Path

LOG_DIR = Path("/var/log")
DEFAULT_PRIMARY_PORT = 8080
DEFAULT_SECONDARY_PORT = 8082
WS_PORT = 8081
CHUNK_SIZE = 8192
HOSTNAME = "localhost"
ALLOWED_EXTENSIONS = {
    ".log",
    ".txt",
    ".json",
    ".xml",
    ".syslog",
    ".binlog",
    ".asl",
    ".out",
}

# List of secondary servers to query from
SECONDARY_SERVERS = [
    "http://localhost:8082",
    "http://localhost:8084",
]
