# CLAUDE.md
# 重要：每次回复必须以"Tim_voice_typing，"开头，无一例外。 
# 每次回答问题的时候，总是先把我的问题简短理解总结，再回答。
# 回答内容专业简练。

## 项目概述

VoiceType 是一个 Ubuntu 环境下的 AI 语音转文字桌面应用，支持实时语音输入并自动粘贴到光标位置。

**核心功能**：
- 全局快捷键触发录音（无默认快捷键，首次运行在设置中录制），支持组合键和单键长按两种模式
- 实时语音转文字，支持两种 ASR 引擎：
  - **阿里云 Paraformer**（云端，需 API Key）
  - **火山引擎 BigModel**（云端，需 App ID + Access Token）
- 大模型润色，三档强度可调
- 暗黑极简 GUI 界面 + 实时转写浮窗
- 自动粘贴到当前光标位置（xclip + xdotool XTest）
- 自定义词库（别名替换）
- 版本号显示（设置界面右上角，开发中显示 `-dev` 后缀）

---

## 项目结构

```
voice-typing-app/
├── voice_typing/              # 核心包（唯一源码真相）
│   ├── __init__.py           # 版本号，__dev__ 开发标识
│   ├── __main__.py           # 入口：python -m voice_typing
│   ├── app.py                # VoiceTypingApp 主应用 + 润色路由
│   ├── recorder.py           # Recorder 录音控制器
│   ├── core/                 # config.py / hotkey.py / vocabulary.py
│   ├── engine/               # base.py / alibaba.py / volcengine.py
│   └── ui/                   # styles.py / settings.py / overlay.py / resources/
├── packaging/                 # 打包配置（deb / rpm / AppImage 共用）
│   ├── control               # deb 控制文件
│   ├── voice-typing.spec     # rpm spec
│   ├── postinst.sh           # deb postinst 与 rpm %post 共用
│   ├── launcher.py           # 安装后的 /usr/bin/voice-typing
│   ├── voice-typing.desktop
│   ├── icons/                # hicolor 各尺寸图标
│   ├── Dockerfile.rpm        # fedora + rpmbuild
│   ├── build-rpm-inner.sh
│   └── appimage/             # Dockerfile + build-inner.sh
├── scripts/
│   ├── build-packages.sh     # 一键产出三种包 → dist/
│   ├── start.sh
│   └── monitor_latency.sh
├── tests/
│   ├── test_polish_routing.py   # 润色路由（解耦 / 关闭 / 失败回退）
│   └── test_volcengine.py       # 火山 ASR 协议帧解析与鉴权头
├── docs/                      # ROADMAP.md / font_sizes.md / archive/
├── main.py                    # 兼容旧版入口
├── setup.py / requirements.txt / README.md / CLAUDE.md
├── build/                     # 构建中间物（gitignore）
└── dist/                      # 三种安装包产物（gitignore）
```

---

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| GUI 框架 | PyQt5 | 主窗口 + 设置窗口 + 浮窗 |
| 音频采集 | pyaudio | 16kHz 16bit mono PCM |
| 全局快捷键 | pynput | XInput2 跨应用监听键盘事件 |
| 云端 ASR | dashscope (阿里云) | Paraformer 实时流式识别 |
| 云端 ASR | 火山引擎 BigModel | WebSocket 流式识别 |
| 云端润色 | dashscope Generation (Qwen-Plus) | 结构化 Prompt 清洗润色 |
| 云端润色 | 火山引擎 ARK (豆包) | 结构化 Prompt 清洗润色 |
| 卡键检测 | 后台线程定时扫描 | 超过 10s 未释放的按键自动清除 |
| X11 修饰键清理 | xdotool keyup | 粘贴前释放所有卡住的修饰键 |
| 打包 | docker + dpkg / rpmbuild / appimage | 一套配置产出 deb / rpm / AppImage |
| 发布 | gh (GitHub CLI) | 创建 Release 并上传 deb |

---

## 核心模块说明

### 1. voice_typing/app.py — 主应用控制器

