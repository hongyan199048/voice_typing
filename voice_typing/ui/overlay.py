"""屏幕下方浮窗 — 实时显示语音转写文字"""

import random
from PyQt5.QtCore import Qt, QTimer, QRect, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFontMetrics, QFont
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QApplication


class StatusIndicator(QWidget):
    """状态指示器：绿色圆球（待机）/ 红色圆球（录音）"""

    def __init__(self):
        super().__init__()
        self.setFixedSize(24, 24)
        self._recording = False
        self._custom_color = None  # 自定义颜色（用于调试闪黄）

    def set_recording(self, recording: bool):
        self._recording = recording
        self._custom_color = None
        self.update()

    def set_color(self, color):
        """直接设置颜色（调试用）"""
        self._custom_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        if self._custom_color:
            color = self._custom_color
        elif self._recording:
            color = QColor(239, 68, 68)  # 红色
        else:
            color = QColor(34, 197, 94)  # 绿色

        painter.setBrush(QBrush(color))
        painter.drawEllipse(4, 4, 16, 16)


class WaveformWidget(QWidget):
    """波形动画组件"""

    BAR_COUNT = 5
    BAR_WIDTH = 3
    BAR_SPACING = 4
    MAX_HEIGHT = 18
    TOTAL_WIDTH = BAR_COUNT * (BAR_WIDTH + BAR_SPACING) - BAR_SPACING  # 31px

    def __init__(self):
        super().__init__()
        self.setMinimumSize(self.TOTAL_WIDTH, 24)
        self.setSizePolicy(self.sizePolicy().Fixed, self.sizePolicy().Fixed)
        self._wave_heights = [0.0] * self.BAR_COUNT
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_wave)

    def start(self):
        self.show()
        self._timer.start(50)  # 20fps

    def stop(self):
        self._timer.stop()
        self._wave_heights = [0.0] * self.BAR_COUNT
        self.update()
        self.hide()

    def _update_wave(self):
        for i in range(len(self._wave_heights)):
            target = random.uniform(0.3, 1.0)
            self._wave_heights[i] = self._wave_heights[i] * 0.6 + target * 0.4
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        for i, height in enumerate(self._wave_heights):
            x = i * (self.BAR_WIDTH + self.BAR_SPACING)
            h = int(height * self.MAX_HEIGHT)
            y = (self.height() - h) // 2

            painter.setBrush(QBrush(QColor(239, 68, 68, 200)))
            painter.drawRoundedRect(x, y, self.BAR_WIDTH, h, 2, 2)


