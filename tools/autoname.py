# -*- coding: utf-8 -*-
r"""«맡김» 기본 이름 표(NAMH 레코드 8, 8 B 칸: 이름 코드 + FF, 끝 FF) 앞 72칸 = 가나 이름 → 한글(2026-11-01)"""
NAMES = ('헬리 코리 안소니 미나 아서 소피 데니 마리 로버트 세리 켄 아리 다미아노 사라 하이네 유나 프레드 테나 리처드 크리스 '
         '레오 세라 레드 메리 케이오스 콘톤 호리 호세 유진 마리아 코코 파이 사모 곰이 주인 아가 헬리 코리 우리 가은 '
         '임자 미미 치치 미치 코스 니나 모테 추추 로로 수소 우우 노노 곰곰 기라 타로 사치 치무 아루 도모 사나 '
         '호로 시오 호기 호코 호시 미사 휴 소요미 나 네 주인 아가').split()


def apply(rec, name_code):
    b = bytearray(rec); assert len(NAMES) == 72
    for i, n in enumerate(NAMES):
        q = [name_code[c] for c in n]; assert len(q) <= 6
        b[i * 8:i * 8 + 8] = bytes(q + [0xFF] + [0x24] * (6 - len(q)) + [0xFF])
    return bytes(b)
