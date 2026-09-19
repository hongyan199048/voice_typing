"""豆包流式语音识别 2.0（Seed-ASR）WebSocket 引擎。"""

import asyncio
import gzip
import json
import queue
import struct
import threading
import uuid

import websockets

from voice_typing.engine.base import BaseEngine

WS_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
DEFAULT_RESOURCE_ID = "volc.seedasr.sauc.duration"

HDR_CONFIG = bytes([0x11, 0x10, 0x11, 0x00])
HDR_AUDIO = bytes([0x11, 0x20, 0x01, 0x00])
HDR_AUDIO_LAST = bytes([0x11, 0x22, 0x01, 0x00])


def _build_frame(header: bytes, payload: bytes) -> bytes:
    compressed = gzip.compress(payload)
    return header + struct.pack(">I", len(compressed)) + compressed


class VolcengineProtocolError(RuntimeError):
    """火山 ASR 服务返回的协议错误。"""


def _build_auth_headers(*, api_key: str, resource_id: str) -> dict:
    """豆包语音控制台签发的 API Key 鉴权。"""
    return {
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": resource_id or DEFAULT_RESOURCE_ID,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "X-Api-Connect-Id": str(uuid.uuid4()),
        "X-Api-Sequence": "-1",
    }


def _build_request_config(*, boosting_table_id: str,
                          correct_words: dict) -> dict:
    """构造 Seed-ASR 2.0 首包参数，避免把 ASR 与后续 LLM 润色混在一起。"""
    config = {
        "user": {"uid": "voice-typing"},
        "audio": {
            "format": "pcm",
            "codec": "raw",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
            "language": "zh-CN",
        },
        "request": {
            "model_name": "bigmodel",
            # bigmodel_async 才支持二遍识别：实时出字后再给出 definite 结果。
            "enable_nonstream": True,
            "enable_itn": True,
            "enable_punc": True,
            # 语义顺滑：服务端删「呃/嗯/那个」等口水词、修口吃重复
            "enable_ddc": True,
            "result_type": "single",
        },
    }

    corpus = {}
    if boosting_table_id:
        corpus["boosting_table_id"] = boosting_table_id

    # 官方协议没有内联 correct_words 字段。把本地词典的正确词作为热词直传；
    # 别名替换仍由应用在识别后本地执行。
    terms = list(dict.fromkeys(term for term in correct_words.values() if term))
    if terms:
        corpus["context"] = json.dumps(
            {"hotwords": [{"word": term} for term in terms]},
            ensure_ascii=False,
        )
    if corpus:
        config["request"]["corpus"] = corpus
    return config


def _parse_response(msg: bytes):
    """解析二进制响应帧，返回 (text, is_final)

    BigModel 2.0 帧布局: [4字节header][4字节序列号][4字节payload长度][payload]
    payload 是否 gzip 由 header 字节 2 的低 4 位决定（0=无压缩，1=gzip）。
    """
    if len(msg) < 4:
        return "", False
    header_size = (msg[0] & 0x0F) * 4
    message_type = msg[1] >> 4
    flags = msg[1] & 0x0F
    compression = msg[2] & 0x0F

    offset = header_size
    if message_type == 0x0F:
        if len(msg) < offset + 8:
            raise VolcengineProtocolError("服务返回了不完整的错误帧")
        error_code = struct.unpack(">I", msg[offset:offset + 4])[0]
        payload_len = struct.unpack(">I", msg[offset + 4:offset + 8])[0]
        payload = msg[offset + 8:offset + 8 + payload_len]
        if compression == 1:
            payload = gzip.decompress(payload)
        detail = payload.decode("utf-8", errors="replace")
        raise VolcengineProtocolError(f"错误码 {error_code}: {detail}")

    if message_type != 0x09:
        return "", False

    # flags=1/3 时，payload size 前存在 4 字节 sequence。
    if flags & 0x01:
        offset += 4
    if len(msg) < offset + 4:
        return "", False
    payload_len = struct.unpack(">I", msg[offset:offset + 4])[0]
    payload = msg[offset + 4:offset + 4 + payload_len]
    if len(payload) != payload_len:
        return "", False
    if compression == 1:
        payload = gzip.decompress(payload)
    data = json.loads(payload)
    if "code" in data and data["code"] != 20000000:
        return "", False
    results = data.get("result", {})
    if isinstance(results, list):
        if not results:
            return "", False
        results = results[0]
    text = results.get("text", "")
    # BigModel 2.0 的 definite 在 utterances[0] 里；服务端最后帧会带 NEG_SEQUENCE flag
    utterances = results.get("utterances") or []
    is_final = any(item.get("definite", False) for item in utterances) or bool(flags & 0x02)
    return text, is_final


