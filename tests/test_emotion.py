"""情绪关键词自检：命中、取最后出现、否定反转、易误伤词、未命中回 neutral。

运行: python3 tests/test_emotion.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typing.core.emotion import detect_emotion


def test_keywords():
    assert detect_emotion("今天真开心") == "happy"
    assert detect_emotion("哇，居然是真的") == "surprised"
    assert detect_emotion("唉，太可惜了") == "sad"
    assert detect_emotion("为什么又报错") == "confused"
    assert detect_emotion("WOW") == "surprised"


def test_everyday_negative_moods():
    assert detect_emotion("我今天的心情特别的不好") == "sad"
    assert detect_emotion("心情不太好") == "sad"
    assert detect_emotion("我好难受") == "sad"
    assert detect_emotion("压力大到快崩溃了") == "sad"
    assert detect_emotion("烦死了") == "squinted"
    assert detect_emotion("今天好累啊") == "sleepy"


def test_negation_flips():
    assert detect_emotion("我今天不开心") == "sad"
    assert detect_emotion("其实不是很满意") == "sad"
    assert detect_emotion("我一点都不难过") == "calm"
    assert detect_emotion("还不错") == "happy"          # 「不错」本身是正面词


def test_last_emotion_wins():
    assert detect_emotion("刚才挺难过的，现在好开心") == "happy"
    assert detect_emotion("开心了一上午，结果下午好累") == "sleepy"


def test_no_false_hits():
    assert detect_emotion("明天早上七点半提醒我去买菜") == "neutral"
    assert detect_emotion("麻烦你帮我查个困难的问题") != "squinted"
    assert detect_emotion("这个月累计用了三百度电") == "neutral"
    assert detect_emotion("") == "neutral"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