class OverlayWindow(QWidget):
    """半透明浮窗，位于屏幕底部中央"""

    def __init__(self):
        super().__init__()
        self.setObjectName("overlay")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 拖拽相关
        self._dragging = False
        self._drag_position = None

        # 组件
        self._indicator = StatusIndicator()
        self._waveform = WaveformWidget()
        self._waveform.hide()  # 初始隐藏
        self._text_received = False  # 当前录音周期是否已收到文字
        self._polish_active = False  # 实时润色进行中时，忽略 ASR 原始文字

        self._text_label = QLabel("")
        self._text_label.setStyleSheet(
            "color: #f0f0f0; font-size: 10pt; background: transparent; padding: 0px;"
        )
        self._text_label.setWordWrap(False)
        self._text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._text_label.hide()  # 初始隐藏

        # 布局
        self._content_layout = QHBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        self._content_layout.addWidget(self._indicator)
        self._content_layout.addWidget(self._waveform)
        self._content_layout.addWidget(self._text_label)
        self._content_layout.addStretch()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.addLayout(self._content_layout)

        # 动画
        self._size_animation = QPropertyAnimation(self, b"geometry")
        self._size_animation.setDuration(300)  # 300ms 过渡
        self._size_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 初始化为最小尺寸（只显示绿色圆球），先设尺寸再定位
        self.resize(56, 48)
        self._center_on_screen()

    def _set_idle_size(self):
        """待机状态：只显示绿色圆球"""
        self._animate_to_size(56, 48)

    def _set_recording_size(self):
        """录音状态：红色圆球 + 波形"""
        self._animate_to_size(100, 48)

    # 圆点中心距窗口左边缘的固定偏移（16 margin + 24/2 indicator）
    DOT_CENTER_X = 28

    def _animate_to_size(self, width: int, height: int):
        """平滑过渡到新尺寸，以红/绿圆点中心为锚点，圆点屏幕位置保持不变"""
        current_rect = self.geometry()

        dot_x = current_rect.x() + self.DOT_CENTER_X
        dot_y = current_rect.y() + current_rect.height() // 2

        x = dot_x - self.DOT_CENTER_X
        y = dot_y - height // 2

        end_rect = QRect(x, y, width, height)
        self._size_animation.setStartValue(current_rect)
        self._size_animation.setEndValue(end_rect)
        self._size_animation.start()

    def _center_on_screen(self):
        """以圆点为中心定位到屏幕底部"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.width() // 2 - self.DOT_CENTER_X
        y = screen.bottom() - self.height() - 60
        self.move(x, y)

    def paintEvent(self, event):
        """绘制半透明圆角背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(20, 20, 20, 230)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 24, 24)

    def flash_yellow(self):
        """按键检测到时闪黄色，用于延迟诊断"""
        self._indicator.set_color(QColor(234, 179, 8))  # 黄色
        self._indicator.update()

    def start_recording(self):
        """开始录音：圆球变红 + 窗口扩展开启动画 + 波形渐现"""
        self._indicator.set_recording(True)
        self._text_received = False
        self._text_label.hide()
        self._set_recording_size()
        QTimer.singleShot(80, self._show_waveform)

    def _show_waveform(self):
        """延迟显示波形，与窗口扩展动画同步"""
        self._waveform.start()
        self._waveform.show()

    def stop_recording(self):
        """停止录音：圆球变绿 + 隐藏波形"""
        self._indicator.set_recording(False)
        self._waveform.stop()

    MAX_LABEL_WIDTH = 600

    def _calc_label_geometry(self, text: str):
        """根据文字计算 label 宽度和对齐方式。
        短文本：左对齐，label 自适应宽度。
        超长文本：右对齐，label 固定最大宽度，显示文字尾部。"""
        fm = QFontMetrics(self._text_label.font())
        text_width = fm.horizontalAdvance(text) + 10

        if text_width <= self.MAX_LABEL_WIDTH:
            self._text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._text_label.setMinimumWidth(0)
            self._text_label.setMaximumWidth(self.MAX_LABEL_WIDTH)
            return text_width, 48
        else:
            self._text_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._text_label.setMinimumWidth(self.MAX_LABEL_WIDTH)
            self._text_label.setMaximumWidth(self.MAX_LABEL_WIDTH)
            return self.MAX_LABEL_WIDTH, 48

    def update_text(self, text: str):
        """实时更新文字（录音时），首次收到文字后隐藏波形。
        当 _polish_active=True 时忽略 ASR 原始文字，由润色流控制显示。"""
        if not text or self._polish_active:
            return

        # 首次收到识别文字 → 隐藏波形，只显示文字
        if not self._text_received:
            self._text_received = True
            self._waveform.stop()
            self._waveform.hide()

        self._text_label.setText(text)
        self._text_label.show()

        label_width, height = self._calc_label_geometry(text)
        width = 24 + 12 + label_width + 32
        self._animate_to_size(width, height)

    def set_text(self, text: str):
        """设置最终文字（录音结束后），隐藏波形"""
        if not text:
            return

        self._waveform.hide()
        self._text_label.setText(text)
        self._text_label.show()

        label_width, height = self._calc_label_geometry(text)
        width = 24 + 12 + label_width + 32
        self._animate_to_size(width, height)

    def reset(self):
        """重置到待机状态"""
        self._indicator.set_recording(False)
        self._waveform.stop()
        self._text_label.hide()
        self._text_label.setText("")
        self._polish_active = False
        self._set_idle_size()

    def mousePressEvent(self, event):
        """鼠标按下：记录拖拽起始位置"""
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动：拖拽窗口"""
        if self._dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放：结束拖拽"""
        if event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()
