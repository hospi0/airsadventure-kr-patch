# -*- coding: utf-8 -*-
r"""받은 번역(my files/번역/aa_*.tsv) 정규화·검사(2026-11-01) — 번호·원문 대조, 토큰·줄 수·쪽 수·줄 폭. python tools/trcheck.py → 요약 + work/text/trcheck.tsv"""
import os, re, sys, glob, json, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = re.compile(r'\{[^{}]*\}|／')


def load():
    jp = {}
    for l in open(os.path.join(ROOT, 'work', 'text', 'jp.tsv'), encoding='utf-8').read().split('\n')[1:]:
        if l: n, loc, s, _ = l.split('\t'); jp[n] = (loc, s)
    ko = {}; bad = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'my files', '번역', 'aa_*.tsv'))):
        for ln, l in enumerate(open(p, encoding='utf-8-sig').read().split('\n')[1:], 2):
            if not l: continue
            c = l.split('\t')
            if len(c) != 4 or c[0] not in jp or jp[c[0]][1] != c[2]: bad.append((os.path.basename(p), ln, l[:80])); continue
            if c[0] in ko: bad.append((os.path.basename(p), ln, '중복 ' + c[0]))
            ko[c[0]] = c[3]
    return jp, ko, bad


def seq(s): return [t for t in TOK.findall(s)]
def width(line): return len(TOK.sub(lambda m: 'X' * 1, line))
def kind(loc):
    if '#' in loc:
        pass
    return loc


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    jp, ko, bad = load(); print('원문', len(jp), '번역', len(ko), '형식 불량', len(bad), bad[:5])
    print('빈 번역', sum(1 for n in jp if not ko.get(n, '').strip()))
    locs = json.load(open(os.path.join(ROOT, 'work', 'text', 'locs.json'), encoding='utf-8'))
    # 줄 폭 분포(원문)
    d = collections.Counter(); bytype = collections.defaultdict(collections.Counter)
    for n, (loc, s) in jp.items():
        for line in re.split(r'／|\{쪽\}', s):
            bytype[loc.split('#')[0].split('/')[0].split('_')[0]][width(line)] += 1
    for k, v in sorted(bytype.items()): print(k, sorted(v.items())[-6:])
    tokdiff = [n for n in jp if n in ko and seq(jp[n][1]) != seq(ko[n])]
    nontok = [n for n in tokdiff if [t for t in seq(jp[n][1]) if t != '／'] != [t for t in seq(ko[n]) if t != '／'] or jp[n][1].count('{쪽}') != ko[n].count('{쪽}')]
    print('토큰열 다름', len(tokdiff), '· 줄 나눔 빼고도 다름', len(nontok))
    for n in nontok[:40]: print(n, jp[n][0], '|', jp[n][1][:70], '|', ko[n][:70])
