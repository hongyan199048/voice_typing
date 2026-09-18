"""暗黑主题 QSS 样式表 — 参考 Typeplus / 豆包语音输入法的克制设置页风格

层次只用颜色和字重区分，字号严格遵守 font_sizes.md 的三档体系（21/16/10pt）。
色板：
    #0a0a0a 侧栏   #0d0d0d 页面   #141414 卡片   #1c1c1c 控件
    #f0f0f0 主文字 #8a8a8a 次要   #666666 占位   #22c55e 强调
"""

DARK_STYLE = """
/* 全局 */
QWidget {
    background-color: #0d0d0d;
    color: #f0f0f0;
    font-size: 10pt;
}

/* 输入框 */
QLineEdit {
    background: #1c1c1c;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 9px 13px;
    color: #f0f0f0;
    selection-background-color: #22c55e;
    selection-color: #0d0d0d;
}
QLineEdit:hover {
    border-color: #3a3a3a;
}
QLineEdit:focus {
    border-color: #22c55e;
    background: #202020;
}
QLineEdit::placeholder {
    color: #666;
}

/* 按钮 */
QPushButton {
    background: #1c1c1c;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 8px 18px;
    color: #e4e4e4;
    font-weight: 500;
}
QPushButton:hover {
    background: #242424;
    border-color: #3a3a3a;
}
QPushButton:pressed {
    background: #181818;
}
QPushButton#accent {
    background: #22c55e;
    color: #08130c;
    border: 1px solid #22c55e;
    font-weight: bold;
}
QPushButton#accent:hover {
    background: #2ade6d;
    border-color: #2ade6d;
}
QPushButton#accent:pressed {
    background: #16a34a;
}
QPushButton#danger {
    background: transparent;
    border: 1px solid #3a2020;
    color: #d16a6a;
}
QPushButton#danger:hover {
    background: #2a1616;
    border-color: #ef4444;
    color: #ef4444;
}

/* 侧边导航按钮 — 选中时左侧绿条 */
QPushButton#nav-btn {
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-radius: 0;
    padding: 10px 14px;
    text-align: left;
    font-weight: 500;
    color: #8a8a8a;
}
QPushButton#nav-btn:hover {
    background: #151515;
    color: #d8d8d8;
}
QPushButton#nav-btn[active="true"] {
    background: #16211a;
    border-left: 2px solid #22c55e;
    color: #f0f0f0;
    font-weight: bold;
}

/* 下拉框 */
QComboBox {
    background: #1c1c1c;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 9px 34px 9px 13px;
    color: #f0f0f0;
    min-height: 18px;
    outline: none;
}
QComboBox:hover { border-color: #3a3a3a; background: #202020; }
QComboBox:focus { border-color: #22c55e; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
}
QComboBox::down-arrow {
    width: 14px;
    height: 14px;
}
/* 下拉弹出层 — 容器 + 视图 */
QComboBox QAbstractItemView,
QComboBox QListView {
    background-color: #1c1c1c;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 5px;
    margin: 0;
    outline: none;
    color: #f0f0f0;
    selection-background-color: #22c55e;
    selection-color: #08130c;
    show-decoration-selected: 1;
}
QComboBox QAbstractItemView::item,
QComboBox QListView::item {
    background-color: transparent;
    padding: 9px 12px;
    min-height: 32px;
    color: #f0f0f0;
    border-radius: 7px;
    margin: 1px 0;
}
QComboBox QAbstractItemView::item:selected,
QComboBox QListView::item:selected {
    background-color: #22c55e;
    color: #08130c;
}
QComboBox QAbstractItemView::item:hover,
QComboBox QListView::item:hover {
    background-color: #262626;
    color: #f0f0f0;
}

/* 进度条 */
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #1c1c1c;
    text-align: center;
    color: #f0f0f0;
    height: 6px;
    font-size: 10pt;
}
QProgressBar::chunk {
    background: #22c55e;
    border-radius: 4px;
}

/* 分组卡片 — 标题在卡片内部左上角 */
QGroupBox {
    border: 1px solid #1e1e1e;
    border-radius: 14px;
    background: #141414;
    margin-top: 0;
    padding: 40px 16px 16px 16px;
    font-weight: bold;
    font-size: 10pt;
}
QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: 18px;
    top: 16px;
    padding: 0;
    color: #f0f0f0;
}

/* 卡片内的布局容器：透明，避免盖出比卡片更暗的色带 */
QWidget#field, QWidget#input-row {
    background: transparent;
}

/* 复选框 */
QCheckBox, QRadioButton {
    background: transparent;
    spacing: 9px;
    color: #e4e4e4;
    padding: 3px 0;
}
QCheckBox:hover, QRadioButton:hover {
    color: #f0f0f0;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border: 1px solid #3a3a3a;
    border-radius: 5px;
    background: #1c1c1c;
}
QCheckBox::indicator:hover {
    border-color: #22c55e;
}
QCheckBox::indicator:checked {
    background: #22c55e;
    border-color: #22c55e;
    image: url(voice_typing/ui/resources/checkmark.svg);
}

/* 单选按钮 */
QRadioButton::indicator {
    width: 17px;
    height: 17px;
    border: 1px solid #3a3a3a;
    border-radius: 9px;
    background: #1c1c1c;
}
QRadioButton::indicator:hover {
    border-color: #22c55e;
}
QRadioButton::indicator:checked {
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                                fx:0.5, fy:0.5,
                                stop:0 #08130c, stop:0.45 #08130c,
                                stop:0.5 #22c55e, stop:1 #22c55e);
    border-color: #22c55e;
}

/* 标签 */
QLabel {
    background: transparent;
    color: #f0f0f0;
}
/* 页面标题 */
QLabel#page-title {
    font-size: 16pt;
    font-weight: bold;
    color: #f0f0f0;
}
/* 设置项标题 */
QLabel#field-label {
    color: #e4e4e4;
    font-weight: 500;
}
/* 设置项说明 / 次要信息 */
QLabel#subtitle, QLabel#field-hint {
    color: #8a8a8a;
    font-size: 10pt;
}
QLabel#status {
    color: #22c55e;
    font-size: 10pt;
}
QLabel#error {
    color: #ef4444;
    font-size: 10pt;
}

/* 统计卡片数值 — 统一白色，绿色只留给强调项 */
QLabel#stat-value {
    font-size: 21pt;
    font-weight: bold;
    color: #f0f0f0;
}
QLabel#stat-value[accent="true"] {
    color: #22c55e;
}
QLabel#stat-label {
    font-size: 10pt;
    color: #8a8a8a;
}

/* 分割线 */
QFrame#separator, QFrame#divider {
    background: transparent;
    border: none;
    border-top: 1px solid #242424;
    max-height: 1px;
}

/* 侧边栏 */
QWidget#sidebar {
    background: #0a0a0a;
    border-right: 1px solid #171717;
}

/* 列表 */
QListWidget {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    background: #161616;
    border: 1px solid #1e1e1e;
    border-radius: 10px;
    padding: 10px 13px;
    margin: 3px 0;
    color: #e4e4e4;
}
QListWidget::item:hover {
    background: #1c1c1c;
    border-color: #2a2a2a;
}
QListWidget::item:selected {
    background: #16211a;
    border-color: #22c55e;
    color: #f0f0f0;
}

/* 滚动条 — 不滑动时隐藏，hover 时出现 */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(60, 60, 60, 140);
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover,
QScrollBar:vertical:hover QScrollBar::handle:vertical {
    background: rgba(90, 90, 90, 220);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* 工具提示 */
QToolTip {
    background: #1c1c1c;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 6px 10px;
    color: #f0f0f0;
    font-size: 10pt;
}
"""

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
