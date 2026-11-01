# -*- coding: utf-8 -*-
r"""병합표 work/text/ko.tsv 최종 검산(2026-11-01): 토큰·쪽 수·쪽당 줄·줄 폭·글꼴·일본어 잔존"""
import os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import trcheck as C, merge_ko as M
sys.stdout.reconfigure(encoding='utf-8')
jp, _, _ = C.load()
ko = dict(l.split('\t', 1) for l in open(os.path.join(ROOT, 'work', 'text', 'ko.tsv'), encoding='utf-8').read().split('\n') if l)
T = {int(a, 16): b for a, b in (l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'charmap_final.tsv'), encoding='utf-8'))}
R = set(T.values()); e = collections.Counter(); ex = []
syl = set(); badch = collections.Counter()
for n, (loc, s) in jp.items():
    k = ko[n]; c = M.C_cat(loc); body = re.sub(r'\{[^{}]*\}', '', k)
    if M.HARD.findall(s) != M.HARD.findall(k): e['토큰'] += 1; ex.append(n)
    if c == 'dialog':
        pj = s.count('{쪽}'); pk = k.count('{쪽}')
        if pj != pk: e['쪽 수'] += 1; ex.append(n)
        for p in k.split('{쪽}'):
            if p.count('／') > 1: e['쪽당 3줄'] += 1; ex.append(n)
            if any(M.w_of(l) > 13 for l in p.split('／')): e['줄 폭'] += 1; ex.append(n)
        if re.search(r'^／|／$|／\{쪽\}|\{쪽\}／', k): e['빈 줄'] += 1; ex.append(n)
    if re.search(r'[ぁ-ゖァ-ヺ]', body): e['가나'] += 1; ex.append(n)
    for ch in body:
        if '가' <= ch <= '힣': syl.add(ch)
        elif ch not in ' ／' and ch not in R:
            fw = chr(ord(ch) + 0xFEE0) if '!' <= ch <= '~' else ch
            if fw not in R: badch[ch] += 1
print('오류', dict(e), ex[:12]); print('음절', len(syl), '글꼴에 없는 글자', badch.most_common(20))
print('행', len(ko), '번역과 같은 행', sum(1 for n in jp if ko[n] == jp[n][1]))
