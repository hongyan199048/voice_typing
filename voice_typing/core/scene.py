"""智能润色：按当前窗口判断使用场景，给润色提示词追加对应的格式要求。

场景只在本地用来挑格式要求，窗口标题不会发给大模型。
"""

# ponytail: 关键词子串匹配，认不出的软件走「其他」（不追加要求）；要更准再加设置页自定义映射
# 浏览器靠窗口标题分辨网站，其它软件只看 WM_CLASS
_BROWSERS = ("google-chrome", "chromium", "firefox", "microsoft-edge", "brave", "opera", "vivaldi")

_BY_CLASS = (
    ("terminal", ("gnome-terminal", "terminator", "konsole", "kitty", "alacritty", "xfce4-terminal",
                  "tilix", "xterm", "urxvt", "wezterm", "lxterminal", "mate-terminal",
                  "deepin-terminal", "qterminal", "guake", "tilda")),
    ("code", ("code", "cursor", "jetbrains", "sublime_text", "zed")),
    ("chat", ("feishu", "lark", "wechat", "weixin", "qq", "dingtalk", "telegram", "slack",
              "discord", "element", "signal", "skype", "teams")),
    ("email", ("thunderbird", "evolution", "geary", "mailspring", "betterbird")),
    ("doc", ("libreoffice", "wps", "obsidian", "typora", "notion", "joplin", "logseq",
             "gedit", "gnome-text-editor", "xed", "marktext")),
)

_BY_TITLE = (
    ("email", ("gmail", "outlook", "邮箱", "邮件", "mail")),
    ("code", ("chatgpt", "claude", "deepseek", "gemini", "kimi", "豆包", "通义", "github")),
    ("doc", ("notion", "文档", "docs", "语雀", "石墨", "confluence", "wiki")),  # 先于聊天：「飞书云文档」
    ("chat", ("微信", "飞书", "钉钉", "telegram", "slack", "discord", "whatsapp")),
)

SCENE_STYLE = {
    "chat": ("当前在聊天软件里发消息：保持口语化的短句，语气自然随意；"
             "不要编号列表、不要分段、不要使用 ** 等 Markdown 符号。"),
    "email": ("当前在写邮件：书面、礼貌、条理清楚，按意思分段；内容有几个并列要点或步骤时，"
              "每条单独一行，排成「1. 2. 3.」编号列表；保留原文的称呼与结尾，"
              "不要自行添加称呼、落款或客套话；不要使用 ** 等 Markdown 符号。"),
    "doc": ("当前在写文档 / 笔记：可以整理得更有条理——内容有几个并列要点或步骤时，"
            "即使说话人没说「第一、第二」，也排成「1. 2. 3.」编号列表，按主题分段；"
            "不要使用 ** 加粗。"),
    "code": ("当前在写代码或给 AI 助手提需求：英文术语、代码标识符、文件名、命令保持原样不翻译；"
             "要点多时可以排成编号列表，让需求清晰明确。"),
    "terminal": "当前在终端里：只输出一行，不分段，句末不加句号。",
}


def detect_scene(wm_class: str, title: str) -> str:
    """WM_CLASS + 窗口标题 → chat / email / doc / code / terminal / other"""
    wm_class, title = wm_class.lower(), title.lower()
    if any(b in wm_class for b in _BROWSERS):
        table, text = _BY_TITLE, title
    else:
        table, text = _BY_CLASS, wm_class
    for scene, keys in table:
        if any(k in text for k in keys):
            return scene
    return "other"


def scene_hint(scene: str) -> str:
    """追加到润色提示词末尾的格式要求；其他场景返回空串（照常润色）"""
    style = SCENE_STYLE.get(scene)
    return (f"\n\n## 输出格式（按当前使用的软件，优先于上文关于列表和分段的规定；"
            f"仍不得改变原意、不得增删内容）\n{style}") if style else ""