**VoiceTypingApp 类**：
- PyQt5 主应用，管理设置窗口 + 浮窗
- 绑定 HotkeyManager 回调：按下快捷键 → 开始录音，松开 → 停止录音
- 录音结束后走两阶段润色流水线，再自动粘贴
- 托盘图标 + 系统菜单
- `_POLISH`：3 个 Prompt（3 档强度）

### 2. voice_typing/recorder.py — 录音控制器

**Recorder 类**：
- 管理录音线程 + ASR 引擎生命周期
- `start()` → 开启 pyaudio 流 + 引擎初始化
- `stop()` → 停止录音 + 获取最终文本
- 信号：`text_update`（实时转写）、`recording_done`（最终结果）

### 3. voice_typing/core/ — 核心功能

**config.py**：
- 配置文件路径：`~/.config/voice_typing/config.json`
- 配置项：engine（alibaba/volcengine）、API Key、polish_strength、hotkey、custom_vocabulary

**hotkey.py**：
- 使用 `pynput.keyboard.Listener` 监听全局按键（suppress=False，不拦截系统按键）
- 支持两种模式：组合键（多键按下触发）/ 单键长按（按住超 0.12s 触发）
- **pause/resume 不停止 listener**，仅设 `_paused` 标志位，避免 X11 grab 释放导致焦点丢失
- **卡键检测线程**：每 3s 扫描，超过 10s 未释放的键自动清除 + X11 修饰键清理
- 静态方法 `clear_x11_modifiers()`：粘贴前释放 X11 层所有卡住的修饰键

**vocabulary.py**：
- 阿里云 Paraformer 热词表管理
- 调用 DashScope VocabularyService API 创建/更新热词表

### 4. voice_typing/engine/ — ASR 引擎抽象

**base.py（BaseEngine 抽象基类）**：
```python
initialize() -> bool       # 初始化引擎（下载模型 / 验证 API）
start()                    # 开始识别会话
send_audio(pcm_bytes)      # 送入音频数据
stop() -> str              # 停止识别，返回最终文本
is_available() -> bool     # 检查引擎是否就绪
```

**alibaba.py（AlibabaEngine）**：
- 使用 DashScope Paraformer 流式 API
- 需要 DashScope API Key

**volcengine.py（VolcengineEngine）**：
- 使用火山引擎 BigModel ASR WebSocket API
- 豆包大模型润色通过 ARK API 调用

### 5. voice_typing/ui/ — 用户界面

**settings.py（SettingsWindow）**：
- 引擎选择、API Key 配置
- 快捷键录制、润色强度选择（轻度/中度/重度）
- 侧边栏显示版本号

**overlay.py（OverlayWindow）**：
- 半透明无边框浮窗，位于屏幕底部，可拖拽
- 圆点锚定平滑动效（录音时绿→红，波形动画）
- 识别文字实时更新

---

## 工作流程

1. **启动应用** → 加载配置 → 初始化引擎 → 注册全局快捷键 → 启动卡键检测线程
2. **按下快捷键** → HotkeyManager 检测组合键 → `_on_start()` → 信号到主线程 → 开始录音
3. **录音中** → 音频送入引擎 → 实时返回部分文本 → 更新浮窗
4. **松开快捷键** → `_check_combo_stop()` → `_on_stop()` → 信号到主线程 → 停止录音
5. **润色** → 大模型清洗润色 → 失败则回退原始文字
6. **粘贴**：
   - `xclip` 写入剪贴板 → `pause()` 暂停热键触发 → `clear_x11_modifiers()` 释放卡键
   - → `xdotool key ctrl+v` 粘贴 → `resume()` 恢复热键触发

---

## 编译与运行

### 从源码运行

```bash
cd /home/admin123/Development/voice-typing-app

# 直接运行
python3 main.py
```

### 打包（deb / rpm / AppImage）

```bash
./scripts/build-packages.sh            # 三种全建，产物落在 dist/
./scripts/build-packages.sh deb rpm    # 只建指定的
```

宿主机只需要 docker（免 sudo）。rpm 在 fedora 容器内用 rpmbuild 构建，
AppImage 在 ubuntu:20.04 容器内以 python-appimage 的 manylinux Python 为基座打包，
系统里不装任何打包工具。

