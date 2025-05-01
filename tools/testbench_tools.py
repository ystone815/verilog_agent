from typing import Dict, Any, Optional
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from utils.output_parsers import Testbench, SimulationResult
from utils.status_manager import StatusManager
from langchain_openai import ChatOpenAI
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

# 테스트벤치 규칙 파일 경로 정의 (추가)
TESTBENCH_RULES_FILE = os.path.join("config", "testbench_rules.md")

class GenerateTestbenchInput(BaseModel):
    """테스트벤치 생성 입력 모델"""
    verilog_code: str = Field(description="테스트할 Verilog 모듈 코드 (DUT)")
    test_cases: str = Field(description="테스트 케이스 설명 (자연어 또는 구체적 벡터 명시)")

class RunSimulationInput(BaseModel):
    """시뮬레이션 실행 입력 모델"""
    verilog_code: str = Field(description="시뮬레이션할 Verilog 모듈 코드")
    testbench_code: str = Field(description="테스트벤치 코드")

class GenerateTestbenchTool(BaseTool):
    name = "generate_testbench"
    description = "Verilog 모듈(DUT) 코드와 테스트 케이스 설명을 바탕으로, 규칙에 맞는 테스트벤치 코드를 생성합니다."
    args_schema = GenerateTestbenchInput

    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
            model=os.getenv("MODEL_NAME", "qwen-3-30b-a3b"),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7"))
        )

    def _load_rules(self) -> str:
        """테스트벤치 규칙 파일을 읽어옵니다."""
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

    def _run(self, verilog_code: str, test_cases: str) -> Dict[str, Any]:
        """테스트벤치 코드를 생성합니다."""
        testbench_rules = self._load_rules()

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

        response = self.llm.invoke(prompt)
        try:
            code_match = response.content.split("```verilog")
            if len(code_match) > 1:
                code = code_match[1].split("```")[0].strip()
            else:
                code_match = response.content.split("```")
                if len(code_match) > 1:
                     code = code_match[1].strip()
                else:
                     code = "// 코드 추출 실패"

            desc_match = response.content.split("```")
            if len(desc_match) > 2:
                 description = desc_match[2].strip()
            else:
                 description = "설명 추출 실패"

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

    async def _arun(self, verilog_code: str, test_cases: str) -> Dict[str, Any]:
        raise NotImplementedError("generate_testbench does not support async")

class RunSimulationTool(BaseTool):
    name = "run_simulation"
    description = "Verilog 모듈과 테스트벤치를 시뮬레이션합니다. 시스템에 iverilog와 vvp가 설치되어 있어야 합니다."
    args_schema = RunSimulationInput
    status_manager: StatusManager

    def __init__(self, status_manager: StatusManager, **kwargs):
        super().__init__(**kwargs)
        self.status_manager = status_manager

    def _get_work_dir(self) -> str:
        """현재 세션의 작업 디렉토리를 가져오거나 새로 생성합니다."""
        if not hasattr(self, '_work_dir') or not self._work_dir or not os.path.isdir(self._work_dir):
            self._work_dir = self.status_manager.get_or_create_work_dir(base_name="sim")
        return self._work_dir

    def _run(self, verilog_code: str, testbench_code: str) -> Dict[str, Any]:
        """세션 작업 디렉토리에서 iverilog와 vvp를 사용하여 시뮬레이션을 실행합니다."""
        status = "success"
        log = ""
        summary = ""
        sim_errors = []
        work_dir = None

        try:
            work_dir = self._get_work_dir()

            # 1. 소스 파일 저장
            design_file_path = os.path.join(work_dir, "design.sv")
            tb_file_path = os.path.join(work_dir, "testbench.sv")
            sim_out_path = os.path.join(work_dir, "simulation.out")
            log_file_path = os.path.join(work_dir, "sim.log") # stdout
            err_file_path = os.path.join(work_dir, "sim.err") # stderr

            with open(design_file_path, 'w', encoding='utf-8') as f:
                f.write(verilog_code)
            with open(tb_file_path, 'w', encoding='utf-8') as f:
                f.write(testbench_code)

            # 2. 컴파일 (iverilog) -g2012 옵션 추가
            compile_cmd = ['iverilog', '-g2012', '-o', sim_out_path, design_file_path, tb_file_path]
            compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True, check=False, cwd=work_dir)

            # 컴파일 로그/에러 저장
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
                # 3. 실행 (vvp)
                run_cmd = ['vvp', sim_out_path]
                run_proc = subprocess.run(run_cmd, capture_output=True, text=True, check=False, cwd=work_dir)

                # 실행 로그/에러 추가 저장
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n>>> Run Command: {' '.join(run_cmd)}\n")
                    f.write(run_proc.stdout)
                with open(err_file_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n>>> Run Command: {' '.join(run_cmd)}\n")
                    f.write(run_proc.stderr)
                
                log = run_proc.stdout # 최종 로그는 vvp의 stdout
                if run_proc.returncode != 0:
                    status = "failed"
                    summary = f"시뮬레이션 실행 중 오류 발생 (종료 코드: {run_proc.returncode})."
                    sim_errors.extend(run_proc.stderr.strip().split('\n'))
                else:
                    # 성공 시 요약 (간단하게 로그 끝부분 또는 특정 키워드 찾기 등)
                    if "FAIL" in log or "fail" in log or "ERROR" in log or "error" in log:
                         status = "failed"
                         summary = "시뮬레이션 로그에서 실패 또는 에러가 감지되었습니다."
                    else:
                         status = "success"
                         summary = "시뮬레이션이 성공적으로 완료되었습니다."
                         # 로그에서 중요한 정보 추출 시도 (예시)
                         last_lines = "\n".join(log.strip().split('\n')[-5:]) # 마지막 5줄
                         summary += f"\n\n[로그 마지막 부분]:\n{last_lines}"

        except FileNotFoundError as e:
             status = "failed"
             summary = f"시뮬레이션 도구({e.filename})를 찾을 수 없습니다. iverilog, vvp가 설치 및 PATH 등록되었는지 확인하세요."
             sim_errors.append(summary)
             if work_dir and os.path.exists(work_dir):
                 err_file_path = os.path.join(work_dir, "sim.err")
                 with open(err_file_path, 'a', encoding='utf-8') as f:
                      f.write(f"\nError: {summary}")
        except Exception as e:
            status = "failed"
            summary = f"시뮬레이션 중 예상치 못한 오류 발생: {str(e)}"
            sim_errors.append(summary)
            if work_dir and os.path.exists(work_dir):
                 err_file_path = os.path.join(work_dir, "sim.err")
                 with open(err_file_path, 'a', encoding='utf-8') as f:
                      f.write(f"\nError: {summary}")

        result = SimulationResult(
            status=status,
            log=log,
            summary=summary,
            exec_dir=work_dir,
            errors=sim_errors
        )
        return result.dict()

    async def _arun(self, verilog_code: str, testbench_code: str) -> Dict[str, Any]:
        raise NotImplementedError("run_simulation does not support async") 