"""浮窗 ✕ 取消：停录、断开回调、丢弃迟到的润色结果，不粘贴。不联网、不启 Qt。

运行: python3 tests/test_cancel.py
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typing.app import VoiceTypingApp


class _Calls:
    """记录被调用的方法名"""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append(name)


class _Recorder(_Calls):
    def __init__(self):
        super().__init__()
        self._app_obj = "app"
        self.text_update = _Calls()
        self.level = _Calls()


class _Stub:
    _on_cancel = VoiceTypingApp._on_cancel
    _run_polish = VoiceTypingApp._run_polish
    _resolve_polish_provider = lambda self: "deepseek"
    _apply_alias_map = lambda self, t: t
    _build_vocabulary_hint = lambda self: ""
    _POLISH = VoiceTypingApp._POLISH
    _POLISH_BYPASS_CHARS = VoiceTypingApp._POLISH_BYPASS_CHARS

    def __init__(self):
        self._config = {}
        self._session = 1
        self._is_recording = True
        self._recording_start_time = 1.0
        self._hotkey = _Calls()
        self._overlay = _Calls()
        self._recorder = _Recorder()
        self._polish_debounce_timer = _Calls()
        self._polish_cancel_event = threading.Event()
        self.emitted = []
        self.polish_done = type("S", (), {"emit": lambda _s, t: self.emitted.append(t)})()


def test_cancel_while_recording_detaches_recorder():
    stub = _Stub()
    recorder = stub._recorder
    stub._on_cancel()
    assert recorder._app_obj is None          # 定稿文字不会再回调 _on_recording_done → 不会粘贴
    assert "disconnect" in recorder.text_update.calls and "disconnect" in recorder.level.calls
    assert "stop" in recorder.calls
    assert stub._recorder is None
    assert "cancel" in stub._hotkey.calls
    assert "reset" in stub._overlay.calls
    assert stub._session == 2 and not stub._is_recording


def test_polish_result_dropped_after_cancel():
    stub = _Stub()
    stub._recorder = None

    def slow_llm(prompt, text):               # 润色进行中用户点了 ✕
        stub._on_cancel()
        return "润色后的文字"

    stub._call_llm = slow_llm
    stub._run_polish("这是一段足够长、会走大模型润色流程的语音识别结果文本。")
    assert stub.emitted == []


def test_polish_result_kept_without_cancel():
    stub = _Stub()
    stub._call_llm = lambda prompt, text: "润色后的文字"
    stub._run_polish("这是一段足够长、会走大模型润色流程的语音识别结果文本。")
    assert stub.emitted == ["润色后的文字"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
