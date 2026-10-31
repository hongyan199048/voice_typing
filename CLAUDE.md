# CLAUDE.md
# 重要：每次回复必须以"Tim_voice_typing，"开头，无一例外。 
# 每次回答问题的时候，总是先把我的问题简短理解总结，再回答。
# 回答内容专业简练。

## 项目概述

VoiceType 是一个 Ubuntu 环境下的 AI 语音转文字桌面应用，支持实时语音输入并自动粘贴到光标位置。

**核心功能**：
- 全局快捷键触发录音（无默认快捷键，首次运行在设置中录制），支持组合键和单键长按两种模式；触发方式可选「按住说话」或「按一下开始、再按一下结束」
- 实时语音转文字，支持两种 ASR 引擎：
  - **阿里云 Paraformer**（云端，需 API Key）
  - **火山引擎 BigModel**（云端，需 App ID + Access Token）
- 大模型润色（DeepSeek / 智谱 GLM / MiniMax，OpenAI 兼容接口），三档强度可调，可选录音中实时润色
- 浅色 GUI 界面（首页 / 历史 / 词典 / 设置四页，与浮窗同一套白底绿强调的胶囊风格；Logo 为绿色圆头表情）+ 实时转写浮窗（Grok 语音浮窗风格：表情头像 + 音量波形）
- 自动粘贴到当前光标位置（xclip + xdotool XTest）
- 自定义词库（别名替换，忽略大小写；火山引擎下全部词条作为热词直传）
- 使用统计 + 历史记录（最近 100 条）
- 版本号显示（设置界面右上角，开发中显示 `-dev` 后缀）+ 启动后自动检测新版本

---

## 项目结构

