# Verilog 양산 규칙 (Design Mate)

## 일반 규칙
[MUST] 모든 신호 및 모듈 이름은 소문자와 언더스코어(_)를 사용합니다 (snake_case).
[MUST] 모든 포트 선언에는 방향(input, output, inout)을 명시합니다.
[MUST] 입력 포트 이름은 `i_` 로 시작합니다.
[MUST] 출력 포트 이름은 `o_` 로 시작합니다.
[MUST] 내부 wire 이름은 `w_` 로 시작합니다.
[MUST] 내부 reg (플립플롭) 이름은 `r_` 로 시작합니다.
[MUST] 리셋 신호는 동기식 액티브 로우 입력 `i_resetn` 을 사용합니다.
[SHOULD] 주석은 코드 라인 위에 작성하거나 라인 끝에 작성합니다.

## 클럭킹
[MUST] 주 클럭 입력 신호 이름은 `i_clk` 로 합니다.
[MUST] 가능하면 Non-blocking 할당 (`<=`)을 사용합니다.

## 피해야 할 사항
[MUST] 초기값 할당 (`initial begin ... end`) 블록은 테스트벤치 외에는 사용하지 않습니다.
[MUST] 명시적인 `generate` 문 외에는 조건부 인스턴스화를 사용하지 않습니다.
[MUST] Latch 생성을 유발하는 코드를 작성하지 않도록 주의합니다. (예: 모든 조건이 처리되지 않은 `if` 또는 `case` 문)

## 기타
[RECOMMEND] 파라미터화 가능한 모듈을 적극 활용합니다.
(여기에 필요한 특정 규칙들을 [MUST]/[SHOULD]/[RECOMMEND] 와 함께 추가하세요) 