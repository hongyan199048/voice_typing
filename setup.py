#!/usr/bin/env python3
"""VoiceType 安装配置"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="voice-typing",
    version="1.5.0",
    author="hongyan199048",
    description="Ubuntu 环境下的 AI 语音转文字工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hongyan199048/voice_typing",
    packages=find_packages(),
    package_data={
        "voice_typing.ui": ["resources/*"],
    },
    install_requires=[
        "PyQt5>=5.15",
        "pyaudio",
        "dashscope",
        "pynput",
        "websockets",
        "openai",
    ],
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
