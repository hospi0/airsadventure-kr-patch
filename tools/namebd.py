# -*- coding: utf-8 -*-
r"""에어즈 어드벤처 이름 입력판 한글화(2026-11-01, 하스피 «이름입력판부터»)
  · 가나판 2장(판1 = 히라가나판 표 NAMH 레코드 5 / 스테이트 s5, 판2 = 가타카나판 표 레코드 6 / s4) → 한글 음절판 2장(59 + 59 = 118)
  · 칸 → 이름 코드: 원래 가나 칸은 그 코드 그대로, 빈칸(24)·゛゜(F0 F1) 칸은 판에 없던 가나 코드로 바꿈, ー(C6) 칸은 그대로
  · 이름 코드 → 대사 글꼴 칸: 25~7A +59 · 7B = 11F(ヴ) · 7C~C2 +58 · C3~C5 +59
  · 판 그림 = NAMH 레코드 12(VDP2 VRAM 0, NBG1 32,768색 칸 128 B) — 칸 공유(두 판 321칸) 충돌 검사
  python tools/namebd.py   → work/build/car/…(⏳) + work/img/prev_namebd.png
"""
import os, sys, glob, collections
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import vdp2render as V

SYL = ('하 스 피 김 이 박 최 정 강 조 윤 장 임 한 오 서 신 권 황 안 송 류 홍 고 문 양 손 배 백 유 남 심 노 곽 성 차 주 우 구 민 진 지 채 원 천 현 도 소 석 선 설 마 길 연 위 명 기 라 금 은 예 경 수 영 준 호 훈 희 아 나 다 미 혜 숙 태 동 상 재 철 승 규 빈 율 린 솔 별 슬 결 람 루 리 레 로 티 키 케 코 크 트 르 베 비 세 시 제 즈 엘 렌 론 드 니 네 카 사 바 파 에 '
       '토 테 투 프 포 모 무 메 미 디 데 두 보 부 브 너 누 느 가 그 거 게 후 히 헤 즈').split()
# 몬스터 이름 작은 글꼴은 가나 칸(161)만 그림 → 몬스터 음절 133 이 이름판 110 + 빈 칸 안에 들게 맞바꿈(2026-11-01)
SWAP_OUT = '곽권규금길람론류린별빈석설손솔송숙심양엘예율윤제차채천철최키티혜홍황훈경배백남동승준'
SWAP_IN = '가거그근내네니대더데래러머메모무버번병부빌사살어언요운인일자타탄터테파프해휴플틀치적'
FD = r'C:\claude\utils\font'
NMB = FD + r'\nanum-myeongjo\NanumMyeongjoExtraBold.ttf'


def syllables(n=110):
    out = []
    for s in SYL:
        if s not in out: out.append(s)
    assert len(out) >= n, len(out)
    out = out[:n]; assert all(c in out for c in '하스피')
    out = [c for c in out if c not in SWAP_OUT] + list(SWAP_IN); assert len(set(out)) == n, len(set(out))
    return sorted(out)


def conv(k):
    if 0x25 <= k <= 0x7A or 0xC3 <= k <= 0xC5: return k + 0x59
    if k == 0x7B: return 0x11F
    if 0x7C <= k <= 0xC2: return k + 0x58
    raise ValueError(hex(k))


def tables():
    t = {}
    for r in ('05', '06'):
        p = glob.glob(os.path.join(ROOT, 'work', 'car', 'Y_BSLCT_BUP_NAMH.CAR_%s_*' % r))[0]
        t[r] = bytearray(open(p, 'rb').read())
    return t


def assign():
    """→ {판: [(줄, 칸, 코드, 음절)]}, 새 표"""
    t = tables(); syl = syllables(); used = set()
    for r in ('05', '06'):
        for o in range(0, 66, 11): used.update(b for b in t[r][o:o + 10])
    spare = [k for k in range(0x25, 0xC6) if k not in used]
    out = {}; i = 0
    for r in ('05', '06'):
        cells = []
        for row in range(6):
            for col in range(10):
                k = t[r][row * 11 + col]
                if k == 0xC6: cells.append((row, col, k, 'ー')); continue
                if k == 0x24: cells.append((row, col, k, None)); continue                       # 두 판 공유 빈칸 — 그대로
                if k in (0xF0, 0xF1): t[r][row * 11 + col] = 0x24; cells.append((row, col, 0x24, '')); continue   # ゛゜ → 빈칸(그림도 지움, 두 판 같음)
                cells.append((row, col, k, syl[i])); i += 1
        out[r] = cells
    assert i == len(syl)
    return out, t


