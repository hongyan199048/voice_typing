"""版本比较自检：只测纯逻辑，不联网。

运行: python3 tests/test_updater.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typing.core.updater import _parse_version, _is_newer


def test_parse_version():
    assert _parse_version("1.6.1") == [1, 6, 1]
    assert _parse_version("v1.6.1") == [1, 6, 1]
    assert _parse_version("V1.6.1") == [1, 6, 1]
    assert _parse_version("1.6") == [1, 6]
    assert _parse_version("") == [0]


def test_newer():
    assert _is_newer("1.6.1", "1.6.2")
    assert _is_newer("1.6.1", "v1.7.0")
    assert _is_newer("1.5.0", "1.6.1")


def test_not_newer():
    assert not _is_newer("1.6.1", "1.6.1")
    assert not _is_newer("1.6.1", "v1.6.1")
    assert not _is_newer("1.6.1", "1.6.0")
    assert not _is_newer("2.0.0", "1.9.9")


def test_numeric_not_string_compare():
    """'1.6.10' 必须大于 '1.6.9'——按字符串比会得出相反结论。"""
    assert _is_newer("1.6.9", "1.6.10")
    assert not _is_newer("1.6.10", "1.6.9")


def test_shorter_version_padded():
    """段数不同时短的补 0：1.6 == 1.6.0 < 1.6.1。"""
    assert not _is_newer("1.6", "1.6.0")
    assert _is_newer("1.6", "1.6.1")
    assert not _is_newer("1.6.1", "1.6")


def test_malformed_does_not_crash():
    assert not _is_newer("1.6.1", "")
    assert not _is_newer("1.6.1", "abc")
    assert _is_newer("abc", "1.0.0")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("全部通过")
