"""浮窗圆点状态流转自检：松键后「处理中」，粘贴后才回待机。不联网、不启 Qt。

运行: python3 tests/test_overlay_states.py
"""
import os
import sys
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typing.app import VoiceTypingApp


class _Overlay:
    """记录被调用的浮窗方法名"""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append(name)


class _Stub:
    _on_recording_done = VoiceTypingApp._on_recording_done
    _on_polish_done = VoiceTypingApp._on_polish_done
    _cached_polish_is_stale = VoiceTypingApp._cached_polish_is_stale
    _resolve_polish_provider = lambda self: "off"  # 不起情绪判断线程

    def __init__(self):
        self._overlay = _Overlay()
        self._engine = None
        self._recording_start_time = time.time()
        self._cached_polished_text = ""
        self._polish_source_text = ""
        self._is_recording = False
        self.pasted = []

    def _update_stats(self, text):
        pass

    def _type_text(self, text):
        self.pasted.append(text)

    def _run_polish(self, text):
        pass


def _run(fn):
    with mock.patch("voice_typing.app.QTimer"), mock.patch("voice_typing.app.threading"):
        fn()


def test_stays_processing_until_polish_pasted():
    stub = _Stub()
    _run(lambda: stub._on_recording_done("明天早上七点半提醒我去买菜"))
    assert "stop_recording" not in stub._overlay.calls  # 润色中：保持转圈
    _run(lambda: stub._on_polish_done("明天早上 7:30 提醒我去买菜。"))
    assert "stop_recording" in stub._overlay.calls
    assert stub.pasted == ["明天早上 7:30 提醒我去买菜。"]


def test_empty_result_returns_to_idle():
    stub = _Stub()
    _run(lambda: stub._on_recording_done(""))
    assert "stop_recording" in stub._overlay.calls


def test_cached_polish_returns_to_idle_and_pastes():
    stub = _Stub()
    stub._cached_polished_text = "已润色"
    stub._polish_source_text = "原文"
    _run(lambda: stub._on_recording_done("原文"))
    assert "stop_recording" in stub._overlay.calls
    assert stub.pasted == ["已润色"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


def test_llm_emotion_overrides_keywords():
    """「遇到很坏的人」没有情绪关键词：大模型判 sad 后，出结果时摆 sad；先到后到都行"""
    from voice_typing.ui.overlay import OverlayWindow
    text = "我今天遇到了一些很坏很坏的人"
    for early in (True, False):
        o = OverlayWindow()
        o.start_recording()
        o.update_text(text)
        o.start_processing()
        if early:
            o.set_emotion("sad")       # 润色还没完，情绪先回来
        o.set_text(text)
        o.stop_recording()
        if not early:
            o.set_emotion("sad")       # 出结果后才回来
        assert o._avatar._expr == "sad"
