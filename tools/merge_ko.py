# -*- coding: utf-8 -*-
r"""번역 병합(2026-11-01): my files/번역 → 정규화 → 말 조판 → work/text/ko.tsv + work/text/unfit.tsv(사람이 고칠 것)
  규칙: 토큰은 원문 순서·개수 그대로 · 대사 = 쪽 수 유지(말 = 번호×64 B)·쪽당 2줄·줄 13칸 · 얼굴이 바뀌는 쪽 경계는 못 넘김
  python tools/merge_ko.py
"""
import os, re, sys, json, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import trcheck as C, extract as X
MAXW = 13; TW = {'{주인공}': 6, '{동료}': 6, '{FFF0}': 6, '{FFF2}': 3, '{값}': 3}
HARD = re.compile(r'\{(?!쪽\})[^{}]*\}')
FIX = os.path.join(ROOT, 'work', 'text', 'ko_fix.tsv')                          # 번호\t손으로 고친 번역


def w_of(s):
    n = 0; i = 0
    while i < len(s):
        if s[i] == '{':
            j = s.index('}', i); n += TW.get(s[i:j + 1], 0 if s[i:j + 1].startswith(('{FFE', '{선택')) else 1); i = j + 1
        else: n += 1; i += 1
    return n


TERMS = [('팩 님', '퍽 님'), ('마그놀리스', '마그노리스'), ('반함초', '연모초'), ('넬마드', '네르마드'), ('마리로', '마릴로'), ('생제르맹', '상제르미')]


def squeeze(s):
    for a, b in TERMS: s = s.replace(a, b)
    s = s.replace('　', ' ').replace('......', '……').replace('...', '…').replace('·', '・').replace('ーッ', 'ー').replace('、', ',')
    s = re.sub('…{2,}', '…', s)                                                  # 말줄임표는 한 칸(하스피 전프로젝트 규칙)
    for q in ('"', "'"):                                                            # 글꼴에 없음 → 원문 괄호 「」(번갈아)
        parts = s.split(q)
        if len(parts) > 1: s = ''.join(a + ('「' if i % 2 == 0 else '」') if i < len(parts) - 1 else a for i, a in enumerate(parts))
    return re.sub(r'([！？!?…。、，,.，：:])[ 　]+(?=\S)', r'\1', s)


def atoms(p):
    """쪽 글 → 끊을 수 있는 조각: 공백은 조각 사이 공백, 부호 뒤는 공백 없이 끊김 가능"""
    out = []
    for i, w in enumerate(p.split(' ')):
        parts = re.findall(r'.+?[！？!?…。、，,.]+(?=[^！？!?…。、，,.」』）]|$)|.+$', w)
        for k, a in enumerate(parts): out.append((a, k == 0 and i > 0))
    return out


def wrap(p, maxl, width=MAXW):
    """DP: 줄 수 ≤ maxl, 줄 폭 ≤ width → 줄 목록 또는 None — 줄 길이 고르게"""
    A = atoms(p); n = len(A); best = {n: (0, [])}
    for i in range(n - 1, -1, -1):
        cur = ''; opts = None
        for j in range(i, n):
            cur = cur + ((' ' if A[j][1] else '') if j > i else '') + A[j][0]
            if w_of(cur) > width: break
            if j + 1 in best:
                c, ls = best[j + 1]
                if len(ls) + 1 <= maxl:
                    cost = c + (width - w_of(cur)) ** 2
                    if opts is None or cost < opts[0]: opts = (cost, [cur] + ls)
        if opts: best[i] = opts
    return best[0][1] if 0 in best else None


def flat(s): return re.sub(r'\s*／\s*', ' ', s).strip()


def faces(loc):
    m = re.match(r'(.+)#(\d\d):([0-9A-F]+)', loc)
    if not m: return None
    ps = glob.glob(os.path.join(ROOT, 'work', 'car', '%s.CAR_%s_*' % (m[1], m[2])))
    if not ps: return None
    return X.words(ps[0]), int(m[3], 16) // 2


def page_faces(w, s0, n):
    return [w[s0 + 32 * i - 2] if s0 + 32 * i - 2 >= 0 else 0 for i in range(n)]


REFLOW = []


def layout(ko, jp, loc):
    """앞머리(얼굴 [번호][あ]가 문장으로 잡힌 プあ·ヘあ)는 조판에서 빼고 되붙임"""
    m = re.match(r'[ァ-ヺ]あ', jp)
    pre = m[0] if m and ko.startswith(m[0]) else ''
    new, why = layout2(ko[len(pre):], jp[len(pre):], loc)
    return (pre + new if new is not None else None), why


