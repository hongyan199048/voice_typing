"""录音 + ASR 控制器"""

import math
import queue
import threading
from array import array

import pyaudio
from PyQt5.QtCore import pyqtSignal, QObject, Qt, QMetaObject, Q_ARG

SAMPLE_RATE = 16000
CHUNK_SIZE = 3200  # 200ms
# 音量 → 0..1 的映射区间（dBFS）。麦克风增益各异，偏小/偏大就调这两个数
LEVEL_FLOOR_DB = -50.0
LEVEL_CEIL_DB = -15.0


def _level(pcm: bytes) -> float:
    """16bit PCM 的响度，按 dBFS 线性映射到 0..1"""
    samples = array("h", pcm)
    rms = math.sqrt(sum(x * x for x in samples) / max(1, len(samples)))
    db = 20 * math.log10(rms / 32768 + 1e-9)
    return min(1.0, max(0.0, (db - LEVEL_FLOOR_DB) / (LEVEL_CEIL_DB - LEVEL_FLOOR_DB)))


class Recorder(QObject):
    """录音 + ASR 控制器，在主线程中用信号通信"""

    text_update = pyqtSignal(str)
    level = pyqtSignal(float)  # 每 100ms 一次实时音量，驱动浮窗波形

    def __init__(self, engine, app_obj=None):
        super().__init__()
        self._engine = engine
        self._recording = False
        self._audio_queue = None
        self._p = None
        self._app_obj = app_obj  # VoiceTypingApp 对象引用
        self._engine_ready = threading.Event()

    def start(self):
        self._p = pyaudio.PyAudio()
        self._recording = True
        self._audio_queue = queue.Queue()

        # 录音线程（立刻启动，不等引擎）
        threading.Thread(target=self._record_audio, daemon=True).start()
        # 引擎初始化 + 音频推流（后台进行，不阻塞主线程）
        threading.Thread(target=self._init_and_feed, daemon=True).start()

    def stop(self):
        self._recording = False

    def _record_audio(self):
        try:
            stream = self._p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
        except Exception:
            # 麦克风打开失败：终止 PyAudio 防资源泄漏，并让推流线程尽快结束
            self._engine.last_error = "麦克风打开失败"
            self._recording = False
            self._p.terminate()
            return

        while self._recording:
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self._audio_queue.put(data)
                half = len(data) // 2
                self.level.emit(_level(data[:half]))
                self.level.emit(_level(data[half:]))
            except Exception:
                break

        stream.stop_stream()
        stream.close()
        self._p.terminate()

    def _init_and_feed(self):
        """后台线程：初始化引擎 → 等待就绪 → 推送音频"""
        import time
        t0 = time.time()
        try:
            if not self._engine.is_available():
                self._engine.initialize()

            self._engine.start()
            if hasattr(self._engine, "set_text_callback"):
                self._engine.set_text_callback(lambda t: self.text_update.emit(t))
            self._engine_ready.set()
            t1 = time.time()
            print(f"[PERF] ⑤ 引擎就绪 → {t1:.3f} (引擎初始化 {(t1-t0)*1000:.0f}ms)")
        except Exception as e:
            print(f"[Recorder] 引擎初始化失败: {e}")
            self._engine.last_error = "识别引擎启动失败，请检查配置"
            self._engine_ready.set()  # 即使失败也解除等待，避免死锁
            return

        # 推送音频到引擎
        while self._recording or (self._audio_queue and not self._audio_queue.empty()):
            try:
                data = self._audio_queue.get(timeout=0.3)
                if self._engine_ready.is_set():
                    self._engine.send_audio(data)
            except queue.Empty:
                continue

        final_text = self._engine.stop()

        if self._app_obj:
            QMetaObject.invokeMethod(
                self._app_obj,
                "_on_recording_done",
                Qt.QueuedConnection,
                Q_ARG(str, final_text)
            )
