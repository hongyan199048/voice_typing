"""快捷键切换模式：按一下开始，再按一下结束"""

import pynput.keyboard as keyboard

from voice_typing.core.hotkey import HotkeyManager


def _make(hotkey, mode):
    events = []
    hk = HotkeyManager(hotkey)
    hk.set_callbacks(lambda: events.append("start"), lambda: events.append("stop"))
    hk.set_mode(mode)
    return hk, events


def _tap(hk, *keys):
    for k in keys:
        hk._on_press(k)
    for k in reversed(keys):
        hk._on_release(k)


def test_toggle_single_key():
    hk, events = _make(["f9"], "toggle")
    _tap(hk, keyboard.Key.f9)
    assert events == ["start"]
    _tap(hk, keyboard.Key.f9)
    assert events == ["start", "stop"]


def test_toggle_ignores_autorepeat():
    hk, events = _make(["f9"], "toggle")
    for _ in range(5):
        hk._on_press(keyboard.Key.f9)
    hk._on_release(keyboard.Key.f9)
    assert events == ["start"]


def test_toggle_combo():
    hk, events = _make(["ctrl", "space"], "toggle")
    _tap(hk, keyboard.Key.ctrl_l, keyboard.Key.space)
    assert events == ["start"]
    _tap(hk, keyboard.Key.ctrl_r, keyboard.Key.space)
    assert events == ["start", "stop"]


def test_hold_mode_unchanged():
    hk, events = _make(["ctrl", "space"], "hold")
    hk._on_press(keyboard.Key.ctrl_l)
    hk._on_press(keyboard.Key.space)
    assert events == ["start"]
    hk._on_release(keyboard.Key.space)
    assert events == ["start", "stop"]


def test_switch_mode_while_recording_stops():
    hk, events = _make(["f9"], "toggle")
    _tap(hk, keyboard.Key.f9)
    hk.set_mode("hold")
    assert events == ["start", "stop"]


def test_cancel_then_next_toggle_starts():
    """浮窗 ✕ 取消后，切换模式下一次按键是开始新录音，而不是结束"""
    hk, events = _make(["f9"], "toggle")
    _tap(hk, keyboard.Key.f9)
    hk.cancel()
    _tap(hk, keyboard.Key.f9)
    assert events == ["start", "start"]


def test_cancel_while_holding_release_does_not_stop():
    """按住说话中点 ✕，之后松开快捷键不再触发结束（否则会走识别粘贴）"""
    hk, events = _make(["ctrl", "space"], "hold")
    hk._on_press(keyboard.Key.ctrl_l)
    hk._on_press(keyboard.Key.space)
    hk.cancel()
    hk._on_release(keyboard.Key.space)
    hk._on_release(keyboard.Key.ctrl_l)
    assert events == ["start"]


def test_click_avatar_toggles_in_any_mode():
    """浮窗单击头像：两种触发方式下都是点一下开始、再点一下结束"""
    for mode in ("hold", "toggle"):
        hk, events = _make(["ctrl", "space"], mode)
        hk.toggle()
        hk.toggle()
        assert events == ["start", "stop"]


def test_click_started_recording_survives_other_keys():
    """点头像开始后敲别的键不结束；按一下快捷键结束"""
    hk, events = _make(["ctrl", "space"], "hold")
    hk.toggle()
    _tap(hk, keyboard.KeyCode.from_char("a"))
    assert events == ["start"]
    _tap(hk, keyboard.Key.ctrl_l, keyboard.Key.space)
    assert events == ["start", "stop"]
