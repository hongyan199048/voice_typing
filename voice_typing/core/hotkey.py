"""全局快捷键管理 — 基于 pynput 的 push-to-talk 监听"""

import subprocess
import threading
import time
import pynput.keyboard as keyboard


def _norm(key):
    """将左右修饰键归一化为通用形式"""
    if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        return keyboard.Key.ctrl
    if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
        return keyboard.Key.alt
    if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
        return keyboard.Key.shift
    return key


def _key_to_str(key):
    """将 pynput Key 转为配置中的字符串"""
    mapping = {
        keyboard.Key.ctrl: "ctrl",
        keyboard.Key.alt: "alt",
        keyboard.Key.shift: "shift",
        keyboard.Key.cmd: "super",
    }
    if hasattr(key, "char") and key.char:
        return key.char.lower()
    if hasattr(key, "name") and key.name:
        return mapping.get(key, key.name)
    if hasattr(key, "vk") and key.vk is not None:
        return f"vk:{key.vk}"
    return ""


def _str_to_key(s):
    """将配置字符串转为 pynput Key"""
    mapping = {
        "ctrl": keyboard.Key.ctrl,
        "alt": keyboard.Key.alt,
        "shift": keyboard.Key.shift,
        "super": keyboard.Key.cmd,
    }
    if s in mapping:
        return mapping[s]
    if s.startswith("vk:"):
        return keyboard.KeyCode.from_vk(int(s[3:]))
    try:
        return getattr(keyboard.Key, s)
    except AttributeError:
        pass
    return keyboard.KeyCode.from_char(s)


