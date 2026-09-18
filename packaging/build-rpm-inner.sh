#!/bin/bash
# 在 fedora 容器内执行：用 /stage 的负载直接打 rpm
set -euo pipefail
mkdir -p /tmp/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
rpmbuild -bb /pkg/voice-typing.spec \
    --define "_vt_version ${VERSION}" \
    --define "_vt_stage /stage" \
    --define "_vt_pkg /pkg" \
    --define "_topdir /tmp/rpmbuild" \
    --define "dist %{nil}"
cp /tmp/rpmbuild/RPMS/x86_64/*.rpm /out/
