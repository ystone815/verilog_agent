from typing import Dict, Any, Optional
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from utils.output_parsers import VerilogModule, LintResult
from utils.status_manager import StatusManager
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

class GenerateVerilogTool(BaseTool):
    name = "generate_verilog"
    description = "스펙과 양산 규칙을 바탕으로 Verilog 모듈 코드를 생성합니다."
    args_schema = GenerateVerilogInput

    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
            model=os.getenv("MODEL_NAME", "qwen-3-30b-a3b"),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7"))
        )

    def _load_rules(self) -> str:
        """Verilog 양산 규칙 파일을 읽어옵니다."""
        rules_content = ""
        try:
            if os.path.exists(VERILOG_RULES_FILE):
                with open(VERILOG_RULES_FILE, 'r', encoding='utf-8') as f:
                    rules_content = f.read()
                print(f"Loaded Verilog rules from {VERILOG_RULES_FILE}") # 로딩 확인 로그
            else:
                print(f"Verilog rules file not found at {VERILOG_RULES_FILE}. Generating without specific rules.")
        except Exception as e:
            print(f"Error loading Verilog rules from {VERILOG_RULES_FILE}: {e}")
        return rules_content

    def _run(self, spec_summary: str, module_name: str) -> Dict[str, Any]:
        """Verilog 모듈 코드를 생성합니다."""
        verilog_rules = self._load_rules()

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

        response = self.llm.invoke(prompt)
        try:
            code_match = response.content.split("```verilog")
            if len(code_match) > 1:
                code = code_match[1].split("```")[0].strip()
            else:
                code_match = response.content.split("```")
                if len(code_match) > 1:
                     code = code_match[1].strip()
                elif "[MUST]" in response.content and ("위반" in response.content or "violates" in response.content):
                    code = "// [MUST] 규칙 위반으로 코드 생성 실패 (아래 설명 참조)"
                else:
                    code = "// 코드 추출 실패"

            desc_match = response.content.split("```")
            if len(desc_match) > 2 :
                 description = desc_match[2].strip()
            elif len(desc_match) == 1 and not code.startswith("// 코드"):
                 description = response.content.strip()
            elif len(desc_match) == 1 and code.startswith("// 코드"):
                 description = "코드 및 설명 추출 실패"
            else:
                 description = response.content

            warnings = [w.strip() for w in description.split("\n") if "주의" in w or "경고" in w or w.startswith("[SHOULD]") or w.startswith("[MUST]") ]

            module = VerilogModule(
                code=code,
                description=description,
                warnings=warnings
            )
            return module.dict()
        except Exception as e:
            print(f"Error parsing LLM response for Verilog generation: {e}")
            code = "// 응답 파싱 오류"
            description = f"LLM 응답 파싱 중 오류 발생: {e}"
            warnings = []

            module = VerilogModule(
                code=code,
                description=description,
                warnings=warnings
            )
            return module.dict()

    async def _arun(self, spec_summary: str, module_name: str) -> Dict[str, Any]:
        raise NotImplementedError("generate_verilog does not support async")

class LintVerilogTool(BaseTool):
    name = "lint_verilog"
    description = "Verilog 코드의 린트 검사를 수행하고 결과를 work 디렉토리에 저장합니다. 시스템에 verilator가 설치되어 있어야 합니다."
    args_schema = LintVerilogInput
    status_manager: StatusManager

    def __init__(self, status_manager: StatusManager, **kwargs):
        super().__init__(**kwargs)
        self.status_manager = status_manager

    def _run(self, code: str) -> Dict[str, Any]:
        """세션 작업 디렉토리에 Verilog 코드를 저장하고 `verilator --lint-only -sv`를 실행합니다."""
        errors = []
        warnings = []
        status = "success"
        work_dir = None

        try:
            work_dir = self.status_manager.get_or_create_work_dir(base_name="lint")

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
                errors.append("Verilator를 찾을 수 없습니다. 시스템에 설치되어 있고 PATH에 등록되어 있는지 확인하세요.")
                with open(err_file_path, 'w', encoding='utf-8') as f:
                    f.write("Error: Verilator not found.")
            except Exception as e:
                status = "failed"
                error_msg = f"Verilator 실행 중 예상치 못한 오류 발생: {str(e)}"
                errors.append(error_msg)
                with open(err_file_path, 'w', encoding='utf-8') as f:
                    f.write(error_msg)

        except Exception as e:
            status = "failed"
            errors.append(f"린트 작업 준비/실행 중 오류 발생: {str(e)}")
            if work_dir and os.path.exists(work_dir):
                try:
                    err_file_path = os.path.join(work_dir, "lint.err")
                    with open(err_file_path, 'w', encoding='utf-8') as f:
                        f.write(f"Error during lint preparation/execution: {str(e)}")
                except Exception as log_e:
                    print(f"Failed to write error log during exception handling: {log_e}")

        result = LintResult(
            status=status,
            errors=errors,
            warnings=warnings,
            exec_dir=work_dir
        )
        return result.dict()

    async def _arun(self, code: str) -> Dict[str, Any]:
        raise NotImplementedError("lint_verilog does not support async") 