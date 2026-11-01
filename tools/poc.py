# -*- coding: utf-8 -*-
r"""에어즈 어드벤처 PoC(2026-11-01, 하스피 «남은 그림 글자 찾아서 모아서 한번에 시험 poc»)
  ① 이름 입력: 판 그림(namebd) + 칸 표 + 이름 글꼴 3벌(대사 16×16 = 갈무리14 · 작은 8×10 = 갈무리7 · 큰 16×24 = 갈무리14 세로 1.5배)
  ② 그림 글자: 타이틀 메뉴 3개(TOPT NBG1 칸·맵) · 기록 칸 띠 «新しい冒険»(INFO VDP1 RGB) · 이름 제목 ヒーロー/ヒロイン/の名前を決めてください(NAMH 10)
              · 설정 제목·항목 4(CNFG NBG1)·速い普通遅い(CNFG VDP1 RGB) · 전투 명령 6(BT_INFO 7) · 경고 캡션(WARN NBG1)
  ③ 작은 글꼴 문자열 «データなし»(0.BIN 0x6B0D0, 이름 코드) → «없음»
  ④ 대사: 첫 이벤트 EV01_1_1 레코드 5(줄 칸 그대로, 줄 1:1)
  → work/build/files/<디스크 경로> + 미리보기 work/img/poc_*.png
  python tools/poc.py
"""
import os, sys, glob, struct, collections, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import car, namebd as NB, vdp2render as V, vdp1cmd, build_text as BT, autoname as AN
DISC = os.path.join(ROOT, 'work', 'disc0'); OUT = os.path.join(ROOT, 'work', 'build', 'files'); IMG = os.path.join(ROOT, 'work', 'img')
FD = r'C:\claude\utils\font'
GAL = FD + r'\Galmuri-v2.40.3\\'
NGB = FD + r'\nanum-gothic\NanumGothicBold.ttf'; NGEB = FD + r'\nanum-gothic\NanumGothicExtraBold.ttf'
T = {int(a, 16): b for a, b in (l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'charmap_final.tsv'), encoding='utf-8'))}
R = {v: k for k, v in T.items()}

SMALL_STR = [(0x6B0D0, 'データなし', '없음')]


# ───────── 글자 칸 배정 ─────────
def allocate(texts, small):
    """이름 음절(가나 칸) + 작은 글꼴에 찍히는 음절(몬스터 이름·없음 → 남는 가나 코드) + 대사 음절(1수준 끝 칸부터 거꾸로) → {음절: 대사 글꼴 칸}, {음절: 이름 코드}"""
    a, tbl = NB.assign()
    name_code = {}
    for r, cells in a.items():
        for row, col, k, s in cells:
            if s and s != 'ー': name_code[s] = k
    used = set(name_code.values()) | {0xC6}
    spare = [k for k in range(0x25, 0xC6) if k not in used]
    for t in small:
        for ch in t:
            if '가' <= ch <= '힣' and ch not in name_code: name_code[ch] = spare.pop(0)
    main = {s: NB.conv(k) for s, k in name_code.items()}
    slot = 0xCB6
    for t in texts:
        for ch in t:
            if '가' <= ch <= '힣' and ch not in main: main[ch] = slot; slot -= 1
    assert slot >= 0x122
    print('작은 글꼴 칸 남음', len(spare), '· 한자 칸 남음', slot - 0x121)
    return main, name_code, a, tbl


# ───────── 글꼴 ─────────
def bitmap(ch, font, size):
    F = ImageFont.truetype(font, size); im = Image.new('L', (40, 40)); d = ImageDraw.Draw(im); d.fontmode = '1'
    d.text((4, 4), ch, font=F, fill=255); a = np.asarray(im) > 0
    ys, xs = np.nonzero(a); return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def main_font(rec, main):
    a = np.unpackbits(np.frombuffer(rec, np.uint8)).reshape(-1, 16, 16).copy()
    for ch, k in main.items():
        g = bitmap(ch, GAL + 'Galmuri14.ttf', 15); h, w = g.shape; assert h <= 15 and w <= 15, (ch, g.shape)
        cell = np.zeros((16, 16), np.uint8); y = 1 + (14 - h) // 2; x = (15 - w) // 2; cell[y:y + h, x:x + w] = g; a[k] = cell
    a[0x19] = 0; a[0x19, 12:14, 2:4] = 1; a[0x19, 12:14, 7:9] = 1; a[0x19, 12:14, 12:14] = 1   # 말줄임표 = 바닥선 점 셋(한국식)
    return np.packbits(a.reshape(-1)).tobytes()


