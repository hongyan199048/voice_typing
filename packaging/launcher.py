#!/usr/bin/env python3
"""VoiceType 启动器（deb / rpm 安装后的 /usr/bin/voice-typing）"""
import sys

APP_DIR = "/usr/share/voice-typing"
# vendor 放在系统 site-packages 之后，用户自己 pip 装的新版本优先
sys.path.insert(0, APP_DIR)
sys.path.append(APP_DIR + "/vendor")

from voice_typing.app import main
main()
