from typing import Dict, Any
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
# from utils.output_parsers import Specification # 더 이상 사용 안 함
import os # 추가
from dotenv import load_dotenv # 추가
from langchain_openai import ChatOpenAI

load_dotenv()

# 스펙 템플릿 파일 경로 정의
SPEC_TEMPLATE_FILE = os.path.join("config", "spec_template.md")

class LoadSpecInput(BaseModel):
    """스펙 문서 로드 입력 모델"""
    source: str = Field(description="스펙 문서의 출처 (파일 경로 또는 텍스트)")

class GenerateSpecInput(BaseModel): # 입력 스키마 수정
    """스펙 생성 입력 모델"""
    requirements: str = Field(description="스펙 생성에 필요한 요구사항 설명")
    module_name: str = Field(description="생성할 모듈의 이름")
    # section 필드 제거
    
# SaveSpecificationInput 스키마 추가
class SaveSpecificationInput(BaseModel):
    """스펙 저장 입력 모델"""
    specification_markdown: str = Field(description="저장할 스펙 Markdown 내용")
    file_path: str = Field(description="스펙을 저장할 파일 경로 (예: work/sim_xxxxxxxx_xxxxxx/specs.md)")

class LoadSpecificationTool(BaseTool):
    name = "load_specification"
    description = "스펙 문서를 로드하고 분석합니다."
    args_schema = LoadSpecInput

    def _run(self, source: str) -> Dict[str, Any]:
        """스펙 문서를 로드하고 분석합니다."""
        # 실제 구현에서는 파일 읽기 또는 텍스트 처리 로직이 들어감
        # TODO: 실제 파일 읽기 및 LLM 기반 요약 기능 구현 필요
        try:
            # 예시: 만약 source가 파일 경로이고 존재한다면 읽기 시도
            if os.path.exists(source):
                 with open(source, 'r', encoding='utf-8') as f:
                     content = f.read()
                 summary = f"'{source}' 파일에서 스펙을 로드했습니다. (내용 요약 필요)"
                 return {"status": "success", "content": content, "source": source, "summary": summary}
            else:
                 # 파일 경로가 아니거나 존재하지 않으면 source 자체를 content로 간주 (텍스트 입력)
                 content = source
                 summary = "텍스트로 제공된 스펙을 로드했습니다. (내용 요약 필요)"
                 return {"status": "success", "content": content, "source": "text", "summary": summary}
        except Exception as e:
             return {"status": "failed", "error": f"스펙 로드 중 오류 발생: {str(e)}"}


    async def _arun(self, source: str) -> Dict[str, Any]:
        raise NotImplementedError("load_specification does not support async")

