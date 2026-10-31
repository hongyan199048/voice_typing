"""智能润色场景识别：WM_CLASS / 浏览器标题 → 场景，及追加的格式要求。

运行: python3 tests/test_scene.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typing.core.scene import detect_scene, scene_hint

# 本机实测的 xprop WM_CLASS 输出
FEISHU = 'WM_CLASS(STRING) = "bytedance-feishu", "Bytedance-feishu"'
VSCODE = 'WM_CLASS(STRING) = "code", "code"'
CHROME = 'WM_CLASS(STRING) = "google-chrome", "Google-chrome"'
TERM = 'WM_CLASS(STRING) = "gnome-terminal-server", "Gnome-terminal"'


def test_apps_by_class():
    assert detect_scene(FEISHU, "飞书") == "chat"
    assert detect_scene(VSCODE, "README.md - voice-typing-app - Visual Studio Code") == "code"
    assert detect_scene(TERM, "admin123@admin123: ~") == "terminal"
    assert detect_scene('WM_CLASS(STRING) = "libreoffice", "libreoffice-writer"', "报告.odt") == "doc"


def test_browser_by_title():
    assert detect_scene(CHROME, "收件箱 - Gmail - Google Chrome") == "email"
    assert detect_scene(CHROME, "ChatGPT - Google Chrome") == "code"
    assert detect_scene(CHROME, "周报 - 飞书云文档 - Google Chrome") == "doc"
    assert detect_scene(CHROME, "MPPI 与 RL 实测对比 - Google Chrome") == "other"


def test_unknown_and_empty_fall_back():
    assert detect_scene("", "") == "other"
    assert detect_scene('WM_CLASS(STRING) = "org.gnome.Nautilus"', "Downloads") == "other"
    assert scene_hint("other") == ""
    assert "编号列表" in scene_hint("doc") and "不要编号列表" in scene_hint("chat")
    assert "编号列表" in scene_hint("email")  # 邮件里并列要点也要分条


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
