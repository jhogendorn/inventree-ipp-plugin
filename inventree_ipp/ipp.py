"""IPP 2.0 wire protocol client per RFC 8010."""

import struct
from enum import IntEnum


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
