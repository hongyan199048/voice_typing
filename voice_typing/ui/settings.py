"""VoiceType 主窗口 — 侧边导航 + 多页面"""

import csv
import subprocess
import os
import threading

from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QByteArray, QSize, QRect, QRectF, QUrl
from PyQt5.QtGui import (QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QDesktopServices,
                         QFont, QFontMetrics, QConicalGradient)
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QPushButton,
    QSystemTrayIcon, QMenu, QAction, QApplication, QMessageBox,
    QListWidget, QListWidgetItem, QScrollArea, QCheckBox,
    QRadioButton, QButtonGroup, QStackedWidget, QFrame,
    QStyledItemDelegate, QStyle, QListView, QFileDialog, QColorDialog,
)

from voice_typing.core.config import load_config, save_config, build_hotwords
from voice_typing.core.updater import check_for_update
from voice_typing.engine.alibaba import AlibabaEngine
from voice_typing.engine.volcengine import VolcengineEngine
from voice_typing.ui.styles import apply_placeholder_color, accent, set_accent, GREEN
from voice_typing.ui.avatar import AvatarWidget
from voice_typing.core.vocabulary import sync_vocabulary, export_vocab_csv, import_vocab_csv


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


def _draw_logo(painter, size, color=GREEN):
    """绘制 Logo：浮窗同款圆头（默认绿）+ 两只竖条眼睛（待机表情的简化几何版）"""
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(QRectF(0, 0, size, size))
    # 小尺寸保底 1.6 × 3px，16px 托盘图标里眼睛也还看得见
    ew, eh = max(1.6, size * 0.11), max(3.0, size * 0.27)
    painter.setBrush(QColor("#FFFFFF"))
    for cx in (0.40, 0.60):
        painter.drawRoundedRect(QRectF(size * cx - ew / 2, size * 0.5 - eh / 2, ew, eh), ew / 2, ew / 2)


def _make_tray_icon(color=GREEN):
    """生成多尺寸 QIcon — 用于托盘和窗口标题，跟随头像颜色"""
    icon = QIcon()
    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        _draw_logo(p, size, color)
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


CARD_BG = QColor("#FFFFFF")
CARD_HOVER = QColor("#FAFAFA")
CARD_BORDER = QColor("#ECEDEF")
CARD_TEXT = QColor("#1F1F1F")
CARD_META = QColor("#8A8A8A")
CARD_META_GAP = 4
META_ROLE = Qt.UserRole + 1  # 卡片第二行的灰色元信息（时间 · 引擎 · 字数 / 易错词）
CARD_RADIUS = 16
CARD_PADDING_H = 18
CARD_PADDING_V = 14
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

    def _layout(self, fm, option, index):
        """(正文, 正文高, 元信息, 元信息高, 卡片高)：paint 与 sizeHint 共用。
        高度一律按实测文字边框算：中文走备用字体，比 lineSpacing 高，按行高画会被裁掉下半截"""
        text_w = self._text_width(option)
        _, display_text = self._calc_lines(fm, index.data(Qt.DisplayRole) or "", text_w)
        r = fm.boundingRect(QRect(0, 0, int(text_w), 99999), Qt.TextWordWrap, display_text)
        text_h = max(fm.lineSpacing(), r.height())
        meta = index.data(META_ROLE) or ""
        meta_h = max(fm.lineSpacing(), fm.boundingRect(meta).height()) if meta else 0
        card_h = text_h + 2 * CARD_PADDING_V
        if meta:
            card_h += CARD_META_GAP + meta_h
        return display_text, text_h, meta, meta_h, card_h

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect
        selected = option.state & QStyle.State_Selected
        hovered = option.state & QStyle.State_MouseOver
        fm = painter.fontMetrics()
        display_text, text_h, meta, meta_h, card_h = self._layout(fm, option, index)

        content_rect = QRect(rect.x(), rect.y() + CARD_MARGIN_V, rect.width(), card_h)
        main, _, tint, _ = accent()
        painter.setBrush(QBrush(QColor(tint) if selected else (CARD_HOVER if hovered else CARD_BG)))
        painter.setPen(QPen(QColor(main) if selected else CARD_BORDER, 1))
        painter.drawRoundedRect(QRectF(content_rect).adjusted(0.5, 0.5, -0.5, -0.5), CARD_RADIUS, CARD_RADIUS)

        inner_w = content_rect.width() - 2 * CARD_PADDING_H
        text_rect = QRect(content_rect.x() + CARD_PADDING_H, content_rect.y() + CARD_PADDING_V, inner_w, text_h)
        painter.setPen(CARD_TEXT)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, display_text)
        if meta:
            meta_rect = QRect(text_rect.x(), text_rect.bottom() + 1 + CARD_META_GAP, inner_w, meta_h)
            painter.setPen(CARD_META)
            painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter,
                             fm.elidedText(meta, Qt.ElideRight, inner_w))

        painter.restore()

    def sizeHint(self, option, index):
        card_h = self._layout(option.fontMetrics, option, index)[-1]
        return QSize(0, card_h + 2 * CARD_MARGIN_V)


