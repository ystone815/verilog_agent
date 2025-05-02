from typing import Dict, Any, Optional, List
from langchain.tools import tool
from langchain.pydantic_v1 import BaseModel, Field
from utils.output_parsers import Testbench, SimulationResult
from langchain_openai import ChatOpenAI
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

# 테스트벤치 규칙 파일 경로 정의
TESTBENCH_RULES_FILE = os.path.join("config", "testbench_rules.md")

class GenerateTestbenchInput(BaseModel):
    """테스트벤치 생성 입력 모델"""
    verilog_code: str = Field(description="테스트할 Verilog 모듈 코드 (DUT)")
    test_cases: str = Field(description="테스트 케이스 설명 (자연어 또는 구체적 벡터 명시)")

class RunSimulationInput(BaseModel):
    """시뮬레이션 실행 입력 모델"""
    verilog_code: str = Field(description="시뮬레이션할 Verilog 모듈 코드")
    testbench_code: str = Field(description="테스트벤치 코드")
    work_dir: str = Field(description="시뮬레이션을 수행하고 로그를 저장할 작업 디렉토리 경로")

def _load_testbench_rules() -> str:
    """테스트벤치 규칙 파일을 읽어옵니다. (내부 헬퍼 함수)"""
    rules_content = ""
    try:
        if os.path.exists(TESTBENCH_RULES_FILE):
            with open(TESTBENCH_RULES_FILE, 'r', encoding='utf-8') as f:
                rules_content = f.read()
            print(f"Loaded testbench rules from {TESTBENCH_RULES_FILE}")
        else:
            print(f"Testbench rules file not found at {TESTBENCH_RULES_FILE}. Generating without specific rules.")
    except Exception as e:
        print(f"Error loading testbench rules from {TESTBENCH_RULES_FILE}: {e}")
    return rules_content

@tool(args_schema=GenerateTestbenchInput)
def generate_testbench(verilog_code: str, test_cases: str) -> Dict[str, Any]:
    """Verilog 모듈(DUT) 코드, 테스트 케이스 설명, 테스트벤치 규칙을 바탕으로 테스트벤치 코드를 생성합니다."""
    llm = ChatOpenAI(
        base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
        model=os.getenv("MODEL_NAME", "qwen-3-30b-a3b"),
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7"))
    )
    testbench_rules = _load_testbench_rules()

    prompt = f"""
    다음 Verilog 모듈(DUT) 코드와 테스트 케이스 설명을 바탕으로, **반드시 준수해야 하는 테스트벤치 규칙**을 따라 Verilog 테스트벤치 코드를 생성해주세요.

    **DUT 코드:**
    ```verilog
    {verilog_code}
    ```

    **테스트 케이스 설명:**
    {test_cases}
    """

    if testbench_rules:
        prompt += f"""
        **테스트벤치 규칙 (반드시 준수):**
        각 규칙 앞에는 중요도를 나타내는 태그 [MUST], [SHOULD], [RECOMMEND] 가 있습니다.
        - **[MUST]** 로 표시된 규칙은 **반드시** 지켜야 합니다.
        - **[SHOULD]** 로 표시된 규칙은 **강력히 권장**됩니다.
        - **[RECOMMEND]** 로 표시된 규칙은 **일반적인 권장 사항**입니다.

        ```markdown
        {testbench_rules}
        ```
        """

    prompt += f"""
    **응답 형식:**
    1. 코드 블록에 완성된 Verilog 테스트벤치 코드 (````verilog ... ````) 를 작성하세요.
    2. 생성된 테스트벤치에 대한 간략한 설명을 작성하세요. (포함된 테스트 케이스 요약 등)
    3. 모든 [MUST] 규칙을 준수했는지 확인하고, 규칙 준수 관련 특이사항이나 주의점이 있다면 명시하세요.
    """

    try:
        response = llm.invoke(prompt)
        content = response.content
        code_match = content.split("```verilog")
        if len(code_match) > 1:
            code = code_match[1].split("```")[0].strip()
        else:
            code_match = content.split("```")
            if len(code_match) > 1:
                code = code_match[1].strip()
            else:
                code = "// 코드 추출 실패"

        desc_match = content.split("```")
        if len(desc_match) > 2:
            description = desc_match[2].strip()
        else:
            potential_desc = content.split(code)[-1].strip() if code != "// 코드 추출 실패" and code in content else content
            description = potential_desc if potential_desc else "설명 추출 실패"

        test_cases_list = [tc.strip() for tc in description.split('\n') if tc.strip() and not tc.startswith("##")]

    except Exception as e:
        print(f"Error parsing LLM response for testbench generation: {e}")
        code = "// 응답 파싱 오류"
        description = f"LLM 응답 파싱 중 오류 발생: {e}"
        test_cases_list = []

    testbench = Testbench(
        code=code,
        description=description,
        test_cases=test_cases_list
    )
    return testbench.dict()

