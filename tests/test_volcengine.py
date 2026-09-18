import gzip
import json
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typing.engine.volcengine import (
    DEFAULT_RESOURCE_ID,
    WS_URL,
    VolcengineProtocolError,
    _build_auth_headers,
    _build_request_config,
    _parse_response,
)


def _server_frame(payload, *, flags=1, message_type=9, compression=1):
    raw = json.dumps(payload).encode()
    if compression == 1:
        raw = gzip.compress(raw)
    header = bytes([0x11, (message_type << 4) | flags, (1 << 4) | compression, 0])
    sequence = struct.pack(">i", -1 if flags == 3 else 1) if flags & 1 else b""
    return header + sequence + struct.pack(">I", len(raw)) + raw


class VolcengineEngineProtocolTests(unittest.TestCase):
    def test_seed_asr_2_defaults_to_optimized_streaming_endpoint(self):
        self.assertEqual(DEFAULT_RESOURCE_ID, "volc.seedasr.sauc.duration")
        self.assertTrue(WS_URL.endswith("/api/v3/sauc/bigmodel_async"))

    def test_new_api_key_auth_is_independent(self):
        headers = _build_auth_headers(
            api_key="new-key",
            resource_id=DEFAULT_RESOURCE_ID,
        )
        self.assertEqual(headers["X-Api-Key"], "new-key")
        self.assertNotIn("X-Api-App-Key", headers)
        self.assertNotIn("X-Api-Access-Key", headers)
        self.assertEqual(headers["X-Api-Sequence"], "-1")

    def test_request_uses_two_pass_recognition_and_inline_hotwords(self):
        config = _build_request_config(
            boosting_table_id="table-id",
            correct_words={"麦德360": "Mid360", "埋360": "Mid360"},
        )
        self.assertEqual(config["audio"]["language"], "zh-CN")
        self.assertTrue(config["request"]["enable_nonstream"])
        self.assertNotIn("language", config["request"])
        corpus = config["request"]["corpus"]
        self.assertEqual(corpus["boosting_table_id"], "table-id")
        self.assertEqual(
            json.loads(corpus["context"]),
            {"hotwords": [{"word": "Mid360"}]},
        )

    def test_response_parser_handles_sequence_and_definite_result(self):
        frame = _server_frame({
            "code": 20000000,
            "result": {
                "text": "测试成功",
                "utterances": [{"definite": True}],
            },
        })
        self.assertEqual(_parse_response(frame), ("测试成功", True))

    def test_response_parser_surfaces_protocol_error(self):
        detail = json.dumps({"message": "invalid resource id"}).encode()
        frame = (
            bytes([0x11, 0xF0, 0x10, 0x00])
            + struct.pack(">I", 45000001)
            + struct.pack(">I", len(detail))
            + detail
        )
        with self.assertRaisesRegex(VolcengineProtocolError, "45000001"):
            _parse_response(frame)


if __name__ == "__main__":
    unittest.main()