def grid(img):
    """판 그림(원본)에서 글자 줄·칸 중심 — 흰 글자 화소 투영"""
    a = np.asarray(img).astype(int); lum = a.mean(2); m = (lum > 170) & (np.abs(a[..., 0] - a[..., 2]) < 70)
    m[:50] = False; m[:, :18] = False
    def clusters(v, gap):
        idx = np.nonzero(v)[0]; out = []; s = idx[0]; p = idx[0]
        for x in list(idx[1:]) + [10 ** 6]:
            if x - p > gap: out.append((s, p)); s = x
            p = x
        return out
    rows = [r for r in clusters(m.sum(1) > 3, 2) if r[1] - r[0] >= 8]
    return m, rows


_K = ['한글2', '영문', '다음', '지우기', '맡김', '끝']; _J = ['한글1', '영문', '다음', '지우기', '맡김', '끝']; _E = ['한글2', '한글1', '다음', '지우기', '맡김', '끝']
CMD = {'05': _K, '06': _J, 'HE': _E, 'K05': _K, 'K06': _J, 'EN': _E}
# 판 = (묶음, 맵 쪽, 칸 표) · 주인공 NAMH(붉은 판) / 히로인 NAMK(초원) · 맵 레코드 = 쪽마다 0x2000 칸에 [크기][LZSS 2중 압축], 쪽 0 영문·1 히라가나·2 가타카나(스테이트 s4·s5·s6·ha·hb 100% 일치)
BOARDS = {'05': ('H', 1, '05'), '06': ('H', 2, '06'), 'HE': ('H', 0, None), 'K05': ('K', 1, '05'), 'K06': ('K', 2, '06'), 'EN': ('K', 0, None)}
REGS = 's4'
GREEN = ('K05', 'K06', 'EN')
_REC = {}


def board_data(f):
    if f not in _REC:
        import struct, car
        n = {'H': 'BUP_NAMH', 'K': 'BUP_NAMK'}[f]; recs = [x for x in car.segments(open(os.path.join(ROOT, 'work', 'disc0', 'Y_BSLCT', n + '.CAR'), 'rb').read())[0] if x[0] == 'rec']
        rec, m = (recs[12][2], recs[7][2]) if f == 'H' else (recs[5][2], recs[0][2])
        _REC[f] = (rec, [car.lz_dec(m, p + 4, struct.unpack_from('>I', m, p)[0])[0] for p in (0, 0x2000, 0x4000)])
    return _REC[f]


def render_board(board, rec=None):
    """원본 레코드(또는 rec)·판 맵으로 NBG1 렌더 → (RGB 352×240, 정보)"""
    f, pg, _ = BOARDS[board]; r0, pages = board_data(f); rec = r0 if rec is None else rec
    orig = V.load
    def load2(name):
        v, reg, cram = orig(name); v = bytearray(v); v[:len(rec)] = rec; v[0x40000:0x44000] = pages[pg]; return bytes(v), reg, cram
    V.load = load2
    try: im, I = V.render(REGS, 1)
    finally: V.load = orig
    return im, I


PAINT_LOST = {}
FIT = {}
CX = lambda c: 32 + 24 * c
CY = lambda r: 71 + 24 * r