@tool(args_schema=RunSimulationInput)
def run_simulation(verilog_code: str, testbench_code: str, work_dir: str) -> Dict[str, Any]:
    """주어진 Verilog 모듈과 테스트벤치 코드를 지정된 작업 디렉토리에서 iverilog와 vvp로 시뮬레이션하고 결과를 반환합니다."""
    status = "success"
    log = ""
    summary = ""
    sim_errors: List[str] = []

    try:
        # 작업 디렉토리 생성 (안전장치)
        os.makedirs(work_dir, exist_ok=True)

        design_file_path = os.path.join(work_dir, "design.sv")
        tb_file_path = os.path.join(work_dir, "testbench.sv")
        sim_out_path = os.path.join(work_dir, "simulation.out")
        log_file_path = os.path.join(work_dir, "sim.log")
        err_file_path = os.path.join(work_dir, "sim.err")

        with open(design_file_path, 'w', encoding='utf-8') as f:
            f.write(verilog_code)
        with open(tb_file_path, 'w', encoding='utf-8') as f:
            f.write(testbench_code)

        # 컴파일
        compile_cmd = ['iverilog', '-g2012', '-o', sim_out_path, design_file_path, tb_file_path]
        compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True, check=False, cwd=work_dir)

        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write(f">>> Compile Command: {' '.join(compile_cmd)}\n")
            f.write(compile_proc.stdout)
        with open(err_file_path, 'w', encoding='utf-8') as f:
            f.write(f">>> Compile Command: {' '.join(compile_cmd)}\n")
            f.write(compile_proc.stderr)

        if compile_proc.returncode != 0:
            status = "failed"
            summary = "시뮬레이션 컴파일 실패."
            sim_errors.extend(compile_proc.stderr.strip().split('\n'))
        else:
            # 실행
            run_cmd = ['vvp', sim_out_path]
            run_proc = subprocess.run(run_cmd, capture_output=True, text=True, check=False, cwd=work_dir)

            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n>>> Run Command: {' '.join(run_cmd)}\n")
                f.write(run_proc.stdout)
            with open(err_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n>>> Run Command: {' '.join(run_cmd)}\n")
                f.write(run_proc.stderr)

            log = run_proc.stdout
            if run_proc.returncode != 0:
                status = "failed"
                summary = f"시뮬레이션 실행 중 오류 발생 (종료 코드: {run_proc.returncode})."
                sim_errors.extend(run_proc.stderr.strip().split('\n'))
            else:
                if "FAIL" in log or "fail" in log or "ERROR" in log or "error" in log:
                    status = "failed"
                    summary = "시뮬레이션 로그에서 실패 또는 에러가 감지되었습니다."
                else:
                    status = "success"
                    summary = "시뮬레이션이 성공적으로 완료되었습니다."
                    last_lines = "\n".join(log.strip().split('\n')[-5:])
                    summary += f"\n\n[로그 마지막 부분]:\n{last_lines}"

    except FileNotFoundError as e:
        status = "failed"
        error_msg = f"시뮬레이션 도구({e.filename})를 찾을 수 없습니다. iverilog, vvp가 설치 및 PATH 등록되었는지 확인하세요."
        summary = error_msg
        sim_errors.append(summary)
        try:
            err_file_path = os.path.join(work_dir, "sim.err")
            with open(err_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\nError: {summary}")
        except Exception as log_e:
             print(f"Failed to write simulation error log: {log_e}")
    except Exception as e:
        status = "failed"
        summary = f"시뮬레이션 중 예상치 못한 오류 발생: {str(e)}"
        sim_errors.append(summary)
        try:
            err_file_path = os.path.join(work_dir, "sim.err")
            with open(err_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\nError: {summary}")
        except Exception as log_e:
             print(f"Failed to write simulation error log: {log_e}")

    result = SimulationResult(
        status=status,
        log=log,
        summary=summary,
        exec_dir=work_dir, # 실행 디렉토리 정보 포함
        errors=sim_errors
    )
    return result.dict() 