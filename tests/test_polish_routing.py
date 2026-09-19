"""润色路由自检：解耦、关闭、失败回退原文。不联网。

运行: python3 tests/test_polish_routing.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typing.app import VoiceTypingApp, _LLM_PROVIDERS


class _Stub:
    """只借 VoiceTypingApp 的润色逻辑，不启动 Qt / 热键 / 引擎。"""

    _resolve_polish_provider = VoiceTypingApp._resolve_polish_provider
    _realtime_polish_enabled = VoiceTypingApp._realtime_polish_enabled
    _call_llm = VoiceTypingApp._call_llm
    _apply_alias_map = VoiceTypingApp._apply_alias_map
    _run_polish = VoiceTypingApp._run_polish
    _build_vocabulary_hint = VoiceTypingApp._build_vocabulary_hint
    _POLISH = VoiceTypingApp._POLISH
    _POLISH_BYPASS_CHARS = VoiceTypingApp._POLISH_BYPASS_CHARS
    _run_realtime_polish_stream = VoiceTypingApp._run_realtime_polish_stream
    _cached_polish_is_stale = VoiceTypingApp._cached_polish_is_stale

    def __init__(self, config):
        self._config = config
        self._cached_polished_text = ""
        self._polish_source_text = ""
        self.emitted = []
        self.polish_done = type("S", (), {"emit": lambda _s, t: self.emitted.append(t)})()
        self.polish_progress = type("S", (), {"emit": lambda _s, t: None})()


LONG = "这个呃这个方案我觉得还是可以的，我们先按这个来做吧，然后再看看效果怎么样。"


def test_provider_independent_of_asr_engine():
    """ASR 选豆包不再把润色带成豆包——两侧解耦。"""
    stub = _Stub({"engine": "volcengine", "polish_provider": "", "glm_api_key": "k"})
    assert stub._resolve_polish_provider() == "glm"

    stub = _Stub({"engine": "alibaba", "polish_provider": "minimax", "minimax_api_key": "k"})
    assert stub._resolve_polish_provider() == "minimax"


def test_no_keys_means_off():
    assert _Stub({"polish_provider": ""})._resolve_polish_provider() == "off"


def test_off_outputs_raw_text_with_alias():
    stub = _Stub({
        "polish_provider": "off",
        "custom_vocabulary": [{"term": "CUDA", "alias": "库达"}],
    })
    stub._run_polish("我在配库达环境，装了半天还是报错，等下再看。")
    assert stub.emitted == ["我在配CUDA环境，装了半天还是报错，等下再看。"]


def test_missing_key_falls_back_to_raw_text():
    """选了厂商但没填 Key：回退原文，不抛异常、不换别家。"""
    stub = _Stub({"polish_provider": "deepseek", "deepseek_api_key": ""})
    assert stub._call_llm("p", LONG) is None
    stub._run_polish(LONG)
    assert stub.emitted == [LONG]


def test_llm_failure_falls_back_to_raw_text():
    """网络/接口异常时回退原文（用不可达 base_url 触发真实异常）。"""
    orig = _LLM_PROVIDERS["deepseek"]
    _LLM_PROVIDERS["deepseek"] = ("http://127.0.0.1:1", "deepseek-chat", "deepseek_api_key")
    try:
        stub = _Stub({"polish_provider": "deepseek", "deepseek_api_key": "sk-fake"})
        stub._run_polish(LONG)
        assert stub.emitted == [LONG]
    finally:
        _LLM_PROVIDERS["deepseek"] = orig


def test_realtime_polish_off_by_default():
    assert not _Stub({"polish_provider": "glm", "glm_api_key": "k"})._realtime_polish_enabled()
    assert _Stub({"polish_provider": "glm", "glm_api_key": "k",
                  "realtime_polish": True})._realtime_polish_enabled()
    # 润色关闭时，开关打开也不跑
    assert not _Stub({"polish_provider": "off", "realtime_polish": True})._realtime_polish_enabled()


class _FakeOverlay:
    """只提供 _run_realtime_polish_stream 读的那一个属性。"""

    def __init__(self, shown_text):
        self._text_label = type("L", (), {"text": lambda _s: shown_text})()


def test_midway_pause_polish_is_not_reused_for_longer_text():
    """中途停顿润过的前缀属于过期缓存，最终文本更长时必须重润，不能拿前缀去粘贴。"""
    import threading

    stub = _Stub({"polish_provider": "off"})
    stub._polish_cancel_event = threading.Event()
    stub._overlay = _FakeOverlay("前半句，")

    stub._run_realtime_polish_stream()          # 模拟停顿 1s：只润了当时浮窗里的前半句
    assert stub._polish_source_text == "前半句，"
    assert not stub._cached_polish_is_stale("前半句，")        # 就说到这儿 → 缓存可用
    assert stub._cached_polish_is_stale("前半句，后半句。")     # 后面又说了 → 缓存作废
    assert _Stub({})._cached_polish_is_stale("随便")           # 从没缓存过 → 视为不可用


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("全部通过")
