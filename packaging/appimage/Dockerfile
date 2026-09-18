FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates file zsync desktop-file-utils python3 \
        build-essential linux-libc-dev portaudio19-dev libasound2-dev \
    && rm -rf /var/lib/apt/lists/*
# appimagetool 自身是 AppImage，容器里没 FUSE，用解压模式运行
ENV APPIMAGE_EXTRACT_AND_RUN=1
