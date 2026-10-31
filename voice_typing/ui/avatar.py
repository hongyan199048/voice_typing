"""浮窗左侧的圆头头像：QPainter 原生绘制，不依赖 QtWebEngine。

眼睛轮廓来自 resources/avatar-eyes.json（scripts/extract_avatar_eyes.py 从 round-avatar
引擎提取的 9 种表情正脸形状）。动作是这里重新做的简化版：表情逐点变形、眨眼、呼吸、
待机四处张望、录音时随音量轻弹、思考时三点跳动。
"""

import json
import math
import os
import random

from PyQt5.QtCore import Qt, QTimer, QElapsedTimer, QPointF, QRectF
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QPolygonF
from PyQt5.QtWidgets import QWidget

_RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
with open(os.path.join(_RES, "avatar-eyes.json"), encoding="utf-8") as _f:
    _DATA = json.load(_f)
EYES = _DATA["eyes"]                          # 表情名 → [左眼点列, 右眼点列]，单位圆坐标
BLINK_BLOCKING = set(_DATA["blinkBlocking"])  # 这些表情眼型特殊，眨眼会很怪，跳过

# 各状态的默认表情与视线（偏航 / 俯仰，度；俯仰正值 = 抬头）
_STATE_FACE = {"idle": "neutral", "listening": "neutral", "thinking": "neutral", "failed": "sad"}
_STATE_GAZE = {"listening": (6.0, 8.0), "failed": (0.0, -10.0)}

FRAME_MS = 16       # 有快动作时 60fps
IDLE_FRAME_MS = 33  # 待机只剩呼吸和缓慢张望时 30fps：半透明窗口每帧合成有固定开销，省一半 CPU
MORPH_S = 0.28                        # 表情变形时长（与原引擎 durations.morph 一致）
BLINK_CLOSE_S, BLINK_HOLD_S, BLINK_OPEN_S = 0.071, 0.033, 0.156  # 合计 0.26s，同原引擎
DOTS_FADE_S = 0.25                    # 头 ⇄ 思考三点的过渡


def _ease(t: float) -> float:
    return 1 - (1 - t) ** 3  # OutCubic


def _project(x: float, y: float, yaw: float, pitch: float):
    """单位球面上的点按视线旋转后正交投影：转头时眼睛靠边会自然压扁"""
    z = math.sqrt(max(0.0, 1 - x * x - y * y))
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    x, z = x * cy + z * sy, -x * sy + z * cy
    y = y * cp - z * sp
    return x, y


