# VoiceType · AI 语音输入工具

[![Release](https://img.shields.io/github/v/release/hongyan199048/voice_typing)](https://github.com/hongyan199048/voice_typing/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](#许可)
[![Platform](https://img.shields.io/badge/platform-Ubuntu%20%2F%20X11-orange)](#系统要求)

> Ubuntu 桌面下的实时 AI 语音转文字工具。按住快捷键说话，松开即把识别并润色后的文字自动粘贴到光标处。

<!-- 可选：在此放一张 GIF 演示，效果远胜千言。 -->

## ✨ 功能特性

- 🎤 **实时语音转写** —— 说话时屏幕底部浮窗同步显示
- ⌨️ **自动粘贴** —— 松开快捷键，文字直接落到当前光标位置
- 🔥 **全局快捷键** —— 支持「组合键」与「单键长按」两种触发模式（默认 `Ctrl+Alt+V`）
- ☁️ **双云端引擎** —— 阿里云 Paraformer / 豆包流式语音识别 2.0，任选其一
- 🪄 **大模型润色** —— 自动清洗口语、补标点，三档强度可调（Qwen-Plus / 豆包）
- 📒 **自定义词库** —— 别名替换，专有名词不再识别错
- 🎨 **暗黑极简界面** —— 设置窗口 + 可拖拽实时浮窗

## 系统要求

- **操作系统**：Ubuntu / 其他 Linux 桌面，**X11 会话**（Wayland 下全局快捷键与粘贴可能失效）
- **Python**：3.8+（从源码运行时）
- **云端账号**：阿里云 DashScope 或火山引擎二选一

## 📦 安装

### 方式一：deb 包（推荐）

复制下面整段即可自动下载并安装**最新版**，无需手动填版本号：

```bash
# 自动获取最新 Release 的 deb 并安装
URL=$(curl -s https://api.github.com/repos/hongyan199048/voice_typing/releases/latest \
  | grep "browser_download_url.*\.deb" | cut -d '"' -f 4)
wget -O voice-typing.deb "$URL"
sudo dpkg -i voice-typing.deb
sudo apt-get install -f   # 自动补齐依赖
```

> 也可前往 [GitHub Releases](https://github.com/hongyan199048/voice_typing/releases) 手动下载指定版本。

安装后从应用菜单启动，或在终端运行 `voice-typing`。

### 方式二：从源码运行

```bash
# 系统依赖
sudo apt install xclip xdotool portaudio19-dev

# 拉取代码并安装 Python 依赖
git clone https://github.com/hongyan199048/voice_typing.git
cd voice_typing
pip install -r requirements.txt

# 启动
python main.py        # 或：python -m voice_typing
```

## 🚀 使用

首次运行会打开设置窗口：

1. **选择引擎** —— 阿里云 Paraformer 或豆包流式语音识别 2.0
2. **配置凭证**
   - 阿里云：填入 [DashScope API Key](https://dashscope.console.aliyun.com/)
   - 豆包 ASR：新版豆包语音控制台填 API Key；旧版控制台填 App ID + Access Token。ASR 凭证与通义千问、火山方舟润色凭证相互独立
3. **润色强度** —— 轻度 / 中度 / 重度（可关闭）
4. **设置快捷键** —— 点击「录制快捷键」，按下你想要的组合
5. *(可选)* **自定义词库** —— 添加别名替换规则

**语音输入流程**：

1. 按住快捷键开始录音
2. 屏幕底部浮窗实时显示转写内容
3. 松开快捷键 → 大模型润色 → 文字自动粘贴到光标位置

## 🔧 故障排查

| 现象 | 排查方向 |
|------|----------|
| 快捷键无响应 | 是否与系统快捷键冲突；尝试更换组合键；确认运行在 X11 而非 Wayland |
| 录音无声音 | 检查麦克风权限；运行 `arecord -l` 确认音频设备 |
| 粘贴失败 | 确认已安装 `xclip` 与 `xdotool`；确认处于 X11 会话 |
| 识别报错 / 无结果 | 检查 API Key 是否正确、网络是否可达对应云服务 |

## ⚙️ 配置文件

配置保存在：

```
~/.config/voice_typing/config.json
```

包含引擎选择、API 凭证、润色强度、快捷键、自定义词库等。

## 📄 许可

[MIT License](LICENSE)

## 🔗 相关链接

- 阿里云 DashScope 控制台：<https://dashscope.console.aliyun.com/>
- 豆包语音控制台：<https://console.volcengine.com/speech/app>