def render_txt(t, size, font=NMB, ss=4):
    f = ImageFont.truetype(font, size * ss); W = int(f.getlength(t)) + 8 * ss; H = size * ss * 2
    im = Image.new('L', (W, H)); ImageDraw.Draw(im).text((2 * ss, size * ss // 2), t, font=f, fill=255)
    a = np.asarray(im).astype(float) / 255; ys, xs = np.nonzero(a > 0.02); a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h2, w2 = -(-a.shape[0] // ss) * ss, -(-a.shape[1] // ss) * ss
    return np.pad(a, ((0, h2 - a.shape[0]), (0, w2 - a.shape[1]))).reshape(h2 // ss, ss, w2 // ss, ss).mean((1, 3))


def inpaint(a, m):
    a = a.copy(); m = m.copy()
    while m.any():
        k = ~m; s_ = np.zeros_like(a); c = np.zeros(m.shape)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            ks = np.roll(np.roll(k, dy, 0), dx, 1); s_ += np.roll(np.roll(a, dy, 0), dx, 1) * ks[..., None]; c += ks
        f = m & (c > 0)
        if not f.any(): break
        a[f] = s_[f] / c[f][:, None]; m &= ~f
    return a


def dil(m):
    p = np.pad(m, 1); r = p.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1): r |= np.roll(np.roll(p, dy, 0), dx, 1)
    return r[1:-1, 1:-1]


SHARED = None


def shared_mask(board):
    """이 판 화면에서 다른 판과 같이 쓰는 칸 자리(8×8 단위) → 화소 가면"""
    global SHARED
    if SHARED is None:
        SHARED = {}
        c = {b: render_board(b)[1]['cells'][:30, :44] for b in BOARDS}
        for b in BOARDS:
            other = set()
            for b2 in BOARDS:
                if b2 != b and BOARDS[b2][0] == BOARDS[b][0]: other |= set(c[b2].ravel().tolist())
            SHARED[b] = np.kron(np.isin(c[b], list(other)), np.ones((8, 8), bool))
    return SHARED.get(board)


def tex_fill(a, m):
    """초원 무늬: 가면 화소를 가까운 안 가린 화소로(뭉갬 대신 결 유지)"""
    out = a.copy(); rem = m.copy()
    for d in (13, 11, 17, 7, 23):
        for dy, dx in ((0, d), (0, -d), (d, 0), (-d, 0), (d, d), (-d, -d), (d, -d), (-d, d)):
            src = np.roll(a, (dy, dx), (0, 1)); f = rem & ~np.roll(m, (dy, dx), (0, 1)); out[f] = src[f]; rem &= ~f
    return inpaint(out, rem) if rem.any() else out


def paint(board, cells):
    """원본 판 그림(RGB, 352×240) → 한글 판 그림"""
    im, I = render_board(board); a = np.asarray(im.crop((0, 0, 352, 240))).astype(float)
    green = board in GREEN; notg = (a[..., 1] - a[..., 0] < 35) if green else np.ones(a.shape[:2], bool)
    lum = a.mean(2); txt = (lum > 140) & (np.abs(a[..., 0] - a[..., 2]) < 80) & notg
    area = np.zeros(txt.shape, bool)
    if cells and not green: area[58:212, 18:262] = True
    if cells and green:                                                          # 초원: 꽃 점을 살리려고 글자 칸 안만
        for r, c_, k, t in cells:
            if t not in ('ー', None): area[CY(r) - 11:CY(r) + 12, CX(c_) - 12:CX(c_) + 13] = True
    for row in range(6):                                                         # ー 칸은 그대로
        for r, c_, k, t in (cells or []):
            if r == row and t in ('ー', None): area[CY(row) - 10:CY(row) + 11, CX(c_) - 11:CX(c_) + 12] = False
    cmd = np.zeros(txt.shape, bool); cmd[58:212, 258:306] = True
    er = dil(dil(txt & area)) | dil(dil(((lum > 110) & (np.abs(a[..., 0] - a[..., 2]) < 90) & notg) & cmd)); out = tex_fill(a, er) if green else inpaint(a, er)
    col = np.percentile(a[txt & (area | cmd)], 97, axis=0)
    ink = np.zeros(a.shape[:2], bool); sm = shared_mask(board); fit = FIT.setdefault(board, [])
    def put(t, cx, cy, size, maxw, private=False):
        best = None
        for sz in range(size, 10, -1):
            g = render_txt(t, sz)
            if g.shape[1] > maxw: continue
            for dy in (0, -1, 1):
                for dx in (0, -1, 1):
                    y = int(round(cy - g.shape[0] / 2)) + dy; x = int(round(cx - g.shape[1] / 2)) + dx
                    m = np.zeros(ink.shape, bool); gm = g > 0.05; m[y:y + g.shape[0], x:x + g.shape[1]] |= gm; m[y + 1:y + 1 + g.shape[0], x + 1:x + 1 + g.shape[1]] |= gm
                    over = int((m & sm).sum()) if (private and sm is not None) else 0
                    if best is None or over < best[0]: best = (over, sz, g, y, x)
                    if over == 0: break
                if best[0] == 0: break
            if best and best[0] == 0: break
        over, size, g, y, x = best; fit.append((t, size, over))
        reg = out[y + 1:y + 1 + g.shape[0], x + 1:x + 1 + g.shape[1]]; reg[:] = reg * (1 - 0.6 * g[..., None])      # 그림자
        reg = out[y:y + g.shape[0], x:x + g.shape[1]]; reg[:] = reg * (1 - g[..., None]) + col * g[..., None]
        ink[y:y + g.shape[0] + 1, x:x + g.shape[1] + 1] |= np.pad(g > 0.05, ((0, 1), (0, 1))) | np.pad(g > 0.05, ((1, 0), (1, 0)))
    if cells:
        for row, c, k, t in cells:
            if t in ('ー', None, ''): continue
            put(t, CX(c), CY(row), 17, 20, private=True)
    for row, t in enumerate(CMD[board]):
        put(t, 284, CY(row), 14, 40)
    sm = shared_mask(board)
    if sm is not None:                                                           # 공유 칸에 번진 새 글자 획은 원래 그림으로 되돌림(잘림 수 셈)
        lost = int((ink & sm).sum()); out[sm] = a[sm] if False else out[sm]
        keep = sm & ink; out[keep] = inpaint_orig[keep] if False else out[keep]
        PAINT_LOST[board] = lost
    return a, np.clip(out, 0, 255), I, ink


def to_cells(rec, I, new, orig_v):
    """바뀐 화소가 든 칸만 RGB16 으로 → {칸 번호: 128 B}"""
    cells = I['cells']; out = {}
    n16 = np.clip(np.rint(new / 8), 0, 31).astype(int)
    for cy in range(30):
        for cx in range(44):
            chn = int(cells[cy, cx]); a0 = chn * 0x20
            old = np.frombuffer(orig_v[a0:a0 + 128], '>u2').reshape(8, 8).astype(int)
            blk = n16[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]
            if blk.shape[:2] != (8, 8): continue
            nv = 0x8000 | blk[..., 2] << 10 | blk[..., 1] << 5 | blk[..., 0]
            nv = np.where((old & 0x8000) == 0, old, nv)
            orgc = np.stack([(old & 31) << 3, (old >> 5 & 31) << 3, (old >> 10 & 31) << 3], -1)
            same = np.abs(np.clip(new[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8], 0, 255) - orgc).max(2) < 6
            nv = np.where(same, old, nv)                                          # 안 바뀐 화소는 원래 값 그대로
            out[chn] = (nv.astype('>u2').tobytes(), bool((nv != old).any()))
    return out


def build():
    """판을 차례로: 공유 칸은 먼저 정한 내용을 따르고, 새 글자 획(그림자 포함)이 닿는 공유 칸만 충돌"""
    a, t = assign()
    nh = glob.glob(os.path.join(ROOT, 'work', 'car', 'Y_BSLCT_BUP_NAMH.CAR_12_*'))[0]
    nk = glob.glob(os.path.join(ROOT, 'work', 'car', 'Y_BSLCT_BUP_NAMK.CAR_05_*'))[0]
    decided = collections.defaultdict(dict); inked = collections.defaultdict(dict); conflict = []; prev = []; bufs = {}; labels = collections.defaultdict(dict)
    for board, (f, pg, tb) in BOARDS.items():
        src = nh if f == 'H' else nk
        if src not in bufs: bufs[src] = bytearray(open(src, 'rb').read())
        v = bytes(open(src, 'rb').read())
        o, n, I, ink = paint(board, a.get(tb))
        cells = I['cells']
        for chn, (b, ch) in to_cells(None, I, n, v).items():
            pos = np.argwhere(cells[:30, :44] == chn)[0]; cy, cx = pos
            has_ink = ink[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8].any()
            cmd_lab = CMD[board][(cy * 8 + 4 - 59) // 24] if cx >= 32 and has_ink else None   # 명령 칸: 판이 달라도 글자가 같으면 충돌 아님(바탕 결만 다름)
            if chn in decided[src]:
                if decided[src][chn] != b:
                    if has_ink and inked[src][chn]:
                        if cmd_lab is None or labels[src].get(chn) != cmd_lab: conflict.append((board, hex(chn)))
                    elif has_ink: decided[src][chn] = b; inked[src][chn] = True; labels[src][chn] = cmd_lab
                continue
            decided[src][chn] = b; inked[src][chn] = has_ink; labels[src][chn] = cmd_lab
        prev.append(o)
    for src, d in decided.items():
        for chn, b in d.items(): bufs[src][chn * 0x20:chn * 0x20 + 128] = b
    print('충돌 칸(두 판 글자가 같은 칸)', len(conflict), conflict[:10])
    # 미리보기 = 고친 레코드로 다시 그림
    rows = []
    for board, o in zip(BOARDS, prev):
        src = nh if BOARDS[board][0] == 'H' else nk
        n = np.asarray(render_board(board, bytes(bufs[src]))[0].crop((0, 0, 352, 240))).astype(float)
        rows.append(np.concatenate([o[:224], np.full((224, 4, 3), 255.0), n[:224]], 1))
    rr = [np.concatenate(rows[i:i + 3], 0) for i in (0, 3)]
    Image.fromarray(np.concatenate([rr[0], np.full((672, 6, 3), 255.0), rr[1]], 1).astype(np.uint8)).save(os.path.join(ROOT, 'work', 'img', 'prev_namebd.png'))
    return a, t, bufs, conflict


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    a, t = assign()
    for r, cells in a.items():
        print('판', r, ''.join(s or '□' for _, _, _, s in cells))
    os.makedirs(os.path.join(ROOT, 'work', 'img'), exist_ok=True)
    build()
