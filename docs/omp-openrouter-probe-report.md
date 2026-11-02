# omp + OpenRouter GLM-5.3 한국어 깨짐 시험 보고서

## 결론

2026-11-03에 OpenRouter의 `z-ai/glm-5.3`과 omp 18.15.0으로 시험 6개를 돌렸다. 한국어 깨짐(`�`)과 화면 깨짐은 한 번도 재현되지 않았다.
깨짐을 잡는 검사 자체는 양성 대조에서 6종을 모두 검출했다. 그러므로 "검사가 못 잡았다"가 아니라 "이 조건에서는 깨지지 않았다"로 읽는다.
대신 인코딩과 무관한 모델 쪽 꼬임이 2건 나왔다. 둘 다 omp의 edit 형식에서 생겼다 (5절).

| 시험 | 대상 지점 | 결과 |
|---|---|---|
| T1. 기본 라우팅 probe | 서빙, 청크 경계 | 통과 |
| T2. 제공자 8곳 고정 probe | 서빙, 청크 경계 | 통과 (청크가 글자를 자른 경우 2번, 깨짐 0) |
| T3. omp 헤드리스 코딩 작업 | omp 디코딩, 도구 인자, 파일 쓰기 | 통과 |
| T4. omp TUI 120칸 | omp 화면 렌더링 | 통과 |
| T5. omp TUI 61칸 | omp 화면 렌더링 (홀수 폭 줄바꿈) | 통과 |
| T6. 과거 omp 세션 기록 | 사용자의 실제 사용 기록 | 깨짐 흔적 없음 |

## 1. 시험 범위와 판정 기준

시험은 분석 문서 5절의 네 지점을 하나씩 겨냥했다. 서빙, 네트워크 청크 경계, omp 바이트 디코딩, omp 화면 렌더링이다.

한 시험은 아래 검사가 모두 0일 때 통과다. 청크 경계 분할은 예외다. 분할이 있어도 `�`가 없으면 통과로 본다. 올바른 클라이언트는 잘린 바이트를 다음 청크와 합치기 때문이다.

| 검사 | 찾는 것 | 뜻 |
|---|---|---|
| `fffdRaw` | 원본 바이트의 `EF BF BD` | 이미 깨진 글자가 전송됐다 |
| `escFFFD` | JSON 안의 `�` | 깨진 글자가 이스케이프되어 전송됐다 |
| `loneHighSurr` | 짝 없는 `\ud800`–`\udbff` | UTF-16 반쪽 글자. 재전송 때 400 오류를 낼 수 있다 |
| `invalidUTF8` | UTF-8로 디코딩되지 않는 파일 | 글자 중간이 잘린 채 저장됐다 |
| `nfdJamo` | U+1100–U+11FF 조합용 자모 | 음절이 자모로 풀렸다 (NFD) |
| 모지바케 | `[À-ï][\x80-¿]{1,2}` | UTF-8 바이트를 Latin-1로 잘못 읽었다 (`안녕` → `ìë…`) |
| 화면 폭 | 테두리 있는 줄의 표시 폭 (wcwidth) | 글자 폭 계산이 어긋나 테두리가 밀렸다 |

## 2. 환경

| 항목 | 값 |
|---|---|
| 모델 | OpenRouter `z-ai/glm-5.3` (2026-11-03 모델 목록에서 확인) |
| omp | 18.15.0 (bun 전역 설치) |
| OS | WSL2, Linux 6.18.54.1 |
| 터미널 | tmux 3.4 |
| probe | 이 저장소 `glm-ko-tok probe`, 커밋 `be97af2` |
| 비용 | omp 실행 3회 합계 $0.06 (omp 세션 기록 기준). probe 비용은 기록하지 않았다 |

## 3. 시험별 절차와 결과

### T1. 기본 라우팅에서는 chat과 responses 모두 깨지지 않았다

목적은 OpenRouter가 고른 제공자에서 원본 스트림이 깨지는지 보는 것이다. omp는 기본으로 Responses API를 쓰므로 두 API를 모두 받았다.

절차: 아래 프롬프트로 `--api chat`, `--api responses`를 각각 한 번 실행했다. `--max-tokens 600`.

```text
다음 문장을 그대로 세 번 출력해: 안녕하세요, 대한민국 서울입니다. ㅋㅋㅋ ㅠㅠ 뷁 똠양꿍 韓國 你好
```

| API | 실제 제공자 | 청크 | 바이트 | 종료 | 추론 한글 | 본문 한글 | `fffdRaw` | 경계 분할 |
|---|---|---:|---:|---|---:|---:|---:|---:|
| chat | InferenceNet | 77 | 46,439 | stop | 76 | 54 | 0 | 0 |
| responses | 응답에 없음 | 121 | 37,991 | completed | 98 | 54 | 0 | 0 |

