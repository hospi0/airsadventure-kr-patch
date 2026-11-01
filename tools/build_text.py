# -*- coding: utf-8 -*-
r"""전체 문장 빌더(2026-11-01): work/text/ko.tsv → 글자 코드로 레코드에 씀
  python tools/build_text.py --verify  → 원문을 넣어 원본 바이트 재현 검사(아무것도 안 씀)
  poc.main() 이 그림·글꼴을 만든 뒤 apply(main_slots, out) 호출 → work/build/files
"""
import os, re, sys, glob, json, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import extract as X, merge_ko as M, trcheck as C, car, extra_text as E
DISC = os.path.join(ROOT, 'work', 'disc0'); CARD = os.path.join(ROOT, 'work', 'car')
T = X.T; R = {}
for k, v in sorted(T.items(), reverse=True): R[v] = k
TW = {'{주인공}': [0xFFFC], '{동료}': [0xFFFB], '{값}': [0xFFF6], '{선택}': [0xFFF9], '{선택끝}': [0xFFEA], '{선택끝3}': [0xFFFA], '{／}': [0x16]}


def enc(s, main):
    out = []; i = 0
    while i < len(s):
        c = s[i]
        if c == '{':
            j = s.index('}', i); t = s[i:j + 1]; i = j + 1
            if t in TW: out += TW[t]
            else: out += [int(x, 16) for x in t[1:-1].split(':')]
            continue
        i += 1
        if c in ' 　': out.append(0)
        elif c in main: out.append(main[c])
        elif c in R: out.append(R[c])
        else:
            fw = '～' if c == '~' else chr(ord(c) + 0xFEE0) if '!' <= c < '~' else c
            out.append(R[fw])
    return out


