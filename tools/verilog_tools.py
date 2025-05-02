from typing import Dict, Any, Optional, List
from langchain.tools import tool
from langchain.pydantic_v1 import BaseModel, Field
from utils.output_parsers import VerilogModule, LintResult
from langchain_openai import ChatOpenAI
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

# 규칙 파일 경로 정의
VERILOG_RULES_FILE = os.path.join("config", "verilog_rules.md")

class GenerateVerilogInput(BaseModel):
    """Verilog 코드 생성 입력 모델"""
    spec_summary: str = Field(description="스펙 요약 또는 요구사항 설명")
    module_name: str = Field(description="생성할 모듈 이름")

class LintVerilogInput(BaseModel):
    """Verilog 린트 입력 모델"""
    code: str = Field(description="린트할 Verilog 코드")
    work_dir: str = Field(description="린트 검사를 수행하고 로그를 저장할 작업 디렉토리 경로")

def _load_verilog_rules() -> str:
    """Verilog 양산 규칙 파일을 읽어옵니다. (내부 헬퍼 함수)"""
    rules_content = ""
    try:
        if os.path.exists(VERILOG_RULES_FILE):
            with open(VERILOG_RULES_FILE, 'r', encoding='utf-8') as f:
                rules_content = f.read()
            print(f"Loaded Verilog rules from {VERILOG_RULES_FILE}")
        else:
            print(f"Verilog rules file not found at {VERILOG_RULES_FILE}. Generating without specific rules.")
    except Exception as e:
        print(f"Error loading Verilog rules from {VERILOG_RULES_FILE}: {e}")
    return rules_content