두 API 모두 입력 문장을 세 줄로 돌려줬고, 각 줄은 입력 문장과 글자 단위로 같았다.

### T2. 제공자 8곳을 고정해도 깨지지 않았다

목적은 제공자마다 디토크나이즈(토큰을 글자로 되돌리는 처리)가 다를 수 있는지 보는 것이다. `--provider`로 한 곳만 허용하고 폴백을 껐다.

절차: 아래 프롬프트로 responses API를 실행했다.

```text
한국어로 "안녕"과 "녕"이 들어간 짧은 인사말 다섯 줄을 써 줘. 각 줄에 ㅋㅋ, 뷁, 韓國 중 하나를 넣어.
```

첫 실행(`--max-tokens 1500`)에서는 8곳 중 6곳이 추론만 하다 한도에 걸렸다. 본문 한글이 0–102자뿐이라, 이 6곳은 `--max-tokens 8000`으로 다시 돌렸다. 아래 표는 본문이 나온 실행 기준이다.

| 제공자 | 한도 | 청크 | 바이트 | 종료 | 추론 한글 | 본문 한글 | `fffdRaw` | 경계 분할 |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| DeepInfra | 1,500 | 269 | 65,380 | completed | 242 | 113 | 0 | 0 |
| SiliconFlow | 1,500 | 376 | 122,761 | completed | 538 | 135 | 0 | 0 |
| Z.AI | 8,000 | 1,348 | 338,450 | completed | 711 | 134 | 0 | 0 |
| Novita | 8,000 | 1,139 | 273,847 | completed | 1,504 | 156 | 0 | 0 |
| Fireworks | 8,000 | 1,133 | 275,316 | completed | 574 | 104 | 0 | 0 |
| Parasail | 8,000 | 417 | 110,809 | completed | 491 | 107 | 0 | 0 |
| AtlasCloud | 8,000 | 349 | 84,275 | completed | 393 | 113 | 0 | 0 |
| Together | 8,000 | 1,739 | 503,135 | incomplete | 2,298 | 42 | 0 | **2** |

Together에서는 네트워크 청크가 UTF-8 글자 중간을 자른 경우가 2번 있었다. 그래도 `�`는 0개였다. 청크 분할만으로는 깨지지 않는다는 분석 문서 5절의 설명과 맞는다.
Together는 8,000 한도에서도 추론이 길어 끝까지 가지 못했지만, 본문 42자와 추론 2,298자가 모두 정상이었다.

### T3. omp 헤드리스 코딩 작업에서 도구 인자와 파일이 깨지지 않았다

목적은 사용자가 의심한 상황, 곧 에이전트가 코드를 고치는 중에 깨지는지 보는 것이다. 이 시험은 omp가 받은 원본 응답과 omp가 파싱한 도구 인자, 디스크에 쓴 파일을 모두 검사한다.

절차: 빈 git 저장소에 한국어 주석이 있는 `app.py`를 두고 아래처럼 실행했다. stdin을 닫지 않으면 omp가 `readPipedInput` 단계에서 멈춘다.

```bash
PI_REQ_DEBUG=1 omp -p --mode json --model openrouter/z-ai/glm-5.3 --thinking low \
  --session-dir ./sess '<프롬프트>' < /dev/null > events.jsonl
```

프롬프트는 `greet`에 `lang` 인자 추가, `"안녕하세요, {name}님! 뷁ㅋㅋ"` 같은 언어별 인사, 한국어 docstring·주석, 한국어 이름의 pytest 테스트 3개, pytest 실행, 한국어 표 요약을 요구했다.

| 항목 | 값 |
|---|---|
| 모델 응답 | 7회 (`rr-session-1`–`7`, 합계 1.37 MB) |
| 도구 호출 | read 1, write 3, bash 3 |
| 도구 오류 | 2건. `python` 없음, `pytest` 없음. 둘 다 환경 문제 |
| 최종 결과 | pytest 3 passed. `test_한국어_인사가_정상적으로_나온다` 등 한국어 이름 정상 |
| 검사 결과 | 원본·세션·파일 전부 0 (모지바케 포함) |

모델은 pytest가 없자 `pip install`이 실패하면 `sudo apt-get install`까지 시도하는 명령을 스스로 실행했다. 깨짐과는 무관하지만, 격리되지 않은 환경에서 omp를 돌릴 때는 알아 둘 동작이다.

### T4. omp TUI 120칸에서 화면이 깨지지 않았다

목적은 omp가 받은 글자는 정상인데 화면에서만 밀리거나 깨지는지 보는 것이다.

절차: tmux 창(120×50)에서 `PI_TUI_WRITE_LOG`를 켜고 omp를 대화형으로 띄웠다. 아래 프롬프트를 입력한 뒤 5초마다 화면을 캡처했다. 같은 화면이 3번 이어지면 끝난 것으로 봤다.

