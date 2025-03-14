"""Module providing all unit tests for utility functions"""

from unittest.mock import patch, MagicMock
from pathlib import Path
from http import HTTPStatus
from utils import (
    is_valid_regex,
    get_first_matching_file,
    is_valid_file,
    get_latest_log_file,
    read_logs_reverse,
    get_file_path,
    get_response,
    get_next_url,
)

from constants import HOSTNAME, DEFAULT_PRIMARY_PORT, LOG_DIR


def test_is_valid_regex():
    assert is_valid_regex(r"\d+")
    assert not is_valid_regex(r"[")


@patch("utils.LOG_DIR", new_callable=MagicMock)
def test_get_first_matching_file(mock_log_dir):
    mock_file = MagicMock()
    mock_file.is_file.return_value = True
    mock_file.name = "logfile.log"
    mock_log_dir.iterdir.return_value = [mock_file]

    assert get_first_matching_file(r"logfile\.log") == mock_file
    assert get_first_matching_file(r"nonexistent\.log") is None


@patch("utils.LOG_DIR", new_callable=MagicMock)
def test_is_valid_file(mock_log_dir):
    mock_file = MagicMock()
    mock_file.resolve.return_value = mock_file
    mock_file.is_file.return_value = True
    mock_file.parent.samefile.return_value = True
    mock_file.suffix = ".log"
    mock_log_dir.resolve.return_value = mock_file

    assert is_valid_file(mock_file)

    # Simulate file not being inside the log directory
    mock_file.suffix = ".log"
    mock_file.parent.samefile.return_value = False
    assert not is_valid_file(mock_file)

    # Simulate file not being a regular file
    mock_file.is_file.return_value = False
    assert not is_valid_file(mock_file)


@patch("utils.LOG_DIR", new_callable=MagicMock)
@patch("utils.is_valid_file")
def test_get_latest_log_file(mock_is_valid_file, mock_log_dir):
    mock_file = MagicMock()
    mock_file.is_file.return_value = True
    mock_file.stat.return_value.st_mtime = 100
    mock_log_dir.iterdir.return_value = [mock_file]
    mock_is_valid_file.return_value = True

    assert get_latest_log_file() == mock_file.name
    mock_is_valid_file.return_value = False
    assert get_latest_log_file() is None


@patch("utils.os.path.getsize")
@patch("utils.mmap.mmap")
@patch("utils.open", new_callable=MagicMock)
def test_read_logs_reverse(mock_open, mock_mmap, mock_getsize):
    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file
    mock_getsize.return_value = 100

    file_content = b"log1\nlog2\nlog3\nlog4\nlog5"
    mock_mmap_instance = MagicMock()
    mock_mmap_instance.read.return_value = file_content
    mock_mmap_instance.__enter__.return_value = mock_mmap_instance
    mock_mmap.return_value = mock_mmap_instance

    logs, next_offset = read_logs_reverse(
        Path("/var/log/install.log"),
        None,
        None,
        3,
        hostname=HOSTNAME,
        server_port=DEFAULT_PRIMARY_PORT,
    )
    expected_logs = [
        {
            "log": "log5",
            "source": f"{HOSTNAME}:{DEFAULT_PRIMARY_PORT}",
            "file": "/var/log/install.log",
        },
        {
            "log": "log4",
            "source": f"{HOSTNAME}:{DEFAULT_PRIMARY_PORT}",
            "file": "/var/log/install.log",
        },
        {
            "log": "log3",
            "source": f"{HOSTNAME}:{DEFAULT_PRIMARY_PORT}",
            "file": "/var/log/install.log",
        },
    ]
    assert logs == expected_logs
    assert next_offset is not None


@patch("utils.get_latest_log_file")
@patch("utils.is_valid_file")
def test_get_file_path(mock_is_valid_file, mock_get_latest_log_file):
    mock_get_latest_log_file.return_value = "latest.log"
    mock_is_valid_file.return_value = True

    file_path, status, message = get_file_path()
    assert file_path == LOG_DIR / "latest.log"
    assert status == HTTPStatus.OK
    assert message == ""

    mock_is_valid_file.return_value = False
    file_path, status, message = get_file_path("invalid.log")
    assert status == HTTPStatus.BAD_REQUEST


def test_get_response():
    response = get_response(
        "logfile.log",
        ["log1", "log2"],
        offset=0,
        limit=2,
        has_next=True,
        next_link="/next",
    )
    expected_response = {
        "pagination": {
            "offset": 0,
            "limit": 2,
            "has_next": True,
            "next": "/next",
        },
        "entries": ["log1", "log2"],
    }
    assert response == expected_response


def test_get_next_url():
    next_url = get_next_url("logfile.log", 100, 10, "error")
    assert next_url == "/logs?filename=logfile.log&offset=100&limit=10&filter=error"
