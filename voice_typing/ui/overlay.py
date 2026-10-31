"""屏幕下方浮窗 — Grok 语音聊天风格：头像 + 音量波形 / 转写文字 + 聊天开关 + ✕ 取消

尺寸、圆角、配色均按 Grok Bot 语音浮窗录屏 1:1 实测（docs/ui/）。
聊天开关打开时，文字改到主胶囊上方的独立文字框里显示，主胶囊始终显示波形。
"""

import os
import random
from collections import deque

from PyQt5.QtCore import (Qt, QTimer, QPoint, QRect, QRectF, QSize, QPropertyAnimation,
                          QEasingCurve, QElapsedTimer, pyqtSignal, pyqtProperty)
from PyQt5.QtGui import QPainter, QColor, QFontMetrics, QIcon, QRegion
from PyQt5.QtWidgets import (QWidget, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
                             QApplication, QGraphicsOpacityEffect)

from voice_typing.core.emotion import detect_emotion
from voice_typing.ui.avatar import AvatarWidget

_RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")

# 胶囊高 86、圆角 43（两端整半圆）；按钮直径 56、间距 11
# 头像控件 88，圆头直径 56 与按钮同大；控件贴胶囊左端，圆头离左端 16，与 ✕ 离右端对称
PILL_H = 86
AVATAR = 88
LEFT = 0             # 胶囊左端 → 头像画布
RIGHT = 16           # 最后一个按钮 → 胶囊右端
BTN = 56
BTN_GAP = 11
BTN_LEAD = 32        # 波形 / 文字 → 第一个按钮
BUTTONS_W = BTN_LEAD + 2 * BTN + BTN_GAP + RIGHT
PILL_MAX_W = 640     # 主胶囊最宽，文字再多也只显示尾部
GREEN = "#14C16E"  # 头像 / 音波的默认色，可在设置页改（config.avatar_color）

# 上方文字框：最宽 480，超出换行；圆角与主胶囊相同，单行时就是同高的胶囊
BUBBLE_MAX_W = 480
BUBBLE_HPAD = 28     # 文字离边的距离，保证多行时首尾行不压到 43 的圆角
BUBBLE_VPAD = 22
BUBBLE_GAP = 8       # 文字框与主胶囊的间距

_TEXT_STYLE = "color: #1f1f1f; font-size: 11pt; background: transparent; padding: 0px;"
_ERROR_STYLE = "color: #E32D34; font-size: 11pt; background: transparent; padding: 0px;"

# 不抢焦点：点浮窗上的按钮也不能把焦点从目标应用拿走，否则粘贴会落空
_FLOATING = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
             | Qt.WindowDoesNotAcceptFocus)
_PAD = 10  # 窗口四周留白，给投影留绘制空间（Qt 画不出窗口边界外）


def _paint_capsule(widget: QWidget, cap: QRectF):
    """投影 → 白底圆角 43 → 发丝描边。主胶囊和上方文字框共用"""
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    radius = PILL_H / 2

    # 柔和投影：主要落在下方，逐层下移、略微外扩
    for i in range(1, 7):
        painter.setBrush(QColor(0, 0, 0, 7))
        shadow = cap.translated(0, i).adjusted(-i / 3, 0, i / 3, 0)
        painter.drawRoundedRect(shadow, radius, radius)

    painter.setBrush(QColor("#FFFFFF"))
    painter.setPen(QColor(0, 0, 0, 16))
    painter.drawRoundedRect(cap.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)


