"""IPP 2.0 wire protocol client per RFC 8010."""

import struct
from enum import IntEnum
from urllib.parse import urlparse

import httpx


class IppOperation(IntEnum):
    PRINT_JOB = 0x0002
    VALIDATE_JOB = 0x0004
    CANCEL_JOB = 0x0008
    GET_JOB_ATTRIBUTES = 0x0009
    GET_PRINTER_ATTRIBUTES = 0x000B


class IppError(Exception):
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"IPP error 0x{status_code:04x}: {message}")


_OPERATION_ATTRIBUTES = 0x01
_JOB_ATTRIBUTES = 0x02
_END_OF_ATTRIBUTES = 0x03
_PRINTER_ATTRIBUTES = 0x04

_TAG_INTEGER = 0x21
_TAG_BOOLEAN = 0x22
_TAG_ENUM = 0x23
_TAG_TEXT = 0x41
_TAG_NAME = 0x42
_TAG_KEYWORD = 0x44
_TAG_URI = 0x45
_TAG_CHARSET = 0x47
_TAG_NATURAL_LANGUAGE = 0x48
_TAG_MIME_MEDIA_TYPE = 0x49


def _encode_attr(tag: int, name: str, value: bytes) -> bytes:
    name_bytes = name.encode("utf-8")
    return (
        struct.pack("b", tag)
        + struct.pack(">H", len(name_bytes))
        + name_bytes
        + struct.pack(">H", len(value))
        + value
    )


def _encode_str_attr(tag: int, name: str, value: str) -> bytes:
    return _encode_attr(tag, name, value.encode("utf-8"))


def _encode_int_attr(tag: int, name: str, value: int) -> bytes:
    return _encode_attr(tag, name, struct.pack(">i", value))


def encode_ipp_request(
    *,
    operation: IppOperation,
    request_id: int,
    printer_uri: str,
    job_name: str | None = None,
    document_format: str | None = None,
    document_data: bytes | None = None,
    job_id: int | None = None,
    copies: int | None = None,
) -> bytes:
    buf = bytearray()
    buf += struct.pack(">bbHI", 2, 0, operation, request_id)
    buf += struct.pack("b", _OPERATION_ATTRIBUTES)
    buf += _encode_str_attr(_TAG_CHARSET, "attributes-charset", "utf-8")
    buf += _encode_str_attr(_TAG_NATURAL_LANGUAGE, "attributes-natural-language", "en")
    buf += _encode_str_attr(_TAG_URI, "printer-uri", printer_uri)
    if job_name is not None:
        buf += _encode_str_attr(_TAG_NAME, "job-name", job_name)
    if document_format is not None:
        buf += _encode_str_attr(_TAG_MIME_MEDIA_TYPE, "document-format", document_format)
    if job_id is not None:
        buf += _encode_int_attr(_TAG_INTEGER, "job-id", job_id)
    if copies is not None and copies > 1:
        buf += struct.pack("b", _JOB_ATTRIBUTES)
        buf += _encode_int_attr(_TAG_INTEGER, "copies", copies)
    buf += struct.pack("b", _END_OF_ATTRIBUTES)
    if document_data is not None:
        buf += document_data
    return bytes(buf)


def decode_ipp_response(data: bytes) -> dict:
    if len(data) < 8:
        raise IppError(0xFFFF, "Response too short")
    _, _, status_code, request_id = struct.unpack(">bbHI", data[:8])
    attributes = {}
    offset = 8
    while offset < len(data):
        tag = data[offset]
        offset += 1
        if tag in (_OPERATION_ATTRIBUTES, _JOB_ATTRIBUTES, _PRINTER_ATTRIBUTES):
            continue
        if tag == _END_OF_ATTRIBUTES:
            break
        if offset + 2 > len(data):
            break
        name_len = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        name = data[offset : offset + name_len].decode("utf-8") if name_len > 0 else ""
        offset += name_len
        if offset + 2 > len(data):
            break
        value_len = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        raw_value = data[offset : offset + value_len]
        offset += value_len
        if not name:
            continue
        if tag in (_TAG_INTEGER, _TAG_ENUM) and value_len == 4:
            attributes[name] = struct.unpack(">i", raw_value)[0]
        elif tag == _TAG_BOOLEAN and value_len == 1:
            attributes[name] = raw_value[0] != 0
        elif tag in (
            _TAG_TEXT, _TAG_NAME, _TAG_KEYWORD, _TAG_URI,
            _TAG_CHARSET, _TAG_NATURAL_LANGUAGE, _TAG_MIME_MEDIA_TYPE,
        ):
            attributes[name] = raw_value.decode("utf-8")
        else:
            attributes[name] = raw_value
    return {
        "status_code": status_code,
        "request_id": request_id,
        "attributes": attributes,
    }


_request_counter = 0


def _next_request_id() -> int:
    global _request_counter
    _request_counter += 1
    return _request_counter


def _ipp_uri_to_http(uri: str) -> str:
    parsed = urlparse(uri)
    scheme = "https" if parsed.scheme == "ipps" else "http"
    return parsed._replace(scheme=scheme).geturl()


def _send_request(uri: str, data: bytes, timeout: float = 30.0) -> dict:
    http_url = _ipp_uri_to_http(uri)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            http_url,
            content=data,
            headers={"Content-Type": "application/ipp"},
        )
        response.raise_for_status()
    result = decode_ipp_response(response.content)
    if result["status_code"] > 0x00FF:
        msg = result["attributes"].get("status-message", "")
        raise IppError(result["status_code"], msg)
    return result


def print_job(
    uri: str,
    pdf_data: bytes,
    job_name: str,
    copies: int = 1,
    timeout: float = 30.0,
) -> dict:
    data = encode_ipp_request(
        operation=IppOperation.PRINT_JOB,
        request_id=_next_request_id(),
        printer_uri=uri,
        job_name=job_name,
        document_format="application/pdf",
        document_data=pdf_data,
        copies=copies,
    )
    result = _send_request(uri, data, timeout)
    job_id = result["attributes"].get("job-id")
    return {"job_id": job_id, "status_code": result["status_code"]}


def get_printer_attributes(uri: str, timeout: float = 10.0) -> dict:
    data = encode_ipp_request(
        operation=IppOperation.GET_PRINTER_ATTRIBUTES,
        request_id=_next_request_id(),
        printer_uri=uri,
    )
    result = _send_request(uri, data, timeout)
    return result["attributes"]


def get_job_attributes(uri: str, job_id: int, timeout: float = 10.0) -> dict:
    data = encode_ipp_request(
        operation=IppOperation.GET_JOB_ATTRIBUTES,
        request_id=_next_request_id(),
        printer_uri=uri,
        job_id=job_id,
    )
    result = _send_request(uri, data, timeout)
    return result["attributes"]


def validate_job(
    uri: str,
    document_format: str = "application/pdf",
    timeout: float = 10.0,
) -> bool:
    data = encode_ipp_request(
        operation=IppOperation.VALIDATE_JOB,
        request_id=_next_request_id(),
        printer_uri=uri,
        document_format=document_format,
    )
    _send_request(uri, data, timeout)
    return True


def cancel_job(uri: str, job_id: int, timeout: float = 10.0) -> None:
    data = encode_ipp_request(
        operation=IppOperation.CANCEL_JOB,
        request_id=_next_request_id(),
        printer_uri=uri,
        job_id=job_id,
    )
    _send_request(uri, data, timeout)
