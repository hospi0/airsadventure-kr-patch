# -*- coding: utf-8 -*-
r"""스테이트의 VDP1 스프라이트 전부 + VDP2 NBG0/1 를 한 장에(그림 글자 찾기용, 2026-11-01)
  python tools/spritesheet.py s1 s2 …  → work/sheet/<s>.png
  색: RGB16 = 그대로 · 4비트 LUT = LUT 의 RGB · 4/8비트 뱅크 = CRAM(뱅크) 근사
"""
import os, sys, struct
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import vdp1cmd, vdp2render as V


def rgb(e):
    e = np.asarray(e).astype(int)
    return np.stack([(e & 31) << 3, (e >> 5 & 31) << 3, (e >> 10 & 31) << 3], -1).astype(np.uint8)


def sprite(v, cram, pm, col, sa, w, h):
    mode = (pm >> 3) & 7
    if mode == 5:
        e = np.frombuffer(v[sa:sa + w * h * 2], '>u2')
        if len(e) < w * h: return None
        return rgb(e.reshape(h, w))
    if mode in (0, 1):
        a = np.frombuffer(v[sa:sa + w * h // 2], np.uint8)
        if len(a) < w * h // 2: return None
        idx = np.stack([a >> 4, a & 15], 1).ravel().reshape(h, w).astype(int)
        if mode == 1:
            lut = np.frombuffer(v[col * 8:col * 8 + 32], '>u2').astype(int); img = rgb(lut[idx])
        else:
            img = rgb(cram[((col & 0x7F0) + idx) & 0x7FF])
        img[idx == 0] = 40
        return img
    if mode in (2, 3, 4):
        a = np.frombuffer(v[sa:sa + w * h], np.uint8)
        if len(a) < w * h: return None
        idx = a.reshape(h, w).astype(int); img = rgb(cram[((col & 0x700) + idx) & 0x7FF]); img[idx == 0] = 40
        return img
    return None


def sheet(s):
    D = os.path.join(ROOT, 'work', 'mem', s)
    v = vdp1cmd.load(D); _, _, cram = V.load(s)
    items = []; seen = set()
    for i, cmd, pm, col, sa, w, h, x, y in vdp1cmd.cmds(v):
        k = (pm, col, sa, w, h)
        if k in seen or w * h < 64: continue
        seen.add(k); im = sprite(v, cram, pm, col, sa, w, h)
        if im is not None: items.append(('%05X %dx%d m%d' % (sa, w, h, (pm >> 3) & 7), im))
    for n in (0, 1):
        try:
            im, I = V.render(s, n)
            if I['on']: items.append(('NBG%d' % n, np.asarray(im.convert('RGB'))[:240, :352]))
        except Exception as e:
            pass
    W = 1100; x = y = 0; rowh = 0; pos = []
    for lab, im in items:
        h, w = im.shape[:2]; sc = 2 if w <= 200 and h <= 120 else 1
        w2, h2 = w * sc, h * sc + 12
        if x + w2 > W: x = 0; y += rowh + 4; rowh = 0
        pos.append((x, y, sc)); x += w2 + 6; rowh = max(rowh, h2)
    cv = Image.new('RGB', (W, y + rowh + 4), (255, 0, 255)); dr = ImageDraw.Draw(cv)
    for (lab, im), (x, y, sc) in zip(items, pos):
        cv.paste(Image.fromarray(im).resize((im.shape[1] * sc, im.shape[0] * sc), Image.NEAREST), (x, y + 12)); dr.text((x, y), lab, fill=(255, 255, 0))
    os.makedirs(os.path.join(ROOT, 'work', 'sheet'), exist_ok=True)
    cv.save(os.path.join(ROOT, 'work', 'sheet', '%s.png' % s))
    return len(items)


if __name__ == '__main__':
    for s in sys.argv[1:]: print(s, sheet(s))
