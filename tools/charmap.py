# -*- coding: utf-8 -*-
r"""에어즈 어드벤처 글꼴 번호 → 문자 표(2026-11-01)
  글꼴 = INITS.CAR 레코드 0(Low RAM 0x00200000, 108,544 B) = 16×16 1비트 3,392칸, 칸 = 32 B(줄마다 2 B, MSB 먼저)
  순서 = 기호 일부 → 숫자·영문(0x40~) → 히라가나(0x7E~) → 가타카나 → 한자 JIS 1수준 순 …
  대조: 칸마다 MS 고딕·메이리오를 크게 그린 SJIS 후보와 모양 상관(가로세로 비 감점),
        SJIS 순서가 앞으로만 가게(앞 칸에서 고른 후보 다음 W 개 안에서 고름, 창 안 최고가 전체 최고보다 많이 낮으면 전체 최고로 다시 맞춤)
  → work/charmap.tsv(번호 · 문자 · 점수 · 전체 1등 · 1등 점수) · work/charmap_sheet_NN.png(칸 + 판독, 낮은 점수 빨강)
  python tools/charmap.py
"""
import os, sys, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def font_glyphs():
    p = glob.glob(os.path.join(ROOT, 'work', 'car', 'INITS.CAR_00_*.bin'))[0]; d = open(p, 'rb').read()
    n = len(d) // 32
    return np.unpackbits(np.frombuffer(d, np.uint8)).reshape(n, 16, 16)


def candidates():
    chars = []
    for hi in list(range(0x81, 0x85)) + list(range(0x88, 0xA0)) + list(range(0xE0, 0xEB)):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F: continue
            try: ch = bytes([hi, lo]).decode('cp932')
            except UnicodeDecodeError: continue
            chars.append(ch)
    return chars


