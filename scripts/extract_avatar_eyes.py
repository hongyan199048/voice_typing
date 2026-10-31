#!/usr/bin/env python3
"""从 docs/ui/round-avatar.html 的引擎里提取 9 种表情的正脸眼睛轮廓 → avatar-eyes.json

开发期工具，需要 playwright（pip install playwright && playwright install chromium）。
运行时不依赖它：浮窗只读生成好的 JSON，用 QPainter 自己画。

坐标：以头部圆心为原点、半径为 1，y 向下；每只眼睛按弧长重采样成 N 个点、
从质心正右方开始顺时针，两种表情之间逐点插值即可平滑变形。
"""

import json
import math
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "ui" / "round-avatar.html"
OUT = ROOT / "voice_typing" / "ui" / "resources" / "avatar-eyes.json"
N = 64
SIZE, R = 200, 60  # 引擎画布 200 时头部半径 60

# 把引擎内部函数挂到 window 上，好在头部旋转为零（正脸）时渲染单帧
_RENDER = """(expr) => {
  const E = window.__eng, G = E.makeConfig(E.RECIPES);
  const rt = E.createRuntime(G, {}); rt.pause();
  rt.setExpression(expr);
  for (let i = 0; i < 120; i++) rt.advance(1 / 60);
  const f = rt.frame(); f.quat = E.lb(0, 0, 0);
  const m = E.buildModel(f, { ink: [0, 0, 0], spot: [0, 0, 0], cutout: true }, 200, G,
                         E.makeMorphGenerators(G), E.makeTrail(G), () => {});
  const r = E.createRenderer(document, 'e' + expr, 200, G); r.render(m);
  return [...r.svg.querySelectorAll('path')].map(p => p.getAttribute('d')).filter(Boolean);
}"""


def _engine_js() -> str:
    html = SRC.read_text(encoding="utf-8")
    js = html[html.index("<script>") + 8: html.index("</script>")]
    marker = "global.RoundAvatar = RoundAvatar;"
    return js.replace(marker, marker + "\nglobal.__eng = { RECIPES, makeConfig, createRuntime, "
                      "buildModel, createRenderer, makeMorphGenerators, makeTrail, lb };")


def _eye_polygons(d: str):
    """路径 = 头部圆（A 弧）+ 若干眼睛折线子路径（M/L/Z）"""
    polys = []
    for sub in re.findall(r"M[^MZ]*Z", d):
        if "A" in sub:
            continue
        nums = list(map(float, re.findall(r"-?\d+(?:\.\d+)?", sub)))
        polys.append([((x - SIZE / 2) / R, (y - SIZE / 2) / R) for x, y in zip(nums[::2], nums[1::2])])
    return polys


def _resample(poly):
    """按弧长等距取 N 点，统一从质心正右方起、顺时针（屏幕坐标），便于逐点插值"""
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))
    if area < 0:
        poly = poly[::-1]
    start = min(range(len(poly)), key=lambda i: abs(math.atan2(poly[i][1] - cy, poly[i][0] - cx)))
    poly = poly[start:] + poly[:start]
    ring = poly + poly[:1]
    seg = [math.dist(a, b) for a, b in zip(ring, ring[1:])]
    total = sum(seg)
    out, i, acc = [], 0, 0.0
    for k in range(N):
        target = total * k / N
        while acc + seg[i] < target:
            acc += seg[i]
            i += 1
        t = (target - acc) / seg[i] if seg[i] else 0
        (x0, y0), (x1, y1) = ring[i], ring[i + 1]
        out.append([round(x0 + (x1 - x0) * t, 4), round(y0 + (y1 - y0) * t, 4)])
    return out


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content("<body></body>")
        page.add_script_tag(content=_engine_js())
        names = page.evaluate("window.__eng.RECIPES.expressionNames")
        eyes = {}
        for name in names:
            paths = page.evaluate(_RENDER, name)
            polys = sorted(_eye_polygons(paths[-1]), key=lambda poly: min(x for x, _ in poly))
            assert len(polys) == 2, (name, len(polys))
            eyes[name] = [_resample(poly) for poly in polys]
        blink_blocking = page.evaluate("window.__eng.RECIPES.blinkBlockingExpressions")
        browser.close()
    OUT.write_text(json.dumps({"blinkBlocking": blink_blocking, "eyes": eyes},
                              separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes): {', '.join(eyes)}")


if __name__ == "__main__":
    main()
