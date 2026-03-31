import struct
import pytest
from unittest.mock import patch, MagicMock
from inventree_ipp.ipp import (
    print_job, get_printer_attributes, get_job_attributes,
    validate_job, cancel_job, IppError, IppOperation,
)


def _make_response(status: int, request_id: int = 1, attrs: bytes = b"") -> bytes:
    return struct.pack(">bbHI", 2, 0, status, request_id) + attrs + b"\x03"


def _make_job_id_response(job_id: int) -> bytes:
    buf = bytearray()
    buf += struct.pack(">bbHI", 2, 0, 0x0000, 1)
    buf += b"\x02"
    buf += b"\x21"
    name = b"job-id"
    buf += struct.pack(">H", len(name)) + name
    buf += struct.pack(">H", 4) + struct.pack(">i", job_id)
    buf += b"\x03"
    return bytes(buf)


def _mock_httpx_post(response_body: bytes, status_code: int = 200):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.content = response_body
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post = MagicMock(return_value=mock_response)
    return mock_client


class TestPrintJob:
    @patch("inventree_ipp.ipp.httpx.Client")
    def test_returns_job_id(self, mock_client_cls):
        client = _mock_httpx_post(_make_job_id_response(42))
        mock_client_cls.return_value = client
        result = print_job("ipp://10.0.0.1:631/ipp/print", b"%PDF-fake", "test-label")
        assert result["job_id"] == 42

    @patch("inventree_ipp.ipp.httpx.Client")
    def test_raises_on_ipp_error(self, mock_client_cls):
        client = _mock_httpx_post(_make_response(0x0400))
        mock_client_cls.return_value = client
        with pytest.raises(IppError) as exc_info:
            print_job("ipp://10.0.0.1:631/ipp/print", b"%PDF", "test")
        assert exc_info.value.status_code == 0x0400

    @patch("inventree_ipp.ipp.httpx.Client")
    def test_sends_to_correct_url(self, mock_client_cls):
        client = _mock_httpx_post(_make_job_id_response(1))
        mock_client_cls.return_value = client
        print_job("ipp://10.0.0.1:631/ipp/print", b"%PDF", "test")
        call_args = client.post.call_args
        assert call_args[0][0] == "http://10.0.0.1:631/ipp/print"


class TestGetPrinterAttributes:
    @patch("inventree_ipp.ipp.httpx.Client")
    def test_returns_printer_state(self, mock_client_cls):
        buf = bytearray()
        buf += struct.pack(">bbHI", 2, 0, 0x0000, 1)
        buf += b"\x04"
        buf += b"\x23"
        name = b"printer-state"
        buf += struct.pack(">H", len(name)) + name
        buf += struct.pack(">H", 4) + struct.pack(">i", 3)
        buf += b"\x03"
        client = _mock_httpx_post(bytes(buf))
        mock_client_cls.return_value = client
        result = get_printer_attributes("ipp://10.0.0.1:631/ipp/print")
        assert result["printer-state"] == 3

    @patch("inventree_ipp.ipp.httpx.Client")
    def test_raises_on_error(self, mock_client_cls):
        client = _mock_httpx_post(_make_response(0x0400))
        mock_client_cls.return_value = client
        with pytest.raises(IppError):
            get_printer_attributes("ipp://10.0.0.1:631/ipp/print")


class TestGetJobAttributes:
    @patch("inventree_ipp.ipp.httpx.Client")
    def test_returns_job_state(self, mock_client_cls):
        buf = bytearray()
        buf += struct.pack(">bbHI", 2, 0, 0x0000, 1)
        buf += b"\x02"
        buf += b"\x23"
        name = b"job-state"
        buf += struct.pack(">H", len(name)) + name
        buf += struct.pack(">H", 4) + struct.pack(">i", 9)
        buf += b"\x03"
        client = _mock_httpx_post(bytes(buf))
        mock_client_cls.return_value = client
        result = get_job_attributes("ipp://10.0.0.1:631/ipp/print", 42)
        assert result["job-state"] == 9


class TestValidateJob:
    @patch("inventree_ipp.ipp.httpx.Client")
    def test_success_returns_true(self, mock_client_cls):
        client = _mock_httpx_post(_make_response(0x0000))
        mock_client_cls.return_value = client
        assert validate_job("ipp://10.0.0.1:631/ipp/print") is True

    @patch("inventree_ipp.ipp.httpx.Client")
    def test_error_raises(self, mock_client_cls):
        client = _mock_httpx_post(_make_response(0x040D))
        mock_client_cls.return_value = client
        with pytest.raises(IppError):
            validate_job("ipp://10.0.0.1:631/ipp/print")


class TestCancelJob:
    @patch("inventree_ipp.ipp.httpx.Client")
    def test_success(self, mock_client_cls):
        client = _mock_httpx_post(_make_response(0x0000))
        mock_client_cls.return_value = client
        cancel_job("ipp://10.0.0.1:631/ipp/print", 42)

    @patch("inventree_ipp.ipp.httpx.Client")
    def test_error_raises(self, mock_client_cls):
        client = _mock_httpx_post(_make_response(0x0400))
        mock_client_cls.return_value = client
        with pytest.raises(IppError):
            cancel_job("ipp://10.0.0.1:631/ipp/print", 42)