class WaveformWidget(QWidget):
    """音量历史条：最新音量从右侧进入、平滑向左滚动，越旧越淡；静音时缩成圆点"""

    BAR_COUNT = 14
    BAR_WIDTH = 5
    BAR_PITCH = 9
    MAX_HEIGHT = 33
    # 高度对比：音量先按「底噪 → 近期最大音量」归一到 0~1（自动适应麦克风灵敏度，
    # 你最大声时就是满格），再取这个次方映射成条长。>1 压矮中低音量、拉开长短差，调回 1 即线性
    CONTRAST = 1.5
    PEAK_DECAY = 0.97     # 每格（100ms）最大音量回落比例：约 2 秒半衰，跟得上说话音量变化
    FLOOR_RISE = 0.003    # 每格底噪允许上浮的量：底噪只会慢慢抬升，一出现更安静的时刻就立刻跟下去
    MIN_RANGE = 0.15      # 底噪到最大音量至少留这么宽，安静时不把噪声放大成高条
    TOTAL_WIDTH = (BAR_COUNT - 1) * BAR_PITCH + BAR_WIDTH  # 122px
    STEP_MS = 100  # 每格时长，与 Recorder 的音量节拍一致
    FRAME_MS = 16  # 重绘间隔：格与格之间连续滑动，而不是每 100ms 整格跳

    def __init__(self):
        super().__init__()
        self.setFixedSize(self.TOTAL_WIDTH, BTN)
        self._levels = deque([0.0] * self.BAR_COUNT, maxlen=self.BAR_COUNT)
        self._pending = deque()
        self._color = QColor(GREEN)  # 跟头像同色
        self._last_level = 0.0
        self._floor = self._peak = None  # 底噪 / 近期最大音量，首个音量到来时初始化
        self._clock = QElapsedTimer()
        self._last_step = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._frame)
        self.hide()

    def push(self, level: float):
        self._pending.append(level)

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def start(self):
        if self._timer.isActive():
            return
        self._levels.extend([0.0] * self.BAR_COUNT)
        self._pending.clear()
        self._last_level = 0.0
        self._floor = self._peak = None
        self._clock.start()
        self._last_step = 0
        self._timer.start(self.FRAME_MS)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    HOLD_DECAY = 0.75  # 这一格没等到新音量：沿用上一格并衰减，而不是补 0

    def _frame(self):
        """音量按 200ms 成对到达，每 100ms 进一格；积压超过两格就丢旧的。
        到达时间有抖动，某一格可能正好没数据——补 0 会在说话中间凿出一个圆点，
        看起来就是「两根一组」，所以改为沿用上一格衰减。每根再乘一点固定的随机起伏，
        同一批音频切出的相邻两格就不会一样高。"""
        now = self._clock.elapsed()
        while now - self._last_step >= self.STEP_MS:
            self._last_step += self.STEP_MS
            while len(self._pending) > 2:
                self._pending.popleft()
            level = self._pending.popleft() if self._pending else self._last_level * self.HOLD_DECAY
            self._last_level = level
            self._levels.append(self._normalize(level) * random.uniform(0.7, 1.0))
        self.update()

    def _normalize(self, level: float) -> float:
        """按底噪与近期最大音量把原始音量拉伸到 0~1：麦克风偏小声也能用满整个高度"""
        if self._floor is None:
            self._floor, self._peak = level, level + self.MIN_RANGE
        self._floor = min(level, self._floor + self.FLOOR_RISE)
        self._peak = max(level, self._peak * self.PEAK_DECAY, self._floor + self.MIN_RANGE)
        return min(1.0, max(0.0, (level - self._floor) / (self._peak - self._floor)))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        frac = min(1.0, (self._clock.elapsed() - self._last_step) / self.STEP_MS) \
            if self._timer.isActive() else 0.0
        cy = self.height() / 2
        r = self.BAR_WIDTH / 2
        for i, level in enumerate(self._levels):
            x = (i - frac) * self.BAR_PITCH
            h = self.BAR_WIDTH + level ** self.CONTRAST * (self.MAX_HEIGHT - self.BAR_WIDTH)
            # 最左三格渐隐、滑出左缘时淡到 0；静音圆点比有声的条更淡
            pos = x / self.BAR_PITCH
            fade = min(1.0, 0.4 + 0.3 * pos) if pos >= 0 else 0.4 * max(0.0, 1 + pos)
            color = QColor(self._color)
            color.setAlphaF(fade * (0.4 + 0.6 * min(1.0, level / 0.15)))
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, cy - h / 2, self.BAR_WIDTH, h), r, r)


