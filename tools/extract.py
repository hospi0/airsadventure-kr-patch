# -*- coding: utf-8 -*-
r"""에어즈 어드벤처 문장 추출(2026-11-01) → work/text/jp.tsv(전체) + my files/tsv/aa_NNN.tsv(18KB 단위, 번호·위치·JP·KO)
  ① 대사 레코드(주소 0x2021AC00·0x2021DF00, 이벤트·마을·실내): 16워드 줄 칸, 줄 = 칸 경계부터 끝 코드까지
     말 = FFFF 까지(줄 FFFD → «／», 쪽 FFFE → «{쪽}»), 얼굴 머리(칸 14·15 워드)는 위치 정보로만(번역 칸에 안 넣음)
  ①′ CP_MAIN 레코드 2(0x202EF000) = 동료 잡담 말풍선: 말 = 8워드 줄 × 3(48 B 고정 칸, 줄바꿈 코드 없음) → 줄 사이 «／», 줄당 8칸 제한
  ② 메뉴·아이템·전투 문구 레코드(0x2021C700·0x202EF900·0x202EF000·0x06038000·BT_INFO): FFFF 끝 문자열
  ③ 전투 MAX 몬스터 이름(파일 0x778)
  토큰: {동료}=FFFB · {주인공}=FFFC · {쪽}=FFFE · ／=FFFD · {선택}=FFF9 · {선택끝}=FFEA · {값}=FFF6 · {FFxx}=그 밖 · {／}=진짜 ／ · 　=0x0000(빈칸)
  같은 원문은 한 줄로 묶음(위치 = 첫 위치, ×N) — 전체 위치는 work/text/locs.json
  python tools/extract.py
"""
import os, sys, glob, struct, json, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CAR = os.path.join(ROOT, 'work', 'car'); DISC = os.path.join(ROOT, 'work', 'disc0')
TSV_DIR = os.path.join(ROOT, 'my files', 'tsv'); TXT = os.path.join(ROOT, 'work', 'text')
LIMIT = 18 * 1024
T = {int(a, 16): b for a, b in (l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'charmap_final.tsv'), encoding='utf-8'))}
TOK = {0xFFFB: '{동료}', 0xFFFC: '{주인공}', 0xFFFE: '{쪽}', 0xFFFD: '／', 0xFFF9: '{선택}', 0xFFEA: '{선택끝}', 0xFFF6: '{값}'}
END = (0xFFFF, 0xFFF0)
DIALOG = (0x2021AC00, 0x2021DF00)
MENU = (0x2021C700, 0x202EF900, 0x202EF000, 0x06038000)


def ch(x):
    if x == 0: return '　'
    if x == 0x16: return '{／}'
    if x in TOK: return TOK[x]
    if x >= 0xFF00: return '{%04X}' % x
    return T.get(x, '{%04X}' % x)


ARG = (0xFFEF, 0xFFEE)                                                             # 뒤 워드 하나를 인자로 가지는 코드


def text(seq):
    out = []; i = 0
    while i < len(seq):
        x = seq[i]
        if x in ARG and i + 1 < len(seq): out.append('{%04X:%04X}' % (x, seq[i + 1])); i += 2; continue
        out.append(ch(x)); i += 1
    return ''.join(out)


