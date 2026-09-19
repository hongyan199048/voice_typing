"""ASR 引擎抽象基类"""

from abc import ABC, abstractmethod


class BaseEngine(ABC):
    """所有 ASR 引擎的基类"""

    # 最近一次失败原因，空表示正常。录音结束却没出文字时由 UI 读取展示；
    # 否则失败只会 print 到 stdout，从桌面菜单启动的用户根本看不到。
    last_error = ""

    @abstractmethod
    def initialize(self) -> bool:
        """初始化引擎，返回是否就绪"""
        ...

    @abstractmethod
    def start(self):
        """开始识别会话"""
        ...

    @abstractmethod
    def send_audio(self, pcm_bytes: bytes):
        """送入 PCM 16kHz 16bit mono 音频数据"""
        ...

    @abstractmethod
    def stop(self) -> str:
        """停止识别，返回最终文本"""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """引擎是否可用（API Key 已配置/模型已下载）"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """引擎名称"""
        ...
