# VoiceType · AI 语音输入工具

[![Release](https://img.shields.io/github/v/release/hongyan199048/voice_typing)](https://github.com/hongyan199048/voice_typing/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](#-许可)
[![Platform](https://img.shields.io/badge/platform-Linux%20%2F%20X11-orange)](#系统要求)

> Linux 桌面下的实时 AI 语音转文字工具。按住快捷键说话，松开即把识别并润色后的文字自动粘贴到光标处——在任何能输入文字的地方都能用。

<!-- 可选：在此放一张 GIF 演示，效果远胜千言。 -->

## ✨ 功能特性

| | |
|---|---|
| 🎤 **实时转写** | 说话时屏幕底部浮窗同步显示识别结果 |
| ⌨️ **自动粘贴** | 松开快捷键，文字直接落到当前光标位置，不限应用 |
| 🔥 **全局快捷键** | 支持「组合键」与「单键长按」两种触发模式（默认 `Ctrl+Alt+V`） |
| ☁️ **双云端引擎** | 阿里云 Paraformer / 豆包流式语音识别 2.0，任选其一 |
| 🪄 **大模型润色** | 自动清洗口语、补标点，三档强度可调；可选 DeepSeek / 智谱 GLM / MiniMax，也可完全关闭 |
| 📒 **自定义词库** | 别名替换 + 云端热词表，专有名词不再识别错 |
| 🎨 **浮窗四种外观** | 玻璃 / 极简 / 霓虹 / 极光，设置里实时切换 |
| 📊 **历史与统计** | 保留最近 100 条识别记录，统计累计时长与字数 |
| 🚀 **托盘常驻** | 支持开机自启，静默启动只显示托盘图标 |

## 系统要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Linux 桌面，**X11 会话**（Wayland 下全局快捷键与粘贴会失效） |
| Python | **3.10+**（从源码运行 / deb / rpm 时。AppImage 自带 Python，无此要求） |
| 系统命令 | `xclip`、`xdotool`（粘贴与修饰键清理依赖） |
| 云端账号 | 阿里云 DashScope 或火山引擎，二选一 |

> 确认当前会话类型：`echo $XDG_SESSION_TYPE`，输出应为 `x11`。

## 📦 安装

提供三种安装包，按需选一种：

| 包格式 | 适用发行版 | 体积 | 依赖处理 |
|---|---|---|---|
| **AppImage** | 任意 Linux | ~108M | Python、Qt、PortAudio 全部自带，宿主只需 `xclip` / `xdotool` |
| **deb** | Debian / Ubuntu | ~12M | PyQt5、PyAudio 走 apt，其余 Python 依赖已打包在内 |
| **rpm** | Fedora / RHEL | ~11M | PyQt5、PyAudio 走 dnf，其余 Python 依赖已打包在内 |

拿不定主意就用 **AppImage**：下载、加执行权限、双击，不装任何东西到系统里。

### AppImage（免安装）

```bash
URL=$(curl -s https://api.github.com/repos/hongyan199048/voice_typing/releases/latest \
  | grep "browser_download_url.*\.AppImage" | cut -d '"' -f 4)
wget -O VoiceType.AppImage "$URL"
chmod +x VoiceType.AppImage
./VoiceType.AppImage
```

### deb（Debian / Ubuntu）

```bash
URL=$(curl -s https://api.github.com/repos/hongyan199048/voice_typing/releases/latest \
  | grep "browser_download_url.*\.deb" | cut -d '"' -f 4)
wget -O voice-typing.deb "$URL"
sudo dpkg -i voice-typing.deb
sudo apt-get install -f   # 自动补齐依赖
```

### rpm（Fedora / RHEL）

```bash
URL=$(curl -s https://api.github.com/repos/hongyan199048/voice_typing/releases/latest \
  | grep "browser_download_url.*\.rpm" | cut -d '"' -f 4)
wget -O voice-typing.rpm "$URL"
sudo dnf install ./voice-typing.rpm
```

deb / rpm 安装后从应用菜单启动，或在终端运行 `voice-typing`。

> 上面装的都是**最近一次发布的 Release**，不一定等于仓库里的最新代码。想要尚未发布的改动请走「从源码运行」。
> 也可前往 [GitHub Releases](https://github.com/hongyan199048/voice_typing/releases) 手动下载指定版本。

### 从源码运行

```bash
sudo apt install xclip xdotool portaudio19-dev     # 系统依赖

git clone https://github.com/hongyan199048/voice_typing.git
cd voice_typing
pip install -r requirements.txt

python3 main.py        # 或：python3 -m voice_typing
```

### ⚠️ 从 v1.5.0 及更早版本升级

**火山引擎（豆包）ASR 的鉴权方式已变更，旧配置无法沿用：**

| | v1.5.0 及更早 | v1.6.0 起 |
|---|---|---|
| 凭证 | App ID + Access Token | 仅 API Key |
| 配置项 | `volc_asr_app_id` / `volc_asr_access_token` | `volc_asr_api_key` |

升级后请到 [豆包语音控制台](https://console.volcengine.com/speech/app) 重新签发 API Key，填入「设置 → 火山引擎 → API Key」。旧的两个配置项已失效，留空不影响使用。**阿里云引擎不受影响**，凭证无需改动。

## 🚀 使用

### 首次配置

首次运行会打开设置窗口，左侧四个页面：**主界面 / 历史记录 / 词典 / 设置**。到「设置」页依次配置：

1. **选择引擎** —— 阿里云 Paraformer 或豆包流式语音识别 2.0
2. **填入凭证**（见下方[凭证说明](#凭证说明)）
3. **润色模型** —— 关闭 / DeepSeek / 智谱 GLM / MiniMax，各自填对应厂商的 Key
4. **润色强度** —— 轻度 / 中度（推荐）/ 重度
5. **快捷键** —— 点击「点击设置快捷键」，按下想要的组合键或单键
6. *(可选)* **浮窗外观**、**开机自启**、**词典**

左下角的状态灯显示「引擎就绪 / 未就绪」，配好了就是绿的。

### 语音输入

1. 按住快捷键开始录音，浮窗圆点由绿转红
2. 浮窗实时显示转写内容
3. 松开快捷键 → 大模型润色 → 文字自动粘贴到光标位置

出错时浮窗会显示一行红色提示（如「识别失败，请检查网络和 API Key」），2.5 秒后自动消失，不会粘贴任何内容。

### 命令行参数

```bash
voice-typing --minimized     # 静默启动，只显示托盘图标（开机自启用）
voice-typing --hidden        # 同上
```

## 🎛️ 配置说明

### 凭证说明

| 引擎 | 需要填 | 去哪申请 |
|---|---|---|
| 阿里云 Paraformer | DashScope API Key | [DashScope 控制台](https://dashscope.console.aliyun.com/) |
| 豆包流式语音识别 2.0 | API Key | [豆包语音控制台](https://console.volcengine.com/speech/app) |

> **ASR 凭证与润色凭证相互独立，不能混用。** 豆包语音控制台签发的 Key 只能用于 ASR；润色用的 DeepSeek / GLM / MiniMax 各有各的 Key。

润色模型的 Key 分别在 [DeepSeek](https://platform.deepseek.com/api_keys)、[智谱开放平台](https://open.bigmodel.cn/usercenter/apikeys)、[MiniMax](https://platform.minimaxi.com/user-center/basic-information/interface-key) 申请。**润色可以完全关闭**，此时直接输出 ASR 原文。

### 豆包资源档位

设置里可选四档，按你在控制台开通的套餐选：

- `2.0 小时版` / `2.0 并发版` —— 推荐，识别质量更好
- `1.0 小时版` / `1.0 并发版` —— 兼容旧应用

### 词典

「词典」页可为每个词条填**正词**和**别名**（多个别名用逗号分隔）。两个引擎的生效方式不同：

| 引擎 | 词典怎么起作用 |
|---|---|
| 阿里云 Paraformer | 保存设置时，词条自动同步为 DashScope 云端热词表 |
| 豆包 | 别名 → 正词作为内联纠错随请求下发；另可在设置里填控制台创建的「热词表 ID」做识别偏置 |

豆包的热词表需要自行到[语音控制台](https://console.volcengine.com/speech/app)创建，把 ID 填进设置即可，留空则不启用。

### 提前润色

「录音过程中提前润色」开启后，说话途中就开始流式润色，松手时若已完成可立刻粘贴。默认关闭。

## 🔧 故障排查

| 现象 | 排查方向 |
|---|---|
| 快捷键无响应 | 是否与系统快捷键冲突；换个组合键；确认 `echo $XDG_SESSION_TYPE` 输出 `x11` |
| 浮窗变红但没有文字 | 看浮窗上的红色提示；多为网络不通或 API Key 有误 |
| 录音无声音 | 检查麦克风权限；`arecord -l` 确认设备存在 |
| 粘贴失败 | 确认已装 `xclip` 与 `xdotool`；确认处于 X11 会话 |
| 使用代理 / VPN 后识别超时 | 系统从睡眠唤醒后代理链路可能未恢复，重连代理再试 |

### 抓日志

从应用菜单启动时，程序输出进了 journald，界面上看不到。排查时请从终端启动：

```bash
python3 -u /usr/bin/voice-typing      # deb / rpm 安装
python3 -u main.py                    # 源码运行
```

**`-u` 不能省** —— Python 输出重定向时是块缓冲的，不加这个参数日志会卡在缓冲区里看不到。

## 🛠️ 从源码打包

宿主机只需要 docker（免 sudo），不往系统里装任何打包工具：

```bash
./scripts/build-packages.sh            # 三种包全建，产物落在 dist/
./scripts/build-packages.sh deb rpm    # 只建指定的
```

rpm 在 fedora 容器内用 rpmbuild 构建，AppImage 在 ubuntu:20.04 容器内以 python-appimage 的 manylinux Python 为基座打包。三种包的内容都从 `voice_typing/` 现场取，不存在第二份源码副本。升级版本号只需改 `voice_typing/__init__.py`，构建脚本从那里读。

跑测试：

```bash
python3 -m pytest tests/ -q
```

## ⚙️ 配置文件

```
~/.config/voice_typing/config.json
```

主要字段：

| 字段 | 说明 |
|---|---|
| `engine` | `alibaba` / `volcengine` |
| `alibaba_api_key` | 阿里云 DashScope Key（ASR 用） |
| `volc_asr_api_key` | 豆包语音控制台 Key（ASR 用） |
| `volc_asr_resource_id` | 豆包资源档位 |
| `polish_provider` | `off` / `deepseek` / `glm` / `minimax` |
| `polish_strength` | `light` / `medium` / `strong` |
| `realtime_polish` | 是否录音过程中提前润色 |
| `hotkey` | 快捷键，如 `["ctrl","alt","v"]` |
| `overlay_style` | `glass` / `minimal` / `neon` / `aurora` |
| `custom_vocabulary` | 词库 `[{"term":"CUDA","alias":"库达"}]` |
| `history` | 最近 100 条识别记录 |

删掉该文件即可恢复默认配置。

## 📄 许可

[MIT License](LICENSE)

## 🔗 相关链接

- 阿里云 DashScope 控制台：<https://dashscope.console.aliyun.com/>
- 豆包语音控制台：<https://console.volcengine.com/speech/app>
- 火山方舟控制台：<https://console.volcengine.com/ark/>
