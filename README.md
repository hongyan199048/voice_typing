# VoiceType · AI 语音输入工具

[![Release](https://img.shields.io/github/v/release/hongyan199048/voice_typing)](https://github.com/hongyan199048/voice_typing/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Linux 桌面下的 AI 语音转文字工具。按住快捷键说话，松开即把识别并润色后的文字自动粘贴到光标处——在任何能打字的地方都能用。

## ✨ 能做什么

- 🎤 **实时转写**：说话时屏幕底部浮窗同步显示识别结果
- ⌨️ **自动粘贴**：松开快捷键，文字直接落到当前光标位置，不限应用
- 🔥 **全局快捷键**：支持组合键与单键长按两种触发方式（默认 `Ctrl+Alt+V`）
- ☁️ **云端识别**：阿里云 Paraformer / 豆包流式语音识别，任选其一
- 🪄 **AI 润色**：自动去口语、补标点，强度可调，也可完全关闭

## 📦 安装

推荐 **AppImage**：下载、加执行权限、运行即可，不装任何东西到系统里。

```bash
# 一行下载 + 运行（Debian/Ubuntu 之外的发行版通用）
URL=$(curl -s https://api.github.com/repos/hongyan199048/voice_typing/releases/latest \
  | grep "browser_download_url.*\.AppImage" | cut -d '"' -f 4)
wget -O VoiceType.AppImage "$URL" && chmod +x VoiceType.AppImage && ./VoiceType.AppImage
```

**Debian / Ubuntu**（一条命令装好，依赖自动补齐）：

```bash
URL=$(curl -s https://api.github.com/repos/hongyan199048/voice_typing/releases/latest \
  | grep "browser_download_url.*_amd64\.deb" | cut -d '"' -f 4)
wget -O voice-typing.deb "$URL" && sudo dpkg -i voice-typing.deb && sudo apt-get install -f
```

**Fedora / RHEL**：

```bash
URL=$(curl -s https://api.github.com/repos/hongyan199048/voice_typing/releases/latest \
  | grep "browser_download_url.*\.rpm" | cut -d '"' -f 4)
wget -O voice-typing.rpm "$URL" && sudo dnf install ./voice-typing.rpm
```

> 也可到 [GitHub Releases](https://github.com/hongyan199048/voice_typing/releases) 手动下载最新版。

## 🚀 使用

**首次配置**（首次运行会打开设置窗口）：

1. 选引擎：阿里云 Paraformer 或豆包，填入对应的 API Key
2. 可选：选润色模型、调润色强度
3. 设快捷键：点「点击设置快捷键」，按下想要的组合键或单键

**语音输入**：按住快捷键开始说话，松开后自动润色并粘贴到光标处。出错时浮窗会显示一行红色提示，不会粘贴任何内容。

## 🔑 去哪申请 API Key

| 引擎 | 申请地址 |
|---|---|
| 阿里云 Paraformer | [阿里云百炼控制台](https://bailian.console.aliyun.com/) —— 登录后鼠标移到右上角头像 → 「API-KEY 管理」 |
| 豆包流式语音识别 | [豆包语音控制台 → API Key](https://console.volcengine.com/speech/new/setting/apikeys) |

> 豆包首次使用要先在控制台左侧「开通管理」里**开通语音识别模型**，否则拿到 Key 也会调用失败。
> 请认准地址里的 `/speech/new/`。旧的 `/speech/app` 是另一套鉴权（App ID + Access Token），本程序用不了。

润色模型（DeepSeek / 智谱 GLM / MiniMax）各自另有 Key，也可**完全关闭**，关闭时直接输出识别原文。

## ⚠️ 注意

- 需要 **X11 桌面**。在终端运行 `echo $XDG_SESSION_TYPE`，输出应为 `x11`；Wayland 下快捷键和粘贴会失效。
- AppImage 版需系统已装 `xclip` 和 `xdotool`（deb / rpm 会自动带上）：`sudo apt install xclip xdotool`。

## 📄 许可

[MIT License](LICENSE)
