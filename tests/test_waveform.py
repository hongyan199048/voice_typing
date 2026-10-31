"""音波自适应归一化自检：麦克风偏小声也能用满高度；安静时底噪不被放大成高条。

运行: python3 tests/test_waveform.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from voice_typing.ui.overlay import WaveformWidget


def _run(levels):
    w = WaveformWidget()
    return [w._normalize(v) for v in levels]


def test_quiet_mic_uses_full_range():
    """说话音量只在 0.2~0.55 之间：最大声处接近满格，较小声处明显矮"""
    out = _run([0.15] * 5 + [0.25, 0.55, 0.3, 0.5, 0.25, 0.55])
    assert max(out[5:]) > 0.95
    assert min(out[5:]) < 0.35


def test_background_noise_stays_low():
    """只有底噪轻微起伏（±0.03）时不放大成高条"""
    out = _run([0.15, 0.18, 0.14, 0.17, 0.15, 0.16] * 5)
    assert max(out[6:]) < 0.3


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
