#!/bin/bash
# 在容器内执行：以 python-appimage 的 manylinux Python 为基座，
# 把 Python 解释器 + Qt + 全部依赖打进一个自包含 AppImage。
set -euo pipefail
export APPIMAGE_EXTRACT_AND_RUN=1
WORK=/tmp/build
rm -rf "$WORK"; mkdir -p "$WORK"; cd "$WORK"

echo "--> 取 manylinux Python 基座"
BASE_URL=$(python3 - <<'PY'
import json, urllib.request
api = "https://api.github.com/repos/niess/python-appimage/releases/tags/python3.10"
data = json.load(urllib.request.urlopen(api))
for a in data["assets"]:
    if "cp310" in a["name"] and "manylinux2014_x86_64" in a["name"]:
        print(a["browser_download_url"]); break
PY
)
curl -fsSL -o python.AppImage "$BASE_URL"
chmod +x python.AppImage
./python.AppImage --appimage-extract >/dev/null
APPDIR="$WORK/squashfs-root"

echo "--> 装依赖（Qt / 音频 / 云端 SDK 全部进包）"
"$APPDIR/AppRun" -m pip install --quiet --no-warn-script-location --upgrade pip
"$APPDIR/AppRun" -m pip install --quiet --no-warn-script-location \
    PyQt5 PyAudio -r /build/vendor-requirements.txt

# PyAudio 是编译出来的，链接的是容器里的 libportaudio，必须一并打进包
mkdir -p "$APPDIR/usr/lib"
cp -L /usr/lib/x86_64-linux-gnu/libportaudio.so.2 "$APPDIR/usr/lib/"
cp -L /usr/lib/x86_64-linux-gnu/libasound.so.2 "$APPDIR/usr/lib/"

echo "--> 放入应用代码"
mkdir -p "$APPDIR/opt/voice-typing"
cp -r /stage/usr/share/voice-typing/voice_typing "$APPDIR/opt/voice-typing/"

echo "--> 桌面入口与图标"
# 基座自带的 python .desktop/图标要清掉，AppImage 根目录只允许一个
rm -f "$APPDIR"/*.desktop "$APPDIR"/*.png "$APPDIR"/.DirIcon
rm -rf "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons"
mkdir -p "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp /stage/usr/share/applications/voice-typing.desktop "$APPDIR/usr/share/applications/"
# AppImage 内不存在 /usr/bin/voice-typing，Exec 改成 AppRun 提供的名字
sed -i 's|^Exec=.*|Exec=voice-typing|' "$APPDIR/usr/share/applications/voice-typing.desktop"
cp "$APPDIR/usr/share/applications/voice-typing.desktop" "$APPDIR/voice-typing.desktop"
ICON=$(ls /stage/usr/share/icons/hicolor/*/apps/voice-typing.png | sort -t/ -k7 -V | tail -1)
cp "$ICON" "$APPDIR/voice-typing.png"
cp "$ICON" "$APPDIR/usr/share/icons/hicolor/256x256/apps/voice-typing.png"
ln -sf voice-typing.png "$APPDIR/.DirIcon"

# 基座的 AppRun 是符号链接，必须先删掉再写，否则会写穿到链接目标
rm -f "$APPDIR/AppRun"
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PYTHONPATH="$HERE/opt/voice-typing:${PYTHONPATH:-}"
export PYTHONHOME="$HERE/opt/python3.10"
export PYTHONDONTWRITEBYTECODE=1
export LD_LIBRARY_PATH="$HERE/usr/lib:${LD_LIBRARY_PATH:-}"
# 粘贴依赖宿主机的 xclip / xdotool，缺了就直说，不要静默失败
for cmd in xclip xdotool; do
    command -v "$cmd" >/dev/null || \
        echo "[VoiceType] 缺少 $cmd，识别可用但无法自动粘贴。请安装：apt install $cmd / dnf install $cmd" >&2
done
exec "$HERE/opt/python3.10/bin/python3.10" -m voice_typing "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

echo "--> 打包"
curl -fsSL -o appimagetool \
    https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool
ARCH=x86_64 ./appimagetool "$APPDIR" "/out/VoiceType-${VERSION}-x86_64.AppImage"
