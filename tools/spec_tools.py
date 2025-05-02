from typing import Dict, Any
from langchain.tools import tool # BaseTool 대신 tool 임포트
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

@tool(args_schema=LoadSpecInput)
def load_specification(source: str) -> Dict[str, Any]:
    """주어진 출처(파일 경로 또는 텍스트)로부터 스펙 문서를 로드하고 내용을 반환합니다."""
    try:
        if os.path.exists(source):
            with open(source, 'r', encoding='utf-8') as f:
                content = f.read()
            summary = f"'{source}' 파일에서 스펙을 로드했습니다." # TODO: LLM 요약 추가 고려
            return {"status": "success", "content": content, "source_type": "file", "source_path": os.path.abspath(source), "summary": summary}
        else:
            content = source
            summary = "텍스트로 제공된 스펙을 로드했습니다." # TODO: LLM 요약 추가 고려
            return {"status": "success", "content": content, "source_type": "text", "summary": summary}
    except Exception as e:
        return {"status": "failed", "error": f"스펙 로드 중 오류 발생: {str(e)}"}

def _load_spec_template() -> str:
    """스펙 템플릿 파일을 읽어옵니다. (내부 헬퍼 함수)"""
    template_content = ""
    try:
        if os.path.exists(SPEC_TEMPLATE_FILE):
            with open(SPEC_TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                template_content = f.read()
            print(f"Loaded spec template from {SPEC_TEMPLATE_FILE}")
        else:
            print(f"Spec template file not found at {SPEC_TEMPLATE_FILE}. Using basic generation.")
            template_content = "# Module Specification: {{MODULE_NAME}}\n\n## Overview\n\n## Inputs\n\n## Outputs\n\n## Functional Description\n"
    except Exception as e:
        print(f"Error loading spec template from {SPEC_TEMPLATE_FILE}: {e}")
        template_content = "# Module Specification: {{MODULE_NAME}}\n\n## Overview\n\n## Inputs\n\n## Outputs\n\n## Functional Description\n"
    return template_content

@tool(args_schema=GenerateSpecInput)
def generate_specification(requirements: str, module_name: str) -> Dict[str, Any]:
    """사용자 요구사항과 스펙 템플릿을 바탕으로 완전한 Verilog 모듈 스펙 문서를 Markdown 형식으로 생성합니다."""
    llm = ChatOpenAI(
        base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
        model=os.getenv("MODEL_NAME", "qwen-3-30b-a3b"),
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.5"))
    )
    spec_template = _load_spec_template()
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
    3.  포트 이름은 `config/verilog_rules.md`에 정의된 명명 규칙(`i_`, `o_` 접두사 등)을 따라야 합니다. (사용자가 요구사항에 관련 내용을 포함했을 수 있음을 가정)
    4.  템플릿에 포함된 `{{PLACEHOLDER}}` 표시는 실제 내용으로 대체되어야 합니다.
    5.  최종 결과물은 **완전한 Markdown 문서** 자체여야 합니다. 다른 부가 설명 없이 스펙 문서 내용만 응답해주세요.
    """

    try:
        response = llm.invoke(prompt)
        generated_spec_md = response.content.strip()
        # 간단한 유효성 검사
        if "| 이름" not in generated_spec_md or "|---|" not in generated_spec_md:
            print("Warning: Generated spec might not contain the required tables.")

        return {"status": "success", "specification_markdown": generated_spec_md}

    except Exception as e:
        print(f"Error during specification generation: {e}")
        return {"status": "failed", "error": f"스펙 생성 중 오류 발생: {str(e)}"}

@tool(args_schema=SaveSpecificationInput)
def save_specification(specification_markdown: str, file_path: str) -> Dict[str, Any]:
    """생성된 스펙 문서를 지정된 파일 경로에 Markdown 파일로 저장합니다."""
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(specification_markdown)
        abs_path = os.path.abspath(file_path)
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