def words(p):
    d = open(p, 'rb').read(); return struct.unpack('>%dH' % (len(d) // 2), d[:len(d) // 2 * 2])


KEEP = (0xFFFC, 0xFFF6, 0xFFF9, 0xFFFB, 0xFFF5, 0xFFF7, 0xFFF2, 0xFFF1)


def is_hdr(w, b0):
    """칸 b0 의 14·15 워드가 줄 머리인가: [얼굴(<0x100)][60~7F] 또는 [0][FF00]"""
    a, b = w[b0 + 14], w[b0 + 15]
    return (b == 0xFF00 and a == 0) or (0x60 <= b <= 0x7F and a < 0x100)


DIALOG_END = {}                                                                     # (id(w), 시작) → 말 끝 코드 위치(build_text 용)


def dialog(w, more=False):
    """→ [(시작 워드, 머리(얼굴), 문장)] — 줄은 칸 경계에서 시작, 끝 코드 뒤 다음 칸으로"""
    out = []; pos = 0; cur = []; cur_start = 0; cur_hdr = None; n = len(w)
    while pos < n:
        if not cur: cur_start = pos; cur_hdr = tuple(w[pos - 2:pos]) if pos >= 2 else ()
        b0 = pos // 16 * 16
        lim = b0 + 14 if b0 + 15 < n and is_hdr(w, b0) else n               # 칸 끝 2워드가 머리면 본문은 14워드까지
        i = pos
        while i < n and not (w[i] >= 0xFFE0 and w[i] not in KEEP and not (more and w[i] == 0xFFF0 and any(w[i + 1:]))) and w[i] != 0xFF00:
            if i >= lim:
                break
            i += 1
        if i >= lim and i < n and not (w[i] >= 0xFFE0 and w[i] not in KEEP and not (more and w[i] == 0xFFF0 and any(w[i + 1:]))):    # 끝 코드 없이 머리에 닿음 = 다음 칸으로 이어지는 줄
            line = w[pos:i]
            while line and line[-1] == 0: line = line[:-1]
            cur.append(text(line)); pos = b0 + 16; continue
        if i >= n: break
        line = w[pos:i]
        # 줄 앞 채움(0)은 빈칸이 아니라 정렬일 수 있음 — 끝 0 만 버림
        while line and line[-1] == 0: line = line[:-1]
        cur.append(text(line))
        t = w[i]
        if t == 0xFF00:                         # 머리 자리에 닿음(본문 없는 칸) — 다음 칸으로
            if not cur[-1]: cur.pop()
            pos = (i // 16 + 1) * 16; continue
        if t in ARG and i + 1 < n:                                          # 아이템 획득 등(인자 1워드) = 말 끝
            cur.append('{%04X:%04X}' % (t, w[i + 1])); i += 1
        if t == 0xFFFA: cur.append('{선택끝3}')
        if t == 0xFFFD: cur.append('／')
        elif t == 0xFFFE: cur.append('{쪽}')
        elif t == 0xFFEA: cur.append('{선택끝}')
        if t in END or t in (0xFFEA, 0xFFEF, 0xFFEE, 0xFFFA):
            s = ''.join(cur).strip('　')
            if s: out.append((cur_start, cur_hdr, s)); DIALOG_END[(id(w), cur_start)] = i
            cur = []
            if t == 0xFFF0: break
        pos = (i // 16 + 1) * 16
        while pos < n and not any(w[pos:pos + 14]) and (pos + 15 >= n or is_hdr(w, pos) or not any(w[pos:pos + 16])): pos += 16   # 빈 칸(쪽 넘김 뒤 둘째 줄 등)
    return out


def strings(w, minlen=1):
    out = []; start = 0
    for i, v in enumerate(w):
        if v == 0xFFFF:
            seg = w[start:i]; s0 = start; start = i + 1
            t = [x for x in seg if x]
            kana = sum(1 for x in t if 0x7E <= x <= 0xCB6); good = sum(1 for x in t if 0x01 <= x <= 0xCBE or x in TOK)
            if len(t) >= minlen and kana >= 1 and good >= 0.9 * len(t):
                out.append((s0, text(seg).strip('　')))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(TXT, exist_ok=True); os.makedirs(TSV_DIR, exist_ok=True)
    items = []                                   # (위치, 원문)
    for p in sorted(glob.glob(os.path.join(CAR, '*.bin'))):
        b = os.path.basename(p); a = int(b.rsplit('_', 1)[1][:8], 16); src = b.split('.CAR_')[0]; rec = b.split('.CAR_')[1][:2]
        if a in DIALOG and not src.startswith('BT_INFO'):
            for s0, hdr, s in dialog(words(p)):
                if len(s) == 2 and s[1] == 'あ': continue                     # 얼굴 머리 [얼굴][007F] 만 남은 것
                items.append(('%s#%s:%04X' % (src, rec, s0 * 2), s))
        elif src == 'INITS' and rec == '01':                                # 아이템 표: [값 번호 ? 종류][이름 6워드][설명 12워드](44 B) · 기술 표: [1000][이름·조작 0끝][설명 0끝](44 B)
            w = words(p); o = 0
            def fld(seq, mn):
                q = list(seq)
                while q and q[-1] in (0xFFFF, 0): q.pop()
                if len(q) < mn or any(not (0x01 <= x < 0xCBF) for x in q) or not any(x >= 0x7E for x in q): return None
                return text(q)
            for e in range(0x1080 // 2, len(w), 22):                          # 장비 이름: [값][이름 0끝] (0x1080 부터 44 B)
                q = [x for x in w[e + 1:e + 22]]
                q = q[:q.index(0)] if 0 in q else q
                if q: items.append(('%s#%s:%04X.장비' % (src, rec, e * 2), text(q)))
            while o + 22 <= len(w):
                if w[o] == 0x1000 and o * 2 >= 0xF00:                         # 기술
                    seg = list(w[o + 1:o + 22]); parts = []; cur = []
                    for x in seg:
                        if x == 0:
                            if cur: parts.append(cur); cur = []
                        else: cur.append(x)
                    if cur: parts.append(cur)
                    if len(parts) >= 2:
                        items.append(('%s#%s:%04X.기술' % (src, rec, o * 2), text(parts[0]))); items.append(('%s#%s:%04X.기술설명' % (src, rec, o * 2), text(parts[1])))
                    o += 22; continue
                a = fld(w[o + 4:o + 10], 2); b = fld(w[o + 10:o + 22], 3)
                if a and b and (w[o + 3] & 0x0FFF) in (0, 3) and o * 2 < 0xF40:
                    items.append(('%s#%s:%04X.이름6' % (src, rec, o * 2), a)); items.append(('%s#%s:%04X.설명12' % (src, rec, o * 2), b)); o += 22
                else: o += 1
        elif src == 'INITS' and rec == '08':                                # 상점 메뉴: 0 으로 나뉜 고정 칸(FFFF 없음) — 칸 = 다음 글자 전까지
            w = words(p); i = 0
            while i < len(w):
                if w[i] == 0 or w[i] < 0x40: i += 1; continue
                j = i
                while j < len(w) and w[j] >= 0x40: j += 1
                items.append(('%s#%s:%04X' % (src, rec, i * 2), text(w[i:j]))); i = j
        elif src.endswith('CP_MAIN') and rec == '02':                     # 동료 잡담 말풍선: 말 = 8워드 줄 × 3 (48 B 고정 칸)
            w = words(p)
            for k in range(0, len(w) - 23, 24):
                ls = []
                for j in range(3):
                    ln = list(w[k + j * 8:k + j * 8 + 8])
                    if 0xFFFF in ln: ln = ln[:ln.index(0xFFFF)]
                    while ln and ln[-1] == 0: ln.pop()
                    ls.append(''.join(ch(x) for x in ln))
                t = '／'.join(ls).rstrip('／')
                if t: items.append(('%s#%s:%04X' % (src, rec, k * 2), t))
        elif (a in MENU or src.split('_')[-1].startswith(('BT_INFO', 'INITS', 'CP_', 'BUP_')) or src.startswith(('BT_INFO', 'INITS', 'CP_', 'Y_BSLCT'))) and a != 0x20200000 and a >> 24 != 0x25 and not (src == 'INITS' and rec == '05'):
            for s0, s in strings(words(p)): items.append(('%s#%s:%04X' % (src, rec, s0 * 2), s))
    for p in sorted(glob.glob(os.path.join(DISC, 'BATTLE', '*.MAX'))):
        d = open(p, 'rb').read(); w = struct.unpack('>24H', d[0x770:0x7A0])
        ok = lambda x: 0x7E <= x <= 0xCB6 or x in (0x05, 0x13)
        best = (0, 0)
        for a in range(len(w)):
            b = a
            while b < len(w) and ok(w[b]): b += 1
            b = min(b, a + 8)                                                     # 이름 칸 = 8워드
            if b - a > best[1] - best[0]: best = (a, b)
        if best[1] - best[0] >= 2:
            items.append(('%s:%04X' % (os.path.basename(p)[:-4], 0x770 + best[0] * 2), ''.join(ch(x) for x in w[best[0]:best[1]])))
    locs = collections.OrderedDict()
    for loc, s in items: locs.setdefault(s, []).append(loc)
    json.dump(locs, open(os.path.join(TXT, 'locs.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    rows = ['%05d\t%s(×%d)\t%s\t' % (k + 1, v[0], len(v), s) for k, (s, v) in enumerate(locs.items())]
    head = '번호\t위치\tJP\tKO\n'
    open(os.path.join(TXT, 'jp.tsv'), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(rows) + '\n')
    # 18KB 단위로 나눔(자투리는 앞 묶음에 합침 — pop 먼저)
    chunks = []; cur = []; size = len(head.encode())
    for r in rows:
        b = len((r + '\n').encode())
        if cur and size + b > LIMIT: chunks.append(cur); cur = []; size = len(head.encode())
        cur.append(r); size += b
    if cur: chunks.append(cur)
    if len(chunks) > 1 and sum(len((r + '\n').encode()) for r in chunks[-1]) < LIMIT // 4:
        last = chunks.pop(); chunks[-1] += last
    for f in glob.glob(os.path.join(TSV_DIR, 'aa_*.tsv')): os.remove(f)
    for k, c in enumerate(chunks):
        open(os.path.join(TSV_DIR, 'aa_%03d.tsv' % (k + 1)), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(c) + '\n')
    nums = [int(r.split('\t')[0]) for c in chunks for r in c]; assert nums == list(range(1, len(rows) + 1))
    print('위치 %d · 고유 문장 %d · 글자 %d · TSV %d개' % (len(items), len(rows), sum(len(s) for s in locs), len(chunks)))


if __name__ == '__main__':
    main()
