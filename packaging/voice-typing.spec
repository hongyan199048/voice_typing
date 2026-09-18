Name:           voice-typing
Version:        %{_vt_version}
Release:        1%{?dist}
Summary:        实时语音转文字桌面应用
License:        MIT
URL:            https://github.com/hongyan199048/voice_typing
BuildArch:      x86_64

# 纯 Python 依赖已 vendor 进 /usr/share/voice-typing/vendor，此处只声明系统包
Requires:       python3 >= 3.8
Requires:       python3-qt5
Requires:       python3-pyaudio
Requires:       xclip
Requires:       xdotool

# 负载是预先装配好的目录树，不需要 rpm 自动推导依赖
AutoReqProv:    no

%description
VoiceType 是一个基于 PyQt5 的语音转文字桌面应用。

全局快捷键按住说话，松开后自动识别并粘贴到光标位置。
支持阿里云 Paraformer 与豆包流式语音识别 2.0 两种云端引擎，
识别结果可选交由 DeepSeek / GLM / MiniMax 润色，也可关闭润色直接输出原文。

%install
cp -r %{_vt_stage}/usr %{buildroot}/

%post
%include %{_vt_pkg}/postinst.sh

%files
/usr/bin/voice-typing
/usr/share/voice-typing
/usr/share/applications/voice-typing.desktop
/usr/share/icons/hicolor/*/apps/voice-typing.*

%changelog
* Sat Sep 19 2026 hongyan199048 <hongyan199048@example.com>
- 与 deb 包同版本构建