class GenerateSpecificationTool(BaseTool): # 도구 수정
    name = "generate_specification"
    description = "요구사항과 템플릿을 바탕으로 완전한 Verilog 모듈 스펙 문서를 Markdown 형식으로 생성합니다."
    args_schema = GenerateSpecInput

    # LLM 초기화 추가 (VerilogTool과 유사하게)
    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
            model=os.getenv("MODEL_NAME", "qwen-3-30b-a3b"),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.5")) # 스펙 생성은 좀 더 결정적으로
        )

    def _load_template(self) -> str:
        """스펙 템플릿 파일을 읽어옵니다."""
        template_content = ""
        try:
            if os.path.exists(SPEC_TEMPLATE_FILE):
                with open(SPEC_TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                print(f"Loaded spec template from {SPEC_TEMPLATE_FILE}")
            else:
                print(f"Spec template file not found at {SPEC_TEMPLATE_FILE}. Using basic generation.")
                # 템플릿 없을 경우 대비 기본 구조 제공 (선택적)
                template_content = "# Module Specification: {{MODULE_NAME}}\n\n## Overview\n\n## Inputs\n\n## Outputs\n\n## Functional Description\n"
        except Exception as e:
            print(f"Error loading spec template from {SPEC_TEMPLATE_FILE}: {e}")
            template_content = "# Module Specification: {{MODULE_NAME}}\n\n## Overview\n\n## Inputs\n\n## Outputs\n\n## Functional Description\n" # 오류 시 기본 구조
        return template_content

    def _run(self, requirements: str, module_name: str) -> Dict[str, Any]: # 입력 변경
        """템플릿과 요구사항을 기반으로 전체 스펙 문서를 생성합니다."""
        spec_template = self._load_template()

        # 템플릿 내 플레이스홀더를 모듈 이름으로 기본 채우기 (선택적)
        processed_template = spec_template.replace("{{MODULE_NAME}}", module_name)

        prompt = f"""
        당신은 Verilog 모듈 설계 전문가입니다. 다음 사용자 요구사항과 제공된 스펙 템플릿을 바탕으로 **완전한** Verilog 모듈 스펙 문서를 Markdown 형식으로 작성해주세요.

        **모듈 이름:** {module_name}
        **사용자 요구사항:**
        ```
        {requirements}
        ```

        **스펙 템플릿 (이 구조와 형식을 따라야 합니다):**
        ```markdown
        {processed_template}
        ```

        **작성 지침:**
        1.  템플릿의 각 섹션 (`## Overview`, `## Parameters`, `## Inputs`, `## Outputs`, `## Functional Description` 등)을 요구사항에 맞게 **상세하고 명확하게** 채워주세요.
        2.  **Parameters, Inputs, Outputs 섹션은 반드시 템플릿에 명시된 Markdown 테이블 형식**을 따라야 합니다. 각 컬럼(이름, 폭, 타입, 설명 등)을 정확하게 작성해주세요. 해당 사항이 없으면 테이블 내용은 비워두거나 '없음'이라고 명시하세요.
        3.  포트 이름은 `config/verilog_rules.md`에 정의된 명명 규칙(`i_`, `o_` 접두사 등)을 따라야 합니다. (이 도구는 규칙 파일을 직접 읽지는 않지만, 사용자가 요구사항에 관련 내용을 포함했을 수 있음을 가정)
        4.  템플릿에 포함된 `{{PLACEHOLDER}}` 표시는 실제 내용으로 대체되어야 합니다.
        5.  최종 결과물은 **완전한 Markdown 문서** 자체여야 합니다. 다른 부가 설명 없이 스펙 문서 내용만 응답해주세요.
        """

        try:
            response = self.llm.invoke(prompt)
            generated_spec_md = response.content.strip()

            # 간단한 유효성 검사 (예: 테이블 헤더 존재 여부)
            if "| 이름" not in generated_spec_md or "|---|" not in generated_spec_md:
                 print("Warning: Generated spec might not contain the required tables.")
                 # 필요 시 여기서 실패 처리 또는 재시도 로직 추가 가능

            return {"status": "success", "specification_markdown": generated_spec_md}

        except Exception as e:
            print(f"Error during specification generation: {e}")
            return {"status": "failed", "error": f"스펙 생성 중 오류 발생: {str(e)}"}


    async def _arun(self, requirements: str, module_name: str) -> Dict[str, Any]: # 입력 변경
        raise NotImplementedError("generate_specification does not support async") 

# SaveSpecificationTool 클래스 추가
class SaveSpecificationTool(BaseTool):
    name = "save_specification"
    description = "생성된 스펙 문서를 지정된 파일 경로에 Markdown 파일로 저장합니다."
    args_schema = SaveSpecificationInput

    def _run(self, specification_markdown: str, file_path: str) -> Dict[str, Any]:
        """스펙 Markdown 내용을 파일로 저장합니다."""
        try:
            # 디렉토리 생성 (필요 시)
            dir_name = os.path.dirname(file_path)
            if dir_name: # 파일 경로에 디렉토리가 포함된 경우
                 os.makedirs(dir_name, exist_ok=True)

            # 파일 쓰기
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(specification_markdown)

            abs_path = os.path.abspath(file_path) # 절대 경로 반환
            return {
                "status": "success",
                "message": f"스펙 문서를 {abs_path} 에 저장했습니다.",
                "file_path": abs_path
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": f"스펙 파일 저장 중 오류 발생: {str(e)}"
            }

    async def _arun(self, specification_markdown: str, file_path: str) -> Dict[str, Any]:
        raise NotImplementedError("save_specification does not support async") 