def layout2(ko, jp, loc):
    """→ (새 번역, None) 또는 (None, 사유)"""
    pj = jp.split('{쪽}'); pk = [p for p in ko.split('{쪽}')]; n = len(pj)
    if len(pk) != n:                                                             # 번역이 쪽을 바꿈 → 말 전체 다시
        pk = None
    if pk:
        if all(all(w_of(l) <= MAXW for l in p.split('／')) and p.count('／') <= 1 for p in pk): return ko, None
        res = []
        for p in pk:
            ls = p.split('／')
            if len(ls) <= 2 and all(w_of(l) <= MAXW for l in ls): res.append(p); continue
            r = wrap(flat(p), 2)
            if r is None: res = None; break
            res.append('／'.join(r))
        if res: return '{쪽}'.join(res), None
    # 쪽을 넘겨 다시 접지 않음(문장이 쪽 중간에서 끊김) — 사람이 쪽에 맞춰 고침
    return None, '쪽 안에 안 들어감' if pk else '쪽 수 다름'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    jp, ko, bad = C.load(); assert not bad
    fix = {}
    if os.path.exists(FIX):
        for l in open(FIX, encoding='utf-8').read().split('\n'):
            if l.strip() and not l.startswith('#'): a, b = l.split('\t'); fix[a] = b
    res = {}; unfit = []; ch = 0
    for n, (loc, s) in jp.items():
        k = fix.get(n, ko[n]); k = squeeze(k)
        res[n] = k
        cat = C_cat(loc)
        if cat != 'dialog' and '　' in ko[n]: res[n] = k = squeeze(fix.get(n, ko[n])).replace(' ', '　') if '　' in s else k
        tk = HARD.findall(s), HARD.findall(k)
        if tk[0] != tk[1]: unfit.append((n, loc, '토큰 다름', s, k)); continue
        if cat == 'cp':
            ls = k.split('／')
            if len(ls) > 3 or any(w_of(x) > 8 for x in ls):
                r = wrap(flat(k), 3, 8)
                if r: res[n] = '／'.join(r)
        if cat == 'dialog':
            new, why = layout(k, s, loc)
            if new is None: unfit.append((n, loc, why, s, k)); continue
            if new != k: ch += 1
            res[n] = new
    with open(os.path.join(ROOT, 'work', 'text', 'ko.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for n in jp: f.write('%s\t%s\n' % (n, res[n]))
    with open(os.path.join(ROOT, 'work', 'text', 'unfit.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for u in unfit: f.write('\t'.join(u) + '\n')
    # 대사 밖 예산
    slots = json.load(open(os.path.join(ROOT, 'work', 'text', 'locs.json'), encoding='utf-8'))
    over = []
    for n, (loc, s) in jp.items():
        cat = C_cat(loc); k = res[n]
        if cat == 'dialog': continue
        lim = {'cp': 8, 'name6': 6, 'desc12': 12, 'monster': 8}.get(cat)
        ls = k.split('／'); ms = max(w_of(x) for x in s.split('／'))
        if cat == 'cp' and (len(ls) > 3 or any(w_of(x) > 8 for x in ls)): over.append((n, loc, 'cp', s, k))
        elif cat in ('name6', 'desc12', 'monster') and w_of(k) > lim: over.append((n, loc, cat, s, k))
        elif cat == 'equip' and '.기술' not in loc and w_of(k) > 21: over.append((n, loc, cat, s, k))
        elif cat in ('bt', 'menu', 'bsel', 'shop') or '.기술' in loc:
            room = min(slot_room(x) for x in slots[s])
            if '.기술' not in loc and tok_words(k) > room: over.append((n, loc, '%s 칸 %d < %d' % (cat, room, tok_words(k)), s, k))
    with open(os.path.join(ROOT, 'work', 'text', 'over.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for u in over: f.write('\t'.join(u) + '\n')
    print('대사 밖 초과', len(over), collections.Counter(u[2].split(' ')[0] for u in over))
    print('쪽 넘겨 다시 접음', len(REFLOW))
    lo = set(REFLOW)
    with open(os.path.join(ROOT, 'work', 'text', 'reflow.tsv'), 'w', encoding='utf-8', newline=chr(10)) as f:
        for n, (loc, s) in jp.items():
            if loc in lo: f.write(n + chr(9) + s + chr(9) + res[n] + chr(10))
    print('다시 접음', ch, '· 안 맞음', len(unfit), collections.Counter(u[2].split(' ')[0] for u in unfit))
    return jp, res, unfit


_W = {}


def tok_words(s):
    n = 0; i = 0
    while i < len(s):
        if s[i] == '{': i = s.index('}', i) + 1; n += 1
        else: n += 1; i += 1
    return n


def slot_room(loc):
    """문자열 시작부터 다음 비0 글(다음 문자열) 앞까지 워드 수 − 끝 코드 1"""
    m = re.match(r'(.+)#(\d\d):([0-9A-F]+)', loc)
    if not m: return 999
    k = (m[1], m[2])
    if k not in _W: _W[k] = X.words(glob.glob(os.path.join(ROOT, 'work', 'car', '%s.CAR_%s_*' % k))[0])
    w = _W[k]; i = int(m[3], 16) // 2
    while i < len(w) and w[i] != 0xFFFF and w[i] != 0: i += 1
    if i < len(w) and w[i] == 0:                                                # 0 이 끼면 칸 안 빈칸 — 끝까지 감
        while i < len(w) and w[i] != 0xFFFF: i += 1
    j = i + 1
    while j < len(w) and w[j] == 0: j += 1
    return j - int(m[3], 16) // 2 - 1


def C_cat(loc):
    s = loc.split('(')[0]
    if ':' in s and '#' not in s: return 'monster'
    for key, c in (('CP_MAIN#02', 'cp'), ('.이름6', 'name6'), ('.설명12', 'desc12'), ('.장비', 'equip'), ('.기술', 'equip')):
        if key in s: return c
    if 'CP_' in s.split('#')[0]: return 'menu'
    if s.startswith('INITS#08'): return 'shop'
    if s.startswith('Y_BSLCT'): return 'bsel'
    if s.startswith('BT_INFO'): return 'bt'
    if s.startswith(('INITS', 'CP')): return 'menu'
    return 'dialog'


if __name__ == '__main__':
    main()
