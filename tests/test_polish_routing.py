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

    def __init__(self, config):
        self._config = config
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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("全部通过")
