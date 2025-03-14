"""Module providing all utility functions"""

import re
import os
import mmap
import logging
from http import HTTPStatus
from pathlib import Path

from constants import (
    LOG_DIR,
    CHUNK_SIZE,
    HOSTNAME,
    DEFAULT_PRIMARY_PORT,
)


def is_valid_regex(file_name) -> bool:
    """Checks if file_name is a valid regex pattern"""
    try:
        re.compile(file_name)
        return True
    except re.error:
        return False


def get_first_matching_file(file_pattern):
    """Searches the log directory for the first file matching the regex pattern."""
    try:
        # get regex pattern
        pattern = re.compile(file_pattern)
        # go through the log directory and get the first matched pattern
        for log_file in LOG_DIR.iterdir():
            if log_file.is_file() and pattern.match(log_file.name):
                return log_file
        return None
    except Exception as e:
        logging.error("Error finding matching file: %s", e)
        return None


def is_valid_file(file_path):
    """Checks if the file has an allowed extension, is inside /var/log, is not a symlink"""
    try:
        real_path = file_path.resolve(strict=True)
        log_dir_resolved = LOG_DIR.resolve(strict=True)

        # Check if the resolved path is a file and is within the LOG_DIR
        if real_path.is_file() and log_dir_resolved in real_path.parents:
            return True
        else:
            return False
    except FileNotFoundError:
        return False


def get_latest_log_file():
    """Returns the file name for latest created log file"""
    try:
        log_files = [f for f in LOG_DIR.iterdir() if f.is_file() and is_valid_file(f)]
        if not log_files:
            return None
        # return the file with latest modified time
        return max(log_files, key=lambda f: f.stat().st_mtime).name
    except Exception:
        return None


def read_logs_reverse(
    file_path,
    filter_text=None,
    offset=None,
    limit=100,
    hostname=HOSTNAME,
    server_port=DEFAULT_PRIMARY_PORT,
) -> (list, int):
    """Reads logs in reverse order efficiently while ensuring offset is the actual file position"""
    logs = []
    file_size = os.path.getsize(file_path)
    # for the first request start from the end of the file
    if offset is None:
        offset = file_size

    found_logs = 0
    last_valid_offset = offset

    with open(file_path, "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            while offset > 0:
                chunk_size = min(CHUNK_SIZE, offset)
                new_offset = offset - chunk_size

                mm.seek(new_offset)
                chunk = mm.read(chunk_size).decode(errors="ignore")

                lines = chunk.split("\n")
                if new_offset > 0:
                    # this indicates that a parital line exists at the begining of the chunk
                    lines = lines[1:]

                for line in reversed(lines):
                    # Empty lines are skipped
                    if not line.strip():
                        continue
                    # only add to the log file if the filter texts exists
                    if filter_text and not re.search(filter_text, line):
                        continue
                    log_entry = {
                        "log": line,
                        "source": f"{hostname}:{server_port}",
                        "file": str(file_path),
                    }

                    logs.append(log_entry)
                    found_logs += 1

                    if found_logs >= limit:
                        remaining_data = "\n".join(lines[:-found_logs])
                        last_valid_offset = (
                            new_offset + len(remaining_data.encode()) + 1
                        )
                        break

                offset = new_offset

    next_offset = last_valid_offset if found_logs >= limit else None

    return logs, next_offset


def get_file_path(filename=None, is_regex=False):
    """Get the file path"""
    # If no filename, get latest log file
    if filename is None:
        filename = get_latest_log_file()
        if filename is None:
            return "", HTTPStatus.NOT_FOUND, "No log files available"

    # If the filename is a regex pattern, fetch the first matching file
    if is_regex and is_valid_regex(filename):
        file_path = get_first_matching_file(filename)
        if not file_path:
            return "", HTTPStatus.NOT_FOUND, "No matching log files found"
    else:
        filename_parts = Path(filename).parts
        file_path = LOG_DIR.joinpath(*filename_parts)
    if not is_valid_file(file_path):
        return (
            "",
            HTTPStatus.BAD_REQUEST,
            "Invalid file type",
        )
    return (file_path, HTTPStatus.OK, "")


def get_response(
    entries,
    offset=0,
    limit=100,
    has_next=False,
    next_link=None,
):
    """Get the response json"""
    return {
        "pagination": {
            "offset": offset,
            "limit": limit,
            "has_next": has_next,
            "next": next_link,
        },
        "entries": entries,
    }


def get_next_url(filename, next_offset, limit, filter_text):
    """Get the next url"""
    next_url = (
        f"/logs?filename={filename}&offset={next_offset}&limit={limit}"
        if next_offset is not None
        else None
    )
    if filter_text and next_url:
        next_url = f"{next_url}&filter={filter_text}"
    return next_url
