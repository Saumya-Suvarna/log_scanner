"""Module providing unit test for all network utility functions"""

from unittest.mock import patch, AsyncMock
from network_utils import (
    handle_external_logs,
    fetch_logs_from_secondary_servers,
)


def test_handle_external_logs():
    with patch(
        "network_utils.fetch_logs_from_secondary_servers",
        return_value=[{"log": "log1", "source": "server1"}],
    ):
        response = handle_external_logs()
        assert response == {
            "source": "External Logs",
            "entries": [{"log": "log1", "source": "server1"}],
        }


def test_fetch_logs_from_secondary_servers():
    with patch(
        "network_utils.fetch_from_servers", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = [[{"log": "log1", "source": "server1"}]]
        logs = fetch_logs_from_secondary_servers()
        assert logs == [{"log": "log1", "source": "server1"}]
