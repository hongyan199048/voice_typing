"""生成 README 用的截图和浮窗动图 → docs/images/。

用演示配置渲染（不读写 ~/.config 里的真实配置，截图里没有个人数据）；
走真实 X 显示但窗口不上屏（WA_DontShowOnScreen），字体与用户看到的一致。
界面改版后重跑一次即可：python3 scripts/make_readme_images.py（需要 Pillow 生成 GIF）
"""
import copy
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "images")

from PyQt5.QtCore import Qt, QRect, QBuffer
from PyQt5.QtGui import QColor, QImage, QPainter, QLinearGradient
from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)
app.setStyle("Fusion")

from voice_typing.core import config as config_mod
from voice_typing.ui import settings as settings_mod
from voice_typing.ui.styles import APP_STYLE, OVERLAY_STYLE
from voice_typing.ui.overlay import OverlayWindow

app.setStyleSheet(APP_STYLE + OVERLAY_STYLE)
settings_mod.save_config = lambda cfg: None  # 演示配置不落盘

DEMO = copy.deepcopy(config_mod.DEFAULT_CONFIG)
DEMO.update({
    "engine": "volcengine",
    "volc_asr_api_key": "demo-key-0000000000000000",
    "polish_provider": "deepseek",
    "deepseek_api_key": "sk-demo000000000000000000",
    "hotkey": ["ctrl", "space"],
    "first_run": False,
    "smart_polish": True,
    "custom_vocabulary": [
        {"term": "Claude Code", "alias": "cloud code, cloudcode"},
        {"term": "DeepSeek", "alias": "deep sick"},
        {"term": "GitHub", "alias": ""},
        {"term": "PyQt5", "alias": "pie qt"},
        {"term": "Ubuntu", "alias": ""},
    ],
    "stats": {"total_seconds": 21600, "total_characters": 58300,
              "total_sessions": 1260, "install_date": "2026-09-01"},
    "history": [
        {"text": "明天上午十点和产品组过一下新版设计稿，记得带上用户反馈的整理。",
         "timestamp": "2026-10-31 15:42:10", "engine": "volcengine", "chars": 31},
        {"text": "太好了，这个方案今天顺利通过评审了！", "timestamp": "2026-10-31 14:05:33",
         "engine": "volcengine", "chars": 18},
        {"text": "帮我把这段代码里的 print 换成 logging，日志级别用 INFO。",
         "timestamp": "2026-10-31 11:20:48", "engine": "volcengine", "chars": 33},
    ],
})


def _offscreen(w):
    w.setAttribute(Qt.WA_DontShowOnScreen)
    w.show()
    app.processEvents()


def _settle(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _save(img: QImage, name):
    img.save(os.path.join(OUT, name))
    print("saved", name)


def _desktop_bg(w, h):
    """浮窗图的底：浅灰渐变，模拟桌面"""
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor("#E9ECEF"))
    g.setColorAt(1, QColor("#DDE2E7"))
    p.fillRect(img.rect(), g)
    p.end()
    return img


def _on_bg(img: QImage, pad=24):
    bg = _desktop_bg(img.width() + 2 * pad, img.height() + 2 * pad)
    p = QPainter(bg)
    p.drawImage(pad, pad, img)
    p.end()
    return bg


def settings_shots():
    w = settings_mod.SettingsWindow(copy.deepcopy(DEMO), None)
    w.resize(1000, 680)
    _offscreen(w)
    _settle(0.3)
    for idx, name in ((0, "home.png"), (2, "dictionary.png")):
        w._select_nav(idx)
        _settle(0.2)
        _save(w.grab().toImage(), name)

    # 设置页较长：拉高窗口一次截全，再分段裁出要讲的部分
    w._select_nav(3)
    w.resize(1000, 3000)
    _settle(0.3)
    full = w.grab().toImage()
    page = w._stack.currentWidget()
    cards = [c for c in page.findChildren(settings_mod.QGroupBox) if c.isVisible() and c.title()]

    def card_rect(title):
        c = next(c for c in cards if c.title() == title)
        return QRect(c.mapTo(w, c.rect().topLeft()), c.size())

    for titles, name in ((("语音识别",), "settings-asr.png"),
                         (("文本润色",), "settings-polish.png"),
                         (("快捷键", "外观"), "settings-hotkey.png")):
        rects = [card_rect(t) for t in titles if any(c.title() == t for c in cards)]
        r = rects[0]
        for extra in rects[1:]:
            r = r.united(extra)
        _save(full.copy(r.adjusted(-24, -8, 24, 8)), name)  # 上下只留 8，免得带进相邻卡片
    print("cards:", [c.title() for c in cards])


