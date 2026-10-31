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

    def grab(settle=0.05):
        _settle(settle)
        return o.grab().toImage()

    frames = []  # (QImage, 截取时刻)：动图每帧时长按真实间隔算，播放速度与实际一致

    def run(seconds, levels=False):
        end = time.time() + seconds
        while time.time() < end:
            if levels:
                o.set_level(0.35 + 0.6 * abs(((time.time() * 2.7) % 2) - 1))
            frames.append((grab(0.015), time.time()))

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
    import io
    from PIL import Image
    imgs = []
    kept = frames[:1]
    for f in frames[1:]:  # 抽到约 30fps：再高肉眼看不出，文件白白变大
        if f[1] - kept[-1][1] >= 0.033:
            kept.append(f)
    frames = kept
    # GIF 帧时长以 10ms 为单位；按相邻两帧的真实间隔取整
    durations = [max(20, round((b[1] - a[1]) * 100) * 10) for a, b in zip(frames, frames[1:])] + [100]
    for f, _ in frames:
        bg = _on_bg(f, pad=16)
        buf = QBuffer()
        buf.open(QBuffer.ReadWrite)
        bg.save(buf, "PNG")
        imgs.append(Image.open(io.BytesIO(bytes(buf.data()))).convert("RGB")
                    .quantize(colors=96, method=Image.MEDIANCUT))
    imgs[0].save(os.path.join(OUT, name), save_all=True, append_images=imgs[1:],
                 duration=durations, loop=0, optimize=True)
    print("saved", name, len(imgs), "frames,", f"{1000 * len(imgs) / sum(durations):.0f} fps")


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


SPOKEN = "嗯那个跟大家说一下明天团建的安排啊，第一个就是早上八点半在公司楼下集合，然后第二个中午呢在那个农家乐吃饭，第三个就是下午五点之前回来，大家记得穿运动鞋"
# 下面两段是 DeepSeek + 中度润色 + 对应场景要求的真实输出（2026-10-31）
CHAT_OUT = "跟大家说一下明天团建的安排啊。第一个就是早上八点半在公司楼下集合，第二个中午在农家乐吃饭，第三个就是下午五点之前回来，大家记得穿运动鞋。"
EMAIL_OUT = ("跟大家说一下明天团建的安排。<br><br>1. 早上八点半在公司楼下集合。<br>2. 中午在农家乐吃饭。<br>"
             "3. 下午五点之前回来。<br><br>大家记得穿运动鞋。")

SMART_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
* { box-sizing: border-box; margin: 0; }
body { width: 1200px; padding: 36px; background: #F5F6F7; color: #1F1F1F;
       font: 15px/1.6 "Noto Sans CJK SC", "Noto Sans SC", sans-serif; }
.said { background: #fff; border: 1px solid #ECEDEF; border-radius: 20px; padding: 16px 22px;
        display: flex; gap: 14px; align-items: center; margin-bottom: 26px; }
.dot { width: 34px; height: 34px; border-radius: 50%; background: #14C16E; flex: none; position: relative; }
.dot::before, .dot::after { content: ""; position: absolute; top: 11px; width: 4px; height: 11px;
        border-radius: 2px; background: #fff; }
.dot::before { left: 12px; } .dot::after { right: 12px; }
.said b { color: #0E9F5A; } .said span { color: #6B6B6B; }
.row { display: flex; gap: 28px; }
.col { flex: 1; }
.cap { font-weight: 700; font-size: 17px; margin: 0 0 4px 4px; }
.cap small { font-weight: 400; color: #6B6B6B; font-size: 14px; margin-left: 8px; }
.win { background: #fff; border-radius: 16px; border: 1px solid #E3E5E8; overflow: hidden;
       box-shadow: 0 8px 24px rgba(0,0,0,.06); height: 400px; display: flex; flex-direction: column; margin-top: 10px; }
.bar { height: 46px; display: flex; align-items: center; padding: 0 18px; border-bottom: 1px solid #ECEDEF;
       font-weight: 600; gap: 8px; }
.lights i { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 6px; }
.chat { flex: 1; background: #F3F4F5; padding: 18px; display: flex; flex-direction: column; gap: 14px; }
.msg { display: flex; gap: 10px; align-items: flex-start; }
.msg.me { flex-direction: row-reverse; }
.av { width: 34px; height: 34px; border-radius: 8px; flex: none; }
.bub { max-width: 400px; padding: 10px 14px; border-radius: 12px; background: #fff; }
.me .bub { background: #B7EBCB; }
.input { height: 64px; border-top: 1px solid #ECEDEF; padding: 12px 18px; color: #A0A0A0; }
.field { display: flex; border-bottom: 1px solid #F0F1F3; padding: 10px 20px; gap: 12px; }
.field span { color: #8A8A8A; width: 52px; }
.body { padding: 16px 20px; }
.send { margin: auto 20px 16px auto; background: #14C16E; color: #fff; border-radius: 18px; padding: 6px 22px; }
</style></head><body>
<div class="said"><div class="dot"></div><div><b>你说的话</b>　<span>“SPOKEN”</span></div></div>
<div class="row">
 <div class="col"><div class="cap">在聊天软件里<small>保持口语，一段话发出去</small></div>
  <div class="win">
   <div class="bar"><span class="lights"><i style="background:#FF5F57"></i><i style="background:#FEBC2E"></i><i style="background:#28C840"></i></span>项目组（8）</div>
   <div class="chat">
    <div class="msg"><div class="av" style="background:#8EA6F2"></div><div class="bub">明天团建怎么安排的？</div></div>
    <div class="msg me"><div class="av" style="background:#14C16E"></div><div class="bub">CHAT_OUT</div></div>
   </div>
   <div class="input">输入消息…</div>
  </div></div>
 <div class="col"><div class="cap">在写邮件时<small>要点自动分条，排版清楚</small></div>
  <div class="win">
   <div class="bar"><span class="lights"><i style="background:#FF5F57"></i><i style="background:#FEBC2E"></i><i style="background:#28C840"></i></span>写邮件</div>
   <div class="field"><span>收件人</span>全体同事</div>
   <div class="field"><span>主题</span>明天团建安排</div>
   <div class="body">EMAIL_OUT</div>
   <div class="send">发送</div>
  </div></div>
</div></body></html>"""


def smart_polish_compare():
    """左聊天、右邮件：同一段口述在两个场景下的真实润色结果（需要 playwright）"""
    from playwright.sync_api import sync_playwright
    html = (SMART_HTML.replace("SPOKEN", SPOKEN).replace("CHAT_OUT", CHAT_OUT)
            .replace("EMAIL_OUT", EMAIL_OUT))
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 600}, device_scale_factor=1.5)
        page.set_content(html)
        page.locator("body").screenshot(path=os.path.join(OUT, "smart-polish.png"))
        browser.close()
    print("saved smart-polish.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    settings_shots()
    overlay_shots()
    avatar_faces()
    smart_polish_compare()
