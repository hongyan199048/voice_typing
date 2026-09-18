#!/usr/bin/env python3
"""VoiceType 安装配置

版本号和依赖都不在这里硬编码，分别取自 voice_typing/__init__.py 和
requirements.txt —— 同一个事实只存一份，避免升级时漏改。
"""

import re
from pathlib import Path

from setuptools import setup, find_packages

ROOT = Path(__file__).parent


def _version():
    text = (ROOT / "voice_typing" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "(.+?)"', text).group(1)


def _requirements():
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.startswith("#")]


setup(
    name="voice-typing",
    version=_version(),
    author="hongyan199048",
    description="Ubuntu 环境下的 AI 语音转文字工具",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    url="https://github.com/hongyan199048/voice_typing",
    packages=find_packages(),
    package_data={
        "voice_typing.ui": ["resources/*"],
    },
    install_requires=_requirements(),
    entry_points={
        "console_scripts": [
            "voice-typing=voice_typing.app:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: POSIX :: Linux",
    ],
)
