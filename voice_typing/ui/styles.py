"""浅色主题 QSS 样式表 — 与屏幕下方的 Grok 风格浮窗同一套视觉语言

层次只用颜色和字重区分，字号严格遵守 font_sizes.md 的三档体系（21/16/10pt）。
色板（与浮窗一致）：
    #F5F6F7 页面底   #FFFFFF 卡片 / 侧栏   #F3F4F5 输入控件   #F1F1F1 次要按钮
    #1F1F1F 主文字   #6B6B6B 次要         #A0A0A0 占位       #ECEDEF 描边
强调色：默认是浮窗头像与音波的绿 #14C16E（深一档作文字，淡一档作选中底），跟随设置页「头像颜色」，
由 set_accent() 整体换掉。
红 #E32D34 只给危险操作与错误。按钮、输入框、导航项一律胶囊（圆角 18：QSS 圆角超过控件半高会整个失效，
高约 38–40 的控件取 18 最稳），卡片圆角 20。
"""

import os

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QLineEdit

PLACEHOLDER_COLOR = "#A0A0A0"

GREEN = "#14C16E"
GREEN_TEXT = "#0E9F5A"
GREEN_TINT = "#E8F8EF"
RED = "#E32D34"

_RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")


def apply_placeholder_color(root):
    """把 root 下所有输入框的占位文字调成灰色。

    QSS 没有 ::placeholder 选择器（写了是空操作），占位色只认调色板的
    PlaceholderText 角色；而 QSS 的 color 会被一并复制到该角色上。样式表对控件
    调色板的这次改写发生在首次 polish 时，所以要先 ensurePolished() 逼它先跑完，
    再用调色板盖掉。"""
    palette = root.palette()
    palette.setColor(QPalette.PlaceholderText, QColor(PLACEHOLDER_COLOR))
    for edit in root.findChildren(QLineEdit):
        edit.ensurePolished()
        edit.setPalette(palette)


