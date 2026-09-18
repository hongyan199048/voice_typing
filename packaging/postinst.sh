#!/bin/bash
# deb postinst / rpm %post 共用。Python 依赖已 vendor 进包，这里不再 pip 装任何东西。
set -e

# 清理旧版残留的 pycache，确保加载新代码
find /usr/share/voice-typing -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 刷新图标缓存，让启动器/dock 拾取图标
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database -q /usr/share/applications 2>/dev/null || true

# uinput udev 规则：pynput 模拟键盘需要访问 /dev/uinput（Electron/Chromium 类应用必需）
RULE=/etc/udev/rules.d/99-voice-typing-uinput.rules
if [ ! -f "$RULE" ]; then
    echo 'KERNEL=="uinput", MODE="0660", GROUP="plugdev"' > "$RULE"
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger --subsystem-match=misc 2>/dev/null || true
    echo "已写入 uinput 权限规则，首次安装请注销重新登录使其生效。"
fi

echo "VoiceType 安装完成，命令行输入 voice-typing 启动。"