def load_rec(src, rec):
    p = glob.glob(os.path.join(CARD, '%s.CAR_%s_*' % (src, rec)))[0]
    d = open(p, 'rb').read(); return list(struct.unpack('>%dH' % (len(d) // 2), d[:len(d) // 2 * 2])), d, p


class Rec:
    def __init__(s, src, rec):
        s.src, s.rec = src, rec; s.w0, s.raw, s.path = load_rec(src, rec); s.w = list(s.w0); s.ends = None; s.tech = {}

    def dial(s):
        if s.ends is None:
            s.keep = tuple(s.w0); r = X.dialog(s.keep, True); s.ends = {a: X.DIALOG_END[(id(s.keep), a)] for a, _, _ in r}
        return s.ends


def end_words(s):
    for tok, w in (('{선택끝}', [0xFFEA]), ('{선택끝3}', [0xFFFA])):
        if s.endswith(tok): return s[:-len(tok)], w
    m = re.search(r'\{(FFE[EF]):([0-9A-F]{4})\}$', s)
    if m: return s[:m.start()], [int(m[1], 16), int(m[2], 16)]
    return s, None


def put_dialog(r, st, text, main):
    e = r.dial()[st]
    m = re.match(r'[ァ-ヺ]あ', text)
    if m and st % 16 == 14: text = text[2:]; st += 2
    if st % 16: raise ValueError('칸 경계 아님 %X' % st)
    first = st // 16; w = r.w; body, tail = end_words(text)
    if tail is None: tail = [r.w0[e]]
    pages = body.split('{쪽}'); n = len(pages)
    for c in range(first, first + 2 * n):
        w[c * 16:c * 16 + 14] = [0] * 14
    for p, pg in enumerate(pages):
        ls = pg.split('／')
        if len(ls) > 2: raise ValueError('쪽 3줄')
        for k, l in enumerate(ls):
            q = enc(l, main)
            if k < len(ls) - 1: q.append(0xFFFD)
            elif p < n - 1: q.append(0xFFFE)
            else: q += tail
            if len(q) > 14: raise ValueError('줄 넘침 %d' % len(q))
            b = (first + 2 * p + k) * 16; w[b:b + len(q)] = q


def put_string(r, st, new, main):
    """FFFF 끝 문자열: 앞 빈칸 유지, 뒤는 다음 글 앞까지 0"""
    w = r.w; i = st
    while r.w0[i] != 0xFFFF: i += 1
    j = i + 1
    while j < len(w) and r.w0[j] == 0: j += 1
    lead = 0
    while r.w0[st + lead] == 0: lead += 1
    body = enc(new, main); lead = max(0, min(lead, j - st - len(body) - 1))     # 칸이 모자라면 앞 빈칸부터 줄임
    q = [0] * lead + body
    if len(q) <= i - st: q += [0] * (i - st - len(q))                           # 끝 코드 자리 유지(원문 뒤 채움 그대로)
    q.append(0xFFFF)
    if len(q) > j - st: raise ValueError('칸 넘침')
    w[st:j] = q + [0] * (j - st - len(q))


def put_field(w, r0, b, n, new, main):
    q = enc(new, main)
    if len(q) > n: raise ValueError('필드 넘침')
    old = r0[b:b + n]; last = old[-1]
    fill = last if last in (0, 0xFFFF) else 0
    if 0xFFFF in old and fill == 0 and len(q) < n: q = q + [0xFFFF]
    w[b:b + n] = q + [fill] * (n - len(q))


def apply_loc(rs, loc, text, main):
    m = re.match(r'(.+)#(\d\d):([0-9A-F]+)(?:\.(.+?))?(?:\(.*)?$', loc)
    src, rec, off, sub = m[1], m[2], int(m[3], 16) // 2, m[4]
    r = rs.setdefault((src, rec), Rec(src, rec)); cat = M.C_cat(loc)
    if cat == 'dialog': put_dialog(r, off, text, main)
    elif cat == 'cp':
        ls = text.split('／'); ls += [''] * (3 - len(ls)); new = []
        for l in ls:
            q = enc(l, main); new += q + [0] * (8 - len(q))
        if 0xFFFF in r.w0[off:off + 24]:
            k = max([i + 1 for i in range(24) if new[i]] or [0])
            if k < 24: new[k] = 0xFFFF
        r.w[off:off + 24] = new
    elif sub == '이름6': put_field(r.w, r.w0, off + 4, 6, text, main)
    elif sub == '설명12': put_field(r.w, r.w0, off + 10, 12, text, main)
    elif sub == '장비': put_field(r.w, r.w0, off + 1, 21, text, main)
    elif sub in ('기술', '기술설명'): r.tech.setdefault(off, {})[sub] = text
    elif cat == 'shop':
        j = off
        while j < len(r.w0) and r.w0[j] >= 0x40: j += 1
        q = enc(text, main)
        if len(q) > j - off: raise ValueError('상점 칸')
        r.w[off:j] = q + [0] * (j - off - len(q))
    else: put_string(r, off, text, main)


def finish_tech(rs, main):
    for r in rs.values():
        for off, d in r.tech.items():
            old = r.w0[off + 1:off + 22]; lead = 0
            while old[lead] == 0: lead += 1
            q = [0] * lead + enc(d.get('기술', ''), main) + [0] + enc(d.get('기술설명', ''), main)
            if len(q) > 21: raise ValueError('기술 %X' % off)
            r.w[off + 1:off + 22] = q + [0] * (21 - len(q))


def items():
    jp, _, _ = C.load()
    ko = dict(l.split('\t', 1) for l in open(os.path.join(ROOT, 'work', 'text', 'ko.tsv'), encoding='utf-8').read().split('\n') if l)
    L = json.load(open(os.path.join(ROOT, 'work', 'text', 'locs.json'), encoding='utf-8'))
    for n, (loc, s) in jp.items(): yield n, s, ko[n], L[s]


def verify():
    sys.stdout.reconfigure(encoding='utf-8')
    rs = {}; err = collections.Counter(); mon = 0
    for n, s, k, locs in items():
        for loc in locs:
            if '#' not in loc: mon += 1; continue
            try: apply_loc(rs, loc, s, {})
            except Exception as e:
                err[type(e).__name__ + ' ' + str(e)[:24]] += 1
                if sum(err.values()) < 12: print(n, loc, repr(e))
    finish_tech(rs, {})
    bad = 0; tot = collections.Counter()
    for (src, rec), r in sorted(rs.items()):
        d = [i for i in range(len(r.w)) if r.w[i] != r.w0[i]]
        if d:
            bad += 1; tot[M.C_cat('%s#%s:0' % (src, rec))] += len(d)
            if bad <= 14: print(src, rec, len(d), [(hex(i * 2), '%04X>%04X' % (r.w0[i], r.w[i])) for i in d[:4]])
    print('레코드', len(rs), '다른 레코드', bad, dict(tot), '오류', err.most_common(8), '몬스터', mon)


def apply_extra(rs, main):
    g = lambda src, rec: rs.setdefault((src, rec), Rec(src, rec))
    r = g('BT_INFO', '00')
    for o, t in E.BT.items(): put_string(r, o // 2, t, main)
    for src in ('CP_MAIN', 'INDOOR_CP_MAIN', 'TOWN_CP_MAIN'):
        r = g(src, '03')
        for o, t in E.CP.items(): put_string(r, o // 2, t, main)
    for p in glob.glob(os.path.join(CARD, 'INDOOR_I*_2021AC00.bin')):
        b = os.path.basename(p); r = g(b.split('.CAR_')[0], b.split('.CAR_')[1][:2])
        if r.w0[0x3C0 // 2] != 0xFFF0: continue
        for o, t in E.INDOOR.items(): put_dialog(r, o // 2, t, main)
    r = g('INITS', '01')
    for o, (a, b_) in E.ITEMS.items():
        put_field(r.w, r.w0, o // 2 + 4, 6, a, main); put_field(r.w, r.w0, o // 2 + 10, 12, b_, main)
    for f in ('Y_BSLCT_BUP_INFO', 'Y_BSLCT_BUP_WARN'):
        r = g(f, '00'); put_field(r.w, r.w0, 0x860 // 2, 16, '용량 부족으로 새 기록 불가', main)
    r = g('INITS', '02')
    for k, t in enumerate(E.PLACES): put_field(r.w, r.w0, k * 6, 6, E.slot(t), main)
    for o, t in E.PLACES2.items(): put_field(r.w, r.w0, o // 2, 6, E.slot(t), main)


def disc_path(src):
    for dp, _, fs in os.walk(DISC):
        for f in fs:
            if f.upper().endswith('.CAR'):
                rel = os.path.relpath(os.path.join(dp, f), DISC).replace(os.sep, '/')
                if rel[:-4].replace('/', '_') == src: return rel
    raise KeyError(src)


def apply(main, name_code, out):
    rs = {}; mon = []
    for n, s, k, locs in items():
        for loc in locs:
            if '#' in loc: apply_loc(rs, loc, k, main)
            else: mon.append((loc, k))
    finish_tech(rs, main); apply_extra(rs, main)
    by = collections.defaultdict(dict)
    for (src, rec), r in rs.items():
        if r.w != r.w0: by[src][int(rec)] = struct.pack('>%dH' % len(r.w), *r.w) + r.raw[len(r.w) * 2:]
    for src, recs in by.items():
        rel = disc_path(src); o = os.path.join(out, rel); p = o if os.path.exists(o) else os.path.join(DISC, rel)
        segs, tail = car.segments(open(p, 'rb').read()); k = -1
        for i, x in enumerate(segs):
            if x[0] == 'rec':
                k += 1
                if k in recs: assert len(x[2]) == len(recs[k]); segs[i] = ('rec', x[1], recs[k])
        os.makedirs(os.path.dirname(o), exist_ok=True); open(o, 'wb').write(car.build(segs, tail))
    for loc, k in mon:
        f, off = loc.split('(')[0].split(':'); off = int(off, 16)
        assert all(c in name_code for c in k if '가' <= c <= '힣'), k
        o = os.path.join(out, 'BATTLE', f + '.MAX'); d = bytearray(open(os.path.join(DISC, 'BATTLE', f + '.MAX'), 'rb').read())
        e = off
        while d[e:e + 2] != bytes((255, 255)): e += 2
        q = enc(k, main)
        if len(q) > 8: raise ValueError(loc)
        q = q + [0xFFFF] + [0] * max(0, (e - off) // 2 - len(q)); d[off:off + len(q) * 2] = struct.pack('>%dH' % len(q), *q)
        nb = [0x24 if c == ' ' else name_code[c] for c in k]; assert len(nb) <= 8, k     # 전투 화면 작은 글꼴 이름 = 16비트 이름 앞 8 B(이름 코드, FF 채움)
        d[off - 8:off] = bytes(nb + [0xFF] * (8 - len(nb)))
        os.makedirs(os.path.dirname(o), exist_ok=True); open(o, 'wb').write(d)
    print('문장 레코드', sum(len(v) for v in by.values()), '· 파일', len(by), '· 몬스터', len(mon))


if __name__ == '__main__' and '--verify' in sys.argv: verify()