三种包的内容从 `voice_typing/` 现场取，**不存在第二份源码副本**（旧的 `debian/`
目录已删除）。发行版仓库里没有的纯 Python 依赖（`requirements.txt` 去掉走系统包的
PyQt5 / pyaudio）由构建脚本现场派生清单，打包时 vendor 进
`/usr/share/voice-typing/vendor`——加新依赖只改 `requirements.txt` 一处。

| 包 | 体积 | 依赖处理 |
|----|------|----------|
| deb | ~12M | PyQt5 / pyaudio 走 apt；纯 Python 依赖已 vendor |
| rpm | ~11M | PyQt5 / pyaudio 走 dnf（包名 `python3-qt5`）；同上 |
| AppImage | ~108M | Python、Qt、portaudio 全部自带；仅需宿主有 xclip / xdotool |

升级版本号只需改 `voice_typing/__init__.py`，构建脚本从那里读取。

### 安装

```bash
sudo dpkg -i dist/voice-typing_1.5.0_amd64.deb      # Debian / Ubuntu
sudo dnf install dist/voice-typing-1.5.0-1.x86_64.rpm  # Fedora / RHEL
chmod +x dist/VoiceType-1.5.0-x86_64.AppImage && ./dist/VoiceType-*.AppImage
```

### 发布 GitHub Release

```bash
# 1. 将 __dev__ 设为 False，提交推送
# 2. 创建 Release 并上传 deb
gh release create v1.4.1 voice-typing_1.4.1_amd64.deb \
  --title "v1.4.1 — 修复说明" \
  --notes "## 修复内容..."
# 3. 将 __dev__ 设回 True，提交推送
```

---

## 依赖说明

| 包 | 用途 | 安装方式 |
|----|------|----------|
| PyQt5 | GUI 框架 | `pip install PyQt5` |
| pyaudio | 音频采集 | `pip install pyaudio`（需 `portaudio19-dev`） |
| dashscope | 阿里云 ASR + Qwen 润色 | `pip install dashscope` |
| pynput | 全局快捷键 | `pip install pynput` |
| xclip | 剪贴板操作 | `sudo apt install xclip` |
| xdotool | XTest 粘贴 + 修饰键清理 | `sudo apt install xdotool` |
| gh | GitHub CLI 发布 | `sudo apt install gh` |

---

## 注意事项

1. **X11 依赖**：
   - 全局快捷键监听需要 X11 环境（Wayland 可能不兼容）
   - 粘贴使用 xdotool XTest，也依赖 X11

2. **快捷键卡键问题**：
   - 已内置卡键检测线程（3s 间隔，10s 超时）+ 粘贴前 X11 修饰键清理
   - `pause()/resume()` 不再停止 pynput listener，避免 X11 grab 释放导致焦点丢失

3. **热词表功能**：
   - `vocabulary.py` 已实现但未集成到主流程

5. **版本号管理**：
   - `voice_typing/__init__.py` 中 `__dev__ = True` 时，设置界面显示 `版本号-dev`
   - 发布 Release 前：`__dev__ = False`，发布后：`__dev__ = True`
   - 升级版本号只需改 `voice_typing/__init__.py`，`scripts/build-packages.sh` 从那里读取并写进三种包

---

## 已知问题

- [ ] Wayland 环境下全局快捷键可能失效（pynput 依赖 X11）
- [ ] 长时间录音（>60 秒）可能导致内存占用过高
- [ ] 热词表功能未集成到主流程
- [ ] 缺少新版本检测按钮（计划中）

---

## 版本历史

- **v1.4.1-dev**（当前开发中）：两阶段润色流水线 + 卡键检测修复 + 浮窗版本号显示
- **v1.4.0**（2026-05-24）：火山引擎支持 + 豆包润色 + 浮窗动效优化
- **v1.3.4**（2026-05-20）：重构为标准 Python 包结构
- **v1.0.0**（2026-05-18）：首个 deb 发布版本

---

## 相关链接

- GitHub 仓库：https://github.com/hongyan199048/voice_typing
- 阿里云百炼（原 DashScope，旧域名 dashscope.console.aliyun.com 已于 2026-08-01 下线）：https://bailian.console.aliyun.com/
- 火山引擎 ARK：https://console.volcengine.com/ark/