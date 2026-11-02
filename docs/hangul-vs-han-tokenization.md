# GLM-5.3 토크나이저는 한글을 바이트 단위로 쪼갠다

## 요약

GLM-5.3 토크나이저는 한글과 중국어를 똑같이 3바이트 UTF-8로 받는다. 차이는 바이트 수가 아니라 어휘(vocab)에 있다.
상용 한자(GB2312 1급) 3,755자 중 92.8%는 토큰 하나이지만, 상용 한글(KS X 1001) 2,350자 중 토큰 하나인 글자는 11.2%(263자)뿐이다.
나머지 한글은 2~3개 토큰으로 나뉘고, 그 조각 토큰은 혼자서는 올바른 UTF-8이 아니다.
스트리밍 중에 토큰마다 따로 문자열로 바꾸는 계층이 있으면 `�`(U+FFFD)가 나온다.
omp 18.15.0의 바이트 디코딩 코드는 이 실수를 하지 않는 것으로 보인다. 그래서 `�`는 서빙 쪽을, 화면 어긋남은 omp 렌더링을 먼저 의심한다.

"중국어 유니코드에만 최적화되어 한글 유니코드와 매칭이 안 된다"는 말은 절반만 맞다.
토크나이저는 유니코드 범위를 보지 않는다. 학습 데이터에 중국어가 많아서 중국어 바이트 조합이 많이 병합(merge)되었을 뿐이다.

| 문자 집합 | 글자 수 | 1토큰 | 2토큰 | 3토큰 | 1토큰 비율 |
|---|---:|---:|---:|---:|---:|
| 한글 KS X 1001 상용 | 2,350 | 263 | 1,337 | 750 | 11.2% |
| 한글 전체 음절 | 11,172 | 263 | 5,653 | 5,256 | 2.4% |
| 한글 호환 자모 ㄱ–ㅣ | 51 | 0 | 51 | 0 | 0.0% |
| 중국어 GB2312 1급 | 3,755 | 3,483 | 272 | 0 | 92.8% |
| 한자 KS X 1001 | 4,888 | 2,400 | 2,147 | 341 | 49.1% |
| CJK 통합 한자 전체 | 20,992 | 4,216 | 15,901 | 875 | 20.1% |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="diagrams/coverage-bar-dark.svg">
  <img alt="문자 집합별 1토큰 비율: 한글 상용 11.2%, 중국어 GB2312 1급 92.8%" src="diagrams/coverage-bar-light.svg">
</picture>

측정: `zai-org/GLM-5.3`의 `tokenizer.json`, 2026-11-03. 재현 명령: `uv run glm-ko-tok compare`.

## 한글과 중국어는 UTF-8에서 둘 다 3바이트다

UTF-8의 바이트 수는 코드포인트(유니코드 번호) 크기로만 정해진다. 언어와는 상관없다.
U+0800부터 U+FFFF까지는 모두 3바이트다. 한글 음절과 상용 한자는 둘 다 이 구간에 있다.

| 코드포인트 구간 | UTF-8 바이트 수 | 예 |
|---|---:|---|
| U+0000–U+007F | 1 | ASCII `A` = `41` |
| U+0080–U+07FF | 2 | `é` = `C3 A9` |
| U+0800–U+FFFF | 3 | `한` = `ED 95 9C`, `中` = `E4 B8 AD` |
| U+10000–U+10FFFF | 4 | 이모지, CJK 확장 B 한자 |

한글과 한자 관련 유니코드 블록은 아래와 같다.