def norm(img, size=16):
    ys, xs = np.nonzero(img > 0.2)
    if len(ys) == 0: return np.zeros(size * size, np.float32), 1.0
    crop = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)
    h, w = crop.shape
    v = np.asarray(Image.fromarray((crop * 255).astype(np.uint8)).resize((size, size), Image.BILINEAR), np.float32).reshape(-1)
    v -= v.mean(); v /= (np.linalg.norm(v) + 1e-6)
    return v, (w + 1) / (h + 1)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    raw = font_glyphs(); n = len(raw)
    G, GA = zip(*[norm(raw[i].astype(float)) for i in range(n)]); G = np.stack(G); GA = np.array(GA)
    chars = candidates(); S = None
    for path in (r'C:\Windows\Fonts\msgothic.ttc', r'C:\Windows\Fonts\meiryo.ttc', r'C:\Windows\Fonts\msmincho.ttc'):
        if not os.path.exists(path): continue
        F = ImageFont.truetype(path, 32); R = []; RA = []
        for ch in chars:
            im = Image.new('L', (44, 44)); ImageDraw.Draw(im).text((4, 2), ch, font=F, fill=255)
            v, ar = norm(np.array(im) / 255.0); R.append(v); RA.append(ar)
        R = np.stack(R); RA = np.array(RA)
        s1 = G @ R.T - 0.3 * np.abs(np.log(GA[:, None] / RA[None, :]))
        S = s1 if S is None else np.maximum(S, s1)
    best = S.argmax(1)
    # 순서 지키는 최적 정렬(DP): 칸 i 에 후보 j 를 줄 때 j 는 앞 칸 후보보다 커야 함 → 점수 합 최대
    idx = [i for i in range(n) if raw[i].any()]; m = len(chars)
    prev = np.full(m, -1e9, np.float32); back = np.zeros((len(idx), m), np.int32)
    for k, i in enumerate(idx):
        if k == 0:
            cur = S[i].astype(np.float32); back[k] = -1
        else:
            pm = np.maximum.accumulate(prev)
            pa = np.maximum.accumulate(np.where(prev >= pm, np.arange(m), 0)).astype(np.int32)   # 앞쪽 최댓값 자리
            cur = np.full(m, -1e9, np.float32)
            cur[1:] = S[i, 1:] + pm[:-1]; back[k, 1:] = pa[:-1]
        prev = cur
    j = int(prev.argmax()); pick = [-1] * n
    for k in range(len(idx) - 1, -1, -1):
        pick[idx[k]] = j; j = back[k, j]
    out = os.path.join(ROOT, 'work', 'charmap.tsv')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('번호\t문자\t점수\t전체1등\t1등점수\n')
        for i in range(n):
            if pick[i] < 0: f.write('%04X\t\t0\t\t0\n' % i); continue
            j = pick[i]; b = best[i]
            f.write('%04X\t%s\t%.3f\t%s\t%.3f\n' % (i, chars[j], S[i, j], chars[b], S[i, b]))
    sc = np.array([S[i, pick[i]] for i in range(n) if pick[i] >= 0]); dis = sum(1 for i in range(n) if pick[i] >= 0 and pick[i] != best[i])
    print('칸 %d · 판독 %d · 점수 중간값 %.3f · 0.6 미만 %d · 순서판독≠전체1등 %d' % (n, len(sc), np.median(sc), (sc < 0.6).sum(), dis))
    # 검토 시트: 한 장 32×24 칸, 칸 = 글꼴(2배) + 판독 글자
    F = ImageFont.truetype(r'C:\Windows\Fonts\msgothic.ttc', 20); per = 32 * 24
    for s in range(0, n, per):
        cv = Image.new('RGB', (32 * 60, 24 * 40), (255, 255, 255)); dr = ImageDraw.Draw(cv)
        for k in range(per):
            i = s + k
            if i >= n: break
            x, y = (k % 32) * 60, (k // 32) * 40
            g = Image.fromarray((1 - raw[i]).astype(np.uint8) * 255).resize((32, 32), Image.NEAREST); cv.paste(g, (x, y + 4))
            if pick[i] >= 0:
                bad = S[i, pick[i]] < 0.6 or pick[i] != best[i]
                dr.text((x + 34, y + 10), chars[pick[i]], font=F, fill=(220, 0, 0) if bad else (0, 0, 160))
            dr.text((x, y - 1), '%X' % i, fill=(150, 150, 150))
        cv.save(os.path.join(ROOT, 'work', 'charmap_sheet_%02d.png' % (s // per)))


if __name__ == '__main__':
    main()


def final():
    """구조로 확정한 표 → work/charmap_final.tsv (번호 · 문자) — 0x01~0x3D 기호는 DP 판독, 나머지는 순서표"""
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'charmap.tsv'), encoding='utf-8')][1:]
    T = {}
    for i in range(0x01, 0x3E): T[i] = rows[i][1]
    for k, ch in enumerate('０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'): T[0x40 + k] = ch
    hira = [bytes([0x82, c]).decode('cp932') for c in range(0x9F, 0xF2)]
    hira = [c for c in hira if c not in 'ゎゐゑ']; assert len(hira) == 80
    for k, ch in enumerate(hira): T[0x7E + k] = ch
    kata = [bytes([0x83, c]).decode('cp932') for c in list(range(0x40, 0x7F)) + list(range(0x80, 0x97))]
    kata = [c for c in kata if c not in 'ヰヱ']; assert len(kata) == 84, len(kata)
    for k, ch in enumerate(kata): T[0xCE + k] = ch
    l1 = []
    for hi in range(0x88, 0x99):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F or (hi == 0x88 and lo < 0x9F): continue
            try: ch = bytes([hi, lo]).decode('cp932')
            except UnicodeDecodeError: continue
            if (hi, lo) > (0x98, 0x72): continue
            l1.append(ch)
    assert len(l1) == 2965, len(l1)
    for k, ch in enumerate(l1): T[0x122 + k] = ch
    for k, ch in enumerate('ⅠⅡⅢⅣⅤⅥ％＆'): T[0xCB7 + k] = ch
    with open(os.path.join(ROOT, 'work', 'charmap_final.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for i in sorted(T): f.write('%04X\t%s\n' % (i, T[i]))
    # 검산: DP 판독과 다른 칸 수(1수준 한자)
    diff = [(i, T[i], rows[i][1]) for i in range(0x122, 0xCB7) if rows[i][1] != T[i]]
    print('확정표', len(T), '· 1수준 DP 와 다른 칸', len(diff), diff[:10])
    return T
