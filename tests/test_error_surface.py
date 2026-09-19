"""失败要让用户看见：录音结束没出文字时，浮窗必须显示原因而不是静默复位。

运行: python3 tests/test_error_surface.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typing.app import VoiceTypingApp


class _FakeOverlay:
    def __init__(self):
        self.calls = []

    def stop_recording(self):
        self.calls.append("stop_recording")

    def set_text(self, t):
        self.calls.append(("set_text", t))

    def reset(self):
        self.calls.append("reset")

    def show_error(self, msg):
        self.calls.append(("show_error", msg))


class _FakeEngine:
    def __init__(self, last_error=""):
        self.last_error = last_error


class _Stub:
    """只借 VoiceTypingApp 的收尾逻辑，不启动 Qt / 热键 / 引擎。"""

    _on_recording_done = VoiceTypingApp._on_recording_done
    _cached_polish_is_stale = VoiceTypingApp._cached_polish_is_stale

    def __init__(self, last_error=""):
        self._overlay = _FakeOverlay()
        self._engine = _FakeEngine(last_error)
        self._cached_polished_text = ""
        self._polish_source_text = ""
        self._recording_start_time = time.time()
        self._recording_duration = 0


def test_engine_error_is_shown_to_user():
    """WS 超时/麦克风打不开这类失败，以前只 print 到 stdout，用户看不到。"""
    stub = _Stub(last_error="识别失败，请检查网络和 API Key")
    stub._on_recording_done("")
    assert ("show_error", "识别失败，请检查网络和 API Key") in stub._overlay.calls
    assert "reset" not in stub._overlay.calls


def test_silence_still_resets_quietly():
    """没说话导致的空结果不是错误，不该弹提示。"""
    stub = _Stub(last_error="")
    stub._on_recording_done("")
    assert "reset" in stub._overlay.calls
    assert not any(c[0] == "show_error" for c in stub._overlay.calls if isinstance(c, tuple))


def test_successful_text_never_shows_error():
    """有识别结果时走正常流程，即便引擎残留了上一次的错误也不提示。"""
    stub = _Stub(last_error="上一次的陈旧错误")
    stub._type_text = lambda t: stub._overlay.calls.append(("type", t))
    stub._run_polish = lambda t: None
    stub._on_recording_done("今天天气不错")
    assert not any(c[0] == "show_error" for c in stub._overlay.calls if isinstance(c, tuple))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("全部通过")