def overlay_shots():
    o = OverlayWindow()
    o.set_avatar_color("#14C16E")
    _offscreen(o)

    def grab():
        _settle(0.05)
        return o.grab().toImage()

    frames = []  # (QImage, 毫秒)

    def run(seconds, levels=False):
        end = time.time() + seconds
        while time.time() < end:
            if levels:
                o.set_level(0.35 + 0.6 * abs(((time.time() * 2.7) % 2) - 1))
            frames.append(grab())

    run(0.8)
    o.start_recording()
    run(1.0, levels=True)
    for part in ("太好了", "太好了，这个方案", "太好了，这个方案今天顺利", "太好了，这个方案今天顺利通过评审了"):
        o.update_text(part)
        run(0.45, levels=True)
    o.start_processing()
    run(0.9)
    o.set_text("太好了，这个方案今天顺利通过评审了！")
    o.stop_recording()
    run(1.6)

    # 静态四态拼图：待机 / 聆听 / 出字 / 聊天气泡
    states = []
    o.reset()
    o._avatar.set_expression("neutral")  # 动图结尾的表情还在停留期
    _settle(0.5)
    states.append(grab())
    o.start_recording()
    for _ in range(25):
        o.set_level(0.3 + 0.6 * (_ % 5) / 4)
        _settle(0.04)
    states.append(grab())
    o.update_text("明天上午十点和产品组过一下新版设计稿")
    states.append(grab())
    o.set_chat(True)
    o.update_text("明天上午十点和产品组过一下新版设计稿，记得带上用户反馈的整理，会后同步给大家。")
    _settle(0.4)
    bubble = o._bubble
    bubble.setAttribute(Qt.WA_DontShowOnScreen)
    bub_img = bubble.grab().toImage() if bubble.isVisible() else None
    pill_img = grab()
    o.set_chat(False)

    _save_gif(frames, "overlay.gif")

    col_w = max(i.width() for i in states)
    gap = 18
    heights = [i.height() for i in states]
    chat_h = (bub_img.height() + 4 if bub_img else 0) + pill_img.height()
    total_h = sum(heights) + chat_h + gap * len(states)
    sheet = QImage(col_w, total_h, QImage.Format_ARGB32)
    sheet.fill(Qt.transparent)
    p = QPainter(sheet)
    y = 0
    for img in states:
        p.drawImage(0, y, img)
        y += img.height() + gap
    if bub_img:
        p.drawImage(o._pill_x() + 10 - 10, y, bub_img)  # 气泡左对齐胶囊
        y += bub_img.height() + 4
    p.drawImage(0, y, pill_img)
    p.end()
    _save(_on_bg(sheet), "overlay-states.png")


def _save_gif(frames, name):
    from PIL import Image
    imgs = []
    for f in frames[::2]:  # 约 10fps 就够看，体积减半
        bg = _on_bg(f, pad=16)
        buf = QBuffer()
        buf.open(QBuffer.ReadWrite)
        bg.save(buf, "PNG")
        import io
        imgs.append(Image.open(io.BytesIO(bytes(buf.data()))).convert("RGB")
                    .quantize(colors=96, method=Image.MEDIANCUT))
    imgs[0].save(os.path.join(OUT, name), save_all=True, append_images=imgs[1:],
                 duration=100, loop=0, optimize=True)
    print("saved", name, len(imgs), "frames")


def avatar_faces():
    from voice_typing.ui.avatar import AvatarWidget
    faces = ("neutral", "happy", "surprised", "sad", "confused", "sleepy")
    tiles = []
    for face in faces:
        a = AvatarWidget(120, 80, "#14C16E")
        a._act_at = 1e9
        _offscreen(a)
        a.set_expression(face)
        a._morph_t = 1.0
        if face == "sleepy":
            a._asleep = True
        tiles.append(a.grab().toImage())
    sheet = QImage(120 * len(tiles), 120, QImage.Format_ARGB32)
    sheet.fill(QColor("#FFFFFF"))
    p = QPainter(sheet)
    for i, t in enumerate(tiles):
        p.drawImage(120 * i, 0, t)
    p.end()
    _save(sheet, "avatar-faces.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    settings_shots()
    overlay_shots()
    avatar_faces()
