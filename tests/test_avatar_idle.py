"""头像待机小动作自检：会做动作并回正、久不动打盹、开始录音 / 鼠标移上来就醒。

运行: python3 tests/test_avatar_idle.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from voice_typing.ui import avatar
from voice_typing.ui.avatar import AvatarWidget


def _run(w, t0, t1, step=0.05):
    """按固定步长推进动画时钟，返回期间出现过的表情"""
    seen, t = set(), t0
    while t < t1:
        w._advance(t, step)
        seen.add(w._expr)
        t += step
    return seen


def test_idle_acts_then_returns_to_neutral():
    w = AvatarWidget(88, 56, "#14C16E")
    seen = _run(w, 0, 60)
    assert seen - {"neutral"}, "待机一分钟应该至少换过一次表情"
    w._act_at = 1e9                      # 不再出新动作
    _run(w, 60, 64)
    assert w._expr == "neutral"


def test_falls_asleep_and_wakes():
    w = AvatarWidget(88, 56, "#14C16E")
    _run(w, 0, avatar.SLEEP_AFTER_S + 3)
    assert w._asleep and w._expr == "sleepy"
    w.set_state("listening")
    assert not w._asleep and w._expr == "neutral"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