_APP_STYLE = """
/* 全局 */
QWidget {
    background-color: #F5F6F7;
    color: #1F1F1F;
    font-size: 10pt;
}

/* 输入框：浅灰胶囊，聚焦变白 + 绿描边 */
QLineEdit {
    background: #F3F4F5;
    border: 1px solid #F3F4F5;
    border-radius: 18px;
    padding: 9px 16px;
    color: #1F1F1F;
    selection-background-color: GREEN;
    selection-color: #FFFFFF;
}
QLineEdit:hover {
    border-color: #E3E5E8;
}
QLineEdit:focus {
    border-color: GREEN;
    background: #FFFFFF;
}

/* 按钮：全圆角胶囊。默认 = 浮窗同款浅灰圆按钮 */
QPushButton {
    background: #F1F1F1;
    border: none;
    border-radius: 18px;
    padding: 9px 20px;
    color: #1F1F1F;
    font-weight: 500;
}
QPushButton:hover {
    background: #E6E6E6;
}
QPushButton:pressed {
    background: #DADADA;
}
QPushButton:disabled {
    background: #F3F4F5;
    color: #B8BCC2;
}
QPushButton#accent {
    background: GREEN;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#accent:hover {
    background: GREEN_HOVER;
}
QPushButton#accent:pressed {
    background: GREEN_PRESSED;
}
QPushButton#danger {
    background: #FDECEC;
    color: RED;
}
QPushButton#danger:hover {
    background: #FAD9D9;
}
QPushButton#danger:disabled {
    background: #F3F4F5;
    color: #B8BCC2;
}

/* 侧边导航：胶囊，选中淡绿底 + 绿字 */
QPushButton#nav-btn {
    background: transparent;
    border: none;
    border-radius: 18px;
    padding: 10px 18px;
    text-align: left;
    font-weight: 500;
    color: #6B6B6B;
}
QPushButton#nav-btn:hover {
    background: #F3F4F5;
    color: #1F1F1F;
}
QPushButton#nav-btn[active="true"] {
    background: GREEN_TINT;
    color: GREEN_TEXT;
    font-weight: bold;
}

/* 下拉框 */
QComboBox {
    background: #F3F4F5;
    border: 1px solid #F3F4F5;
    border-radius: 18px;
    padding: 9px 36px 9px 16px;
    color: #1F1F1F;
    min-height: 18px;
    outline: none;
}
QComboBox:hover { border-color: #E3E5E8; }
QComboBox:focus { border-color: GREEN; background: #FFFFFF; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 30px;
    border: none;
}
QComboBox::down-arrow {
    image: url(RES/arrow-down.svg);
    width: 16px;
    height: 16px;
}
/* 下拉弹出层 — 容器 + 视图 */
QComboBox QAbstractItemView,
QComboBox QListView {
    background-color: #FFFFFF;
    border: 1px solid #ECEDEF;
    border-radius: 16px;
    padding: 6px;
    margin: 0;
    outline: none;
    color: #1F1F1F;
    selection-background-color: GREEN_TINT;
    selection-color: GREEN_TEXT;
    show-decoration-selected: 1;
}
QComboBox QAbstractItemView::item,
QComboBox QListView::item {
    background-color: transparent;
    padding: 9px 14px;
    min-height: 32px;
    color: #1F1F1F;
    border-radius: 12px;
    margin: 1px 0;
}
QComboBox QAbstractItemView::item:selected,
QComboBox QListView::item:selected {
    background-color: GREEN_TINT;
    color: GREEN_TEXT;
}
QComboBox QAbstractItemView::item:hover,
QComboBox QListView::item:hover {
    background-color: #F3F4F5;
    color: #1F1F1F;
}

/* 进度条 */
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #ECEDEF;
    text-align: center;
    color: #1F1F1F;
    height: 6px;
    font-size: 10pt;
}
QProgressBar::chunk {
    background: GREEN;
    border-radius: 4px;
}

/* 分组卡片：白底大圆角，标题在卡片内部左上角 */
QGroupBox {
    border: 1px solid #ECEDEF;
    border-radius: 20px;
    background: #FFFFFF;
    margin-top: 0;
    padding: 44px 20px 20px 20px;
    font-weight: bold;
    font-size: 10pt;
}
QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: 22px;
    top: 18px;
    padding: 0;
    color: #1F1F1F;
}

/* 卡片内的布局容器：透明，避免盖出页面底色的色带 */
QWidget#field, QWidget#input-row {
    background: transparent;
}

/* 复选框 */
QCheckBox, QRadioButton {
    background: transparent;
    spacing: 10px;
    color: #1F1F1F;
    padding: 3px 0;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1.5px solid #CFD2D6;
    border-radius: 6px;
    background: #FFFFFF;
}
QCheckBox::indicator:hover {
    border-color: GREEN;
}
QCheckBox::indicator:checked {
    background: GREEN;
    border-color: GREEN;
    image: url(RES/checkmark.svg);
}

/* 单选按钮：选中 = 绿环 + 白芯 */
QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 1.5px solid #CFD2D6;
    border-radius: 10px;
    background: #FFFFFF;
}
QRadioButton::indicator:hover {
    border-color: GREEN;
}
QRadioButton::indicator:checked {
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                stop:0 #FFFFFF, stop:0.38 #FFFFFF,
                                stop:0.42 GREEN, stop:1 GREEN);
    border-color: GREEN;
}

/* 标签 */
QLabel {
    background: transparent;
    color: #1F1F1F;
}
/* 页面标题 */
QLabel#page-title {
    font-size: 16pt;
    font-weight: bold;
    color: #1F1F1F;
}
/* 设置项标题：常规字重，与加粗的卡片标题拉开层级 */
QLabel#field-label {
    color: #1F1F1F;
    font-weight: normal;
}
/* 设置项说明 / 次要信息 */
QLabel#subtitle, QLabel#field-hint {
    color: #6B6B6B;
    font-size: 10pt;
}
QLabel#status {
    color: GREEN_TEXT;
    font-size: 10pt;
}
QLabel#error {
    color: RED;
    font-size: 10pt;
}

/* 统计卡片数值 — 统一深色，绿色只留给强调项 */
QLabel#stat-value {
    font-size: 21pt;
    font-weight: bold;
    color: #1F1F1F;
}
QLabel#stat-value[accent="true"] {
    color: GREEN_TEXT;
}
QLabel#stat-label {
    font-size: 10pt;
    color: #6B6B6B;
}

/* 分割线 */
QFrame#separator, QFrame#divider {
    background: transparent;
    border: none;
    border-top: 1px solid #F0F1F3;
    max-height: 1px;
}

/* 侧边栏 */
QWidget#sidebar {
    background: #FFFFFF;
    border-right: 1px solid #ECEDEF;
}
/* 侧边栏底部的引擎状态胶囊 */
QWidget#status-chip {
    background: #F3F4F5;
    border-radius: 15px;
}
QWidget#status-chip QLabel {
    color: #6B6B6B;
}

/* 列表：容器透明，每一项由 CardDelegate 画成白色圆角卡片 */
QListWidget {
    background: transparent;
    border: none;
    outline: none;
}

/* 滚动条 */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 40);
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover,
QScrollBar:vertical:hover QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 80);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* 工具提示 */
QToolTip {
    background: #FFFFFF;
    border: 1px solid #ECEDEF;
    border-radius: 10px;
    padding: 6px 10px;
    color: #1F1F1F;
    font-size: 10pt;
}
"""


def accent_shades(color):
    """强调色 → (主色, 文字色, 选中底色, 悬停色)。文字和悬停取深一档，选中底是主色 10% 混白"""
    c = QColor(color)
    tint = QColor(*(round(255 - (255 - v) * 0.1) for v in c.getRgb()[:3]))
    return c.name(), c.darker(125).name(), tint.name(), c.darker(112).name()


_accent = accent_shades(GREEN)


def accent():
    """当前强调色 (主色, 文字色, 选中底色, 悬停色)；自绘控件在 paintEvent 里取"""
    return _accent


def app_style():
    main, text, tint, hover = _accent
    return (_APP_STYLE.replace("GREEN_TINT", tint).replace("GREEN_TEXT", text)
            .replace("GREEN_HOVER", hover).replace("GREEN_PRESSED", text)
            .replace("GREEN", main).replace("RED", RED).replace("RES", _RES))


def set_accent(color):
    """全局换强调色：重设整个应用的样式表（QSS 控件立即跟着变），自绘控件需各自 update()"""
    global _accent
    _accent = accent_shades(color)
    QApplication.instance().setStyleSheet(app_style() + OVERLAY_STYLE)


APP_STYLE = app_style()

OVERLAY_STYLE = """
QWidget#overlay {
    background: transparent;
}
QLabel#transcript {
    background: transparent;
    color: #f0f0f0;
    font-size: 10pt;
    padding: 16px 24px;
}
QLabel#indicator {
    background: #22c55e;
    border-radius: 5px;
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
}
"""
