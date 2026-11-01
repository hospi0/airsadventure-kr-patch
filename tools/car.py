# -*- coding: utf-8 -*-
r"""에어즈 어드벤처 CAR 묶음(2026-11-01) — [u32 적재 주소][u32 풀린 크기][압축 자료] 반복(4바이트 정렬) · 맵 묶음은 FFFFFFFF 로 시작하는 0x20 B 설명 머리가 앞·중간에 끼어 있음(건너뜀)
  압축 = 16비트 워드 LZSS: 깃발 워드(LSB 먼저, 1 = 참조) 뒤 항목 16개
     날것 = 워드 1개 · 참조 = 워드 v: 위치 = v >> 8(최근 256워드 창 안), 길이 = (v & 0xFF) + 2 워드(겹친 복사 허용)
  python tools/car.py <파일> → 레코드 목록
"""
import struct, sys


def lz_dec(d, o, n_bytes):
    """o 부터 풀어 n_bytes 만들기 → (풀린 바이트, 끝난 위치)
    참조 워드 v: 위치 p = v >> 8, 길이 = (v & 0xFF) + 2 워드, 원본 = (출력 < 256 이면 p, 아니면 출력 − 256 + p) — 최근 256워드 창
    (INITS 108,544 B·BUP_INFO 를 스테이트 RAM 과 대조해 1바이트도 다르지 않음, 2026-11-01)"""
    out = []; nw = n_bytes // 2
    while len(out) < nw:
        fl = struct.unpack_from('>H', d, o)[0]; o += 2
        for b in range(16):
            if len(out) >= nw: break
            v = struct.unpack_from('>H', d, o)[0]; o += 2
            if fl >> b & 1:
                p = v >> 8; ln = (v & 0xFF) + 2; n = len(out); s0 = p if n < 256 else n - 256 + p
                for k in range(ln): out.append(out[s0 + k] if 0 <= s0 + k < len(out) else 0)
            else:
                out.append(v)
    return struct.pack('>%dH' % nw, *out[:nw]), o


def records(d):
    """→ [(적재 주소, 풀린 바이트, 압축 시작, 압축 끝)]"""
    o = 0; out = []
    while o + 8 <= len(d):
        a, n = struct.unpack_from('>II', d, o)
        if a == 0xFFFFFFFF:                                                     # 맵 묶음 설명 머리 0x20 B(FFFFFFFF 1 주소 크기 40 n 0 0) — 중간에도 나옴
            o += 0x20; continue
        if n == 0 or n > 0x200000: break
        try:
            raw, e = lz_dec(d, o + 8, n)
        except struct.error:
            break
        out.append((a, raw, o + 8, e)); o = (e + 3) & ~3                      # 레코드는 4바이트 정렬
    return out, o


if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read(); rs, end = records(d)
    for a, raw, s, e in rs: print('%08X  풀림 %7d  압축 %06X‥%06X' % (a, len(raw), s, e))
    print('끝', hex(end), '/', hex(len(d)))


def lz_enc(raw):
    """lz_dec 의 역: 16비트 워드 LZSS(최근 256워드 창, 위치 = 창 안 칸, 길이 2~257) — 탐욕 + 워드 해시"""
    import collections
    w = struct.unpack('>%dH' % (len(raw) // 2), raw); n = len(w)
    out = bytearray(); i = 0; heads = collections.defaultdict(list)
    while i < n:
        fl = 0; items = []
        for b in range(16):
            if i >= n: break
            best_l = 0; best_s = 0
            key = w[i]
            if i + 1 < n:
                cand = heads.get((w[i], w[i + 1]), [])
                lo = max(0, i - 256)
                for s0 in reversed(cand):
                    if s0 < lo: break
                    l = 0
                    while l < 257 and i + l < n and w[s0 + l] == w[i + l]: l += 1
                    if l > best_l: best_l = l; best_s = s0
                    if l == 257: break
            if i < 256 and best_l < 2:                                          # 시작 0 채움 구간: 앞 «0» 참조(출력<256 이면 p = 절대 위치)
                pass
            if best_l >= 2:
                p = best_s if i < 256 else best_s - (i - 256)
                if 0 <= p <= 255:
                    fl |= 1 << b; items.append(struct.pack('>H', (p << 8) | (best_l - 2)))
                    for k in range(best_l):
                        if i + k + 1 < n: heads[(w[i + k], w[i + k + 1])].append(i + k)
                    i += best_l; continue
            items.append(struct.pack('>H', w[i]))
            if i + 1 < n: heads[(w[i], w[i + 1])].append(i)
            i += 1
        out += struct.pack('>H', fl) + b''.join(items)
    return bytes(out)


def segments(d):
    """→ [('hdr', 0x20 B) | ('rec', 주소, 풀린 바이트)] — build() 로 다시 묶음"""
    o = 0; out = []
    while o + 8 <= len(d):
        a, n = struct.unpack_from('>II', d, o)
        if a == 0xFFFFFFFF: out.append(('hdr', d[o:o + 0x20])); o += 0x20; continue
        if n == 0 or n > 0x200000: break
        raw, e = lz_dec(d, o + 8, n); out.append(('rec', a, raw)); o = (e + 3) & ~3
    return out, d[o:]


def build(segs, tail=b''):
    out = bytearray()
    for s in segs:
        if s[0] == 'hdr': out += s[1]; continue
        _, a, raw = s; c = lz_enc(raw)
        out += struct.pack('>II', a, len(raw)) + c
        while len(out) % 4: out += b'\0'
    return bytes(out) + tail
