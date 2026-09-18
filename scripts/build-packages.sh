#!/usr/bin/env bash
# 一次构建 deb / rpm / AppImage 三种包，产物落在 dist/
#
# 宿主机只需要 docker（免 sudo）。rpm 和 AppImage 都在容器里构建，
# 不往系统里装任何打包工具。
#
#   ./scripts/build-packages.sh            # 三个全建
#   ./scripts/build-packages.sh deb rpm    # 只建指定的
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION=$(python3 -c "import re;print(re.search(r'__version__ = \"(.+?)\"', open('voice_typing/__init__.py').read()).group(1))")
STAGE="$ROOT/build/stage"
DIST="$ROOT/dist"
TARGETS=("$@")
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=(deb rpm appimage)

log() { printf '\033[32m==>\033[0m %s\n' "$*"; }

# 容器一律以宿主用户身份运行，否则产出的文件是 root 属主，宿主既删不掉也改不了
DOCKER_AS_ME=(--user "$(id -u):$(id -g)" -e HOME=/tmp)

# 清理可能残留的 root 属主目录（早期版本以 root 跑过容器时会有）
clean_dir() {
    [ -e "$1" ] || return 0
    rm -rf "$1" 2>/dev/null && return 0
    log "借容器清理 root 属主残留：$1"
    docker run --rm -v "$(dirname "$1"):/p" alpine:3 rm -rf "/p/$(basename "$1")"
}

need_docker() {
    command -v docker >/dev/null || { echo "需要 docker：$1 无法构建" >&2; exit 1; }
    docker info >/dev/null 2>&1 || { echo "docker 不可用（未运行或需要 sudo）" >&2; exit 1; }
}

# ---------- 公共负载 ----------
# 三种包共用同一份内容，全部从 voice_typing/ 现场取，不依赖 debian/ 下的副本
build_payload() {
    log "准备负载 v$VERSION"
    clean_dir "$STAGE"
    mkdir -p "$STAGE/usr/share/voice-typing" "$STAGE/usr/bin" \
             "$STAGE/usr/share/applications" "$ROOT/build"

    cp -r voice_typing "$STAGE/usr/share/voice-typing/"
    find "$STAGE" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

    install -m 755 packaging/launcher.py "$STAGE/usr/bin/voice-typing"
    cp packaging/voice-typing.desktop "$STAGE/usr/share/applications/"
    cp -r packaging/icons "$STAGE/usr/share/icons"

    # vendor 清单 = requirements.txt 去掉走系统包的 PyQt5 / pyaudio，
    # 不单独维护第二份列表，加新依赖只改 requirements.txt 一处
    grep -vE '^\s*(#|$)' requirements.txt \
        | grep -viE '^(PyQt5|pyaudio)' > "$ROOT/build/vendor-requirements.txt"
    log "vendor 纯 Python 依赖：$(tr '\n' ' ' < "$ROOT/build/vendor-requirements.txt")"
    docker run --rm "${DOCKER_AS_ME[@]}" \
        -v "$STAGE:/stage" -v "$ROOT/build:/build:ro" \
        python:3.10 \
        pip install --quiet --no-compile --target /stage/usr/share/voice-typing/vendor \
                    -r /build/vendor-requirements.txt
    # pip --target 会带一堆 dist-info 和测试目录，清掉省体积
    find "$STAGE/usr/share/voice-typing/vendor" \
         \( -name "__pycache__" -o -name "tests" -o -name "*.dist-info" \) \
         -type d -exec rm -rf {} + 2>/dev/null || true
    du -sh "$STAGE/usr/share/voice-typing/vendor" | sed 's/^/    vendor: /'
}

# ---------- deb ----------
build_deb() {
    log "构建 deb"
    local d="$ROOT/build/deb"
    clean_dir "$d"; mkdir -p "$d/DEBIAN"
    cp -r "$STAGE"/* "$d/"
    sed "s/^Version:.*/Version: $VERSION/" packaging/control > "$d/DEBIAN/control"
    install -m 755 packaging/postinst.sh "$d/DEBIAN/postinst"
    # dpkg-deb 要求目录属主可写且权限规整
    find "$d" -type d -exec chmod 755 {} +
    dpkg-deb --build --root-owner-group "$d" "$DIST/voice-typing_${VERSION}_amd64.deb" >/dev/null
    log "  → dist/voice-typing_${VERSION}_amd64.deb"
}

# ---------- rpm ----------
build_rpm() {
    need_docker rpm
    log "构建 rpm（fedora 容器内 rpmbuild）"
    docker build -q -t voice-typing-rpmbuild -f packaging/Dockerfile.rpm packaging >/dev/null
    docker run --rm "${DOCKER_AS_ME[@]}" \
        -v "$STAGE:/stage:ro" -v "$DIST:/out" -v "$ROOT/packaging:/pkg:ro" \
        -e VERSION="$VERSION" voice-typing-rpmbuild /pkg/build-rpm-inner.sh
    log "  → dist/voice-typing-${VERSION}-1.x86_64.rpm"
}

# ---------- AppImage ----------
build_appimage() {
    need_docker AppImage
    log "构建 AppImage（容器内打包独立 Python + Qt）"
    docker build -q -t voice-typing-appimage -f packaging/appimage/Dockerfile packaging >/dev/null
    docker run --rm "${DOCKER_AS_ME[@]}" \
        -v "$STAGE:/stage:ro" -v "$DIST:/out" -v "$ROOT/packaging:/pkg:ro" \
        -v "$ROOT/build:/build:ro" \
        -e VERSION="$VERSION" voice-typing-appimage /pkg/appimage/build-inner.sh
    log "  → dist/VoiceType-${VERSION}-x86_64.AppImage"
}

mkdir -p "$DIST"
build_payload
for t in "${TARGETS[@]}"; do
    case "$t" in
        deb) build_deb ;;
        rpm) build_rpm ;;
        appimage) build_appimage ;;
        *) echo "未知目标: $t（可选 deb / rpm / appimage）" >&2; exit 1 ;;
    esac
done

log "完成"
ls -lh "$DIST" | tail -n +2 | awk '{printf "    %-45s %s\n", $9, $5}'