```
voice-typing-app/
├── voice_typing/              # 核心包（唯一源码真相）
│   ├── __init__.py           # 版本号，__dev__ 开发标识
│   ├── __main__.py           # 入口：python -m voice_typing
│   ├── app.py                # VoiceTypingApp 主应用 + 润色路由
│   ├── recorder.py           # Recorder 录音控制器
│   ├── core/                 # config.py / hotkey.py / updater.py / vocabulary.py / emotion.py / scene.py
│   ├── engine/               # base.py / alibaba.py / volcengine.py
│   └── ui/                   # styles.py / settings.py / overlay.py / avatar.py / resources/
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
│   ├── make_readme_images.py # README 截图 + 浮窗动图 → docs/images/（演示配置，界面改版后重跑）
│   ├── start.sh
│   └── monitor_latency.sh
├── tests/
│   ├── test_polish_routing.py   # 润色路由（解耦 / 关闭 / 失败回退）
│   ├── test_volcengine.py       # 火山 ASR 协议帧解析与鉴权头
│   ├── test_error_surface.py    # 失败不静默（错误提示到浮窗）
│   ├── test_overlay_states.py   # 浮窗状态切换
│   ├── test_emotion.py          # 转写文本 → 头像表情
│   ├── test_avatar_idle.py      # 头像待机小动作、打盹与唤醒
│   ├── test_scene.py            # 智能润色：窗口 → 场景
│   ├── test_waveform.py         # 音波自适应归一化
│   ├── test_cancel.py           # 浮窗 ✕ 取消：停录、丢弃迟到结果
│   ├── test_dict_io.py          # 词典 CSV 导入导出
│   └── test_updater.py          # 版本号解析与新版本判断
├── docs/                      # ROADMAP.md / font_sizes.md / archive/ / ui/（Grok 浮窗录屏 + 头像演示页）
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
| 浮窗头像 | QPainter | 原生绘制，眼睛形状数据 `resources/avatar-eyes.json` |
| 音频采集 | pyaudio | 16kHz 16bit mono PCM |
| 全局快捷键 | pynput | XInput2 跨应用监听键盘事件 |
| 云端 ASR | dashscope (阿里云) | Paraformer 实时流式识别 |
| 云端 ASR | 火山引擎 BigModel | WebSocket 流式识别 |
| 云端润色 | openai SDK（OpenAI 兼容接口） | DeepSeek（deepseek-chat）/ 智谱 GLM（glm-4-flash）/ MiniMax（MiniMax-Text-01），流式输出 |
| WebSocket | websockets | 火山 ASR 流式连接 |
| 更新检测 | urllib（stdlib） | 查询 GitHub Releases latest |
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
- 录音结束后走润色流水线，再自动粘贴
- 托盘图标 + 系统菜单
- `_POLISH`：3 个 Prompt（3 档强度），用户文本包进 `<转写文本>` 标签防止 LLM 把问句当指令回答
- `_LLM_PROVIDERS`：润色厂商表（base_url, model, key 字段），新增厂商只加一行
- 润色路由 `_resolve_polish_provider()`：显式 `polish_provider` 优先 → 否则按已填 Key 推断 → 都没有则 `off`；与 ASR 引擎解耦
- 少于 15 字（`_POLISH_BYPASS_CHARS`）跳过润色；失败 / 取消回退原文，不跨厂商重试
- 智能润色（`smart_polish`，默认开）：润色线程里读当前窗口 WM_CLASS + 标题（`_active_window`），`core/scene.py` 判成聊天 / 邮件 / 文档 / 代码 / 终端，往提示词末尾追加该场景的格式要求；浏览器按标题认网站，认不出走「其他」不追加；标题不发给大模型
- 实时润色（`realtime_polish`，默认关）：停顿 1s debounce 提前润色；仅当源文本与最终文本一致时才用缓存
- `_apply_alias_map()`：词库别名替换（忽略大小写）
- `_update_stats()`：累计时长 / 字数 / 次数 + 历史记录
- 粘贴时检测终端窗口（xprop WM_CLASS），终端用 `ctrl+shift+v`

### 2. voice_typing/recorder.py — 录音控制器

**Recorder 类**：
- 管理录音线程 + ASR 引擎生命周期
- `start()` → 开启 pyaudio 流 + 引擎初始化
- `stop()` → 停止录音 + 获取最终文本
- 信号：`text_update`（实时转写）、`level`（每 100ms 一次 0..1 音量，`LEVEL_FLOOR_DB` / `LEVEL_CEIL_DB` 可调）、`recording_done`（最终结果）

### 3. voice_typing/core/ — 核心功能

**config.py**：
- 配置文件路径：`~/.config/voice_typing/config.json`
- 配置项：engine（alibaba/volcengine）、alibaba_api_key、volc_asr_api_key / volc_asr_resource_id / volc_boosting_table_id、polish_provider（off/deepseek/glm/minimax）+ 各厂商 Key、polish_strength、realtime_polish、smart_polish、avatar_color、overlay_chat、hotkey、custom_vocabulary、stats、history
- 加载时补齐缺失默认值；旧版润色厂商（千问 / 豆包方舟）置空重新推断，`doubao_*` 字段仅保留兼容

**updater.py**：
- `check_for_update()` 查 GitHub `releases/latest`（天然排除 prerelease），逐段数值比较版本号
- 设置界面显示后后台线程检查，有新版本在版本号旁显示「新版本 vX 可用」链接；无网 / 失败静默

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
- 使用豆包流式语音识别 2.0（BigModel）WebSocket 二进制协议，默认资源 `volc.seedasr.sauc.duration`
- 鉴权仅需 `X-Api-Key`（豆包语音控制台 Key，与方舟 Key 独立）
- 支持热词直传 + 控制台热词表 ID（boosting_table_id）

### 5. voice_typing/ui/ — 用户界面

**settings.py（SettingsWindow）**：
- 样式集中在 `styles.py` 的 `APP_STYLE`（浅色、绿 #14C16E 强调、胶囊控件圆角 18 / 卡片 20）；内容区限宽 960 居中
- Logo `_draw_logo`（绿色圆头 + 两只竖条眼睛），安装包图标 `packaging/icons/` 由它生成
- 四页导航：首页（Hero 横幅 + 统计卡片）/ 历史 / 词典（词条 + 别名；导入 / 导出 / 全选）/ 设置
- 词典文件：CSV 两列「词汇,易错词」（`core/vocabulary.py` 的 `export_vocab_csv` / `import_vocab_csv`），导出带 BOM 便于 Excel 打开；导入兼容纯文本一行一词、GBK 编码，已有词汇跳过
- 设置页：引擎选择、API Key、快捷键录制、润色厂商与强度（轻度/中度/重度）、实时润色开关
- 显示版本号 + 新版本提示

**overlay.py（OverlayWindow）**：
- 白色胶囊浮窗，位于屏幕底部，可拖拽；尺寸 / 圆角 / 配色按 Grok Bot 语音浮窗录屏 1:1 实测（胶囊高 86px）
- 左侧头像（圆头直径 56，与右侧按钮同大）：`ui/avatar.py` 的 `AvatarWidget`，QPainter 原生绘制；状态（待机 / 聆听 / 思考 / 失败）+ 9 种表情逐点变形、眨眼、呼吸、张望
  - 眼睛轮廓由 `scripts/extract_avatar_eyes.py` 从 `docs/ui/round-avatar.html` 引擎提取（开发期需 playwright，运行时不需要）
- 单击头像（移动不到拖拽阈值）= 开始 / 结束语音输入：`avatar_clicked` → `HotkeyManager.toggle()`，与快捷键共用录音状态，两种触发方式下都是点一下开始、再点一下结束
- 表情：说话中用 `core/emotion.py` 关键词即时判断（取最后出现的情绪词）；定稿后若开了润色，`app._run_emotion` 与润色并行让同一个大模型判情绪（`_EMOTION_PROMPT`，max_tokens 5，约 1s），经 `overlay.set_emotion` 盖过关键词结果，失败退回关键词；出结果后摆表情停留 `EMOTION_HOLD_S`（4s）再回正（说话时人在看别的窗口，出结果才是看头像的时候）
- 头像帧率分三档：快动作 60fps / 眼睛转向 30fps / 只剩呼吸 10fps（呼吸胀缩不到 1 像素，降帧看不出），待机平均约 15fps
- 待机小动作（`avatar.py`）：每 5–12s 随机换表情 / 连眨 / 蹦一下 / 歪头；待机 90s 打盹（犯困脸 + 飘 z），鼠标移上来或切状态就醒
- 录音时显示 14 根音量历史条（`Recorder.level` 每 100ms 推一次）
- 右侧两个圆按钮：聊天开关（选中加深，存配置 `overlay_chat`）+ 红色 ✕（`cancel_requested` → `app._on_cancel`：停录、丢弃识别 / 润色结果、不粘贴；`HotkeyManager.cancel()` 清录音标记，松键 / 下次按键不再当作结束）
- 聊天关：出字后文字替换波形，主胶囊最宽 640px（超长只显示尾部）
- 聊天开：主胶囊始终显示波形，文字进上方 `TextBubble`（最宽 480px、多行换行、圆角 43、左对齐主胶囊）
- 两个浮窗都带 `WindowDoesNotAcceptFocus`，点按钮不会抢走目标应用焦点
- 待机只显示头像；窗口固定最大尺寸、只改胶囊宽度。浮窗在屏幕靠右处时胶囊贴窗口右侧、向左展开（`_place_pill` 拖动时自动切换），保证能拖到任一屏幕边缘、展开不出屏
- 头像与音波颜色 `set_avatar_color`，来自设置页「外观」（默认绿 + 黑 / 青绿 / 蓝 / 紫 + 自定义，点选即预览，「确定」保存到 `avatar_color`）；设置界面的强调色也跟着换（`styles.set_accent` 重设全局 QSS，自绘部分取 `styles.accent()`）

---

## 工作流程

1. **启动应用** → 加载配置 → 初始化引擎 → 注册全局快捷键 → 启动卡键检测线程
2. **按下快捷键** → HotkeyManager 检测组合键 → `_on_start()` → 信号到主线程 → 开始录音
3. **录音中** → 音频送入引擎 → 实时返回部分文本 → 更新浮窗
4. **松开快捷键** → `_check_combo_stop()` → `_on_stop()` → 信号到主线程 → 停止录音
5. **润色** → 别名替换 + 大模型清洗润色（流式推到浮窗）→ 失败则回退原始文字
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
sudo apt install ./dist/voice-typing_1.6.7_amd64.deb  # Debian / Ubuntu（别用 dpkg -i：不会自动装依赖）
sudo dnf install dist/voice-typing-1.6.7-1.x86_64.rpm  # Fedora / RHEL
chmod +x dist/VoiceType-1.6.7-x86_64.AppImage && ./dist/VoiceType-*.AppImage
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
| dashscope | 阿里云 Paraformer ASR | `pip install dashscope` |
| websockets | 火山 ASR WebSocket | `pip install websockets` |
| openai | 润色（OpenAI 兼容接口） | `pip install openai` |
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
- [x] 新版本检测（`core/updater.py`，启动后自动检查）

---

## 版本历史

- **v1.6.7**（2026-10-31）：智能润色（按当前软件调整格式，默认开）+ 大模型判情绪、出结果后表情停留 + 头像待机小动作与打盹 + 待机降帧省 CPU + README 面向普通用户重写
- **v1.6.6**（2026-10-31）：界面强调色 + 托盘 / 窗口图标跟随头像颜色 + 单击浮窗头像开始 / 结束语音输入 + 首页统计数字过万显示「万」
- **v1.6.5**（未单独发布）：Grok 风格浮窗（原生表情头像 + 自适应音波 + 聊天气泡 + ✕ 取消）+ 设置界面重做 + 词典导入导出 + 头像颜色；去掉 QtWebEngine 依赖
- **v1.6.4**（2026-10-08）：快捷键新增「按一下开始、再按一下结束」切换模式 + 首页 Hero 横幅 + 浮窗晕染外观 + 词典页布局调整
- **v1.6.3**（2026-09-28）：取消默认快捷键（首次运行录制）+ 词库全部词条作火山热词 + 别名替换忽略大小写
- **v1.6.2**（2026-09-20）：新版本检测提示 + 实时润色缓存过期修复 + 失败不再静默
- **v1.6.0**（2026-09-19）：火山鉴权简化 + 浮窗主题 + deb/rpm/AppImage 三包构建体系
- **v1.5.0**（2026-06-23）：BigModel 2.0 适配 + 流式润色 + DeepSeek 支持
- **v1.4.2 ~ v1.4.9**（2026-06）：设置界面重写 + 移除本地引擎 + 新 logo + UI 修复
- **v1.4.1**（2026-05-30）：修复快捷键串键、光标消失、长按录音中断
- **v1.4.0**（2026-05-24）：火山引擎支持 + 豆包润色 + 浮窗动效优化
- **v1.3.4**（2026-05-20）：重构为标准 Python 包结构
- **v1.0.0**（2026-05-18）：首个 deb 发布版本

---

## 相关链接

- GitHub 仓库：https://github.com/hongyan199048/voice_typing
- 阿里云百炼（原 DashScope，旧域名 dashscope.console.aliyun.com 已于 2026-08-01 下线）：https://bailian.console.aliyun.com/
- 火山引擎 ARK：https://console.volcengine.com/ark/