def row_pal(glyphs, h, shadow):
    """원본 글꼴 줄별 잉크 색 번호(그림자 번호 뺀 최빈)"""
    pal = []
    for y in range(h):
        c = collections.Counter(v for g in glyphs for v in g[y].tolist() if v not in (0, shadow))
        pal.append(c.most_common(1)[0][0] if c else None)
    last = next(p for p in pal if p is not None)
    for i, p in enumerate(pal):
        if p is None: pal[i] = last
        else: last = p
    return pal


def g4(d, o, w, h):
    a = np.frombuffer(d[o:o + w * h // 2], np.uint8); return np.stack([a >> 4, a & 15], 1).ravel().reshape(h, w).astype(int)


def p4(a):
    a = a.astype(np.uint8).ravel(); return ((a[0::2] << 4) | a[1::2]).tobytes()


def nfont(rec, name_code, w, h, shadow, render):
    """이름 글꼴(이름 코드 순 4비트) — 줄별 색 + 오른쪽 아래 그림자"""
    rec = bytearray(rec); sz = w * h // 2
    ref = [g4(rec, k * sz, w, h) for k in range(0x0A, 0x24)]                 # A~Z 줄 색
    pal = row_pal(ref, h, shadow)
    for ch, k in name_code.items():
        g = render(ch); gh, gw = g.shape
        cell = np.zeros((h, w), int); y = (h - 1 - gh) // 2; x = max(0, (w - 1 - gw) // 2)
        ink = np.zeros((h, w), bool); ink[y:y + gh, x:x + gw] = g[:min(gh, h - y), :min(gw, w - x)]
        sh = np.zeros((h, w), bool); sh[1:, 1:] = ink[:-1, :-1]; sh &= ~ink
        for yy in range(h): cell[yy][ink[yy]] = pal[yy]
        cell[sh] = shadow
        rec[k * sz:(k + 1) * sz] = p4(cell)
    return bytes(rec)


def small_glyph(ch): return bitmap(ch, GAL + 'Galmuri7.ttf', 8)


def big_glyph(ch):
    g = bitmap(ch, GAL + 'Galmuri14.ttf', 15)
    yi = (np.arange(int(g.shape[0] * 1.5)) / 1.5).astype(int); return g[yi]


# ───────── 그림 공용 ─────────
def aa(t, font, size, ss=4, sp=0):
    f = ImageFont.truetype(font, size * ss); W = int(f.getlength(t) + sp * ss * len(t)) + 8 * ss; H = size * ss * 2
    im = Image.new('L', (W, H)); d = ImageDraw.Draw(im); x = 2 * ss
    for c in t: d.text((x, size * ss // 2), c, font=f, fill=255); x += f.getlength(c) + sp * ss
    a = np.asarray(im).astype(float) / 255; ys, xs = np.nonzero(a > 0.02); a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h2, w2 = -(-a.shape[0] // ss) * ss, -(-a.shape[1] // ss) * ss
    return np.pad(a, ((0, h2 - a.shape[0]), (0, w2 - a.shape[1]))).reshape(h2 // ss, ss, w2 // ss, ss).mean((1, 3))


def fit(t, font, h, w, sp=0):
    for s in range(h * 2, 5, -1):
        g = aa(t, font, s, sp=sp)
        if g.shape[0] <= h and g.shape[1] <= w: return g
    raise AssertionError(t)


def italic(g, k=0.25):
    h, w = g.shape; out = np.zeros((h, w + int(h * k) + 1))
    for y in range(h): s = int((h - 1 - y) * k); out[y, s:s + w] = g[y]
    return out


def blend(img, g, x, y, col, shadow=None, sdx=1, sdy=1):
    h, w = g.shape
    if shadow is not None:
        reg = img[y + sdy:y + sdy + h, x + sdx:x + sdx + w]; reg[:] = reg * (1 - g[..., None]) + np.array(shadow) * g[..., None]
    reg = img[y:y + h, x:x + w]; reg[:] = reg * (1 - g[..., None]) + np.array(col) * g[..., None]


def textmask(a, lum_th=150, sat_th=70):
    lum = a.mean(2); return (lum > lum_th) & (np.abs(a[..., 0] - a[..., 2]) < sat_th)


# ── RGB16 스프라이트 ──
def rgb_sprite(rec, off, w, h):
    e = np.frombuffer(rec[off:off + w * h * 2], '>u2').reshape(h, w).astype(int)
    return e, np.stack([(e & 31) << 3, (e >> 5 & 31) << 3, (e >> 10 & 31) << 3], -1).astype(float)


def rgb_put(rec, off, e0, img):
    n = np.clip(np.rint(img / 8), 0, 31).astype(int)
    v = 0x8000 | n[..., 2] << 10 | n[..., 1] << 5 | n[..., 0]
    org = np.stack([(e0 & 31) << 3, (e0 >> 5 & 31) << 3, (e0 >> 10 & 31) << 3], -1)
    v = np.where(np.abs(img - org).max(2) < 6, e0, v); v = np.where((e0 & 0x8000) == 0, e0, v)
    rec[off:off + v.size * 2] = v.astype('>u2').tobytes()


# ── NBG1 32,768색 통그림(스테이트 렌더 → 고침 → 칸으로) ──
NBG1_LOST = [0, 0]


def nbg1_edit(state, recbuf, painter, mapbuf=None, mapaddr=0x40000):
    orig = V.load
    def load2(name):
        v, reg, cram = orig(state); v = bytearray(v); v[:len(recbuf)] = recbuf
        if mapbuf is not None: v[mapaddr:mapaddr + len(mapbuf)] = mapbuf
        return bytes(v), reg, cram
    V.load = load2
    try: im, I = V.render(state, 1)
    finally: V.load = orig
    a = np.asarray(im.convert('RGB')).astype(float)[:240, :352]; new = painter(a.copy())
    cells = I['cells']; n16 = np.clip(np.rint(new / 8), 0, 31).astype(int); ch = 0
    for cy in range(30):
        for cx in range(44):
            chn = int(cells[cy, cx]); a0 = chn * 0x20
            if a0 + 128 > len(recbuf): continue
            old = np.frombuffer(bytes(recbuf[a0:a0 + 128]), '>u2').reshape(8, 8).astype(int)
            blk = n16[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]; nb = new[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]
            if blk.shape[:2] != (8, 8): continue
            nv = 0x8000 | blk[..., 2] << 10 | blk[..., 1] << 5 | blk[..., 0]
            org = np.stack([(old & 31) << 3, (old >> 5 & 31) << 3, (old >> 10 & 31) << 3], -1)
            nv = np.where(np.abs(nb - org).max(2) < 6, old, nv)
            NBG1_LOST[0] += int(((nv != old) & ((old & 0x8000) == 0)).sum())   # 칸 안 투명 화소에 그리려다 버려진 수
            nv = np.where((old & 0x8000) == 0, old, nv)
            if (nv != old).any(): recbuf[a0:a0 + 128] = nv.astype('>u2').tobytes(); ch += 1
    NBG1_LOST[1] += int((np.abs(new - a).max(2)[cells[:30, :44] .repeat(8, 0).repeat(8, 1) == 0] > 8).sum())   # 맵에 없는 칸(빈 칸)에 그리려다 버려진 수
    return a, new, ch


# ── 타이틀 메뉴(TOPT): 레코드 0 = 칸, 레코드 1 = 맵 두 쪽(줄 0~31 기록 없음·32~63 기록 있음, 칸마다 u32 번호)
#    글자 칸만 맵에 올라 있고 글자 사이는 빈 칸 → 칸 안만 고치면 잘린다. 글자 칸 풀을 모아 맵째 다시 짠다.
TOPT_ITEMS = [('모험 선택', (17, 45)), ('기록 삭제', (49,)), ('기록 복사', (53,))]
TOPT_X0, TOPT_X1 = 9, 31                                                        # 글자 열(32~ 은 덩굴 그림)


def topt_menu(rec0, rec1, spec=TOPT_ITEMS):
    r0 = bytearray(rec0); m = np.frombuffer(rec1, '>u4').astype(np.uint32).copy().reshape(64, 64)
    rows = [t + k for _, tops in spec for t in tops for k in range(3)]
    pool = sorted({int(c) for y in rows for c in m[y, TOPT_X0:TOPT_X1] if c})
    ink = []
    for c in pool:
        e = np.frombuffer(bytes(rec0[c * 0x20:c * 0x20 + 128]), '>u2'); ink += [int(v) for v in e if v & 0x8000]
    best = collections.Counter(ink).most_common(40); e = max((v for v, _ in best), key=lambda v: (v & 31) + (v >> 5 & 31) + (v >> 10 & 31))
    col = np.array([(e & 31) << 3, (e >> 5 & 31) << 3, (e >> 10 & 31) << 3], float)
    W = (TOPT_X1 - TOPT_X0) * 8; cells = {}; free = list(pool); pics = []
    for t, tops in spec:
        syl = [italic(fit(c, NGEB, 21, 22), 0.2) for c in t.replace(' ', '')]
        cv = np.zeros((24, W)); L, R = 8, W - 8; step = (R - L - syl[-1].shape[1]) / (len(syl) - 1)
        for k, g in enumerate(syl):
            x = int(round(L + k * step)); y = (24 - g.shape[0]) // 2
            cv[y:y + g.shape[0], x:x + g.shape[1]] = np.maximum(cv[y:y + g.shape[0], x:x + g.shape[1]], g)
        n = np.clip(np.rint(cv[..., None] * col / 8), 0, 31).astype(int)
        v = 0x8000 | n[..., 2] << 10 | n[..., 1] << 5 | n[..., 0]; v = np.where(cv >= 0.12, v, 0).astype(np.uint16)
        pics.append(v)
        ids = np.zeros((3, TOPT_X1 - TOPT_X0), np.uint32)
        for cy in range(3):
            for cx in range(TOPT_X1 - TOPT_X0):
                blk = v[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]
                if not blk.any(): continue
                key = blk.tobytes()
                if key not in cells:
                    cells[key] = free.pop(0); r0[cells[key] * 0x20:cells[key] * 0x20 + 128] = blk.astype('>u2').tobytes()
                ids[cy, cx] = cells[key]
        for top in tops: m[top:top + 3, TOPT_X0:TOPT_X1] = ids
    return bytes(r0), m.astype('>u4').tobytes(), len(cells), len(pool)


def bands(a, x0, y0, x1, y1, lum_th=150, sat_th=60, gap=3):
    """영역 안 흰 글자 줄 범위 → [(y0, y1, x0, x1)]"""
    m = textmask(a, lum_th, sat_th)[y0:y1, x0:x1]; rows = np.nonzero(m.sum(1) > 0)[0]; out = []
    if not len(rows): return out
    s0 = p0 = rows[0]
    for r in list(rows[1:]) + [10 ** 6]:
        if r - p0 > gap:
            xs = np.nonzero(m[s0:p0 + 1].any(0))[0]; out.append((y0 + s0, y0 + p0 + 1, x0 + xs.min(), x0 + xs.max() + 1)); s0 = r
        p0 = r
    return out


def tex_fill(a, m, shifts=(15, 30, 45, -15, -30, 8, -8)):
    """가면 화소를 위아래로 떨어진 같은 열의 무늬로 채움(무늬 바탕용)"""
    b = a.copy(); H = a.shape[0]
    for y, x in zip(*np.nonzero(m)):
        for dy in shifts:
            yy = y + dy
            if 0 <= yy < H and not m[yy, x]: b[y, x] = a[yy, x]; break
    return b


def erase_box(a, x0, y0, x1, y1, lum_th=150, sat_th=70, grow=2, tex=False):
    m = np.zeros(a.shape[:2], bool); m[y0:y1, x0:x1] = textmask(a, lum_th, sat_th)[y0:y1, x0:x1]
    for _ in range(grow): m = NB.dil(m)
    m[:y0] = False; m[y1:] = False; m[:, :x0] = False; m[:, x1:] = False
    return (tex_fill(a, m) if tex else NB.inpaint(a, m)), m


# ───────── 대사 ─────────
CTRL = {'{주}': 0xFFFC, '{동}': 0xFFFB}


def enc_line(s, main):
    out = []; i = 0
    while i < len(s):
        if s[i] == '{':
            j = s.index('}', i); out.append(CTRL[s[i:j + 1]]); i = j + 1; continue
        c = s[i]
        if c == ' ': out.append(0)
        elif c in main: out.append(main[c])
        elif c in R: out.append(R[c])
        else:
            fw = chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c
            out.append(R[fw])
        i += 1
    return out


def dialog_rec(raw, lines, main):
    w = list(struct.unpack('>%dH' % (len(raw) // 2), raw)); n = len(w); k = 0
    for b in range(0, n, 16):
        seg = w[b:b + 14]
        t = next((i for i, x in enumerate(seg) if x in (0xFFFD, 0xFFFE, 0xFFFF)), None)
        if t is None: continue
        if not any(x for x in seg[:t]): continue                                 # 빈 줄 칸
        new = enc_line(lines[k], main); k += 1
        assert len(new) < 14, (lines[k - 1], len(new))
        term = seg[t]; body = new + [term]; body += [0] * (14 - len(body)); w[b:b + 14] = body
    assert k == len(lines), (k, len(lines))
    return struct.pack('>%dH' % n, *w)


# ───────── 빌드 ─────────
def carfile(rel):
    return car.segments(open(os.path.join(DISC, rel), 'rb').read())


def save_car(rel, segs, tail):
    p = os.path.join(OUT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(car.build(segs, tail)); return p


def recidx(segs, n):
    k = -1
    for i, s in enumerate(segs):
        if s[0] == 'rec':
            k += 1
            if k == n: return i
    raise IndexError(n)


def main():
    sys.stdout.reconfigure(encoding='utf-8'); os.makedirs(OUT, exist_ok=True); os.makedirs(IMG, exist_ok=True)
    its = list(BT.items()); mons = [k for n, j, k, l in its if '#' not in l[0]]
    main_slots, name_code, boards, tbl = allocate([k for n, j, k, l in its] + BT.E.texts(), mons + [x[2] for x in SMALL_STR])
    print('대사 글꼴 칸', len(main_slots), '· 이름 코드 음절', len(name_code))
    prev = []
    # INITS: 대사 글꼴(0) · 작은 글꼴(22)
    segs, tail = carfile('INITS.CAR')
    i0 = recidx(segs, 0); segs[i0] = ('rec', segs[i0][1], main_font(segs[i0][2], main_slots))
    i22 = recidx(segs, 22); sf = nfont(segs[i22][2], name_code, 8, 10, 0xF, small_glyph); segs[i22] = ('rec', segs[i22][1], sf)
    i25 = recidx(segs, 25); assert len(segs[i25][2]) == len(sf); segs[i25] = ('rec', segs[i25][1], sf)   # 작은 글꼴 사본(0x2022CF00)
    save_car('INITS.CAR', segs, tail)
    # NAMH: 표 5·6 · 제목 조각 10 · 판 그림 12
    _, _, bufs, conflict = NB.build(); assert not conflict
    segs, tail = carfile('Y_BSLCT/BUP_NAMH.CAR')
    for n in (5, 6):
        i = recidx(segs, n); segs[i] = ('rec', segs[i][1], bytes(tbl['%02d' % n]))
    i8 = recidx(segs, 8); segs[i8] = ('rec', segs[i8][1], AN.apply(segs[i8][2], name_code))         # «맡김» 기본 이름
    nh = [k for k in bufs if 'NAMH' in k][0]; nk = [k for k in bufs if 'NAMK' in k][0]
    i = recidx(segs, 12); segs[i] = ('rec', segs[i][1], bytes(bufs[nh]))
    i = recidx(segs, 10); r10 = bytearray(segs[i][2])
    pieces = [(0, 72, '주인공'), (72 * 12, 72, '히로인'), (72 * 12 * 2 + 72 * 12 * 0, None, None)]
    # 조각: 0 = ヒーロー(72×24), 864 = ヒロイン(72×24), 1728 = の名前を決めてください(184×24)
    for off, w, t in ((0, 72, '주인공'), (864, 72, '히로인'), (1728, 184, '의 이름을 정해 주세요')):
        g0 = g4(r10, off, w, 24)
        plate = collections.Counter(g0.ravel().tolist()).most_common(1)[0][0]
        rows = np.nonzero((g0 != plate).any(1))[0]; y0t, y1t = rows.min(), rows.max()
        g = italic(fit(t, NGB, y1t - y0t + 1, w - 6), 0.25)
        g = g[:, np.nonzero((g > 0.08).any(0))[0].min():np.nonzero((g > 0.08).any(0))[0].max() + 1]   # 잉크만
        cell = np.where(g0 == 0, 0, plate).astype(int); y = y0t; x = 0 if w == 184 else w - g.shape[1]   # 두 조각이 맞닿음(주인공 72 + 뒷말 184) → 이름은 오른쪽 맞춤
        hh, ww = g.shape; ww = min(ww, w - x - 1); hh = min(hh, 24 - y)
        lv = np.rint(plate - g[:hh, :ww] * (plate - 1)).astype(int)
        reg = cell[y:y + hh, x:x + ww]; reg[:] = np.where(g[:hh, :ww] > 0.08, np.minimum(reg, lv), reg)
        r10[off:off + w * 12] = p4(cell); prev.append(('이름 제목 %s' % t, np.kron(np.stack([g0 * 16] * 3, -1), np.ones((2, 2, 1))), np.kron(np.stack([cell * 16] * 3, -1), np.ones((2, 2, 1)))))
    segs[i] = ('rec', segs[i][1], bytes(r10))
    save_car('Y_BSLCT/BUP_NAMH.CAR', segs, tail)
    segs, tail = carfile('Y_BSLCT/BUP_NAMK.CAR'); i = recidx(segs, 5); segs[i] = ('rec', segs[i][1], bytes(bufs[nk]))
    i = recidx(segs, 3); assert len(segs[i][2]) == len(r10); segs[i] = ('rec', segs[i][1], bytes(r10))   # 히로인 묶음에 같은 제목 사본
    save_car('Y_BSLCT/BUP_NAMK.CAR', segs, tail)
    t0 = g4(r10, 0, 72, 24); t1 = g4(r10, 864, 72, 24); t2 = g4(r10, 1728, 184, 24)
    Image.fromarray(np.kron(np.concatenate([np.concatenate([t0, t2], 1), np.concatenate([t1, t2], 1)], 0).astype(np.uint8) * 16, np.ones((3, 3), np.uint8))).save(os.path.join(IMG, 'prev_nametitle.png'))
    # INFO: 큰 글꼴(3) · 기록 칸 띠(1·2 의 0x0)
    segs, tail = carfile('Y_BSLCT/BUP_INFO.CAR')
    i = recidx(segs, 3); r3 = bytearray(segs[i][2]); SM0 = 0xA800                              # 큰 글꼴 224칸 × 192 B(0 부터, s6 스프라이트로 검산) · 작은 글꼴 사본 +0xA800
    r3[:SM0] = nfont(bytes(r3[:SM0]), name_code, 16, 24, 1, big_glyph); assert len(r3) - SM0 == len(sf)
    r3[SM0:] = sf; bigrec = bytes(r3); segs[i] = ('rec', segs[i][1], bigrec)
    for n in (1, 2):
        i = recidx(segs, n); r = bytearray(segs[i][2]); e0, img = rgb_sprite(r, 0, 192, 56)
        o = img.copy(); img, m = erase_box(img, 20, 8, 172, 50, 170, 60, 2)
        g = italic(fit('새로운 모험', NGEB, 26, 150), 0.2); col = np.percentile(o[m], 90, axis=0) if m.any() else (255, 255, 255)
        blend(img, g, (192 - g.shape[1]) // 2, (56 - g.shape[0]) // 2, col, (120, 60, 120))
        rgb_put(r, 0, e0, img); segs[i] = ('rec', segs[i][1], bytes(r))
        if n == 1: prev.append(('기록 칸 띠', o, img))
    save_car('Y_BSLCT/BUP_INFO.CAR', segs, tail)
    # WARN: 큰 글꼴(1) · 캡션(2, 맵 3)
    segs, tail = carfile('Y_BSLCT/BUP_WARN.CAR')
    i = recidx(segs, 1); segs[i] = ('rec', segs[i][1], bigrec)
    i2 = recidx(segs, 2); i3 = recidx(segs, 3); r2 = bytearray(segs[i2][2])
    def warn_paint(a):
        # 원본 세로 글(x 5~14, y 9~217)을 흰 띠로 덮고 검은 글자를 칸 가운데 찍음(하스피 지시, 부드러운 글꼴)
        # 칸 0 은 화면 밖 빈자리에도 쓰이는 공용 칸이라 못 고침 → 띠는 줄 1(y 8)부터, 원본 잉크는 y 9~
        X0, X1, Y0, Y1 = 3, 18, 8, 220; b = a.copy(); b[Y0:Y1, X0:X1] = 255
        t = '무심코 애마에게 태클을 거는 헨리'; STEP, GAP, SS = 13, 7, 4
        F = ImageFont.truetype(NGB, 13 * SS); W_ = X1 - X0
        y = Y0 + ((Y1 - Y0) - sum(GAP if c == ' ' else STEP for c in t)) // 2
        for c in t:
            if c == ' ': y += GAP; continue
            im = Image.new('L', (W_ * SS, STEP * SS)); ImageDraw.Draw(im).text((W_ * SS / 2, STEP * SS / 2), c, font=F, fill=255, anchor='mm')
            al = np.asarray(im.resize((W_, STEP), Image.BOX)).astype(float)[..., None] / 255
            reg = b[y:y + STEP, X0:X1]; reg[:] = reg * (1 - al); y += STEP
        return b
    o, n_, chg = nbg1_edit('s8', r2, warn_paint, segs[i3][2]); segs[i2] = ('rec', segs[i2][1], bytes(r2)); prev.append(('경고 캡션', o, n_))
    save_car('Y_BSLCT/BUP_WARN.CAR', segs, tail)
    # TOPT: 타이틀 «冒険を選ぶ»
    segs, tail = carfile('Y_BSLCT/BUP_TOPT.CAR'); i0_ = recidx(segs, 0); i1_ = recidx(segs, 1)
    r0, r1, nc, np_ = topt_menu(segs[i0_][2], segs[i1_][2]); print('타이틀 메뉴 칸', nc, '/', np_)
    segs[i0_] = ('rec', segs[i0_][1], r0); segs[i1_] = ('rec', segs[i1_][1], r1); save_car('Y_BSLCT/BUP_TOPT.CAR', segs, tail)
    # CNFG: 제목·항목(1) · 버튼(0)
    segs, tail = carfile('Y_BSLCT/BUP_CNFG.CAR'); i = recidx(segs, 1); r = bytearray(segs[i][2])
    def cnfg(a):
        bd = [x for x in bands(a, 4, 4, 340, 230, 190, 40, 2) if 6 <= x[1] - x[0] <= 24 and x[3] - x[2] > 40]
        print('설정 글자 줄', bd)
        texts = ['설정 변경', '메시지 속도', '컨트롤러 표시', '전투 메시지', '전투 카메라']
        b = a.copy()
        for (y0, y1, x0, x1), t in zip(bd, texts):
            col = np.percentile(a[y0:y1, x0:x1][textmask(a, 190, 40)[y0:y1, x0:x1]], 90, axis=0)
            b, m = erase_box(b, x0 - 3, y0 - 3, x1 + 4, y1 + 4, 165, 50, 2, tex=True)
            g = italic(fit(t, NGEB if t == texts[0] else NGB, y1 - y0 + 2, 200), 0.25)
            x = (x0 + x1) // 2 - g.shape[1] // 2 if t == texts[0] else x0
            blend(b, g, x, (y0 + y1) // 2 - g.shape[0] // 2, col, (60, 30, 20))
        return b
    o, n_, chg = nbg1_edit('s8', r, cnfg); segs[i] = ('rec', segs[i][1], bytes(r)); prev.append(('설정', o, n_))
    i = recidx(segs, 0); r = bytearray(segs[i][2])
    for off, t in ((0x3000, '빠름'), (0x3780, '빠름'), (0x3F00, '보통'), (0x4680, '보통'), (0x4E00, '느림'), (0x5580, '느림')):   # 안 고른 칸·고른 칸(빨강) 두 벌씩
        e0, img = rgb_sprite(r, off, 40, 24); o = img.copy()
        lum = img.mean(2); m = (lum > 170); m[:3] = m[-3:] = False; m[:, :4] = m[:, -4:] = False
        for _ in range(1): m = NB.dil(m)
        img = NB.inpaint(img, m); g = italic(fit(t, NGEB, 14, 30), 0.2)
        blend(img, g, 20 - g.shape[1] // 2, 12 - g.shape[0] // 2, (255, 255, 255), (0, 0, 0))
        rgb_put(r, off, e0, img); prev.append(('버튼 ' + t, o, img))
    segs[i] = ('rec', segs[i][1], bytes(r)); save_car('Y_BSLCT/BUP_CNFG.CAR', segs, tail)
    # BT_INFO 7: 전투 명령
    segs, tail = carfile('BT_INFO.CAR'); i = recidx(segs, 7); r = bytearray(segs[i][2])
    for off, w, t in ((0x11C0, 24, '공격'), (0x1280, 24, '방어'), (0x1340, 24, '도구'), (0x1400, 32, '도망'), (0x1500, 24, '전진'), (0x15C0, 24, '후퇴')):
        g0 = g4(r, off, w, 16); vals = collections.Counter(g0.ravel().tolist()); vals.pop(0, None)
        bright = max(vals); dark = min(vals)
        g = bitmap(t, GAL + 'Galmuri11.ttf', 12)
        if g.shape[1] > w - 2: g = bitmap(t, GAL + 'Galmuri9.ttf', 10)
        cell = np.zeros_like(g0); hh, ww = g.shape; y = max(0, (13 - hh) // 2); x = (w - 1 - ww) // 2
        ink = np.zeros(g0.shape, bool); ink[y:y + hh, x:x + ww] = g
        sh = np.zeros_like(ink); sh[1:, 1:] = ink[:-1, :-1]; sh &= ~ink
        cell[sh] = 2; cell[ink] = 1
        r[off:off + w * 8] = p4(cell)
        prev.append(('전투 ' + t, np.kron(np.stack([g0 * 16] * 3, -1), np.ones((3, 3, 1))), np.kron(np.stack([cell * 16] * 3, -1), np.ones((3, 3, 1)))))
    segs[i] = ('rec', segs[i][1], bytes(r)); save_car('BT_INFO.CAR', segs, tail)
    # 0.BIN 작은 글꼴 문자열
    b = bytearray(open(os.path.join(DISC, '0.BIN'), 'rb').read())
    for off, jp, kr in SMALL_STR:
        n = len(jp); new = [name_code[c] for c in kr]; pad = (n - len(new)) // 2
        seq = [0x24] * pad + new + [0x24] * (n - len(new) - pad)
        b[off:off + n] = bytes(seq)
    for off in (0x3A388, 0x3A516):                                                # 능력 화면 攻·防 = 코드 안 글꼴 번호 2개
        assert b[off:off + 4] == bytes.fromhex('04850B34'); b[off:off + 4] = struct.pack('>HH', main_slots['공'], main_slots['방'])
    open(os.path.join(OUT, '0.BIN'), 'wb').write(b)
    BT.apply(main_slots, name_code, OUT)
    print('NBG1 버려진 화소: 투명 칸', NBG1_LOST[0], '· 빈 칸', NBG1_LOST[1])
    # 미리보기
    tiles = []
    for lab, o, n_ in prev:
        o = np.clip(o, 0, 255).astype(np.uint8); n_ = np.clip(n_, 0, 255).astype(np.uint8)
        tiles.append((lab, np.concatenate([o, np.full((o.shape[0], 4, 3), 255, np.uint8), n_], 1)))
    W = max(t.shape[1] for _, t in tiles); H = sum(t.shape[0] + 14 for _, t in tiles)
    cv = Image.new('RGB', (W, H), (40, 40, 40)); d = ImageDraw.Draw(cv); y = 0
    for lab, t in tiles: cv.paste(Image.fromarray(t), (0, y + 14)); y += t.shape[0] + 14
    cv.save(os.path.join(IMG, 'poc_gfx.png'))
    print('파일', sorted(os.path.relpath(p, OUT) for p in glob.glob(os.path.join(OUT, '**', '*'), recursive=True) if os.path.isfile(p)))


if __name__ == '__main__':
    main()
