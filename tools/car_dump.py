# -*- coding: utf-8 -*-
"""CAR 전부 풀어 work/car/<경로_>_<번호>_<주소>.bin 으로 (python tools/car_dump.py)"""
import sys, glob, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import car
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, 'work', 'disc0'); O = os.path.join(ROOT, 'work', 'car'); os.makedirs(O, exist_ok=True); n = 0
for p in sorted(glob.glob(os.path.join(R, '**', '*.CAR'), recursive=True)):
    d = open(p, 'rb').read(); rs, e = car.records(d)
    nm = os.path.relpath(p, R).replace(os.sep, '_')
    for k, (a, raw, s, t) in enumerate(rs):
        open(os.path.join(O, '%s_%02d_%08X.bin' % (nm, k, a)), 'wb').write(raw); n += 1
print(n)
