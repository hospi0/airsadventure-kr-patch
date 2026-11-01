# 에어즈 어드벤처 (세가 새턴 일본판) 한글 패치

> **내려받기:** [릴리즈 페이지](https://github.com/hospi0/airsadventure-kr-patch/releases/latest) — v0.9
>
> 이 저장소에는 도구와 작업 문서만 있습니다(ROM·빌드 결과물 없음).

## 내용

- 대사·메뉴·아이템·몬스터 이름·전투 문구·지명 전체
- 타이틀 메뉴, 기록 선택, 이름 입력판 6장, 설정 화면, 전투 명령, 경고 화면 그림 글자
- 이름 입력 한글 음절 110자, "맡김" 기본 이름
- 말줄임표 한국식(바닥선 점 셋)

## 빌드 순서

```
python tools/merge_ko.py
python tools/poc.py
python tools/discbuild.py --write
python tools/make_dist.py
```

작업 기록은 `docs/00_초기조사.md`.
