"""VoiceType 主窗口 — 侧边导航 + 多页面"""

import subprocess
import os
import threading

from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QByteArray, QSize, QRect, QRectF, QUrl
from PyQt5.QtGui import (QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QDesktopServices,
                         QPainterPath, QRadialGradient, QFont, QFontMetrics)
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QPushButton,
    QSystemTrayIcon, QMenu, QAction, QApplication, QMessageBox,
    QListWidget, QListWidgetItem, QScrollArea, QCheckBox,
    QRadioButton, QButtonGroup, QStackedWidget, QFrame,
    QStyledItemDelegate, QStyle, QListView,
)

from voice_typing.core.config import load_config, save_config, build_hotwords
from voice_typing.core.updater import check_for_update
from voice_typing.engine.alibaba import AlibabaEngine
from voice_typing.engine.volcengine import VolcengineEngine
from voice_typing.ui.overlay import OVERLAY_THEMES, DEFAULT_OVERLAY_THEME
from voice_typing.ui.styles import mesh_gradient, apply_placeholder_color
from voice_typing.core.vocabulary import sync_vocabulary


class _DarkComboBox(QComboBox):
    """暗色主题 QComboBox：showPopup 时把外层容器变透明，消除白边"""

    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView()
        view.setSpacing(2)
        self.setView(view)

    def showPopup(self):
        super().showPopup()
        # 弹出后容器才真正存在，此时取 view 的 parent 容器并设透明
        container = self.view().parentWidget()
        if container is not None:
            container.setAttribute(Qt.WA_TranslucentBackground, True)
            container.setWindowFlags(
                container.windowFlags()
                | Qt.FramelessWindowHint
                | Qt.NoDropShadowWindowHint
            )
            container.setStyleSheet("background: transparent; border: none;")
            container.show()


def _draw_logo(painter, size):
    """绘制「笔意留白」logo：圆角暗底 + 缺口晕染色圆弧"""
    bg = QColor(13, 13, 13)

    corner = max(2.0, size * 0.22)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(bg))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, size, size), corner, corner)

    # 弧形笔触：小尺寸用更粗的笔以保持气场，大尺寸用更纤细比例
    if size <= 18:
        stroke_w = size * 0.14
        margin = size * 0.15
    elif size <= 32:
        stroke_w = size * 0.105
        margin = size * 0.17
    else:
        stroke_w = size * 0.075
        margin = size * 0.18

    diameter = size - 2 * margin
    rect = QRectF(margin, margin, diameter, diameter)

    pen = QPen(QBrush(mesh_gradient(rect)), stroke_w)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    # Qt drawArc：0° 在 3 点钟方向，正值逆时针，单位 1/16°
    # 缺口约 55°，置于右上（约 1 点钟方向），整圈空 305°
    start_angle = int(57.5 * 16)
    span_angle = int(305 * 16)
    painter.drawArc(rect, start_angle, span_angle)


def _make_tray_icon():
    """生成多尺寸 QIcon — 用于托盘和窗口标题"""
    icon = QIcon()
    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        _draw_logo(p, size)
        p.end()
        icon.addPixmap(pix)
    return icon


def _make_eye_icon(visible=True):
    """生成眼睛图标（SVG）"""
    if visible:
        svg_data = """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"
                  fill="#9ca3af"/>
        </svg>
        """
    else:
        svg_data = """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"
                  fill="#9ca3af"/>
        </svg>
        """

    renderer = QSvgRenderer(QByteArray(svg_data.encode()))
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


CARD_BG = QColor("#1a1a1a")
CARD_HOVER = QColor("#222222")
CARD_TEXT = QColor("#f0f0f0")
CARD_TEXT_SELECTED = QColor("#1a0b05")
CARD_RADIUS = 10
CARD_PADDING_H = 14
CARD_PADDING_V = 12
CARD_MARGIN_V = 4
CARD_MAX_LINES = 3
CARD_MIN_HEIGHT = 48


