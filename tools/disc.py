# -*- coding: utf-8 -*-
"""에어즈 어드벤처 트랙 1 ISO 읽기(2026-11-01, 데스 크림존 tools/disc.py 를 옮김) — 파일 목록·꺼내기.
  python tools/disc.py list <장 0~3>      → 목록
  python tools/disc.py dump <장> [최대 MB]  → work/disc<장>/ (최대 MB 넘는 파일은 건너뜀)"""
import os, struct, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = ['Airs Adventure (Japan)']


ROMS = r'C:\claude\roms\ss\Airs Adventure (Japan)'      # 원본(읽기만)


def bin_path(n): return os.path.join(ROMS, NAMES[n] + ' (Track 1).bin')


def sec(f, l, n=1):
    f.seek(l * 2352); raw = f.read(n * 2352)                             # 한 번에 읽고 섹터마다 사용자 자료 2048 B 만(예전 += 는 큰 AVI 에서 제곱 시간)
    return b''.join(raw[i * 2352 + 16:i * 2352 + 2064] for i in range(n))


def files(path):
    f = open(path, 'rb'); pvd = sec(f, 16)
    out = []
    def walk(l, s, pre):
        d = sec(f, l, (s + 2047) // 2048); i = 0
        while i < len(d):
            L = d[i]
            if L == 0: i = (i // 2048 + 1) * 2048; continue
            nm = d[i + 33:i + 33 + d[i + 32]]
            lba, sz, fl = struct.unpack_from('<I', d, i + 2)[0], struct.unpack_from('<I', d, i + 10)[0], d[i + 25]
            if nm not in (b'\0', b'\1'):
                n = nm.decode('latin1').split(';')[0]
                if fl & 2: walk(lba, sz, pre + n + '/')
                else: out.append((pre + n, lba, sz))
            i += L
    walk(struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0], '/')
    return out


def read(name, path):
    for n, l, s in files(path):
        if n == name or n.split('/')[-1] == name:
            return sec(open(path, 'rb'), l, (s + 2047) // 2048)[:s]
    raise KeyError(name)


if __name__ == '__main__':
    cmd, n = sys.argv[1], int(sys.argv[2]); p = bin_path(n)
    if cmd == 'list':
        for nm, l, s in files(p): print('%-40s %8d %10d' % (nm, l, s))
    else:
        mx = float(sys.argv[3]) * 1e6 if len(sys.argv) > 3 else 1e12
        out = os.path.join(ROOT, 'work', 'disc%d' % n); f = open(p, 'rb'); k = 0
        for nm, l, s in files(p):
            if s > mx: continue
            q = os.path.join(out, *nm.strip('/').split('/')); os.makedirs(os.path.dirname(q), exist_ok=True)
            open(q, 'wb').write(sec(f, l, (s + 2047) // 2048)[:s]); k += 1
        print(k, '개 →', out)
