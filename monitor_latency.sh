#!/bin/bash
# 按键延迟监控：X11 底层事件 vs app 日志
# 用法：./monitor_latency.sh

cd "$(dirname "$0")"

echo "=== 按键延迟监控 ==="
echo "[X11] = 操作系统收到按键的时间"
echo "[APP] = app 触发录音的时间"
echo "差值 = 真实按键到录音延迟"
echo ""

# 先杀掉旧进程
pkill -f "python3 main.py" 2>/dev/null
sleep 1

# 启动 app，stdout+stderr 写到临时文件
APP_LOG=$(mktemp /tmp/voicetype.XXXXXX)
python3 main.py > "$APP_LOG" 2>&1 &
APP_PID=$!
sleep 2

echo "app 已启动 (PID=$APP_PID)，监控中..."
echo "按 Fn 键测试，Ctrl+C 停止"
echo "-------------------------------------------"

# 监控 X11 键盘事件（用 xdotool 获取按键时间戳）
xev -root -event keyboard 2>/dev/null | while IFS= read -r line; do
    if echo "$line" | grep -q "KeyPress"; then
        echo -e "\033[36m[X11] $(date +%H:%M:%S.%3N)  $line\033[0m"
    fi
done &

# 监控 app 日志
tail -f "$APP_LOG" 2>/dev/null | while IFS= read -r line; do
    if echo "$line" | grep -qE "\[PERF\] [①②③④⑤]"; then
        echo -e "\033[32m[APP] $(date +%H:%M:%S.%3N)  $line\033[0m"
    fi
done &

# 等待退出
trap "kill $APP_PID 2>/dev/null; rm -f '$APP_LOG'; kill 0 2>/dev/null; exit" INT TERM
wait