class CardDelegate(QStyledItemDelegate):
    """卡片式列表项 — 自适应高度，最多 3 行，超出省略号"""

    def _text_width(self, option):
        w = option.rect.width()
        return max(w - 2 * CARD_PADDING_H, 100)

    def _calc_lines(self, fm, text, width):
        if not text:
            return 1, text
        r = fm.boundingRect(QRect(0, 0, int(width), 99999), Qt.TextWordWrap, text)
        line_h = fm.lineSpacing()
        needed = max(1, (r.height() + line_h - 1) // line_h)
        if needed <= CARD_MAX_LINES:
            return needed, text
        # 二分查找截断点 + 省略号
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            candidate = text[:mid] + "..."
            cr = fm.boundingRect(QRect(0, 0, int(width), 99999), Qt.TextWordWrap, candidate)
            cl = max(1, (cr.height() + line_h - 1) // line_h)
            if cl <= CARD_MAX_LINES:
                lo = mid
            else:
                hi = mid - 1
        return CARD_MAX_LINES, text[:lo] + "..." if lo > 0 else "..."

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect
        selected = option.state & QStyle.State_Selected
        hovered = option.state & QStyle.State_MouseOver

        bg = CARD_HOVER if hovered else CARD_BG

        fm = painter.fontMetrics()
        text = index.data(Qt.DisplayRole) or ""
        text_w = self._text_width(option)
        _, display_text = self._calc_lines(fm, text, text_w)

        line_h = fm.lineSpacing()
        r = fm.boundingRect(QRect(0, 0, int(text_w), 99999), Qt.TextWordWrap, display_text)
        text_h = max(line_h, r.height())
        card_h = text_h + 2 * CARD_PADDING_V

        content_rect = QRect(
            rect.x(),
            rect.y() + CARD_MARGIN_V,
            rect.width(),
            card_h,
        )
        painter.setBrush(QBrush(mesh_gradient(QRectF(content_rect))) if selected else QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(content_rect, CARD_RADIUS, CARD_RADIUS)

        text_color = CARD_TEXT_SELECTED if selected else CARD_TEXT
        painter.setPen(text_color)
        text_rect = content_rect.adjusted(CARD_PADDING_H, CARD_PADDING_V, -CARD_PADDING_H, -CARD_PADDING_V)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, display_text)

        painter.restore()

    def sizeHint(self, option, index):
        text = index.data(Qt.DisplayRole) or ""
        fm = option.fontMetrics
        text_w = self._text_width(option)
        _, display_text = self._calc_lines(fm, text, text_w)
        line_h = fm.lineSpacing()
        r = fm.boundingRect(QRect(0, 0, int(text_w), 99999), Qt.TextWordWrap, display_text)
        text_h = max(line_h, r.height())
        card_h = text_h + 2 * CARD_PADDING_V
        return QSize(0, card_h + 2 * CARD_MARGIN_V)


class HeroBanner(QWidget):
    """主页顶部的产品介绍：晕染光斑背景 + Logo + 渐变标语 + 三步用法。
    标语和光斑构图取自宣传视频；渐变文字 QSS 做不到，所以整块自绘。"""

    TITLE = "按住说话，松开上屏"
    SUBTITLE = "专为 Ubuntu 打造的 AI 语音输入 · 光标在哪，文字就到哪"
    # 光斑 (中心x, 中心y, 横半径, 纵半径, 颜色)，位置均为横幅宽高的比例。构图取自视频
    # --vt-mesh 的三处椭圆光；颜色用橙 + 玫红——琥珀在暗底上低透明度会发棕发灰
    BLOBS = ((0.12, 0.30, 0.36, 0.72, "#F26A2A"),
             (0.42, 0.95, 0.33, 0.85, "#E8458B"),
             (0.88, 0.10, 0.25, 0.60, "#E8458B"))
    GLOW_ALPHA = 100

    def __init__(self):
        super().__init__()
        self.setFixedHeight(160)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        w, h = rect.width(), rect.height()
        card = QPainterPath()
        card.addRoundedRect(rect, 14, 14)

        # ① 底色 + 低透明度晕染光斑
        p.fillPath(card, QColor("#141414"))
        p.save()
        p.setClipPath(card)
        for cx, cy, rx, ry, color in self.BLOBS:
            grad = QRadialGradient(0, 0, 1)
            c = QColor(color)
            c.setAlpha(self.GLOW_ALPHA)
            grad.setColorAt(0, c)
            c.setAlpha(0)
            grad.setColorAt(1, c)
            p.save()
            p.translate(cx * w, cy * h)
            p.scale(rx * w, ry * h)
            p.fillRect(QRectF(-1, -1, 2, 2), QBrush(grad))
            p.restore()
        p.restore()
        p.setPen(QPen(QColor("#1e1e1e"), 1))
        p.drawPath(card)

        # ② Logo
        logo = 76
        p.save()
        p.translate(32, (h - logo) / 2)
        _draw_logo(p, logo)
        p.restore()
        x = 32 + logo + 28

        # ③ 渐变标语 + 副标题
        font = QFont(self.font())
        font.setPointSize(21)
        font.setBold(True)
        p.setFont(font)
        fm = QFontMetrics(font)
        title_rect = QRectF(x, 26, fm.horizontalAdvance(self.TITLE), fm.height())
        p.setPen(QPen(QBrush(mesh_gradient(title_rect)), 1))
        p.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, self.TITLE)

        font.setPointSize(10)
        font.setBold(False)
        p.setFont(font)
        fm = QFontMetrics(font)
        p.setPen(QColor("#8a8a8a"))
        p.drawText(QRectF(x, title_rect.bottom() + 4, w - x, fm.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, self.SUBTITLE)

        # ④ 三步用法：按住快捷键 → 说话 → 松开，文字自动上屏
        y = title_rect.bottom() + fm.height() + 22
        cap_h = fm.height() + 10
        steps = [("按住快捷键", None), ("→", "arrow"),
                 ("说话", None), ("→", "arrow"), ("松开，文字自动上屏", None)]
        for text, kind in steps:
            tw = fm.horizontalAdvance(text)
            p.setPen(QColor("#F26A2A" if kind == "arrow" else "#e4e4e4"))
            p.drawText(QRectF(x, y, tw, cap_h), Qt.AlignLeft | Qt.AlignVCenter, text)
            x += tw + 10


class SettingsWindow(QWidget):
    """VoiceType 主窗口 — 侧边导航 + 多页面"""

    engine_changed = pyqtSignal(object)
    overlay_style_changed = pyqtSignal(str)
    update_found = pyqtSignal(str, str)   # (最新版本号, Release 页面地址)

    def __init__(self, config, hotkey_manager):
        super().__init__()
        self._config = config
        self._hotkey = hotkey_manager
        self._engine = None
        self._nav_btns = []
        self._new_hotkey_keys = None
        self.update_found.connect(self._on_update_found)

        self._init_ui()
        self._init_tray()
        self._apply_config()
        self._create_engine()
        self._select_nav(0)  # 默认显示主页

    # ---------- UI 框架 ----------

    def _init_ui(self):
        self.setWindowTitle("VoiceType")
        self.setMinimumSize(1000, 620)
        self.resize(1000, 680)
        self.setWindowIcon(_make_tray_icon())

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 侧边栏 ----
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(4)

        # Logo
        from voice_typing import __version__, __dev__
        logo = QLabel("VoiceType")
        logo.setStyleSheet("font-size: 16pt; font-weight: bold; color: #f0f0f0; padding: 8px 8px 4px 8px;")
        sidebar_layout.addWidget(logo)

        self._version = __version__
        ver_text = f"v{__version__}-dev" if __dev__ else f"v{__version__}"
        ver_label = QLabel(ver_text)
        ver_label.setStyleSheet("font-size: 10pt; color: #666; padding: 0 8px 8px 8px;")
        sidebar_layout.addWidget(ver_label)

        # 有新版本时才显示，点击跳到 Release 页面
        self._update_label = QLabel()
        self._update_label.setVisible(False)
        self._update_label.setStyleSheet(
            "font-size: 10pt; color: #F26A2A; padding: 0 8px 8px 8px;"
        )
        self._update_label.setTextFormat(Qt.RichText)
        self._update_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self._update_label.linkActivated.connect(self._open_update_url)
        sidebar_layout.addWidget(self._update_label)

        # 导航按钮
        nav_items = [
            ("主界面", 0),
            ("历史记录", 1),
            ("词典", 2),
            ("设置", 3),
        ]
        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("nav-btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._select_nav(i))
            sidebar_layout.addWidget(btn)
            self._nav_btns.append(btn)

        sidebar_layout.addStretch()

        # 引擎状态指示
        status_row = QHBoxLayout()
        self._sidebar_indicator = QLabel()
        self._sidebar_indicator.setFixedSize(8, 8)
        self._sidebar_indicator.setStyleSheet(
            "background: #666; border-radius: 4px; min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px;"
        )
        status_row.addWidget(self._sidebar_indicator)
        self._sidebar_engine_label = QLabel("引擎未就绪")
        self._sidebar_engine_label.setStyleSheet("font-size: 10pt; color: #aaa;")
        status_row.addWidget(self._sidebar_engine_label)
        status_row.addStretch()
        sidebar_layout.addLayout(status_row)

        root.addWidget(sidebar)

        # ---- 分割线 ----
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("QFrame { color: #1a1a1a; }")
        root.addWidget(sep)

        # ---- 内容区 ----
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_home_page())
        self._stack.addWidget(self._build_history_page())
        self._stack.addWidget(self._build_dictionary_page())
        self._stack.addWidget(self._build_settings_page())
        root.addWidget(self._stack)

        # 输入框建好后统一调一次占位文字颜色（QSS 管不到）
        apply_placeholder_color(self)

        # 窗口显示后再查，不挡启动
        QTimer.singleShot(0, self._check_for_update)

    # ---------- 更新检查 ----------

    def _check_for_update(self):
        """后台查一次最新 Release；没网/查不到就什么都不做，标签保持隐藏。"""
        def worker():
            result = check_for_update(self._version)
            if result and result["update"]:
                self.update_found.emit(result["latest"], result["url"])

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_found(self, latest, url):
        self._update_label.setText(
            f'<a href="{url}" style="color: #F26A2A; text-decoration: none;">'
            f'新版本 v{latest} 可用</a>'
        )
        self._update_label.setVisible(True)

    def _open_update_url(self, url):
        QDesktopServices.openUrl(QUrl(url))

    # ---------- 导航 ----------

    def _select_nav(self, index):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_btns):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if index == 0:
            self._refresh_home()
        elif index == 1:
            self._refresh_history()

    # ---------- Page 0: 主界面 ----------

    def _build_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(14)

        self._hero = HeroBanner()
        layout.addWidget(self._hero)
        layout.addSpacing(10)

        title = QLabel("使用统计")
        title.setObjectName("page-title")
        layout.addWidget(title)

        layout.addSpacing(8)

        # 4 个统计卡片
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(16)

        # 只有首项用晕染色强调，其余走白色——单一强调色是成熟设置页的共同做法
        stats_defs = [
            ("total_seconds", "使用时长", "分钟", True),
            ("total_characters", "输入字数", "字", False),
            ("total_sessions", "录音次数", "次", False),
            ("efficiency", "输入效率", "字/分钟", False),
        ]

        self._stat_labels = {}
        for key, label_text, unit, accent in stats_defs:
            card = self._make_stat_card(key, label_text, unit, accent)
            cards_layout.addWidget(card, 1)

        layout.addWidget(cards_widget)

        layout.addSpacing(16)

        # 当前引擎信息
        engine_card = QGroupBox("当前状态")
        elayout = QVBoxLayout(engine_card)
        elayout.setSpacing(8)

        self._home_engine_name = QLabel("")
        self._home_engine_name.setStyleSheet("font-size: 10pt; font-weight: bold;")
        elayout.addWidget(self._home_engine_name)

        self._home_engine_status = QLabel("")
        self._home_engine_status.setObjectName("subtitle")
        elayout.addWidget(self._home_engine_status)

        layout.addWidget(engine_card)
        layout.addStretch()

        return page

    def _make_stat_card(self, key, label_text, unit, accent=False):
        card = QGroupBox("")
        card.setStyleSheet(
            "QGroupBox { border: 1px solid #1e1e1e; border-radius: 14px;"
            " background: #141414; padding: 18px; }"
        )
        layout = QVBoxLayout(card)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("stat-label")
        layout.addWidget(label)

        value_label = QLabel("--")
        value_label.setObjectName("stat-value")
        value_label.setProperty("accent", "true" if accent else "false")
        layout.addWidget(value_label)

        unit_label = QLabel(unit)
        unit_label.setObjectName("stat-label")
        layout.addWidget(unit_label)

        self._stat_labels[key] = value_label
        return card

    def _refresh_home(self):
        """刷新主页统计和引擎状态"""
        stats = self._config.get("stats", {})
        total_sec = stats.get("total_seconds", 0)
        total_chars = stats.get("total_characters", 0)
        total_sessions = stats.get("total_sessions", 0)
        total_min = total_sec / 60.0

        if total_min < 0.1 and total_sec > 0:
            self._stat_labels["total_seconds"].setText("< 0.1")
        else:
            self._stat_labels["total_seconds"].setText(f"{total_min:.1f}")
        self._stat_labels["total_characters"].setText(str(total_chars))
        self._stat_labels["total_sessions"].setText(str(total_sessions))

        if total_min > 0 and total_chars > 0:
            efficiency = total_chars / total_min
            self._stat_labels["efficiency"].setText(f"{efficiency:.0f}")
        else:
            self._stat_labels["efficiency"].setText("--")

        if self._engine and self._engine.is_available():
            self._home_engine_name.setText(f"引擎已就绪：{self._engine.name}")
            if self._config.get("hotkey"):
                self._home_engine_status.setText("快捷键可用，随时可以开始语音输入")
            else:
                self._home_engine_status.setText("请到「设置」页面录制快捷键")
            self._sidebar_indicator.setStyleSheet(
                "background: #22c55e; border-radius: 4px; min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px;"
            )
            self._sidebar_engine_label.setText("引擎就绪")
        else:
            self._home_engine_name.setText("引擎未就绪")
            self._home_engine_status.setText("请到「设置」页面配置 API Key")
            self._sidebar_indicator.setStyleSheet(
                "background: #666; border-radius: 4px; min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px;"
            )
            self._sidebar_engine_label.setText("未就绪")

    # ---------- Page 1: 历史记录 ----------

    def _build_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(16)

        title_row = QHBoxLayout()
        title = QLabel("历史记录")
        title.setObjectName("page-title")
        title_row.addWidget(title)
        title_row.addStretch()

        copy_btn = QPushButton("复制选中")
        copy_btn.clicked.connect(self._copy_history_item)
        title_row.addWidget(copy_btn)

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_history)
        title_row.addWidget(clear_btn)
        layout.addLayout(title_row)

        hint = QLabel("所有历史记录仅保存在本地设备上")
        hint.setObjectName("subtitle")
        layout.addWidget(hint)

        self._history_list = QListWidget()
        self._history_list.setStyleSheet("""
            QListWidget {
                background: #141414;
                border: 1px solid #1e1e1e;
                border-radius: 14px;
                padding: 8px;
            }
        """)
        self._history_list.setItemDelegate(CardDelegate())
        self._history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._history_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        layout.addWidget(self._history_list)

        self._history_empty_label = QLabel("暂无历史记录")
        self._history_empty_label.setObjectName("subtitle")
        self._history_empty_label.setAlignment(Qt.AlignCenter)
        self._history_empty_label.hide()
        layout.addWidget(self._history_empty_label)

        return page

    def _refresh_history(self):
        self._history_list.clear()
        history = self._config.get("history", [])
        if not history:
            self._history_list.hide()
            self._history_empty_label.show()
            return
        self._history_list.show()
        self._history_empty_label.hide()
        for entry in history:
            text = entry.get("text", "")
            ts = entry.get("timestamp", "")
            engine = entry.get("engine", "")
            chars = entry.get("chars", 0)
            meta_parts = []
            if ts:
                meta_parts.append(ts)
            if engine:
                meta_parts.append(engine)
            if chars:
                meta_parts.append(f"{chars}字")
            meta = "  ·  ".join(meta_parts)
            display = f"{text}\n{meta}" if meta else text
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, text)
            self._history_list.addItem(item)

    def _copy_history_item(self):
        item = self._history_list.currentItem()
        if item:
            text = item.data(Qt.UserRole)
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), timeout=2)

    def _clear_history(self):
        self._config["history"] = []
        save_config(self._config)
        self._history_list.clear()
        self._history_list.hide()
        self._history_empty_label.show()

    # ---------- Page 2: 词典 ----------

    def _build_dictionary_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(16)

        title_row = QHBoxLayout()
        title = QLabel("自定义词典")
        title.setObjectName("page-title")
        title_row.addWidget(title)
        title_row.addStretch()

        self._dict_del_btn = QPushButton("删除选中")
        self._dict_del_btn.clicked.connect(self._delete_dict_item)
        title_row.addWidget(self._dict_del_btn)
        layout.addLayout(title_row)

        hint = QLabel("添加常用的专业词汇，识别更准确。列表中按住 Ctrl / Shift 可多选，一次删除多条")
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._dict_list = QListWidget()
        self._dict_list.setStyleSheet("""
            QListWidget {
                background: #141414;
                border: 1px solid #1e1e1e;
                border-radius: 14px;
                padding: 8px;
            }
        """)
        self._dict_list.setItemDelegate(CardDelegate())
        self._dict_list.setSelectionMode(QListWidget.ExtendedSelection)
        self._dict_list.itemSelectionChanged.connect(self._on_dict_selection_changed)
        self._dict_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._dict_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        layout.addWidget(self._dict_list, 1)

        self._dict_empty_label = QLabel("暂无词条，添加专业词汇以提升识别准确率")
        self._dict_empty_label.setObjectName("subtitle")
        self._dict_empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._dict_empty_label)

        # 添加词条：词汇（必填）← 易错词（选填），箭头方向与列表里的「词汇 ← 易错词」一致；
        # 下方用一句例子直观示意替换效果
        add_card = QGroupBox("添加词条")
        grid = QGridLayout(add_card)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        term_label = QLabel('词汇 <span style="color: #F26A2A;">· 必填</span>')
        term_label.setObjectName("field-label")
        grid.addWidget(term_label, 0, 0)
        alias_label = QLabel('易错词 <span style="color: #8a8a8a;">· 选填，多个用逗号隔开</span>')
        alias_label.setObjectName("field-label")
        grid.addWidget(alias_label, 0, 2)

        self._dict_status = QLabel("")
        self._dict_status.setObjectName("status")
        grid.addWidget(self._dict_status, 0, 3, Qt.AlignRight)

        self._dict_term_input = QLineEdit()
        self._dict_term_input.setPlaceholderText("如：Claude Code")
        self._dict_term_input.setMinimumHeight(48)
        self._dict_term_input.returnPressed.connect(self._add_dict_item)
        grid.addWidget(self._dict_term_input, 1, 0)

        arrow = QLabel("←")
        arrow.setStyleSheet("font-size: 16pt; color: #F26A2A;")
        arrow.setToolTip("识别结果里出现右边的易错词时，自动替换成左边的词汇")
        grid.addWidget(arrow, 1, 1)

        self._dict_alias_input = QLineEdit()
        self._dict_alias_input.setPlaceholderText("如：cloud code, cloudcode")
        self._dict_alias_input.setMinimumHeight(48)
        self._dict_alias_input.returnPressed.connect(self._add_dict_item)
        grid.addWidget(self._dict_alias_input, 1, 2)

        add_btn = QPushButton("添加")
        add_btn.setObjectName("accent")
        add_btn.clicked.connect(self._add_dict_item)
        add_btn.setFixedWidth(80)
        add_btn.setMinimumHeight(48)
        grid.addWidget(add_btn, 1, 3)

        example = QLabel(
            '效果：识别出「用 <s>cloud code</s> 写代码」，自动改成「用 '
            '<span style="color: #F26A2A;">Claude Code</span> 写代码」<br>'
            '只填词汇也有用：它会作为热词发给识别引擎，让引擎更容易认出这个词'
        )
        example.setObjectName("field-hint")
        example.setTextFormat(Qt.RichText)
        grid.addWidget(example, 2, 0, 1, 4)

        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(2, 3)
        layout.addWidget(add_card)
        return page

    def _refresh_dict_list(self):
        self._dict_list.clear()
        vocab = self._config.get("custom_vocabulary", [])
        for item_data in vocab:
            if isinstance(item_data, dict):
                term = item_data.get("term", "")
                alias = item_data.get("alias", "")
            else:
                term = str(item_data)
                alias = ""
            display = f"{term}   ←   {alias}" if alias else term
            list_item = QListWidgetItem(display)
            list_item.setData(Qt.UserRole, {"term": term, "alias": alias})
            self._dict_list.addItem(list_item)
        has_items = self._dict_list.count() > 0
        self._dict_list.setVisible(has_items)
        self._dict_empty_label.setVisible(not has_items)

    def _add_dict_item(self):
        term = self._dict_term_input.text().strip()
        alias = self._dict_alias_input.text().strip()
        if not term:
            self._dict_status.setText("请输入词汇")
            QTimer.singleShot(2000, lambda: self._dict_status.setText(""))
            return

        for i in range(self._dict_list.count()):
            data = self._dict_list.item(i).data(Qt.UserRole)
            if data and data.get("term") == term:
                self._dict_status.setText(f"'{term}' 已存在")
                QTimer.singleShot(2000, lambda: self._dict_status.setText(""))
                return

        display = f"{term}   ←   {alias}" if alias else term
        item = QListWidgetItem(display)
        item.setData(Qt.UserRole, {"term": term, "alias": alias})
        self._dict_list.addItem(item)
        self._dict_list.show()
        self._dict_empty_label.hide()
        self._dict_term_input.clear()
        self._dict_alias_input.clear()
        self._dict_term_input.setFocus()
        self._save_dict()

    def _on_dict_selection_changed(self):
        n = len(self._dict_list.selectedItems())
        self._dict_del_btn.setText(f"删除选中（{n}）" if n > 1 else "删除选中")

    def _delete_dict_item(self):
        items = self._dict_list.selectedItems()
        if not items:
            return
        # 多选删除先确认，防止 Ctrl+A 误删整个词库
        if len(items) > 1 and QMessageBox.question(
            self, "删除词条", f"确定删除选中的 {len(items)} 个词条？"
        ) != QMessageBox.Yes:
            return
        for item in items:
            self._dict_list.takeItem(self._dict_list.row(item))
        if self._dict_list.count() == 0:
            self._dict_list.hide()
            self._dict_empty_label.show()
        self._save_dict()

    def _save_dict(self):
        vocab = []
        for i in range(self._dict_list.count()):
            data = self._dict_list.item(i).data(Qt.UserRole) or {}
            term = data.get("term") or self._dict_list.item(i).text()
            vocab.append({"term": term, "alias": data.get("alias", "")})
        self._config["custom_vocabulary"] = vocab

        # 同步热词表
        engine_type = self._config.get("engine", "alibaba")
        api_key = self._config.get("alibaba_api_key", "")
        hotwords = [v["term"] for v in vocab if v["term"]]
        if engine_type == "alibaba" and hotwords and api_key:
            phrase_id = sync_vocabulary(
                api_key=api_key,
                hotwords=hotwords,
                phrase_id=self._config.get("phrase_id", ""),
            )
            if phrase_id:
                self._config["phrase_id"] = phrase_id

        save_config(self._config)
        self._create_engine()  # 新词立即作为热词生效，无需重启
        self._dict_status.setText("已保存")
        QTimer.singleShot(2000, lambda: self._dict_status.setText(""))

    # ---------- Page 3: 设置 ----------

    def _build_settings_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(16)

        title = QLabel("设置")
        title.setObjectName("page-title")
        layout.addWidget(title)

        # ① 语音识别 (ASR)
        asr_card = QGroupBox("语音识别")
        asr_v = QVBoxLayout(asr_card)
        asr_v.setSpacing(12)

        self._engine_combo = _DarkComboBox()
        self._engine_combo.addItem("阿里云 Paraformer（云端）", "alibaba")
        self._engine_combo.addItem("豆包流式语音识别 2.0（云端）", "volcengine")
        self._engine_combo.currentIndexChanged.connect(self._on_engine_preview)
        asr_v.addWidget(self._field(
            "识别引擎", self._engine_combo,
            "决定语音送到哪家云端转写。切换引擎不影响下方的润色设置。",
        ))
        asr_v.addWidget(self._divider())

        self._api_status = QLabel("")
        self._api_status.setObjectName("status")

        # 阿里云 Key（仅识别用）
        self._api_wrapper, self._api_input = self._make_password_input(
            "sk-...", self._api_status
        )
        self._alibaba_api_widget = self._field(
            "DashScope API Key", self._api_wrapper,
            "阿里云控制台签发，仅用于 Paraformer 识别。",
        )
        asr_v.addWidget(self._alibaba_api_widget)

        # 豆包 ASR 凭证（来自豆包语音控制台，与方舟润色 Key 不共用）
        self._volc_api_widget = QWidget()
        self._volc_api_widget.setObjectName("field")
        volc_layout = QVBoxLayout(self._volc_api_widget)
        volc_layout.setContentsMargins(0, 0, 0, 0)
        volc_layout.setSpacing(12)

        api_key_wrapper, self._volc_api_key_input = self._make_password_input("X-Api-Key")
        volc_layout.addWidget(self._field(
            "豆包语音控制台 API Key", api_key_wrapper,
            "在豆包语音控制台签发，与方舟大模型的 Key 不是同一个。",
        ))
        volc_layout.addWidget(self._divider())

        self._volc_resource_combo = _DarkComboBox()
        self._volc_resource_combo.addItem(
            "2.0 小时版（volc.seedasr.sauc.duration）",
            "volc.seedasr.sauc.duration",
        )
        self._volc_resource_combo.addItem(
            "2.0 并发版（volc.seedasr.sauc.concurrent）",
            "volc.seedasr.sauc.concurrent",
        )
        self._volc_resource_combo.addItem(
            "1.0 小时版（兼容旧应用）",
            "volc.bigasr.sauc.duration",
        )
        self._volc_resource_combo.addItem(
            "1.0 并发版（兼容旧应用）",
            "volc.bigasr.sauc.concurrent",
        )
        volc_layout.addWidget(self._field(
            "资源版本", self._volc_resource_combo,
            "对应你在控制台开通的计费方式，选错会鉴权失败。",
        ))
        volc_layout.addWidget(self._divider())

        self._volc_boosting_input = QLineEdit()
        self._volc_boosting_input.setPlaceholderText("留空则不启用")
        volc_layout.addWidget(self._field(
            "热词表 ID（可选）", self._volc_boosting_input,
            "控制台创建的热词表，做识别偏置。词典页的本地词库会另行随请求发送。",
        ))

        asr_v.addWidget(self._volc_api_widget)
        asr_v.addWidget(self._api_status)
        layout.addWidget(asr_card)

        # ② 文本润色 (LLM)
        polish_llm_card = QGroupBox("文本润色")
        polish_llm_layout = QVBoxLayout(polish_llm_card)
        polish_llm_layout.setSpacing(12)

        self._polish_provider_combo = _DarkComboBox()
        self._polish_provider_combo.addItem("关闭润色（直接输出识别原文）", "off")
        self._polish_provider_combo.addItem("DeepSeek", "deepseek")
        self._polish_provider_combo.addItem("智谱 GLM", "glm")
        self._polish_provider_combo.addItem("MiniMax", "minimax")
        polish_llm_layout.addWidget(self._field(
            "润色模型", self._polish_provider_combo,
            "识别完成后交给大模型清洗口语。与上方识别引擎完全独立。",
        ))

        self._polish_off_hint = QLabel("识别结果不经大模型处理，直接粘贴（仍会应用词库别名替换）。")
        self._polish_off_hint.setObjectName("field-hint")
        self._polish_off_hint.setWordWrap(True)
        polish_llm_layout.addWidget(self._polish_off_hint)

        self._polish_key_divider = self._divider()
        polish_llm_layout.addWidget(self._polish_key_divider)

        # 每家一个 Key 输入框，按所选模型显隐
        self._polish_key_widgets = {}
        self._polish_key_inputs = {}
        for provider, label, hint in (
            ("deepseek", "DeepSeek API Key", "deepseek.com 控制台签发。"),
            ("glm", "智谱 GLM API Key", "bigmodel.cn 控制台签发。"),
            ("minimax", "MiniMax API Key", "minimaxi.com 控制台签发。"),
        ):
            wrapper, field = self._make_password_input(label)
            box = self._field(label, wrapper, hint)
            polish_llm_layout.addWidget(box)
            self._polish_key_widgets[provider] = box
            self._polish_key_inputs[provider] = field

        self._realtime_polish_check = QCheckBox("录音过程中提前润色")
        self._realtime_polish_row = self._field(
            "提前润色", self._realtime_polish_check,
            "边说边润色，结束录音后出字更快，代价是可能多消耗 token。",
        )
        polish_llm_layout.addWidget(self._divider())
        polish_llm_layout.addWidget(self._realtime_polish_row)

        self._polish_provider_combo.currentIndexChanged.connect(self._on_polish_provider_preview)

        # 润色强度
        polish_llm_layout.addWidget(self._divider())
        strength_label = QLabel("润色强度")
        strength_label.setObjectName("field-label")
        polish_llm_layout.addWidget(strength_label)
        strength_hint = QLabel("决定大模型改动原话的尺度，越重改得越多。")
        strength_hint.setObjectName("field-hint")
        polish_llm_layout.addWidget(strength_hint)

        self._polish_group = QButtonGroup(self)
        self._polish_light = QRadioButton("轻度 — 仅删明显语气词，一字不改")
        self._polish_medium = QRadioButton("中度 — 删语气词、修正标点，保留原文（推荐）")
        self._polish_strong = QRadioButton("重度 — 删语气词、理顺表达、修正标点")
        self._polish_group.addButton(self._polish_light, 0)
        self._polish_group.addButton(self._polish_medium, 1)
        self._polish_group.addButton(self._polish_strong, 2)
        polish_llm_layout.addWidget(self._polish_light)
        polish_llm_layout.addWidget(self._polish_medium)
        polish_llm_layout.addWidget(self._polish_strong)
        layout.addWidget(polish_llm_card)

        # 浮窗外观
        overlay_card = QGroupBox("浮窗外观")
        ov_layout = QVBoxLayout(overlay_card)
        ov_layout.setSpacing(12)

        self._overlay_style_combo = _DarkComboBox()
        for name, theme in OVERLAY_THEMES.items():
            self._overlay_style_combo.addItem(theme["label"], name)
        # 选中即时生效，方便直接在屏幕上比对
        self._overlay_style_combo.currentIndexChanged.connect(
            lambda _: self.overlay_style_changed.emit(
                self._overlay_style_combo.currentData()
            )
        )
        ov_layout.addWidget(self._field(
            "外观样式", self._overlay_style_combo,
            "切换即时生效，可直接看屏幕下方的浮窗对比。"
            "玻璃档是高透明度模拟，X11 下拿不到真正的背景模糊。",
        ))
        layout.addWidget(overlay_card)

        # ③ 快捷键
        hotkey_card = QGroupBox("快捷键")
        hlayout = QVBoxLayout(hotkey_card)
        hk_hint = QLabel("支持组合键，也支持单键。")
        hk_hint.setObjectName("field-hint")
        hlayout.addWidget(hk_hint)
        self._hotkey_mode_combo = _DarkComboBox()
        self._hotkey_mode_combo.addItem("按住说话，松开结束", "hold")
        self._hotkey_mode_combo.addItem("按一下开始，再按一下结束", "toggle")
        hlayout.addWidget(self._field("触发方式", self._hotkey_mode_combo))
        hrow = QHBoxLayout()
        self._hotkey_btn = QPushButton(self._hotkey_display())
        self._hotkey_btn.setMinimumHeight(44)
        self._hotkey_btn.clicked.connect(self._record_hotkey)
        hrow.addWidget(self._hotkey_btn)
        self._clear_hotkey_btn = QPushButton("清除")
        self._clear_hotkey_btn.setFixedWidth(80)
        self._clear_hotkey_btn.clicked.connect(self._clear_hotkey)
        hrow.addWidget(self._clear_hotkey_btn)
        hlayout.addLayout(hrow)
        layout.addWidget(hotkey_card)

        # ④ 开机启动
        autostart_card = QGroupBox("启动与运行")
        alayout_auto = QVBoxLayout(autostart_card)
        self._autostart_check = QCheckBox("开机自动启动 VoiceType")
        alayout_auto.addWidget(self._autostart_check)
        layout.addWidget(autostart_card)

        layout.addStretch()

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._cancel_btn = QPushButton("重置")
        self._cancel_btn.setMinimumWidth(100)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        self._apply_btn = QPushButton("确定")
        self._apply_btn.setObjectName("accent")
        self._apply_btn.setMinimumWidth(100)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)
        layout.addLayout(btn_row)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._status_label = QLabel("")
        self._status_label.setObjectName("status")
        self._status_label.setContentsMargins(40, 8, 40, 8)
        outer.addWidget(self._status_label)
        return page

    # ---------- 托盘 ----------

    def _init_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("VoiceType — 语音输入")

        menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)
        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # ---------- 引擎 ----------

    @staticmethod
    def _field(label_text, widget, hint=""):
        """一个设置项：标题 + 可选说明 + 控件。
        密码框填完只剩一串圆点，没有标题就认不出是哪一项。"""
        box = QWidget()
        box.setObjectName("field")
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        lab = QLabel(label_text)
        lab.setObjectName("field-label")
        v.addWidget(lab)
        if hint:
            h = QLabel(hint)
            h.setObjectName("field-hint")
            h.setWordWrap(True)
            v.addWidget(h)
        v.addWidget(widget)
        return box

    @staticmethod
    def _divider():
        """卡片内设置项之间的细分隔线"""
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        return line

    def _make_password_input(self, placeholder, status_label=None):
        """创建带眼睛显示/隐藏切换的密码输入框"""
        wrapper = QWidget()
        wrapper.setObjectName("input-row")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setEchoMode(QLineEdit.Password)
        layout.addWidget(input_field)

        eye_btn = QPushButton()
        eye_btn.setIcon(_make_eye_icon(visible=True))
        eye_btn.setFixedSize(35, 35)
        eye_btn.setStyleSheet("""
            QPushButton { border: none; background: transparent; }
            QPushButton:hover { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
        """)
        eye_btn.setCursor(Qt.PointingHandCursor)
        eye_btn.setToolTip("显示/隐藏")

        def toggle():
            if input_field.echoMode() == QLineEdit.Password:
                input_field.setEchoMode(QLineEdit.Normal)
                eye_btn.setIcon(_make_eye_icon(visible=False))
            else:
                input_field.setEchoMode(QLineEdit.Password)
                eye_btn.setIcon(_make_eye_icon(visible=True))
        eye_btn.clicked.connect(toggle)

        if status_label is not None:
            def on_text_changed(text):
                if text and len(text) > 10:
                    status_label.setText("API Key 已填写")
                else:
                    status_label.setText("")
            input_field.textChanged.connect(on_text_changed)

        return wrapper, input_field

    def _create_engine(self):
        engine_type = self._config.get("engine", "alibaba")
        if engine_type == "alibaba":
            engine = AlibabaEngine(
                api_key=self._config.get("alibaba_api_key", ""),
                phrase_id=self._config.get("phrase_id", ""),
            )
            engine.initialize()
        elif engine_type == "volcengine":
            engine = VolcengineEngine(
                api_key=self._config.get("volc_asr_api_key", ""),
                resource_id=self._config.get(
                    "volc_asr_resource_id", "volc.seedasr.sauc.duration"
                ),
                boosting_table_id=self._config.get("volc_boosting_table_id", ""),
                hotwords=build_hotwords(self._config),
            )
            engine.initialize()
        else:
            engine = AlibabaEngine(
                api_key=self._config.get("alibaba_api_key", ""),
                phrase_id=self._config.get("phrase_id", ""),
            )
            engine.initialize()
        self._engine = engine
        self.engine_changed.emit(self._engine)

    # ---------- 配置应用 ----------

    def _apply_config(self):
        engine = self._config.get("engine", "alibaba")
        idx = self._engine_combo.findData(engine)
        if idx >= 0:
            self._engine_combo.setCurrentIndex(idx)

        self._api_input.setText(self._config.get("alibaba_api_key", ""))
        self._volc_api_key_input.setText(self._config.get("volc_asr_api_key", ""))
        resource_id = self._config.get(
            "volc_asr_resource_id", "volc.seedasr.sauc.duration"
        )
        resource_idx = self._volc_resource_combo.findData(resource_id)
        if resource_idx >= 0:
            self._volc_resource_combo.setCurrentIndex(resource_idx)
        self._volc_boosting_input.setText(self._config.get("volc_boosting_table_id", ""))

        # 润色模型：显式配置优先，未配置则按已填 Key 推断（与后端 _resolve_polish_provider 一致）
        provider = self._config.get("polish_provider", "")
        if not provider:
            provider = next(
                (name for name in ("deepseek", "glm", "minimax")
                 if self._config.get(f"{name}_api_key")),
                "off",
            )
        pidx = self._polish_provider_combo.findData(provider)
        if pidx >= 0:
            self._polish_provider_combo.setCurrentIndex(pidx)

        ov_idx = self._overlay_style_combo.findData(
            self._config.get("overlay_style", DEFAULT_OVERLAY_THEME)
        )
        if ov_idx >= 0:
            self._overlay_style_combo.setCurrentIndex(ov_idx)

        mode_idx = self._hotkey_mode_combo.findData(self._config.get("hotkey_mode", "hold"))
        if mode_idx >= 0:
            self._hotkey_mode_combo.setCurrentIndex(mode_idx)

        self._refresh_credential_visibility()

        self._autostart_check.setChecked(self._config.get("autostart", False))

        strength = self._config.get("polish_strength", "medium")
        btn = {"light": self._polish_light, "medium": self._polish_medium, "strong": self._polish_strong}.get(strength)
        if btn:
            btn.setChecked(True)

        for name, field in self._polish_key_inputs.items():
            field.setText(self._config.get(f"{name}_api_key", ""))
        self._realtime_polish_check.setChecked(self._config.get("realtime_polish", False))

        self._refresh_dict_list()

    # ---------- 事件处理 ----------

    def _on_engine_preview(self, index=None):
        self._refresh_credential_visibility()

    def _on_polish_provider_preview(self, index=None):
        self._refresh_credential_visibility()

    def _refresh_credential_visibility(self):
        """识别与润色各自独立：ASR 凭证只看引擎，润色 Key 只看润色模型。"""
        engine_type = self._engine_combo.currentData()
        provider = self._polish_provider_combo.currentData()
        self._volc_api_widget.setVisible(engine_type == "volcengine")
        self._alibaba_api_widget.setVisible(engine_type == "alibaba")
        for name, widget in self._polish_key_widgets.items():
            widget.setVisible(provider == name)
        self._polish_off_hint.setVisible(provider == "off")
        self._polish_key_divider.setVisible(provider != "off")
        self._realtime_polish_row.setVisible(provider != "off")

    def _on_apply(self):
        engine_type = self._engine_combo.currentData()
        self._config["engine"] = engine_type
        self._config["alibaba_api_key"] = self._api_input.text()
        self._config["volc_asr_api_key"] = self._volc_api_key_input.text().strip()
        self._config["volc_asr_resource_id"] = self._volc_resource_combo.currentData()
        self._config["volc_boosting_table_id"] = self._volc_boosting_input.text().strip()
        self._config["polish_provider"] = self._polish_provider_combo.currentData()
        self._config["overlay_style"] = self._overlay_style_combo.currentData()

        autostart = self._autostart_check.isChecked()
        self._config["autostart"] = autostart
        self._set_autostart(autostart)

        if self._polish_light.isChecked():
            self._config["polish_strength"] = "light"
        elif self._polish_strong.isChecked():
            self._config["polish_strength"] = "strong"
        else:
            self._config["polish_strength"] = "medium"

        for name, field in self._polish_key_inputs.items():
            self._config[f"{name}_api_key"] = field.text().strip()
        # 润色关闭时「提前润色」那行是隐藏的，勾选状态必须跟着清掉；
        # 否则这个看不见的 True 会留在配置里，下次选回某个润色模型
        # 就莫名其妙带着提前润色跑（缓存前缀 → 只粘出前半句，见 app.py）。
        self._config["realtime_polish"] = (
            self._config["polish_provider"] != "off"
            and self._realtime_polish_check.isChecked()
        )

        if self._new_hotkey_keys is not None:
            self._config["hotkey"] = self._new_hotkey_keys
            self._new_hotkey_keys = None

        hotkey_mode = self._hotkey_mode_combo.currentData()
        if hotkey_mode != self._config.get("hotkey_mode", "hold"):
            self._config["hotkey_mode"] = hotkey_mode
            self._hotkey.set_mode(hotkey_mode)

        # 自定义词库（从词典页同步）
        vocab = []
        hotwords = []
        for i in range(self._dict_list.count()):
            data = self._dict_list.item(i).data(Qt.UserRole) or {}
            term = data.get("term") or self._dict_list.item(i).text()
            vocab.append({"term": term, "alias": data.get("alias", "")})
            if term:
                hotwords.append(term)
        self._config["custom_vocabulary"] = vocab

        if engine_type == "alibaba" and hotwords and self._config.get("alibaba_api_key"):
            self._status_label.setText("正在同步热词表...")
            QApplication.processEvents()
            phrase_id = sync_vocabulary(
                api_key=self._config.get("alibaba_api_key"),
                hotwords=hotwords,
                phrase_id=self._config.get("phrase_id", ""),
            )
            if phrase_id:
                self._config["phrase_id"] = phrase_id
            else:
                self._status_label.setText("热词同步失败（识别仍可用，热词不生效）")
                QTimer.singleShot(3000, lambda: self._update_status())
        elif not vocab:
            self._config["phrase_id"] = ""

        save_config(self._config)
        self._create_engine()
        self._update_status()
        self._refresh_dict_list()

        self._status_label.setText("设置已保存并应用")
        QTimer.singleShot(2000, lambda: self._update_status())

    def _on_cancel(self):
        self._new_hotkey_keys = None
        self._hotkey.set_hotkey(self._config.get("hotkey", []))
        self._apply_config()
        self._status_label.setText("已重置为上次保存的设置")
        QTimer.singleShot(2000, lambda: self._update_status())

    def _record_hotkey(self):
        self._hotkey_btn.setText("按下快捷键组合...")
        self._hotkey_btn.setStyleSheet("border-color: #F26A2A; color: #F26A2A;")
        self._hotkey.stop()

        def on_done(keys):
            if len(keys) >= 1:
                self._new_hotkey_keys = keys
                self._hotkey.set_hotkey(keys)
            self._hotkey_btn.setText(self._hotkey_display())
            self._hotkey_btn.setStyleSheet("")
            self._hotkey.start()

        from voice_typing.core.hotkey import HotkeyManager
        self._record_listener = HotkeyManager.record_key_sequence(on_done)

    def _clear_hotkey(self):
        self._new_hotkey_keys = []
        self._hotkey_btn.setText("点击设置快捷键")
        self._hotkey.set_hotkey([])

    _VK_LABELS = {269025067: "Fn"}

    @classmethod
    def _key_label(cls, s):
        if s.startswith("vk:"):
            vk = int(s[3:])
            if vk in cls._VK_LABELS:
                return cls._VK_LABELS[vk]
            return f"Key({vk})"
        return s.upper()

    def _hotkey_display(self):
        if self._new_hotkey_keys is not None:
            keys = self._new_hotkey_keys
        else:
            keys = self._config.get("hotkey", [])
        if not keys:
            return "点击设置快捷键"
        return " + ".join(self._key_label(k) for k in keys)

    def _update_status(self):
        if self._engine and self._engine.is_available():
            self._status_label.setText(f"引擎就绪: {self._engine.name}")
        else:
            self._status_label.setText("引擎未就绪，请配置 API Key")

    # ---------- 托盘事件 ----------

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
    AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "voice-typing.desktop")

    def _set_autostart(self, enable: bool):
        if enable:
            os.makedirs(self.AUTOSTART_DIR, exist_ok=True)
            with open(self.AUTOSTART_FILE, "w") as f:
                f.write("""[Desktop Entry]
Type=Application
Name=VoiceType
Exec=/usr/bin/voice-typing
Icon=voice-typing
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
""")
        else:
            if os.path.exists(self.AUTOSTART_FILE):
                os.remove(self.AUTOSTART_FILE)

    def _quit_app(self):
        self._hotkey.stop()
        self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "VoiceType",
            "已最小化到系统托盘，快捷键仍然可用",
            QSystemTrayIcon.Information,
            2000,
        )