```text
app.py에 farewell(name) 함수를 추가해. 반환값은 "안녕히 가세요, {name}님! ㅠㅠ 뷁 똠양꿍 韓國" 이다.
한국어 docstring과 주석도 달고, 마지막에 바꾼 내용을 한국어 표로 요약해. 표 셀에 긴 한국어 문장을 넣어.
```

| 항목 | 값 |
|---|---|
| 도구 호출 | read 1, edit 2 (1건 실패), bash 1 |
| 캡처 | 7장 + 전체 스크롤백 |
| 도구 박스 줄 | 131줄 모두 폭 120 |
| 마크다운 표 줄 | 99줄 모두 폭 119 (항상 1칸 좁음. 의도된 여백으로 본다) |
| `�` | 캡처 0, TUI 쓰기 로그 0 |

### T5. omp TUI 61칸에서도 화면이 깨지지 않았다

목적은 좁은 홀수 폭에서 2칸짜리 글자(한글, 한자)가 줄 끝에 걸릴 때 줄바꿈이 밀리는지 보는 것이다. 절차와 프롬프트는 T4와 같고 폭만 61이다.

| 항목 | 값 |
|---|---|
| 도구 호출 | read 1, edit 1, bash 1 |
| 도구 박스 줄 | 85줄 모두 폭 61 |
| 마크다운 표 줄 | 168줄 모두 폭 60 |
| `�` | 캡처 0, TUI 쓰기 로그 0 |

표 셀은 `farewell(nam` / `e)`처럼 단어 중간에서 줄을 바꿨지만 테두리는 모두 맞았다.

### T6. 과거 omp 세션 기록에 깨짐 흔적이 없었다

목적은 사용자가 실제로 본 깨짐이 기록에 남아 있는지 보는 것이다. `~/.omp` 아래 세션 JSONL에서 `EF BF BD`와 `�`를 찾았다.
`�`가 있는 세션은 1개, 4곳이었다. 4곳 모두 분석 문서에 원래 적힌 `�`를 omp가 파일 읽기로 가져온 것이었다.

## 4. 양성 대조: 검사는 깨진 입력을 모두 잡았다

깨진 글자를 일부러 넣은 파일 6개와 정상 파일 1개로 검사를 돌렸다. 깨진 파일은 모두 해당 검사에서 1 이상이 나왔고, 정상 파일은 모두 0이었다.

| 대조 파일 | 넣은 것 | 걸린 검사 |
|---|---|---|
| `fffd.txt` | `안녕` + `EF BF BD` | `fffdRaw=1` |
| `esc.json` | `{"a":"�"}` | `escFFFD=1` |
| `surr.json` | `{"a":"\ud83d x"}` | `loneHighSurr=1` |
| `trunc.txt` | `EB 85` ('녕'의 앞 2바이트) | `invalidUTF8=1` |
| `nfd.txt` | NFD로 푼 `한글` | `nfdJamo=6` |
| `moji.txt` | `안녕`을 Latin-1로 잘못 읽은 글자 | 모지바케 2 |
| `clean.txt` | `안녕하세요` | 없음 |

probe 쪽 검출은 `tests/test_probe.py`가 이미 단위 시험으로 다룬다.

## 5. 발견: 인코딩이 아니라 omp edit 형식에서 모델이 꼬였다

omp의 edit 도구는 `[파일#해시]` 헤더와 `PUT >줄번호:` 뒤에 `+` 줄을 붙이는 자체 형식을 쓴다. GLM-5.3은 이 형식에서 두 번 실수했다.

| 실행 | 모델이 보낸 것 | 결과 |
|---|---|---|
| T4 (120칸) | 헤더를 `[app.py#4779]`가 아니라 `[greet.py#4779]`로 씀 | `File not found: greet.py`. 다음 호출에서 스스로 고침 |
| T5 (61칸) | `Returns:` 다음 줄을 8칸이 아니라 15칸 들여씀 | 그대로 파일에 기록됨. 문법 오류는 아님 |

T4는 omp 세션 기록의 도구 인자로 확인했다. T5는 같은 기록에서 15칸이 이미 인자에 들어 있었다. 다만 두 TUI 실행은 `PI_REQ_DEBUG`가 꺼져 있어서, 원본 SSE에서도 그랬는지는 확인하지 못했다.
사용자가 말한 "코딩 중 코드가 꼬이는" 현상이 이런 종류라면, 원인은 문자 인코딩이 아니라 모델이 omp의 edit 형식을 다루는 방식이다.

## 6. 한계

