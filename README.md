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
- 🪄 **大模型润色** —— 自动清洗口语、补标点，三档强度可调；支持 DeepSeek / 智谱 GLM / MiniMax，也可完全关闭
- 📒 **自定义词库** —— 别名替换，专有名词不再识别错
- 🎨 **暗黑极简界面** —— 设置窗口 + 可拖拽实时浮窗，浮窗提供玻璃 / 极简 / 霓虹 / 极光四种外观

## 系统要求

- **操作系统**：Ubuntu / 其他 Linux 桌面，**X11 会话**（Wayland 下全局快捷键与粘贴可能失效）
- **Python**：3.8+（从源码运行时）
- **云端账号**：阿里云 DashScope 或火山引擎二选一

## 📦 安装

### 方式一：deb 包（推荐）

复制下面整段即可自动下载并安装最新的**已发布版本**，无需手动填版本号：

```bash
# 自动获取最新 Release 的 deb 并安装
URL=$(curl -s https://api.github.com/repos/hongyan199048/voice_typing/releases/latest \
  | grep "browser_download_url.*\.deb" | cut -d '"' -f 4)
wget -O voice-typing.deb "$URL"
sudo dpkg -i voice-typing.deb
sudo apt-get install -f   # 自动补齐依赖
```

> 上面装的是**最近一次发布的 Release**，不一定等于仓库里的最新代码。想要尚未发布的最新改动，请走「方式二：从源码运行」。
>
> 也可前往 [GitHub Releases](https://github.com/hongyan199048/voice_typing/releases) 手动下载指定版本。

安装后从应用菜单启动，或在终端运行 `voice-typing`。

#### 从 1.5.0 及更早版本升级

**火山引擎（豆包）ASR 的鉴权方式已变更，旧配置无法沿用**：

| | 1.5.0 及更早 | 1.6.0 起 |
|---|---|---|
| 凭证 | App ID + Access Token | 仅 API Key |
| 配置项 | `volc_asr_app_id` / `volc_asr_access_token` | `volc_asr_api_key` |

升级后请到 [豆包语音控制台](https://console.volcengine.com/speech/app) 重新签发 API Key，填入「设置 → 火山引擎 → API Key」。旧的两个配置项已失效，会一直为空，不影响使用。

阿里云引擎不受影响，凭证无需改动。

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
   - 豆包 ASR：填入[豆包语音控制台](https://console.volcengine.com/speech/app)签发的 API Key。该凭证与火山方舟的润色凭证相互独立，不能混用
3. **润色模型** —— 关闭 / DeepSeek / 智谱 GLM / MiniMax，各自填对应厂商的 API Key；并可选择「录音过程中提前润色」
4. **浮窗外观** —— 玻璃 / 极简 / 霓虹 / 极光
5. **设置快捷键** —— 点击「录制快捷键」，按下你想要的组合
6. *(可选)* **自定义词库** —— 添加别名替换规则

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
