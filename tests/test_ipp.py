import struct
from inventree_ipp.ipp import encode_ipp_request, decode_ipp_response, IppOperation

class TestEncodeIppRequest:
    def test_get_printer_attributes_encoding(self):
        msg = encode_ipp_request(
            operation=IppOperation.GET_PRINTER_ATTRIBUTES,
            request_id=1,
            printer_uri="ipp://10.0.0.1:631/ipp/print",
        )
        ver_major, ver_minor, op, req_id = struct.unpack('>bbHI', msg[:8])
        assert ver_major == 2
        assert ver_minor == 0
        assert op == 0x000B
        assert req_id == 1
        assert msg[8:9] == b'\x01'
        assert msg.endswith(b'\x03')
        assert b'attributes-charset' in msg
        assert b'attributes-natural-language' in msg
        assert b'printer-uri' in msg

    def test_print_job_includes_document_data(self):
        pdf_data = b'%PDF-1.4 fake pdf content'
        msg = encode_ipp_request(
            operation=IppOperation.PRINT_JOB,
            request_id=2,
            printer_uri="ipp://10.0.0.1:631/ipp/print",
            job_name="test-label",
            document_format="application/pdf",
            document_data=pdf_data,
        )
        _, _, op, _ = struct.unpack('>bbHI', msg[:8])
        assert op == 0x0002
        eoa_idx = msg.rindex(b'\x03', 0, msg.index(pdf_data))
        assert msg[eoa_idx + 1:] == pdf_data

    def test_print_job_includes_copies(self):
        msg = encode_ipp_request(
            operation=IppOperation.PRINT_JOB,
            request_id=3,
            printer_uri="ipp://10.0.0.1:631/ipp/print",
            job_name="test",
            document_format="application/pdf",
            document_data=b'%PDF',
            copies=3,
        )
        assert b'copies' in msg

    def test_cancel_job_includes_job_id(self):
        msg = encode_ipp_request(
            operation=IppOperation.CANCEL_JOB,
            request_id=4,
            printer_uri="ipp://10.0.0.1:631/ipp/print",
            job_id=42,
        )
        _, _, op, _ = struct.unpack('>bbHI', msg[:8])
        assert op == 0x0008
        assert b'job-id' in msg

class TestDecodeIppResponse:
    def test_decode_success_response(self):
        raw = struct.pack('>bbHI', 2, 0, 0x0000, 1) + b'\x03'
        result = decode_ipp_response(raw)
        assert result['status_code'] == 0x0000
        assert result['request_id'] == 1

    def test_decode_error_response(self):
        raw = struct.pack('>bbHI', 2, 0, 0x0400, 1) + b'\x03'
        result = decode_ipp_response(raw)
        assert result['status_code'] == 0x0400

    def test_decode_extracts_integer_attribute(self):
        buf = bytearray()
        buf += struct.pack('>bbHI', 2, 0, 0x0000, 1)
        buf += b'\x02'
        buf += b'\x21'
        buf += struct.pack('>H', 6) + b'job-id'
        buf += struct.pack('>H', 4) + struct.pack('>i', 42)
        buf += b'\x03'
        result = decode_ipp_response(bytes(buf))
        assert result['attributes']['job-id'] == 42

    def test_decode_extracts_string_attribute(self):
        buf = bytearray()
        buf += struct.pack('>bbHI', 2, 0, 0x0000, 1)
        buf += b'\x04'
        buf += b'\x44'
        name = b'printer-state-reasons'
        buf += struct.pack('>H', len(name)) + name
        val = b'none'
        buf += struct.pack('>H', len(val)) + val
        buf += b'\x03'
        result = decode_ipp_response(bytes(buf))
        assert result['attributes']['printer-state-reasons'] == 'none'