- 세션이 짧다. omp 실행은 3회, 모델 응답은 합계 16회였다. 긴 세션이나 큰 컨텍스트에서만 생기는 문제는 이 시험으로 잡지 못한다.
- 프롬프트가 3종뿐이다. 이모지, 옛한글, NFD 입력은 출력 쪽에서만 검사했고 입력으로 넣지 않았다.
- 터미널은 tmux 하나다. Windows Terminal, iTerm2, VS Code 터미널은 글자 폭 표가 다를 수 있다.
- probe는 응답이 `max_output_tokens`로 끊겨도 `finished cleanly: True`라고 표시하고, `U+FFFD in deltas`는 본문 델타만 센다. 추론 델타는 `fffdRaw`(원본 바이트)로만 검사된다.
- 모델 출력은 매번 다르다. 같은 시험을 다시 돌리면 5절의 실수는 안 나올 수도 있다.

## 7. 다음 행동

1. 평소 omp를 쓸 때 로그를 켠다: `PI_REQ_DEBUG=1 PI_TUI_WRITE_LOG=/tmp/omp-tui.log omp --model openrouter/z-ai/glm-5.3`.
2. 깨짐이나 꼬임이 다시 보이면 그 디렉터리의 `rr-session-*.res.log`, TUI 로그, 화면 캡처를 함께 남기고 아래 스캐너를 돌린다.
3. `�`가 원본에 있으면 제공자를, 원본은 정상인데 화면만 깨지면 omp를, 글자는 정상인데 코드만 꼬이면 모델의 edit 형식 처리를 의심한다.

## 부록: 재현 방법

<details>
<summary>T1, T2 명령</summary>

```bash
uv run glm-ko-tok probe --target openrouter --api responses --model z-ai/glm-5.3 \
  --provider Together --prompt '<T2 프롬프트>' --max-tokens 8000 --out runs/or8k-Together.jsonl
```

</details>

<details>
<summary>T4, T5 tmux 캡처 스크립트</summary>

```bash
#!/usr/bin/env bash
# usage: tui-run.sh NAME COLS   (run from an empty git repo with app.py)
# tmux runs omp with the tmux server's PATH, not the caller's PATH.
N=$1; C=$2; T=$PWD/tui-$N; mkdir -p "$T/snap"
tmux new-session -d -s "omp-$N" -x "$C" -y 50 -c "$PWD" \
  "env PI_TUI_WRITE_LOG=$T/tui-write.log omp --model openrouter/z-ai/glm-5.3 --thinking low --session-dir $T/sess; sleep 3600"
sleep 8
tmux send-keys -t "omp-$N" -l '<T4 프롬프트>'; sleep 1; tmux send-keys -t "omp-$N" Enter
for i in $(seq -w 1 90); do
  sleep 5
  tmux capture-pane -p -t "omp-$N" > "$T/snap/$i.txt"
  # stop after three identical captures
  [ "$i" -gt 6 ] && cmp -s "$T/snap/$i.txt" "$T/snap/$(printf %02d $((10#$i-1))).txt" \
    && cmp -s "$T/snap/$(printf %02d $((10#$i-1))).txt" "$T/snap/$(printf %02d $((10#$i-2))).txt" && break
done
tmux capture-pane -p -S - -t "omp-$N" > "$T/final.txt"
```

</details>

<details>
<summary>스캐너 (검사 6종)</summary>

```python
"""Scan files under a directory for broken Korean text."""
import pathlib, re, sys

JAMO = re.compile('[ᄀ-ᇿ]')
MOJI = re.compile('[À-ï][\u0080-¿]{1,2}')
root = pathlib.Path(sys.argv[1])
for p in sorted(root.rglob('*')):
    if not p.is_file() or '.git' in p.parts or p.suffix == '.pyc':
        continue
    b = p.read_bytes()
    try:
        t, bad = b.decode('utf-8'), 0
    except UnicodeDecodeError:
        t, bad = b.decode('utf-8', 'replace'), 1
    hits = {
        'fffdRaw': b.count(b'\xef\xbf\xbd'),
        'escFFFD': len(re.findall(rb'\\ufffd', b, re.I)),
        'loneHighSurr': len(re.findall(rb'\\ud[89ab][0-9a-f]{2}(?!\\ud[c-f])', b, re.I)),
        'invalidUTF8': bad,
        'nfdJamo': len(JAMO.findall(t)),
        'mojibake': len(MOJI.findall(t)),
    }
    if any(hits.values()):
        print(p.relative_to(root), hits)
```

</details>

<details>
<summary>화면 폭 검사</summary>

```python
"""Report display widths of bordered lines in tmux captures."""
import collections, glob, sys
from wcwidth import wcswidth  # uv run --with wcwidth python ...

widths = collections.Counter()
for f in glob.glob(sys.argv[1]):
    for line in open(f, encoding='utf-8'):
        s = line.rstrip()
        if s.endswith(('│', '╮', '╯', '┐', '┘', '┤')):
            widths[wcswidth(s)] += 1
print(sorted(widths.items()))
```

</details>