class HeroBanner(QWidget):
    """主页顶部的产品介绍：白色大圆角卡片 + 浮窗同款头像 + 标语 + 三步用法。
    与屏幕下方浮窗同一套视觉；标语后半句用绿色，整块自绘。"""

    TITLE = ("按住说话，", "松开上屏")
    SUBTITLE = "专为 Ubuntu 打造的 AI 语音输入 · 光标在哪，文字就到哪"
    STEPS = ("按住快捷键", "说话", "松开，文字自动上屏")
    HEIGHT = 168
    AVATAR = 120   # 头像控件边长，留出呼吸 / 张望的余量
    HEAD = 80      # 圆头直径

    def __init__(self):
        super().__init__()
        self.setFixedHeight(self.HEIGHT)
        self._avatar = AvatarWidget(self.AVATAR, self.HEAD, GREEN)
        self._avatar.setParent(self)
        self._avatar.move(20, (self.HEIGHT - self.AVATAR) // 2)

    def set_avatar_color(self, color):
        self._avatar.set_color(color)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        w = rect.width()

        # ① 白底大圆角卡片
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#ECEDEF"), 1))
        p.drawRoundedRect(rect, 20, 20)
        x = 20 + self.AVATAR + 12

        # ② 标语：前半句深色、后半句绿色
        font = QFont(self.font())
        font.setPointSize(21)
        font.setBold(True)
        p.setFont(font)
        fm = QFontMetrics(font)
        y = 30
        tx = x
        for part, color in zip(self.TITLE, ("#1F1F1F", accent()[1])):
            tw = fm.horizontalAdvance(part)
            p.setPen(QColor(color))
            p.drawText(QRectF(tx, y, tw, fm.height()), Qt.AlignLeft | Qt.AlignVCenter, part)
            tx += tw
        y += fm.height() + 4

        font.setPointSize(10)
        font.setBold(False)
        p.setFont(font)
        fm = QFontMetrics(font)
        p.setPen(QColor("#6B6B6B"))
        p.drawText(QRectF(x, y, w - x, fm.height()), Qt.AlignLeft | Qt.AlignVCenter, self.SUBTITLE)
        y += fm.height() + 16

        # ③ 三步用法：浅灰胶囊 + 绿色箭头，和浮窗按钮同色
        cap_h = fm.height() + 14
        for i, text in enumerate(self.STEPS):
            tw = fm.horizontalAdvance(text) + 28
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#F3F4F5"))
            p.drawRoundedRect(QRectF(x, y, tw, cap_h), cap_h / 2, cap_h / 2)
            p.setPen(QColor("#1F1F1F"))
            p.drawText(QRectF(x, y, tw, cap_h), Qt.AlignCenter, text)
            x += tw
            if i < len(self.STEPS) - 1:
                p.setPen(QColor(accent()[0]))
                p.drawText(QRectF(x, y, 30, cap_h), Qt.AlignCenter, "→")
                x += 30


# 头像颜色预设：默认绿 + docs/ui/round-avatar.html 里的四色
AVATAR_COLORS = (("默认绿", GREEN), ("黑", "#000000"), ("青绿", "#1DB8A0"),
                 ("蓝", "#5B7FE5"), ("紫", "#8B5CF6"))


class _ColorSwatch(QPushButton):
    """圆形色块：选中时外圈加一道同色细环。color=None 是「自定义」——彩虹色环，
    选过颜色后中间填上那个颜色"""

    def __init__(self, color, tip):
        super().__init__()
        self.color = QColor(color) if color else None
        self.setCheckable(True)
        self.setFixedSize(40, 40)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QRectF(self.rect()).center()
        ring = self.color if self.color is not None else QColor("#1F1F1F")
        if self.isChecked() or self.underMouse():
            ring = QColor(ring)
            ring.setAlpha(255 if self.isChecked() else 70)
            p.setPen(QPen(ring, 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, 18, 18)
        p.setPen(Qt.NoPen)
        if self.color is None or self.property("custom"):
            rainbow = QConicalGradient(c, 90)
            for i, hue in enumerate(range(0, 361, 60)):
                rainbow.setColorAt(i / 6, QColor.fromHsv(hue % 360, 200, 235))
            p.setBrush(QBrush(rainbow))
            p.drawEllipse(c, 13, 13)
            p.setBrush(self.color if self.color is not None else QColor("#FFFFFF"))
            p.drawEllipse(c, 8, 8)
        else:
            p.setBrush(self.color)
            p.drawEllipse(c, 13, 13)


CONTENT_MAX_W = 960  # 内容区最宽（含页面左右各 40 的边距）


class SettingsWindow(QWidget):
    """VoiceType 主窗口 — 侧边导航 + 多页面"""

    engine_changed = pyqtSignal(object)
    avatar_color_changed = pyqtSignal(str)  # 点色块即预览（浮窗头像 + 音波），「确定」才保存
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
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(4)

        # Logo
        from voice_typing import __version__, __dev__
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(13, 4, 0, 0)  # 头像圆头左缘对齐导航文字（侧栏边距 12 + 胶囊内边距 18）
        logo_row.setSpacing(6)
        self._logo_avatar = AvatarWidget(40, 30, GREEN)
        logo_row.addWidget(self._logo_avatar)
        logo = QLabel("VoiceType")
        logo.setStyleSheet("font-size: 16pt; font-weight: bold; color: #1F1F1F;")
        logo_row.addWidget(logo)
        logo_row.addStretch()
        sidebar_layout.addLayout(logo_row)

        self._version = __version__
        ver_text = f"v{__version__}-dev" if __dev__ else f"v{__version__}"
        ver_label = QLabel(ver_text)
        ver_label.setStyleSheet("font-size: 10pt; color: #A0A0A0; padding: 2px 18px 14px 18px;")
        sidebar_layout.addWidget(ver_label)

        # 有新版本时才显示，点击跳到 Release 页面
        self._update_label = QLabel()
        self._update_label.setVisible(False)
        self._update_label.setStyleSheet("font-size: 10pt; padding: 0 18px 14px 18px;")
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

        # 引擎状态胶囊：圆点对齐导航文字
        status_chip = QWidget()
        status_chip.setObjectName("status-chip")
        status_chip.setFixedHeight(30)
        status_row = QHBoxLayout(status_chip)
        status_row.setContentsMargins(18, 0, 14, 0)
        status_row.setSpacing(8)
        self._sidebar_indicator = QLabel()
        self._sidebar_indicator.setFixedSize(8, 8)
        self._sidebar_indicator.setStyleSheet(
            "background: #C4C7CC; border-radius: 4px; min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px;"
        )
        status_row.addWidget(self._sidebar_indicator)
        self._sidebar_engine_label = QLabel("引擎未就绪")
        self._sidebar_engine_label.setStyleSheet("font-size: 10pt; color: #6B6B6B;")
        status_row.addWidget(self._sidebar_engine_label)
        sidebar_layout.addWidget(status_chip, 0, Qt.AlignLeft)

        root.addWidget(sidebar)

        # ---- 分割线 ----

        # ---- 内容区 ----
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_home_page())
        self._stack.addWidget(self._build_history_page())
        self._stack.addWidget(self._build_dictionary_page())
        self._stack.addWidget(self._build_settings_page())
        # 限宽居中：窗口拉大 / 最大化时卡片不被拉成一长条
        self._stack.setMaximumWidth(CONTENT_MAX_W)
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        # 内容区伸展因子 1、两侧留白 0：空间先给内容区，到上限后剩下的才平分两侧居中
        content_layout.addStretch(0)
        content_layout.addWidget(self._stack, 1)
        content_layout.addStretch(0)
        root.addWidget(content, 1)

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
            f'<a href="{url}" style="color: {accent()[1]}; text-decoration: none;">'
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
        self._stat_units = {}
        for key, label_text, unit, accent in stats_defs:
            card = self._make_stat_card(key, label_text, unit, accent)
            cards_layout.addWidget(card, 1)

        layout.addWidget(cards_widget)

        layout.addSpacing(16)

        # 当前状态：一行 —— 状态圆点 + 结论 + 说明，没准备好时右侧给出下一步
        engine_card = QGroupBox("")
        engine_card.setStyleSheet("QGroupBox { padding: 20px 24px; }")
        erow = QHBoxLayout(engine_card)
        erow.setSpacing(14)
        self._home_dot = QLabel()
        self._home_dot.setFixedSize(10, 10)
        erow.addWidget(self._home_dot, 0, Qt.AlignVCenter)
        etexts = QVBoxLayout()
        etexts.setSpacing(2)
        self._home_engine_name = QLabel("")
        self._home_engine_name.setStyleSheet("font-weight: bold;")
        etexts.addWidget(self._home_engine_name)
        self._home_engine_status = QLabel("")
        self._home_engine_status.setObjectName("subtitle")
        etexts.addWidget(self._home_engine_status)
        erow.addLayout(etexts, 1)
        self._home_action_btn = QPushButton("去设置")
        self._home_action_btn.setObjectName("accent")
        self._home_action_btn.setCursor(Qt.PointingHandCursor)
        self._home_action_btn.clicked.connect(lambda: self._select_nav(3))
        erow.addWidget(self._home_action_btn)

        layout.addWidget(engine_card)
        layout.addStretch()

        return page

    def _make_stat_card(self, key, label_text, unit, accent=False):
        card = QGroupBox("")
        card.setStyleSheet(
            "QGroupBox { border: 1px solid #ECEDEF; border-radius: 20px;"
            " background: #FFFFFF; padding: 20px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)  # 内边距已由 QSS padding 给出，再叠默认边距会挤掉数字
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("stat-label")
        layout.addWidget(label)

        # 数字与单位同一行、底边对齐：62.1 分钟
        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        value_label = QLabel("--")
        value_label.setObjectName("stat-value")
        value_label.setProperty("accent", "true" if accent else "false")
        value_row.addWidget(value_label, 0, Qt.AlignBottom)
        unit_label = QLabel(unit)
        unit_label.setObjectName("stat-label")
        unit_label.setContentsMargins(0, 0, 0, 5)
        value_row.addWidget(unit_label, 0, Qt.AlignBottom)
        value_row.addStretch()
        layout.addLayout(value_row)

        self._stat_labels[key] = value_label
        self._stat_units[key] = (unit_label, unit)
        return card

    def _set_stat(self, key, value, decimals=0):
        """数字过万写成「16.3 万字」，卡片宽度固定，数字再涨也放得下"""
        unit_label, unit = self._stat_units[key]
        if value >= 10000:
            text, unit = f"{value / 10000:.1f}", "万" + unit
        else:
            text = f"{value:.{decimals}f}"
        self._stat_labels[key].setText(text)
        unit_label.setText(unit)

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
            self._set_stat("total_seconds", total_min, 1 if total_min < 100 else 0)
        self._set_stat("total_characters", total_chars)
        self._set_stat("total_sessions", total_sessions)

        if total_min > 0 and total_chars > 0:
            efficiency = total_chars / total_min
            self._set_stat("efficiency", efficiency)
        else:
            self._stat_labels["efficiency"].setText("--")

        ready = bool(self._engine and self._engine.is_available())
        has_hotkey = bool(self._config.get("hotkey"))
        dot = accent()[0] if ready and has_hotkey else "#C4C7CC"
        self._home_dot.setStyleSheet(f"background: {dot}; border-radius: 5px;")
        self._home_action_btn.setVisible(not (ready and has_hotkey))
        self._home_action_btn.setText("去设置" if not ready else "录制快捷键")
        if ready:
            self._home_engine_name.setText(f"引擎已就绪：{self._engine.name}")
            if has_hotkey:
                self._home_engine_status.setText("快捷键可用，随时可以开始语音输入")
            else:
                self._home_engine_status.setText("还差一步：录制一个快捷键")
            self._sidebar_indicator.setStyleSheet(
                f"background: {accent()[0]}; border-radius: 4px; min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px;"
            )
            self._sidebar_engine_label.setText("引擎就绪")
        else:
            self._home_engine_name.setText("引擎未就绪")
            self._home_engine_status.setText("填好语音识别的 API Key 即可开始使用")
            self._sidebar_indicator.setStyleSheet(
                "background: #C4C7CC; border-radius: 4px; min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px;"
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
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self._clear_history)
        title_row.addWidget(clear_btn)
        layout.addLayout(title_row)

        hint = QLabel("所有历史记录仅保存在本地设备上")
        hint.setObjectName("subtitle")
        layout.addWidget(hint)

        self._history_list = QListWidget()
        self._history_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                padding: 0;
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
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, text)
            item.setData(META_ROLE, "  ·  ".join(meta_parts))
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

        self._dict_import_btn = QPushButton("导入")
        self._dict_import_btn.setToolTip("从 CSV（词汇,易错词）或纯文本（一行一个词汇）导入，已有词汇会跳过")
        self._dict_import_btn.clicked.connect(self._import_dict)
        title_row.addWidget(self._dict_import_btn)
        self._dict_export_btn = QPushButton("导出")
        self._dict_export_btn.setToolTip("导出为 CSV，可用 Excel / WPS 打开编辑")
        self._dict_export_btn.clicked.connect(self._export_dict)
        title_row.addWidget(self._dict_export_btn)
        self._dict_select_btn = QPushButton("全选")
        self._dict_select_btn.clicked.connect(self._toggle_select_all_dict)
        title_row.addWidget(self._dict_select_btn)

        self._dict_del_btn = QPushButton("删除选中")
        self._dict_del_btn.setObjectName("danger")
        self._dict_del_btn.setEnabled(False)
        self._dict_del_btn.clicked.connect(self._delete_dict_item)
        title_row.addWidget(self._dict_del_btn)
        layout.addLayout(title_row)

        # 说明 + 操作反馈同一行：说明可换行，反馈变长时让说明折行，而不是把整页撑宽挤扁按钮
        hint_row = QHBoxLayout()
        hint = QLabel("添加常用的专业词汇，识别更准确。按住 Ctrl / Shift 可多选；可导入、导出 CSV 文件")
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        hint_row.addWidget(hint, 1)
        self._dict_status = QLabel("")
        self._dict_status.setObjectName("status")
        hint_row.addWidget(self._dict_status, 0, Qt.AlignRight | Qt.AlignTop)
        layout.addLayout(hint_row)

        # 添加词条：词汇（必填）← 易错词（选填），箭头方向与列表里的「词汇 ← 易错词」一致；
        # 下方用一句例子直观示意替换效果
        add_card = QGroupBox("添加词条")
        grid = QGridLayout(add_card)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self._dict_term_label = QLabel()
        self._dict_term_label.setObjectName("field-label")
        grid.addWidget(self._dict_term_label, 0, 0)
        alias_label = QLabel('易错词 <span style="color: #6B6B6B;">· 选填，多个用逗号隔开</span>')
        alias_label.setObjectName("field-label")
        grid.addWidget(alias_label, 0, 2)


        self._dict_term_input = QLineEdit()
        self._dict_term_input.setPlaceholderText("如：Claude Code")
        self._dict_term_input.setMinimumHeight(48)
        self._dict_term_input.setStyleSheet("border-radius: 24px;")  # 比全局输入框高，圆角跟着放大保持胶囊
        self._dict_term_input.returnPressed.connect(self._add_dict_item)
        grid.addWidget(self._dict_term_input, 1, 0)

        self._dict_arrow = QLabel("←")
        self._dict_arrow.setToolTip("识别结果里出现右边的易错词时，自动替换成左边的词汇")
        grid.addWidget(self._dict_arrow, 1, 1)

        self._dict_alias_input = QLineEdit()
        self._dict_alias_input.setPlaceholderText("如：cloud code, cloudcode")
        self._dict_alias_input.setMinimumHeight(48)
        self._dict_alias_input.setStyleSheet("border-radius: 24px;")
        self._dict_alias_input.returnPressed.connect(self._add_dict_item)
        grid.addWidget(self._dict_alias_input, 1, 2)

        add_btn = QPushButton("添加")
        add_btn.setObjectName("accent")
        add_btn.clicked.connect(self._add_dict_item)
        add_btn.setFixedWidth(80)
        add_btn.setMinimumHeight(48)
        add_btn.setStyleSheet("border-radius: 24px;")
        grid.addWidget(add_btn, 1, 3)

        self._dict_example = QLabel()
        self._dict_example.setObjectName("field-hint")
        self._dict_example.setTextFormat(Qt.RichText)
        grid.addWidget(self._dict_example, 2, 0, 1, 4)

        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(2, 3)
        layout.addWidget(add_card)
        self._dict_list = QListWidget()
        self._dict_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                padding: 0;
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

        layout.addStretch()
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
            self._append_dict_item(term, alias)
        self._update_dict_controls()

    def _append_dict_item(self, term, alias):
        item = QListWidgetItem(term)
        item.setData(Qt.UserRole, {"term": term, "alias": alias})
        item.setData(META_ROLE, f"易错词：{alias}" if alias else "")
        self._dict_list.addItem(item)

    def _dict_entries(self):
        return [self._dict_list.item(i).data(Qt.UserRole) for i in range(self._dict_list.count())]

    def _update_dict_controls(self):
        """列表 / 空状态显隐 + 导出、全选、删除按钮的可用状态与文字"""
        count = self._dict_list.count()
        selected = len(self._dict_list.selectedItems())
        self._dict_list.setVisible(count > 0)
        self._dict_empty_label.setVisible(count == 0)
        self._dict_export_btn.setEnabled(count > 0)
        self._dict_select_btn.setEnabled(count > 0)
        self._dict_select_btn.setText("取消全选" if count and selected == count else "全选")
        self._dict_del_btn.setEnabled(selected > 0)
        self._dict_del_btn.setText(f"删除选中（{selected}）" if selected > 1 else "删除选中")

    def _flash_dict_status(self, text, ms=3000):
        self._dict_status.setText(text)
        QTimer.singleShot(ms, lambda: self._dict_status.setText(""))

    def _toggle_select_all_dict(self):
        if len(self._dict_list.selectedItems()) == self._dict_list.count():
            self._dict_list.clearSelection()
        else:
            self._dict_list.selectAll()

    def _export_dict(self):
        default = os.path.join(os.path.expanduser("~"), "VoiceType词典.csv")
        path, _ = QFileDialog.getSaveFileName(self, "导出词典", default, "CSV 文件 (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        entries = self._dict_entries()
        try:
            export_vocab_csv(entries, path)
        except OSError as e:
            self._flash_dict_status(f"导出失败：{e.strerror or e}")
            return
        self._flash_dict_status(f"已导出 {len(entries)} 条")

    def _import_dict(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入词典", os.path.expanduser("~"), "词典文件 (*.csv *.txt);;所有文件 (*)")
        if not path:
            return
        try:
            entries = import_vocab_csv(path)
        except (OSError, ValueError, csv.Error) as e:
            self._flash_dict_status(f"导入失败：{e}")
            return
        existing = {e["term"] for e in self._dict_entries()}
        added = [e for e in entries if e["term"] not in existing]
        for e in added:
            self._append_dict_item(e["term"], e["alias"])
        self._update_dict_controls()
        if added:
            self._save_dict()
        skipped = len(entries) - len(added)
        self._flash_dict_status(f"导入 {len(added)} 条" + (f"，跳过 {skipped} 条已有词汇" if skipped else ""))

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

        self._append_dict_item(term, alias)
        self._update_dict_controls()
        self._dict_term_input.clear()
        self._dict_alias_input.clear()
        self._dict_term_input.setFocus()
        self._save_dict()

    def _on_dict_selection_changed(self):
        self._update_dict_controls()

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
        self._update_dict_controls()
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
        self._api_status.hide()  # 没内容时不占位，否则卡片底部多出一截空白

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
        self._realtime_divider = self._divider()  # 随「提前润色」一起显隐，否则关闭润色时两条线叠在一起
        polish_llm_layout.addWidget(self._realtime_divider)
        polish_llm_layout.addWidget(self._realtime_polish_row)

        self._smart_polish_check = QCheckBox("按当前使用的软件调整格式")
        self._smart_polish_row = self._field(
            "智能润色", self._smart_polish_check,
            "聊天软件里保持口语短句；写邮件分段、礼貌；写文档整理成要点列表；"
            "写代码和问 AI 时英文术语保持原样。认不出的软件照常润色。",
        )
        self._smart_divider = self._divider()
        polish_llm_layout.addWidget(self._smart_divider)
        polish_llm_layout.addWidget(self._smart_polish_row)

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

        # ③ 快捷键
        hotkey_card = QGroupBox("快捷键")
        hlayout = QVBoxLayout(hotkey_card)
        hlayout.setSpacing(12)
        self._hotkey_mode_combo = _DarkComboBox()
        self._hotkey_mode_combo.addItem("按住说话，松开结束", "hold")
        self._hotkey_mode_combo.addItem("按一下开始，再按一下结束", "toggle")
        hlayout.addWidget(self._field("触发方式", self._hotkey_mode_combo))
        hlayout.addWidget(self._divider())
        hrow_widget = QWidget()
        hrow_widget.setObjectName("input-row")
        hrow = QHBoxLayout(hrow_widget)
        hrow.setContentsMargins(0, 0, 0, 0)
        self._hotkey_btn = QPushButton(self._hotkey_display())
        self._hotkey_btn.setMinimumHeight(44)
        self._hotkey_btn.clicked.connect(self._record_hotkey)
        hrow.addWidget(self._hotkey_btn)
        self._clear_hotkey_btn = QPushButton("清除")
        self._clear_hotkey_btn.setFixedWidth(80)
        self._clear_hotkey_btn.clicked.connect(self._clear_hotkey)
        hrow.addWidget(self._clear_hotkey_btn)
        hlayout.addWidget(self._field("快捷键", hrow_widget, "支持组合键，也支持单键。点击后直接按下想用的按键。"))
        layout.addWidget(hotkey_card)

        # ④ 外观：头像颜色（浮窗头像、音波、首页头像同色）
        look_card = QGroupBox("外观")
        look_v = QVBoxLayout(look_card)
        swatch_row = QWidget()
        swatch_row.setObjectName("input-row")
        srow = QHBoxLayout(swatch_row)
        srow.setContentsMargins(0, 4, 0, 0)
        srow.setSpacing(6)
        self._color_preview = AvatarWidget(64, 44, GREEN)
        srow.addWidget(self._color_preview)
        srow.addSpacing(10)
        self._swatch_group = QButtonGroup(self)
        self._swatches = []
        for name, color in AVATAR_COLORS:
            sw = _ColorSwatch(color, name)
            sw.clicked.connect(lambda _, c=color: self._set_avatar_color(c))
            self._swatch_group.addButton(sw)
            self._swatches.append(sw)
            srow.addWidget(sw)
        self._custom_swatch = _ColorSwatch(None, "自定义颜色")
        self._custom_swatch.setProperty("custom", True)
        self._custom_swatch.clicked.connect(self._pick_custom_color)
        self._swatch_group.addButton(self._custom_swatch)
        srow.addWidget(self._custom_swatch)
        srow.addStretch()
        look_v.addWidget(self._field(
            "头像颜色", swatch_row,
            "浮窗头像、音波和整个界面的强调色都用这个颜色；最后一个是自定义。",
        ))
        layout.addWidget(look_card)

        # ⑤ 开机启动
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
        """创建密码输入框：眼睛图标嵌在输入框右侧，点一下显示明文，再点隐藏"""
        wrapper = QWidget()
        wrapper.setObjectName("input-row")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)

        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setEchoMode(QLineEdit.Password)
        layout.addWidget(input_field)

        eye = input_field.addAction(_make_eye_icon(visible=True), QLineEdit.TrailingPosition)
        eye.setToolTip("显示 / 隐藏")

        def toggle():
            hidden = input_field.echoMode() == QLineEdit.Password
            input_field.setEchoMode(QLineEdit.Normal if hidden else QLineEdit.Password)
            eye.setIcon(_make_eye_icon(visible=not hidden))
        eye.triggered.connect(toggle)

        if status_label is not None:
            def on_text_changed(text):
                status_label.setText("API Key 已填写" if text and len(text) > 10 else "")
                status_label.setVisible(bool(status_label.text()))
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

        mode_idx = self._hotkey_mode_combo.findData(self._config.get("hotkey_mode", "hold"))
        if mode_idx >= 0:
            self._hotkey_mode_combo.setCurrentIndex(mode_idx)

        self._refresh_credential_visibility()

        self._autostart_check.setChecked(self._config.get("autostart", False))
        self._set_avatar_color(self._config.get("avatar_color", GREEN))

        strength = self._config.get("polish_strength", "medium")
        btn = {"light": self._polish_light, "medium": self._polish_medium, "strong": self._polish_strong}.get(strength)
        if btn:
            btn.setChecked(True)

        for name, field in self._polish_key_inputs.items():
            field.setText(self._config.get(f"{name}_api_key", ""))
        self._realtime_polish_check.setChecked(self._config.get("realtime_polish", False))
        self._smart_polish_check.setChecked(self._config.get("smart_polish", True))

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
        self._realtime_divider.setVisible(provider != "off")
        self._smart_polish_row.setVisible(provider != "off")
        self._smart_divider.setVisible(provider != "off")

    # ---------- 头像颜色 ----------

    def _set_avatar_color(self, color):
        """预览：头像、浮窗（经信号）和整个界面的强调色同时换色；勾选对应色块"""
        self._avatar_color = color
        preset = next((sw for sw in self._swatches if sw.color.name().lower() == color.lower()), None)
        if preset is not None:
            preset.setChecked(True)
        else:
            self._custom_swatch.color = QColor(color)
            self._custom_swatch.setChecked(True)
        self._custom_swatch.update()
        self._color_preview.set_color(color)
        self._hero.set_avatar_color(color)
        self._logo_avatar.set_color(color)
        self._apply_accent(color)
        self.avatar_color_changed.emit(color)

    def _apply_accent(self, color):
        """界面强调色跟头像色：QSS 部分 set_accent 一次换完，自绘和内联样式的几处在这里补"""
        set_accent(color)
        icon = _make_tray_icon(color)
        self._tray.setIcon(icon)
        self.setWindowIcon(icon)
        apply_placeholder_color(self)  # 重设样式表会把占位色冲回正文色
        main, text = accent()[:2]
        self._dict_term_label.setText(f'词汇 <span style="color: {text};">· 必填</span>')
        self._dict_arrow.setStyleSheet(f"font-size: 16pt; color: {main};")
        self._dict_example.setText(
            '效果：识别出「用 <s>cloud code</s> 写代码」，自动改成「用 '
            f'<span style="color: {text};">Claude Code</span> 写代码」<br>'
            '只填词汇也有用：它会作为热词发给识别引擎，让引擎更容易认出这个词'
        )
        self._refresh_home()
        self.update()  # 首页横幅、列表卡片是自绘的

    def _pick_custom_color(self):
        current = QColor(self._avatar_color)
        color = QColorDialog.getColor(current, self, "自定义头像颜色")
        # 取消时 QButtonGroup 已经把勾挪到了「自定义」上，按当前颜色挪回去
        self._set_avatar_color(color.name() if color.isValid() else self._avatar_color)

    def _on_apply(self):
        engine_type = self._engine_combo.currentData()
        self._config["engine"] = engine_type
        self._config["alibaba_api_key"] = self._api_input.text()
        self._config["volc_asr_api_key"] = self._volc_api_key_input.text().strip()
        self._config["volc_asr_resource_id"] = self._volc_resource_combo.currentData()
        self._config["volc_boosting_table_id"] = self._volc_boosting_input.text().strip()
        self._config["polish_provider"] = self._polish_provider_combo.currentData()

        self._config["avatar_color"] = self._avatar_color
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
        self._config["smart_polish"] = self._smart_polish_check.isChecked()

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
            self._show_status("正在同步热词表...")
            QApplication.processEvents()
            phrase_id = sync_vocabulary(
                api_key=self._config.get("alibaba_api_key"),
                hotwords=hotwords,
                phrase_id=self._config.get("phrase_id", ""),
            )
            if phrase_id:
                self._config["phrase_id"] = phrase_id
            else:
                self._show_status("热词同步失败（识别仍可用，热词不生效）", ok=False)
                QTimer.singleShot(3000, lambda: self._update_status())
        elif not vocab:
            self._config["phrase_id"] = ""

        save_config(self._config)
        self._create_engine()
        self._update_status()
        self._refresh_dict_list()

        self._show_status("设置已保存并应用")
        QTimer.singleShot(2000, lambda: self._update_status())

    def _on_cancel(self):
        self._new_hotkey_keys = None
        self._hotkey.set_hotkey(self._config.get("hotkey", []))
        self._apply_config()
        self._show_status("已重置为上次保存的设置")
        QTimer.singleShot(2000, lambda: self._update_status())

    def _record_hotkey(self):
        self._hotkey_btn.setText("按下快捷键组合...")
        _, text, tint, _ = accent()
        self._hotkey_btn.setStyleSheet(f"background: {tint}; color: {text};")
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
            self._show_status(f"引擎就绪：{self._engine.name}")
        else:
            self._show_status("引擎未就绪，请配置 API Key", ok=False)

    def _show_status(self, text, ok=True):
        """设置页底部状态：成功绿、失败红"""
        self._status_label.setText(text)
        self._status_label.setObjectName("status" if ok else "error")
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

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