class HotkeyManager:
    """全局 push-to-talk 快捷键管理

    支持两种模式：
    - 组合键（多键）：全部按下立即触发录音
    - 单键长按（一键）：按住超过 1 秒触发录音，松手结束

    关键设计：
    - pause/resume 不停止 pynput listener（避免 X11 grab 释放导致窗口焦点丢失），
      仅设置 _paused 标志屏蔽热键触发
    - 卡键检测线程：超过 MAX_KEY_HOLD_SEC 未释放的按键自动清除，
      防止 X11 丢失 key-up 事件导致修饰键永久残留
    """

    LONG_PRESS_SEC = 0.05
    MAX_KEY_HOLD_SEC = 10.0        # 单键最长保持，超时自动清除
    STALE_CHECK_INTERVAL = 3.0     # 卡键检测间隔

    def __init__(self, hotkey_list=None):
        self._keys = set()
        self._press_times = {}      # key → timestamp，检测卡键
        self._lock = threading.RLock()
        self._listener = None
        self._recording = False
        self._on_start = None
        self._on_stop = None
        self._hotkey_set = frozenset()
        self._is_long_press = False
        self._press_time = None
        self._long_press_timer = None
        self._paused = False
        self._stale_timer_running = False

        if hotkey_list:
            self.set_hotkey(hotkey_list)

    # ---- public API ----

    def set_hotkey(self, hotkey_list):
        keys = frozenset(_str_to_key(s) for s in hotkey_list)
        self._hotkey_set = keys
        self._is_long_press = len(hotkey_list) == 1
        self._clear_state()

    def set_callbacks(self, on_start, on_stop, on_key_detected=None):
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_key_detected = on_key_detected  # 按键检测到时立即回调（调试用）

    def start(self):
        if self._listener is not None:
            return
        self._clear_state()
        self._paused = False
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False,
        )
        self._listener.start()
        self._start_stale_checker()

    def stop(self):
        self._stop_stale_checker()
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._clear_state()

    def pause(self):
        """暂停热键触发（粘贴前调用），不停止监听器避免 X11 焦点丢失"""
        with self._lock:
            self._paused = True
            self._keys.clear()
            self._press_times.clear()
            self._recording = False

    def resume(self):
        """恢复热键触发（粘贴后调用）"""
        with self._lock:
            self._paused = False
            self._keys.clear()
            self._press_times.clear()

    @staticmethod
    def clear_x11_modifiers():
        """释放 X11 层面所有卡住的修饰键（解决丢事件导致的系统级卡键）"""
        try:
            subprocess.run(
                ["xdotool", "keyup", "ctrl", "alt", "shift", "super"],
                timeout=1,
                capture_output=True,
            )
        except Exception:
            pass

    def _release_all_keys(self):
        """释放所有按着的键（修饰键 + 普通键），防止组合键松开顺序问题"""
        try:
            # 释放修饰键
            subprocess.run(
                ["xdotool", "keyup", "ctrl", "alt", "shift", "super"],
                timeout=1, capture_output=True,
            )
            # 释放所有普通键（当前按着的）
            with self._lock:
                for k in list(self._keys):
                    key_str = _key_to_str(k)
                    if key_str and key_str not in ("ctrl", "alt", "shift", "super"):
                        try:
                            subprocess.run(
                                ["xdotool", "keyup", key_str],
                                timeout=1, capture_output=True,
                            )
                        except Exception:
                            pass
        except Exception:
            pass

    # ---- 内部 ----

    def _clear_state(self):
        with self._lock:
            self._keys.clear()
            self._press_times.clear()
            self._recording = False

    def _start_stale_checker(self):
        self._stop_stale_checker()
        self._stale_timer_running = True
        threading.Thread(target=self._stale_check_loop, daemon=True).start()

    def _stop_stale_checker(self):
        self._stale_timer_running = False

    def _stale_check_loop(self):
        while self._stale_timer_running:
            time.sleep(self.STALE_CHECK_INTERVAL)
            if not self._stale_timer_running:
                return
            self._purge_stale_keys()

    def _purge_stale_keys(self):
        now = time.time()
        with self._lock:
            # 录音中不检测卡键：长按模式下用户会一直按住触发键，属于正常行为
            if self._recording:
                return
            stale = [
                k for k, t in self._press_times.items()
                if now - t > self.MAX_KEY_HOLD_SEC
            ]
            if stale:
                for k in stale:
                    self._keys.discard(k)
                    self._press_times.pop(k, None)
                if self._is_long_press:
                    self._on_long_press_release()
                else:
                    self._check_combo_stop()
                self.clear_x11_modifiers()

    # ---- 单键长按模式 ----

    def _on_long_press_start(self):
        with self._lock:
            if self._recording or self._paused:
                return
            self._recording = True
            if self._on_start:
                self._on_start()

    def _on_long_press_release(self):
        with self._lock:
            if self._long_press_timer:
                self._long_press_timer.cancel()
                self._long_press_timer = None
            self._press_time = None
            was_recording = self._recording
            self._recording = False
            if was_recording and self._on_stop:
                self._on_stop()

    # ---- 组合键模式 ----

    def _check_combo_start(self):
        if self._paused:
            return
        if self._hotkey_set and self._hotkey_set.issubset(self._keys):
            if not self._recording:
                self._recording = True
                if self._on_start:
                    self._on_start()

    def _check_combo_stop(self):
        if self._hotkey_set and not self._hotkey_set.issubset(self._keys):
            if self._recording:
                self._recording = False
                # 释放所有按着的键，防止先松修饰键导致剩余键被输入
                self._release_all_keys()
                if self._on_stop:
                    self._on_stop()

    # ---- 事件分发 ----

    def _on_press(self, key):
        with self._lock:
            k = _norm(key)
            if k in self._keys:
                return
            self._keys.add(k)
            self._press_times[k] = time.time()

            if not self._hotkey_set or self._paused:
                return

            if self._is_long_press:
                if k in self._hotkey_set and self._press_time is None:
                    self._press_time = time.time()
                    # 按键检测到，立刻通知（用于延迟诊断）
                    if self._on_key_detected:
                        self._on_key_detected()
                    if self.LONG_PRESS_SEC <= 0:
                        self._on_long_press_start()
                    else:
                        self._long_press_timer = threading.Timer(
                            self.LONG_PRESS_SEC, self._on_long_press_start
                        )
                        self._long_press_timer.start()
            else:
                self._check_combo_start()

    def _on_release(self, key):
        with self._lock:
            k = _norm(key)
            self._keys.discard(k)
            self._press_times.pop(k, None)

            if not self._hotkey_set or self._paused:
                return

            if self._is_long_press:
                if k in self._hotkey_set:
                    self._on_long_press_release()
            else:
                self._check_combo_stop()

    @staticmethod
    def record_key_sequence(on_done):
        """录制快捷键组合（用于设置界面）"""
        recorded = set()
        done = threading.Event()

        KEY_ORDER = {
            keyboard.Key.ctrl: 0, keyboard.Key.alt: 1,
            keyboard.Key.shift: 2, keyboard.Key.cmd: 3,
        }

        def on_press(key):
            k = _norm(key)
            recorded.add(k)

        def on_release(key):
            threading.Timer(0.15, _check_done).start()

        def _check_done():
            if done.is_set():
                return
            done.set()
            sorted_keys = sorted(recorded, key=lambda k: KEY_ORDER.get(k, 99))
            result = [_key_to_str(k) for k in sorted_keys if _key_to_str(k)]
            listener.stop()
            on_done(result)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        return listener