@tool(args_schema=GenerateVerilogInput)
def generate_verilog(spec_summary: str, module_name: str) -> Dict[str, Any]:
    """스펙 요약 및 Verilog 규칙을 바탕으로 Verilog 모듈 코드를 생성합니다."""
    llm = ChatOpenAI(
        base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
        model=os.getenv("MODEL_NAME", "qwen-3-30b-a3b"),
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7"))
    )
    verilog_rules = _load_verilog_rules()

    prompt = f"""
    다음 요구사항과 **반드시 준수해야 하는 Verilog 양산 규칙**을 바탕으로 Verilog 모듈을 생성해주세요.

    **모듈 이름:** {module_name}
    **요구사항:**
    {spec_summary}
    """

    if verilog_rules:
        prompt += f"""
        **Verilog 양산 규칙 (반드시 준수):**
        각 규칙 앞에는 중요도를 나타내는 태그 [MUST], [SHOULD], [RECOMMEND] 가 있습니다.
        - **[MUST]** 로 표시된 규칙은 **반드시** 지켜야 합니다. 위반 시 생성에 실패한 것으로 간주하고 그 이유를 설명에 명시하세요.
        - **[SHOULD]** 로 표시된 규칙은 **강력히 권장**됩니다. 가능한 한 지켜주세요. 지키지 못했다면 그 이유를 설명에 포함할 수 있습니다.
        - **[RECOMMEND]** 로 표시된 규칙은 **일반적인 권장 사항**입니다.

        ```markdown
        {verilog_rules}
        ```
        """

    prompt += f"""
    **응답 형식:**
    1. 코드 블록에 완성된 Verilog 코드 (````verilog ... ````) 를 작성하세요.
    2. 생성된 코드에 대한 간략한 설명을 작성하세요.
    3. 모든 [MUST] 규칙을 준수했는지 확인하고, 만약 위반했다면 코드 대신 위반 사항을 설명하세요. 다른 규칙에 대한 준수 여부나 잠재적 문제점에 대한 주의사항/경고가 있다면 명시하세요.
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
            elif "[MUST]" in content and ("위반" in content or "violates" in content):
                code = "// [MUST] 규칙 위반으로 코드 생성 실패 (아래 설명 참조)"
            else:
                code = "// 코드 추출 실패"

        desc_match = content.split("```")
        if len(desc_match) > 2:
            description = desc_match[2].strip()
        elif len(desc_match) == 1 and not code.startswith("// 코드"):
            description = content.strip()
        elif len(desc_match) == 1 and code.startswith("// 코드"):
            description = "코드 및 설명 추출 실패"
        else:
            # 설명 부분이 코드 블록 뒤에 바로 오지 않는 경우 등 대비
            potential_desc = content.split(code)[-1].strip() if code != "// 코드 추출 실패" and code in content else content
            description = potential_desc if potential_desc else "설명 추출 실패"


        warnings = [w.strip() for w in description.split("\n") if "주의" in w or "경고" in w or w.startswith("[SHOULD]") or w.startswith("[MUST]")]

        module = VerilogModule(
            code=code,
            description=description,
            warnings=warnings
        )
        return module.dict()
    except Exception as e:
        print(f"Error parsing LLM response for Verilog generation: {e}")
        module = VerilogModule(
            code="// 응답 파싱 오류",
            description=f"LLM 응답 파싱 중 오류 발생: {e}",
            warnings=[]
        )
        return module.dict()

@tool(args_schema=LintVerilogInput)
def lint_verilog(code: str, work_dir: str) -> Dict[str, Any]:
    """주어진 Verilog 코드를 지정된 작업 디렉토리에서 `verilator --lint-only -sv`로 린트 검사하고 결과를 반환합니다."""
    errors: List[str] = []
    warnings: List[str] = []
    status = "success"

    try:
        # 작업 디렉토리가 없으면 생성 (호출 전에 생성되는 것이 이상적이나 안전장치로 추가)
        os.makedirs(work_dir, exist_ok=True)

        verilog_file_path = os.path.join(work_dir, "source.sv")
        with open(verilog_file_path, 'w', encoding='utf-8') as f:
            f.write(code)

        log_file_path = os.path.join(work_dir, "lint.log")
        err_file_path = os.path.join(work_dir, "lint.err")

        try:
            process = subprocess.run(
                ['verilator', '--lint-only', '-sv', verilog_file_path, '-Wno-fatal'],
                capture_output=True,
                text=True,
                check=False,
                cwd=work_dir
            )

            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.write(process.stdout)
            with open(err_file_path, 'w', encoding='utf-8') as f:
                f.write(process.stderr)

            stderr_content = process.stderr
            if stderr_content:
                for line in stderr_content.strip().split('\n'):
                    line_strip = line.strip()
                    if not line_strip:
                        continue
                    if line_strip.startswith('%Error:'):
                        errors.append(line_strip)
                        status = "failed"
                    elif line_strip.startswith('%Warning:'):
                        warnings.append(line_strip)

            if process.returncode != 0 and status != "failed":
                status = "failed"
                if not errors:
                    errors.append(f"Verilator exited with code {process.returncode}. See {err_file_path} for details.")

        except FileNotFoundError:
            status = "failed"
            error_msg = "Verilator를 찾을 수 없습니다. 시스템에 설치되어 있고 PATH에 등록되어 있는지 확인하세요."
            errors.append(error_msg)
            try:
                with open(err_file_path, 'w', encoding='utf-8') as f:
                    f.write("Error: Verilator not found.")
            except Exception as log_e:
                print(f"Failed to write lint error log: {log_e}")
        except Exception as e:
            status = "failed"
            error_msg = f"Verilator 실행 중 예상치 못한 오류 발생: {str(e)}"
            errors.append(error_msg)
            try:
                with open(err_file_path, 'w', encoding='utf-8') as f:
                    f.write(error_msg)
            except Exception as log_e:
                print(f"Failed to write lint error log: {log_e}")

    except Exception as e:
        status = "failed"
        errors.append(f"린트 작업 준비/실행 중 오류 발생: {str(e)}")
        # 오류 로깅 시도
        try:
            err_file_path = os.path.join(work_dir, "lint.err")
            with open(err_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\nError during lint preparation/execution: {str(e)}")
        except Exception as log_e:
            print(f"Failed to write error log during exception handling: {log_e}")

    result = LintResult(
        status=status,
        errors=errors,
        warnings=warnings,
        exec_dir=work_dir # 실행 디렉토리 정보 포함
    )
    return result.dict() 