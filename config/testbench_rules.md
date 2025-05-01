# Verilog Testbench 규칙 (Design Mate)

## 일반 규칙
[MUST] 테스트벤치 모듈 이름은 테스트 대상 모듈 이름 뒤에 `_tb` 접미사를 붙입니다. (예: `my_module_tb`)
[MUST] 테스트벤치 내에서 DUT(Device Under Test) 인스턴스 이름은 `dut` 또는 `u_dut`로 합니다.
[MUST] DUT의 입력 포트에 연결되는 테스트벤치 신호는 `reg` 또는 `logic` 타입으로 선언합니다.
[MUST] DUT의 출력 포트에 연결되는 테스트벤치 신호는 `wire` 또는 `logic` 타입으로 선언합니다.
[SHOULD] 모든 테스트 벡터 또는 시나리오에 대해 명확한 주석을 작성합니다.
[RECOMMEND] 테스트 케이스를 관리하기 위해 `task`를 활용하는 것을 고려합니다.

## 클럭 및 리셋 생성
[MUST] 테스트벤치 내에서 클럭(`i_clk`) 신호를 생성합니다. (예: `initial begin i_clk = 0; forever #5 i_clk = ~i_clk; end`)
[MUST] 테스트벤치 내에서 리셋(`i_resetn`) 신호를 제어합니다. (예: 시뮬레이션 시작 시 일정 시간 동안 low로 유지 후 high로 변경)

## 자극(Stimulus) 인가
[SHOULD] DUT의 입력에 값을 인가할 때는 Non-blocking 할당(`<=`) 또는 적절한 지연(` #delay`)을 사용하여 레이스 컨디션을 피합니다.
[SHOULD] 입력 자극은 클럭 엣지에 맞춰 동기적으로 변경하는 것을 권장합니다.

## 결과 확인 및 종료
[MUST] 예상되는 출력 값과 실제 DUT의 출력 값을 비교하는 로직을 포함합니다.
[SHOULD] SystemVerilog Assertions (`assert property`) 또는 `$display`, `$monitor` 등을 사용하여 결과를 확인하고 로그를 출력합니다.
[MUST] 모든 테스트 시나리오가 완료된 후 시뮬레이션을 종료하기 위해 `$finish;`를 호출합니다.

## 기타
[RECOMMEND] 파일 입출력(`$fopen`, `$fread`, `$fscanf` 등)을 사용하여 테스트 벡터를 관리하는 것을 고려합니다.
(여기에 필요한 특정 규칙들을 [MUST]/[SHOULD]/[RECOMMEND] 와 함께 추가하세요) 