# 字号体系

## 层级总览

| 层级 | 字号 | 角色 |
|------|------|------|
| Hero | 21pt | 统计大数字 |
| 标题 | 16pt | Logo、页面标题 |
| 正文/辅助 | 10pt | 全局默认、引擎名称、说明文字、状态、标签、浮窗、列表项 |

---

## 详细对照

### 21pt — Hero

| 位置 | 文件 | 行 |
|------|------|----|
| #stat-value | styles.py | 189 |

### 16pt — 标题

| 位置 | 文件 | 行 |
|------|------|----|
| 侧边栏 Logo "VoiceType" | settings.py | 120 |
| 页面标题 ×4 (使用统计/历史记录/自定义词典/设置) | settings.py | 199, 308, 388, 527 |

### 10pt — 正文/辅助

| 位置 | 文件 | 行 |
|------|------|----|
| 全局 QWidget | styles.py | 8 |
| QGroupBox::title | styles.py | 122 |
| QLabel#subtitle | styles.py | 169 |
| QLabel#status | styles.py | 173 |
| QLabel#error | styles.py | 177 |
| QLabel#stat-label | styles.py | 194 |
| QToolTip | styles.py | 235 |
| QLabel#transcript (浮窗) | styles.py | 248 |
| 浮窗文字标签 (内联) | overlay.py | 109 |
| 首页引擎名称 | settings.py | 232 |
| 版本号标签 | settings.py | 125 |
| 引擎状态标签 | settings.py | 156 |
| 统计单位标签 | settings.py | 259 |
| 历史记录列表项 QListWidget::item | settings.py | 329 |
| 词典列表项 QListWidget::item | settings.py | 404 |

---

## 规则

- 所有字号统一使用 `pt` 单位，不再使用 `px`
- 全局 QSS 控制公共组件，内联 setStyleSheet 控制特例
- 新增 UI 元素从 3 个层级中选择，不引入新字号
