"""检查 GitHub Release 是否有新版本。

只用 stdlib，不引入新依赖——打包时 vendor 清单不必动。
releases/latest 只返回非 prerelease / 非 draft 的最新正式版，dev 标签天然被排除。
"""

import json
import urllib.request

_RELEASES_URL = (
    "https://api.github.com/repos/hongyan199048/voice_typing/releases/latest"
)


def _parse_version(v):
    """'v1.6.10' → [1, 6, 10]。非数字段按 0 处理，缺失段补 0。"""
    parts = []
    for p in (v or "").lstrip("vV").split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return parts


def _is_newer(current, latest):
    """逐段数值比较，避免 '1.6.10' < '1.6.9' 这种字符串比较的坑。"""
    c, l = _parse_version(current), _parse_version(latest)
    for i in range(max(len(c), len(l))):
        a = c[i] if i < len(c) else 0
        b = l[i] if i < len(l) else 0
        if a != b:
            return b > a
    return False


def check_for_update(current_version, timeout=5):
    """查最新 Release。返回 {'update': bool, 'latest': str, 'url': str}。

    已是最新 / 网络失败 / 解析失败一律返回 None，调用方不提示即可。
    """
    try:
        req = urllib.request.Request(
            _RELEASES_URL, headers={"User-Agent": "voice-typing"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        tag = data.get("tag_name", "")
        if not tag:
            return None
        return {
            "update": _is_newer(current_version, tag),
            "latest": tag.lstrip("vV"),
            "url": data.get("html_url", ""),
        }
    except Exception:
        return None
