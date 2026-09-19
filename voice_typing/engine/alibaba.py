"""阿里云 Paraformer 实时语音识别引擎"""

import queue
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback

from voice_typing.engine.base import BaseEngine


class ParaformerCallback(RecognitionCallback):
    """接收实时识别结果"""

    def __init__(self):
        super().__init__()
        self.final_text = ""
        self.last_preview = ""  # 最近一次未定稿预览，停止时兜底防尾字丢失
        self._sentences = []  # 累积所有句子
        self._on_text = None

    def set_on_text(self, callback):
        self._on_text = callback

    def on_event(self, result):
        sentence = result.get_sentence()
        if sentence and sentence.get("text"):
            text = sentence["text"]
            sentence_id = sentence.get("sentence_id", 0)
            end_time = sentence.get("end_time")
            is_final = end_time is not None and end_time > 0  # end_time 存在且 > 0 表示句子结束

            # 使用 sentence_id 去重：只在句子最终确定时添加
            if is_final:
                # 检查是否已存在该 sentence_id
                if not any(sid == sentence_id for sid, _ in self._sentences):
                    self._sentences.append((sentence_id, text))
                    self.final_text = "".join(t for _, t in self._sentences)
                self.last_preview = ""  # 句子已定稿，清空兜底
            else:
                # 实时预览（不保存，但记录用于停止时兜底）
                preview = "".join(t for _, t in self._sentences) + text
                self.last_preview = preview
                if self._on_text:
                    self._on_text(preview)
                return

            if self._on_text:
                self._on_text(self.final_text)


class AlibabaEngine(BaseEngine):
    """阿里云 Paraformer 实时语音识别"""

    name = "阿里云 Paraformer"

    def __init__(self, api_key: str = "", phrase_id: str = None):
        self._api_key = api_key
        self._recognition = None
        self._callback = None
        self._queue = queue.Queue()
        self._running = False
        self._phrase_id = phrase_id  # 热词表ID（UUID格式）

    def initialize(self) -> bool:
        if not self._api_key:
            return False
        dashscope.api_key = self._api_key
        return True

    def is_available(self) -> bool:
        return bool(self._api_key)

    def set_api_key(self, key: str):
        self._api_key = key

    def set_phrase_id(self, phrase_id: str):
        self._phrase_id = phrase_id

    def start(self):
        self._callback = ParaformerCallback()
        self._queue = queue.Queue()
        self._running = True

        model = "paraformer-realtime-v2"
        print(f"[Alibaba] 模型: {model}")
        self._recognition = Recognition(
            model=model,
            format="pcm",
            sample_rate=16000,
            callback=self._callback,
            enable_punctuation_prediction=True,
            enable_inverse_text_normalization=True,
        )

        # 传入热词表 phrase_id / vocabulary_id
        # phrase_id → v1 格式（resources），vocabulary_id → v2 格式（parameters）
        if self._phrase_id:
            print(f"[热词] 传入 phrase_id / vocabulary_id: {self._phrase_id}")
            self._recognition.start(
                phrase_id=self._phrase_id,
                vocabulary_id=self._phrase_id,
            )
        else:
            self._recognition.start()

    def set_text_callback(self, cb):
        if self._callback:
            self._callback.set_on_text(cb)

    def send_audio(self, pcm_bytes: bytes):
        if self._running and self._recognition:
            self._recognition.send_audio_frame(pcm_bytes)

    def stop(self) -> str:
        self._running = False
        if self._recognition:
            self._recognition.stop()
        if not self._callback:
            return ""
        final = self._callback.final_text.strip()
        preview = self._callback.last_preview.strip()
        # 若最后一句未定稿（尾字未进 final_text），用预览兜底，防止丢字
        return preview if len(preview) > len(final) else final