class VolcengineEngine(BaseEngine):
    """豆包流式语音识别 2.0（双向流式优化版）。"""

    name = "豆包流式语音识别 2.0"

    def __init__(self, api_key: str = "", resource_id: str = DEFAULT_RESOURCE_ID,
                 boosting_table_id: str = "", correct_words: dict = None):
        self._api_key = api_key
        self._resource_id = resource_id or DEFAULT_RESOURCE_ID
        self._boosting_table_id = boosting_table_id  # 控制台热词表 ID（识别偏置）
        self._correct_words = correct_words or {}     # 内联错词→正词映射
        self._running = False
        self._audio_queue = None
        self._text_callback = None
        self._final_text = ""
        self._last_preview = ""  # 最近一次未定稿预览，停止时兜底防尾字丢失
        self._ws_done = None

    def initialize(self) -> bool:
        return bool(self._api_key)

    def is_available(self) -> bool:
        return bool(self._api_key)

    def set_text_callback(self, cb):
        self._text_callback = cb

    def start(self):
        self.last_error = ""
        self._running = True
        self._audio_queue = queue.Queue()
        self._final_text = ""
        self._last_preview = ""
        self._ws_done = threading.Event()
        threading.Thread(target=self._run_ws, daemon=True).start()

    def _run_ws(self):
        asyncio.run(self._ws_session())

    async def _ws_session(self):
        headers = _build_auth_headers(
            api_key=self._api_key,
            resource_id=self._resource_id,
        )
        try:
            async with websockets.connect(
                WS_URL,
                additional_headers=headers,
                max_size=10_000_000,
                ping_interval=20,
            ) as ws:
                print(f"[Volcengine] 模型档位: {self._resource_id}")
                response_headers = getattr(
                    getattr(ws, "response", None), "headers", None
                ) or getattr(ws, "response_headers", None)
                if response_headers:
                    log_id = response_headers.get("X-Tt-Logid")
                    if log_id:
                        print(f"[Volcengine] X-Tt-Logid: {log_id}")

                config = _build_request_config(
                    boosting_table_id=self._boosting_table_id,
                    correct_words=self._correct_words,
                )
                payload = json.dumps(config).encode()
                await ws.send(_build_frame(HDR_CONFIG, payload))

                async def send_loop():
                    loop = asyncio.get_event_loop()
                    while self._running:
                        try:
                            data = await loop.run_in_executor(
                                None, lambda: self._audio_queue.get(timeout=0.3)
                            )
                        except queue.Empty:
                            continue
                        await ws.send(_build_frame(HDR_AUDIO, data))
                    # drain remaining audio
                    while True:
                        try:
                            data = self._audio_queue.get_nowait()
                            await ws.send(_build_frame(HDR_AUDIO, data))
                        except queue.Empty:
                            break
                    await ws.send(_build_frame(HDR_AUDIO_LAST, b""))

                async def recv_loop():
                    final_parts = []
                    async for msg in ws:
                        text, is_final = _parse_response(msg)
                        if not text:
                            continue
                        if is_final:
                            # 仅去重相邻重复（防同一句 final 被重发），
                            # 保留用户真实重复说的短语（如"对对对"）
                            if not final_parts or text != final_parts[-1]:
                                final_parts.append(text)
                            self._final_text = "".join(final_parts)
                            self._last_preview = ""  # 已定稿，清空兜底
                            preview = self._final_text
                        else:
                            preview = "".join(final_parts) + text
                            self._last_preview = preview  # 记录未定稿预览用于兜底
                        if self._text_callback:
                            self._text_callback(preview)

                await asyncio.gather(send_loop(), recv_loop())
        except Exception as e:
            print(f"[Volcengine] WS 连接异常: {e}")
            self.last_error = "识别失败，请检查网络和 API Key"
        finally:
            self._ws_done.set()

    def send_audio(self, pcm_bytes: bytes):
        if self._running and self._audio_queue is not None:
            self._audio_queue.put(pcm_bytes)

    def stop(self) -> str:
        self._running = False
        self._ws_done.wait(timeout=10)
        final = self._final_text.strip()
        preview = (self._last_preview or "").strip()
        # 若最后一句未定稿，用预览兜底，防止丢字
        return preview if len(preview) > len(final) else final