class AvatarWidget(QWidget):
    """绿色圆头 + 白色眼睛。size 是控件边长，头部直径 = head_d"""

    def __init__(self, size: int, head_d: int, color: str):
        super().__init__()
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._r = head_d / 2
        self._color = QColor(color)

        self._clock = QElapsedTimer()
        self._clock.start()
        self._last = 0.0

        self._state = "idle"
        self._from = self._to = EYES["neutral"]   # 变形起止点列
        self._morph_t = 1.0
        self._expr = "neutral"

        self._blink_at = self._next_blink(0.0)    # 下次眨眼开始时刻（秒）
        self._yaw = self._pitch = 0.0             # 当前视线（弧度，平滑跟随目标）
        self._gaze_target = (0.0, 0.0)
        self._wander_at = 0.0                     # 待机下次换张望方向的时刻
        self._level = self._bounce = 0.0          # 录音音量 → 头部轻弹
        self._dots = 0.0                          # 0 = 头，1 = 思考三点

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)

    # 只在可见时跑动画：主窗口多数时间缩在托盘里，隐藏时不该空转
    def showEvent(self, event):
        self._timer.start(FRAME_MS)

    def hideEvent(self, event):
        self._timer.stop()

    # ---- 对外接口 ----

    def set_state(self, state: str):
        """idle / listening / thinking / failed；切状态回到该状态的默认表情"""
        self._state = state
        self._wander_at = 0.0
        self.set_expression(_STATE_FACE.get(state, "neutral"))

    def set_expression(self, name: str):
        if name not in EYES or name == self._expr:
            return
        self._from = self._current_eyes()
        self._to = EYES[name]
        self._expr = name
        self._morph_t = 0.0

    def set_level(self, level: float):
        self._level = level

    def set_color(self, color: str):
        """头像主色（圆头 + 思考三点）；眼睛始终是白色"""
        self._color = QColor(color)
        self.update()

    # ---- 动画 ----

    @staticmethod
    def _next_blink(now: float) -> float:
        return now + random.uniform(2.5, 6.0)

    def _current_eyes(self):
        t = _ease(self._morph_t)
        return [[(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for a, b in zip(ea, eb)]
                for ea, eb in zip(self._from, self._to)]

    def _blink_amount(self, now: float) -> float:
        """0 = 睁开，1 = 闭上"""
        if self._expr in BLINK_BLOCKING or self._state == "thinking":
            if now >= self._blink_at:
                self._blink_at = self._next_blink(now)
            return 0.0
        dt = now - self._blink_at
        if dt < 0:
            return 0.0
        if dt < BLINK_CLOSE_S:
            return dt / BLINK_CLOSE_S
        if dt < BLINK_CLOSE_S + BLINK_HOLD_S:
            return 1.0
        if dt < BLINK_CLOSE_S + BLINK_HOLD_S + BLINK_OPEN_S:
            return 1 - _ease((dt - BLINK_CLOSE_S - BLINK_HOLD_S) / BLINK_OPEN_S)
        self._blink_at = self._next_blink(now)
        return 0.0

    def _advance(self, now: float, dt: float):
        self._morph_t = min(1.0, self._morph_t + dt / MORPH_S)

        # 视线：待机时每 1.5–4s 随机换个方向看；其它状态用固定朝向
        if self._state == "idle":
            if now >= self._wander_at:
                self._wander_at = now + random.uniform(1.5, 4.0)
                self._gaze_target = (random.uniform(-14, 14), random.uniform(-8, 8)) \
                    if random.random() < 0.7 else (0.0, 0.0)
        else:
            self._gaze_target = _STATE_GAZE.get(self._state, (0.0, 0.0))
        k = 1 - math.exp(-dt * 6)  # 指数趋近，约 0.5s 跟上
        self._yaw += (math.radians(self._gaze_target[0]) - self._yaw) * k
        self._pitch += (math.radians(self._gaze_target[1]) - self._pitch) * k

        target = self._level if self._state == "listening" else 0.0
        self._bounce += (target - self._bounce) * (1 - math.exp(-dt * 12))

        step = dt / DOTS_FADE_S
        self._dots = min(1.0, self._dots + step) if self._state == "thinking" \
            else max(0.0, self._dots - step)

    # ---- 绘制 ----

    def paintEvent(self, event):
        now = self._clock.elapsed() / 1000
        dt = min(0.1, now - self._last)
        self._last = now
        self._advance(now, dt)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        cx, cy = self.width() / 2, self.height() / 2

        if self._dots < 1:
            self._paint_head(painter, cx, cy, now, 1 - self._dots)
        if self._dots > 0:
            self._paint_dots(painter, cx, cy, now, self._dots)

        gaze_moving = abs(math.radians(self._gaze_target[0]) - self._yaw) > 0.02 \
            or abs(math.radians(self._gaze_target[1]) - self._pitch) > 0.02
        busy = (self._state != "idle" or self._morph_t < 1 or 0 < self._dots < 1 or gaze_moving
                or now >= self._blink_at - FRAME_MS / 1000)
        self._timer.setInterval(FRAME_MS if busy else IDLE_FRAME_MS)

    def _paint_head(self, painter: QPainter, cx: float, cy: float, now: float, weight: float):
        breath = math.sin(now * 2 * math.pi / 3.2)
        scale = (0.6 + 0.4 * weight) * (1 + 0.06 * self._bounce)
        r = self._r * scale
        sx, sy = 1 + 0.012 * breath, 1 - 0.012 * breath  # 呼吸：轻微挤压
        hy = cy + 0.8 * breath - 2.5 * self._bounce

        painter.setOpacity(weight)
        painter.setBrush(self._color)
        painter.drawEllipse(QPointF(cx, hy), r * sx, r * sy)

        blink = self._blink_amount(now)
        path = QPainterPath()
        for eye in self._current_eyes():
            pts = [_project(x, y, self._yaw, self._pitch) for x, y in eye]
            ey = sum(p[1] for p in pts) / len(pts)
            squeeze = 1 - 0.92 * blink  # 眨眼：以眼睛中心为轴纵向压扁
            path.addPolygon(QPolygonF([
                QPointF(cx + x * r * sx, hy + (ey + (y - ey) * squeeze) * r * sy) for x, y in pts
            ]))
            path.closeSubpath()
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawPath(path)
        painter.setOpacity(1.0)

    def _paint_dots(self, painter: QPainter, cx: float, cy: float, now: float, weight: float):
        """思考：三个圆点依次上下跳、明暗起伏"""
        painter.setBrush(self._color)
        for i in range(3):
            phase = now * 2 * math.pi / 1.1 - i * 0.7
            lift = max(0.0, math.sin(phase))
            painter.setOpacity(weight * (0.45 + 0.55 * lift))
            x = cx + (i - 1) * 15 * weight
            painter.drawEllipse(QRectF(x - 5, cy - 5 - 4 * lift, 10, 10))
        painter.setOpacity(1.0)