| 블록 | 범위 | 글자 수 | UTF-8 | 첫 바이트 |
|---|---|---:|---:|---|
| 한글 음절 (Hangul Syllables) | U+AC00–U+D7A3 | 11,172 | 3 | `EA`–`ED` |
| 한글 자모 (Hangul Jamo, 조합용) | U+1100–U+11FF | 256 | 3 | `E1` |
| 한글 호환 자모 (ㄱ, ㅏ 등) | U+3130–U+318F | 94 | 3 | `E3` |
| 한글 자모 확장 A / B (옛한글) | U+A960–U+A97F, U+D7B0–U+D7FF | 29 + 72 | 3 | `EA`, `ED` |
| CJK 통합 한자 | U+4E00–U+9FFF | 20,992 | 3 | `E4`–`E9` |
| CJK 통합 한자 확장 A | U+3400–U+4DBF | 6,592 | 3 | `E3`–`E4` |
| CJK 통합 한자 확장 B 이후 | U+20000– | 수만 자 | 4 | `F0` |
| CJK 호환 한자 (한국 중복 한자 포함) | U+F900–U+FAFF | 472 | 3 | `EF` |

한글 음절은 첫 바이트가 `EA`–`ED`, 상용 한자는 `E4`–`E9`이다. 그래서 바이트 수준에서도 두 문자 체계는 서로 다른 바이트 조합을 쓴다.
병합 규칙은 어느 한쪽에 몰려 학습될 수 있다.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="diagrams/utf8-blocks-dark.svg">
  <img alt="UTF-8 바이트 길이 구간과 한글·한자 블록 위치" src="diagrams/utf8-blocks-light.svg">
</picture>