def _round_button(icon: QIcon, style: str) -> QPushButton:
    button = QPushButton()
    button.setIcon(icon)
    button.setIconSize(QSize(24, 24))
    button.setFixedSize(BTN, BTN)
    button.setFocusPolicy(Qt.NoFocus)
    button.setCursor(Qt.PointingHandCursor)
    # 全局样式表给 QPushButton 设了底色/圆角/内边距，这里逐项盖掉
    button.setStyleSheet(
        f"QPushButton {{ border: none; border-radius: {BTN // 2}px; padding: 0; }}" + style
    )
    return button


class TextBubble(QWidget):
    """聊天模式下浮在主胶囊正上方、左边对齐的文字框"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(_FLOATING)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(_PAD + BUBBLE_HPAD, _PAD + BUBBLE_VPAD,
                                  _PAD + BUBBLE_HPAD, _PAD + BUBBLE_VPAD)
        layout.addWidget(self._label)

    def show_text(self, text: str, style: str, pill: QRect, align_right: bool):
        """pill 是主胶囊在屏幕上的矩形；浮窗靠屏幕右侧时与胶囊右端对齐，免得伸出屏幕"""
        self._label.setStyleSheet(style)
        self._label.setText(text)
        self._label.ensurePolished()
        fm = QFontMetrics(self._label.font())
        width = min(BUBBLE_MAX_W, fm.horizontalAdvance(text) + 2 * BUBBLE_HPAD + 4)
        height = max(PILL_H, self._label.heightForWidth(width - 2 * BUBBLE_HPAD) + 2 * BUBBLE_VPAD)
        self.resize(width + 2 * _PAD, height + 2 * _PAD)
        self.place(pill, align_right)
        self.show()

    def place(self, pill: QRect, align_right: bool):
        """贴在主胶囊上方，文字变多时向上长高"""
        x = pill.x() + pill.width() + _PAD - self.width() if align_right else pill.x() - _PAD
        self.move(x, pill.y() - BUBBLE_GAP - self.height() + _PAD)

    def paintEvent(self, event):
        _paint_capsule(self, QRectF(self.rect().adjusted(_PAD, _PAD, -_PAD, -_PAD)))


class OverlayWindow(QWidget):
    """白色胶囊浮窗，位于屏幕底部中央。

    窗口固定为最大尺寸、从不缩放，展开 / 收起只改里面胶囊的宽度并把窗口形状裁到胶囊：
    合成器下逐帧改顶层窗口尺寸开销大、容易掉帧，改子控件宽度只是重绘。
    窗口管理器要求整个窗口留在屏幕内，所以胶囊在窗口里靠左（向右展开）还是靠右
    （向左展开）按位置自动选：往右放不下就朝左长，圆点才能拖到屏幕任一边缘。
    """

    chat_toggled = pyqtSignal(bool)  # 用户点了聊天开关，app 负责记到配置里
    cancel_requested = pyqtSignal()  # 用户点了 ✕：放弃本次语音，app 负责停录、丢弃结果
    avatar_clicked = pyqtSignal()    # 单击头像（没拖动）：app 负责开始 / 结束语音输入

    PAD = _PAD

    def __init__(self):
        super().__init__()
        self.setObjectName("overlay")
        self.setWindowFlags(_FLOATING)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(PILL_MAX_W + 2 * self.PAD, PILL_H + 2 * self.PAD)

        # 拖拽相关
        self._dragging = False
        self._drag_position = None
        self._press_pos = None  # 按下时的全局坐标：松开时移动不到拖拽阈值才算单击

        self._avatar = AvatarWidget(AVATAR, BTN, GREEN)
        self._avatar.setToolTip("单击开始 / 结束语音输入，按住可拖动")

        # 显示状态：_render() 只看这几个量决定画什么
        self._active = False         # 胶囊展开（开始录音 → 复位前）
        self._listening = False      # 录音中（松键前）
        self._text = ""              # 当前要显示的文字
        self._error = False          # 文字是不是错误提示
        self._polish_active = False  # 实时润色进行中时，忽略 ASR 原始文字

        self._waveform = WaveformWidget()
        self._bubble = TextBubble()

        # 聊天模式下也照常写入（只是不显示）：实时润色从这里取原文
        self._text_label = QLabel("")
        self._text_label.setStyleSheet(_TEXT_STYLE)
        self._text_label.setWordWrap(False)
        self._text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._text_label.hide()

        # 聊天开关（选中后底色和图标加深）+ ✕ 取消本次语音
        chat_icon = QIcon(os.path.join(_RES, "ov-chat.svg"))
        chat_icon.addFile(os.path.join(_RES, "ov-chat-on.svg"), QSize(), QIcon.Normal, QIcon.On)
        self._chat_button = _round_button(
            chat_icon,
            "QPushButton { background: #F1F1F1; }"
            "QPushButton:hover:!checked { background: #E6E6E6; }"
            "QPushButton:checked { background: #D6D6D6; }",
        )
        self._chat_button.setCheckable(True)
        self._chat_button.toggled.connect(self._on_chat_toggled)
        cancel_button = _round_button(
            QIcon(os.path.join(_RES, "ov-close.svg")),
            "QPushButton { background: #E32D34; }"
            "QPushButton:hover, QPushButton:pressed { background: #C9252C; }",
        )
        cancel_button.clicked.connect(self.cancel_requested)

        self._buttons = QWidget()
        self._buttons.setObjectName("overlay-buttons")  # 全局样式表会给 QWidget 刷页面底色
        self._buttons.setStyleSheet("QWidget#overlay-buttons { background: transparent; }")
        buttons_layout = QHBoxLayout(self._buttons)
        buttons_layout.setContentsMargins(BTN_LEAD, 0, RIGHT, 0)
        buttons_layout.setSpacing(BTN_GAP)
        buttons_layout.addWidget(self._chat_button)
        buttons_layout.addWidget(cancel_button)
        # 展开 / 收起途中按钮贴着胶囊右端走，按进度淡入淡出，不挤压、不被切半
        self._buttons_fade = QGraphicsOpacityEffect(self._buttons)
        self._buttons.setGraphicsEffect(self._buttons_fade)

        # 中间区（波形 / 文字）：夹在头像与按钮之间，胶囊变宽时逐渐露出
        self._middle = QWidget()
        self._middle.setObjectName("overlay-middle")
        self._middle.setStyleSheet("QWidget#overlay-middle { background: transparent; }")
        middle_layout = QHBoxLayout(self._middle)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        middle_layout.addWidget(self._waveform)
        middle_layout.addWidget(self._text_label)
        middle_layout.addStretch()

        # 胶囊内容：宽度由动画驱动，各块位置在 _set_pill_width 里手动摆；
        # 高 88（头像控件比 86 的胶囊高 2px，上下各探出 1px）
        self._pill = QWidget(self)
        self._pill.setObjectName("overlay-pill")
        self._pill.setStyleSheet("QWidget#overlay-pill { background: transparent; }")
        for child in (self._avatar, self._middle, self._buttons):
            child.setParent(self._pill)
        self._avatar.move(LEFT, 0)

        # 动画：只动胶囊宽度
        self._pill_w = 0
        self._grow_left = False  # True：胶囊贴窗口右侧、向左展开（浮窗在屏幕靠右处时）
        self._size_animation = QPropertyAnimation(self, b"pillWidth")
        self._size_animation.setDuration(300)  # 300ms 过渡
        self._size_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 初始化为待机尺寸（只显示头像）
        self.pillWidth = AVATAR
        self._center_on_screen()

    def _show_emotion(self, text: str):
        self._avatar.set_expression(detect_emotion(text))

    def set_avatar_color(self, color: str):
        """头像与音波同色（设置页「头像颜色」）"""
        self._avatar.set_color(color)
        self._waveform.set_color(color)

    def set_level(self, level: float):
        """Recorder 每 100ms 推一次音量"""
        self._waveform.push(level)
        self._avatar.set_level(level)

    # ---- 聊天开关 ----

    def set_chat(self, on: bool):
        """启动时恢复上次的选择，不触发 chat_toggled"""
        self._chat_button.blockSignals(True)
        self._chat_button.setChecked(on)
        self._chat_button.blockSignals(False)

    def _on_chat_toggled(self, on: bool):
        self.chat_toggled.emit(on)
        self._render()

    # ---- 尺寸 ----

    @staticmethod
    def _active_width(middle: int) -> int:
        return LEFT + AVATAR + middle + BUTTONS_W

    MAX_LABEL_WIDTH = PILL_MAX_W - (LEFT + AVATAR + BUTTONS_W)

    def _calc_label_width(self, text: str) -> int:
        """短文本左对齐、宽度自适应；超长文本右对齐、固定最大宽度，显示文字尾部"""
        fm = QFontMetrics(self._text_label.font())
        text_width = fm.horizontalAdvance(text) + 10

        if text_width <= self.MAX_LABEL_WIDTH:
            self._text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._text_label.setMinimumWidth(0)
            self._text_label.setMaximumWidth(self.MAX_LABEL_WIDTH)
            return text_width
        self._text_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._text_label.setMinimumWidth(self.MAX_LABEL_WIDTH)
        self._text_label.setMaximumWidth(self.MAX_LABEL_WIDTH)
        return self.MAX_LABEL_WIDTH

    def _get_pill_width(self) -> int:
        return self._pill_w

    def _pill_x(self) -> int:
        """胶囊在窗口里的左边 x：向右展开时贴左，向左展开时贴右"""
        return self.width() - self.PAD - self._pill_w if self._grow_left else self.PAD

    def _pill_screen_rect(self) -> QRect:
        return QRect(self.x() + self._pill_x(), self.y() + self.PAD, self._pill_w, PILL_H)

    def _set_pill_width(self, width: int):
        self._pill_w = width
        h = PILL_H + 2
        px = self._pill_x()
        self._pill.setGeometry(px, self.PAD - 1, width, h)
        self._middle.setGeometry(LEFT + AVATAR, 0, max(0, width - LEFT - AVATAR - BUTTONS_W), h)
        self._buttons.setGeometry(width - BUTTONS_W, (h - BTN) // 2, BUTTONS_W, BTN)
        # 胶囊宽到按钮能完整排在头像右边后才开始淡入，到录音宽度时完全显出；收起时反向，碰到头像前已消失
        start = LEFT + AVATAR + BUTTONS_W
        span = self._active_width(WaveformWidget.TOTAL_WIDTH) - start
        fade = min(1.0, max(0.0, (width - start) / span))
        self._buttons_fade.setOpacity(fade)
        self._buttons.setVisible(fade > 0.01)
        # 窗口形状裁到胶囊（含投影留白）：空着的部分不挡下面应用的鼠标
        self.setMask(QRegion(px - self.PAD, 0, width + 2 * self.PAD, self.height()))
        if self._bubble.isVisible():  # 向左展开时胶囊左端在动，文字框跟着走
            self._bubble.place(self._pill_screen_rect(), self._grow_left)
        self.update()

    pillWidth = pyqtProperty(int, _get_pill_width, _set_pill_width)

    def _animate_to_width(self, width: int):
        """平滑过渡到新宽度；目标没变就不重启，否则缓动曲线反复从头加速会显得一顿一顿"""
        anim = self._size_animation
        if anim.state() == QPropertyAnimation.Running:
            if anim.endValue() == width:
                return
            anim.stop()
        elif self._pill_w == width:
            return
        anim.setStartValue(self._pill_w)
        anim.setEndValue(width)
        anim.start()

    def _center_on_screen(self):
        """头像居中放到屏幕底部"""
        screen = QApplication.primaryScreen().availableGeometry()
        self._place_pill(QPoint(screen.center().x() - AVATAR // 2, screen.bottom() - PILL_H - 70))

    def _place_pill(self, pill_pos: QPoint):
        """把胶囊左上角放到屏幕坐标 pill_pos，并据此选展开方向，保证整个窗口在屏幕内"""
        screen = QApplication.screenAt(pill_pos) or self.screen()
        avail = screen.availableGeometry()
        self._grow_left = pill_pos.x() - self.PAD + self.width() > avail.right() + 1
        x = (pill_pos.x() + self._pill_w + self.PAD - self.width()) if self._grow_left \
            else pill_pos.x() - self.PAD
        self.move(x, pill_pos.y() - self.PAD)
        self._set_pill_width(self._pill_w)  # 方向可能变了：重摆胶囊在窗口里的位置与形状

    def moveEvent(self, event):
        """拖拽时上方文字框跟着走"""
        if self._bubble.isVisible():
            self._bubble.place(self._pill_screen_rect(), self._grow_left)

    def paintEvent(self, event):
        _paint_capsule(self, QRectF(self._pill_x(), self.PAD, self._pill_w, PILL_H))

    # ---- 渲染 ----

    def _render(self):
        """按当前状态决定：波形 / 胶囊内文字 / 上方文字框 / 按钮，以及胶囊宽度。

        聊天开：展开期间始终显示波形，文字只进上方文字框。
        聊天关：录音中未出字时显示波形；出字后文字占掉波形的位置。
        """
        chat = self._chat_button.isChecked()
        style = _ERROR_STYLE if self._error else _TEXT_STYLE
        self._text_label.setText(self._text)

        if self._active and (chat or (self._listening and not self._text)):
            self._waveform.start()
        else:
            self._waveform.stop()

        in_pill = self._active and not chat and bool(self._text)
        middle = WaveformWidget.TOTAL_WIDTH
        if in_pill:
            self._text_label.setStyleSheet(style)
            middle = self._calc_label_width(self._text)
        self._text_label.setVisible(in_pill)
        self._animate_to_width(self._active_width(middle) if self._active else AVATAR)

        if self._active and chat and self._text:
            self._bubble.show_text(self._text, style, self._pill_screen_rect(), self._grow_left)
        else:
            self._bubble.hide()

    # ---- 状态 ----

    def flash_yellow(self):
        """按键检测到的瞬间：头像先进入聆听"""
        self._avatar.set_state("listening")

    def start_recording(self):
        """开始录音：头像聆听 + 胶囊展开；80ms 后再出波形，与展开动画同步"""
        self._avatar.set_state("listening")
        self._active = True
        self._listening = True
        self._text = ""
        self._error = False
        self._animate_to_width(self._active_width(WaveformWidget.TOTAL_WIDTH))
        QTimer.singleShot(80, self._render)

    def start_processing(self):
        """松开快捷键：头像思考 = 识别定稿 / 润色中"""
        self._avatar.set_state("thinking")
        self._listening = False
        self._render()

    def stop_recording(self):
        """录音与处理都结束：头像回待机"""
        self._avatar.set_state("idle")
        self._listening = False
        self._render()

    def update_text(self, text: str):
        """实时更新文字（录音时）。
        当 _polish_active=True 时忽略 ASR 原始文字，由润色流控制显示。"""
        if not text or self._polish_active:
            return
        self._show_emotion(text)
        self._text = text
        self._render()

    def set_text(self, text: str):
        """设置最终文字 / 润色流文字（录音结束后）"""
        if not text:
            return
        self._show_emotion(text)
        self._text = text
        self._render()

    def show_error(self, msg: str):
        """显示一行错误提示，2.5s 后自动复位。不写剪贴板、不触发粘贴。"""
        self._polish_active = False
        self._avatar.set_state("failed")
        self._active = True
        self._text = msg
        self._error = True
        self._render()
        QTimer.singleShot(2500, self.reset)

    def reset(self):
        """重置到待机状态"""
        self._avatar.set_state("idle")
        self._active = False
        self._listening = False
        self._text = ""
        self._error = False
        self._polish_active = False
        self._render()

    def mousePressEvent(self, event):
        """鼠标按下：记录按在胶囊上的哪个位置"""
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_position = event.globalPos() - self._pill_screen_rect().topLeft()
            self._press_pos = event.globalPos()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动：拖拽胶囊（必要时切换展开方向）"""
        if self._dragging and event.buttons() == Qt.LeftButton:
            self._place_pill(event.globalPos() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放：结束拖拽；在头像上按下又松开、没拖动 = 单击"""
        if event.button() == Qt.LeftButton:
            self._dragging = False
            moved = (event.globalPos() - self._press_pos).manhattanLength()
            on_avatar = self._avatar.rect().contains(self._avatar.mapFrom(self, event.pos()))
            if moved < QApplication.startDragDistance() and on_avatar:
                self.avatar_clicked.emit()
            event.accept()