블록 범위와 글자 수의 원본은 [Unicode Character Code Charts](https://www.unicode.org/charts/)와 [Unicode Standard 3.12 Conjoining Jamo Behavior](https://www.unicode.org/versions/latest/core-spec/chapter-3/#G24646)이다.

## 한글 음절은 자모를 계산식으로 합친 번호다

한글 음절 11,172자는 초성 19개, 중성 21개, 종성 28개(받침 없음 포함)의 모든 조합이다.
코드포인트는 `0xAC00 + (초성 × 21 + 중성) × 28 + 종성`으로 정해진다.
예를 들어 `한`은 초성 ㅎ(18), 중성 ㅏ(0), 종성 ㄴ(4)이므로 `0xAC00 + (18 × 21 + 0) × 28 + 4 = U+D55C`이다.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="diagrams/hangul-compose-dark.svg">
  <img alt="한글 음절 조합식과 NFD 9바이트 경로" src="diagrams/hangul-compose-light.svg">
</picture>

같은 `한`을 NFD(자모를 풀어 쓴 형태)로 보내면 3글자, 9바이트가 된다.
GLM-5.3은 NFD `한`을 9개 토큰으로 쪼갠다. 9개 모두 혼자서는 `�`이다.
macOS 파일 이름이나 일부 복사·붙여넣기 경로에서 NFD 한글이 들어올 수 있다.

## 토크나이저는 유니코드 범위가 아니라 바이트 병합으로 동작한다

GLM-5.3의 `tokenizer.json`은 byte-level BPE(바이트를 병합 규칙으로 합치는 방식)이다. 측정한 구성은 아래와 같다.

| 항목 | 값 |
|---|---|
| model | BPE, 어휘 154,820개, 병합 규칙 321,649개 |
| byte_fallback | false |
| pre_tokenizer | Split(정규식) → ByteLevel |
| decoder | ByteLevel |

처리 순서는 아래와 같다. 한글이 불리해지는 지점은 4단계 하나뿐이다.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="diagrams/tokenizer-pipeline-dark.svg">
  <img alt="GLM-5.3 토크나이저 처리 단계" src="diagrams/tokenizer-pipeline-light.svg">
</picture>

1단계 정규식은 `\p{L}`(모든 언어의 글자)로 단어를 나눈다. 한글과 한자는 둘 다 `\p{L}`이므로 이 단계에서는 차별이 없다.
2·3단계는 모든 바이트를 똑같이 다룬다. 4단계의 병합 규칙만 학습 데이터의 빈도를 반영한다.
어휘 154,856개(추가 토큰 포함) 중 한자를 포함한 토큰은 28,642개, 한글 음절을 포함한 토큰은 565개다. 이 50배 차이가 1토큰 비율의 차이를 만든다.

## 같은 3바이트라도 한글은 글자 중간에서 잘린다

`你好`는 6바이트가 토큰 하나로 합쳐진다. `안녕`은 `안` 3바이트는 토큰 하나지만, `녕`은 `EB 85`와 `95` 두 토큰으로 갈린다.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="diagrams/byte-split-dark.svg">
  <img alt="안녕과 你好의 바이트·토큰 경계 비교" src="diagrams/byte-split-light.svg">
</picture>

비슷한 뜻의 문장으로 비교해도 같은 경향이 나온다. 두 문장은 직역 관계가 아니므로 숫자는 경향으로만 읽어야 한다.

| 문장 | 글자 | 바이트 | 토큰 | 토큰/글자 | 혼자 `�`인 토큰 |
|---|---:|---:|---:|---:|---:|
| 오늘 날씨가 정말 좋네요. 산책하러 갈까요? | 19 | 58 | 24 | 1.26 | 10 |
| 今天天气真好。我们去散步吧？ | 14 | 42 | 8 | 0.57 | 0 |
| 토크나이저는 텍스트를 토큰으로 나눕니다. | 19 | 58 | 24 | 1.26 | 14 |
| 分词器把文本切分成词元。 | 12 | 36 | 10 | 0.83 | 0 |
| 대한민국의 수도는 서울입니다. | 14 | 42 | 12 | 0.86 | 0 |
| 大韩民国的首都是首尔。 | 11 | 33 | 8 | 0.73 | 0 |

자주 쓰는 단어(`대한민국`, `서울`)는 한글도 잘 병합된다. 깨지기 쉬운 것은 덜 흔한 음절(`녕`, `똠`, `늘`)과 신조어, 자모, NFD 한글이다.
한국 한자도 같은 문제가 있다. `大韓民國`에서 `韓`은 `E9 9F`와 `93`으로 갈린다.

## 깨짐은 토큰을 하나씩 문자열로 바꾸는 계층에서 생긴다

토크나이저 자체는 틀리지 않는다. 토큰 전체를 한 번에 디코딩하면 원문이 그대로 나온다.
문제는 스트리밍이다. 서버나 클라이언트가 토큰 하나, 또는 네트워크 청크 하나마다 UTF-8 디코딩을 하면 미완성 바이트가 `�`로 바뀐다.

`samples/korean.txt`의 36개 문장으로 재현하면 차이가 분명하다. 토큰마다 따로 디코딩하면 36개 중 30개 문장에서 `�`가 모두 223개 나온다.
바이트를 모았다가 디코딩하는 두 방식(Python incremental decoder, `tokenizers`의 `DecodeStream`)은 36개 모두 원문과 같고 `�`가 0개다.
재현 명령: `uv run glm-ko-tok stream-sim --file samples/korean.txt --per-line`.

깨짐이 생길 수 있는 지점은 네 곳이다. 각 지점은 다른 증거로 가려낸다.

| 위험 지점 | 확인 방법 | 이 지점이 원인일 때 보이는 증거 |
|---|---|---|
| 1. 서빙 디코딩 (vLLM, OpenRouter 제공자) | `glm-ko-tok probe`로 원본 SSE 저장 | 원본 바이트에 이미 `EF BF BD`(U+FFFD)가 있음 |
| 2. 네트워크 청크 경계 | probe가 청크 경계에서 잘린 글자를 셈 | 경계에서 잘린 글자가 있음. 이것만으로는 깨지지 않음 |
| 3. 클라이언트 바이트 디코딩 (omp) | `PI_REQ_DEBUG=1`로 omp가 받은 응답 저장 | 응답 로그는 정상, omp 출력에만 `�` |
| 4. 터미널 렌더링 (omp TUI) | `PI_TUI_WRITE_LOG`로 omp가 터미널에 쓴 텍스트 저장 | 로그 텍스트는 정상, 화면만 깨짐 |

## omp 18.15.0의 바이트 디코딩은 정상으로 보이고, 남은 의심 지점은 렌더링이다

설치된 omp 18.15.0의 TypeScript 소스를 읽기 전용으로 감사했다. 실행 검증은 아직 하지 않았으므로 아래 내용은 코드 근거에 기반한 가설이다.

OpenRouter 경로는 기본으로 Responses API를 쓴다 (`pi-ai/src/stream.ts:925`, `PI_OPENROUTER_RESPONSES !== "0"`).
Responses와 Chat Completions 모두 같은 SSE 디코더를 지난다.
이 디코더는 청크에서 마지막 줄바꿈(LF/CR)까지만 디코딩하고 나머지 바이트는 버퍼에 남긴다 (`pi-utils/src/stream.ts:190-219`).
줄바꿈은 ASCII 1바이트이므로 한글 3바이트 중간을 자를 수 없다. 그래서 3번 지점이 원인일 가능성은 낮다.

남은 의심 지점은 4번 터미널 렌더링이다. 근거는 아래와 같고 가능성 순서로 적었다.

1. 조합형 자모(U+1100–U+11FF, NFD 한글)의 폭 계산이 터미널과 다를 수 있다. 소스 주석에 "`Bun.stringWidth` counts each conjoining jamo as a separate cell"이라고 적혀 있다 (`pi-tui/src/components/input.ts:41-50`). 입력창은 NFC로 정규화하지만, 모델 출력 경로에는 정규화가 없다.
2. 한글 호환 자모(ㅋ, ㅠ 등 U+3131–U+318E)의 폭은 플랫폼으로 추정한다. macOS가 아니면 2칸으로 계산한다 (`pi-tui/src/utils.ts:291-303`). 터미널이 1칸으로 그리면 `ㅋㅋㅋ`가 들어간 줄의 정렬이 어긋난다.
3. 아주 긴 줄을 자를 때 마지막 칸 뒤의 폭 0 문자가 버려질 수 있다 (`pi-tui/src/tui.ts:4196-4250`). NFD 한글이면 받침이나 모음이 사라진다.

완성형 한글(U+AC00–U+D7A3)은 특별 처리 없이 2칸으로 계산하며, 이는 일반 터미널과 같다.
그러므로 평범한 완성형 한글이 `�`로 깨진다면 omp보다 서빙 쪽(1번)을 먼저 의심해야 한다.

## 반론과 한계

"토큰이 많이 쪼개지면 모델이 한국어를 못 한다"는 결론은 이 분석에서 나오지 않는다. 이 문서는 토큰 수와 바이트 경계만 측정했고, 모델 품질은 측정하지 않았다.
토큰이 많으면 같은 문장에 비용과 컨텍스트를 더 쓴다는 점만 확실하다.

중국어 문장 비교는 직역 쌍이 아니다. 토큰/글자 비율은 경향으로만 쓴다. 정확한 비교에는 병렬 말뭉치(예: FLORES-200)가 필요하다.

이 결과는 GLM-5.3 `tokenizer.json` 하나에만 해당한다. 다른 모델 토크나이저는 다시 측정해야 한다.

## 다음 행동

1. OpenRouter 원본 스트림을 저장한다: `uv run glm-ko-tok probe --target openrouter --api responses --model <id> --prompt <한글 프롬프트> --out runs/or-responses.jsonl`. omp는 기본으로 Responses API를 쓴다.
2. 같은 프롬프트로 omp를 실행하면서 두 로그를 켠다: `PI_REQ_DEBUG=1 PI_TUI_WRITE_LOG=runs/omp-tui.log omp --model openrouter/<id>`. `PI_REQ_DEBUG=1`은 현재 디렉터리에 `rr-session-N.json`과 `rr-session-N.res.log`를 쓴다.
3. 위험 지점 표로 원인을 하나로 좁힌다. 원본에 `�`가 있으면 서빙 쪽, 로그는 정상인데 화면만 깨지면 omp 렌더링 쪽에 이슈를 낸다.
