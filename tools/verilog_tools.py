from typing import Dict, Any
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from utils.output_parsers import VerilogModule, LintResult
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

class GenerateVerilogInput(BaseModel):
    """Verilog 코드 생성 입력 모델"""
    spec_summary: str = Field(description="스펙 요약 또는 요구사항 설명")
    module_name: str = Field(description="생성할 모듈 이름")

class LintVerilogInput(BaseModel):
    """Verilog 린트 입력 모델"""
    code: str = Field(description="린트할 Verilog 코드")

class GenerateVerilogTool(BaseTool):
    name = "generate_verilog"
    description = "스펙을 바탕으로 Verilog 모듈 코드를 생성합니다."
    args_schema = GenerateVerilogInput

    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
            model=os.getenv("MODEL_NAME", "qwen-3-30b-a3b"),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7"))
        )

    def _run(self, spec_summary: str, module_name: str) -> Dict[str, Any]:
        """Verilog 모듈 코드를 생성합니다."""
        prompt = f"""
        다음 요구사항을 바탕으로 Verilog 모듈을 생성해주세요:
        
        모듈 이름: {module_name}
        요구사항: {spec_summary}
        
        다음 형식으로 응답해주세요:
        1. 코드 블록에 Verilog 코드를 작성
        2. 코드 설명
        3. 주의사항이나 경고사항
        """
        
        response = self.llm.invoke(prompt)
        code = response.content.split("```")[1].strip()
        description = response.content.split("```")[2].strip()
        warnings = [w.strip() for w in description.split("\n") if "주의" in w or "경고" in w]
        
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
    description = "Verilog 코드의 린트 검사를 수행합니다."
    args_schema = LintVerilogInput

    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(
            base_url="http://localhost:8000/v1",
            api_key="EMPTY",
            model="qwen-3-30b-a3b",
            temperature=0.7
        )

    def _run(self, code: str) -> Dict[str, Any]:
        """Verilog 코드의 린트 검사를 수행합니다."""
        prompt = f"""
        다음 Verilog 코드를 검토하고 린트 검사를 수행해주세요:
        
        ```verilog
        {code}
        ```
        
        다음 형식으로 응답해주세요:
        1. 에러 목록 (없으면 빈 리스트)
        2. 경고 목록 (없으면 빈 리스트)
        3. 개선 제안
        """
        
        response = self.llm.invoke(prompt)
        content = response.content
        
        errors = []
        warnings = []
        
        if "에러" in content:
            errors = [e.strip() for e in content.split("에러")[1].split("\n") if e.strip()]
        if "경고" in content:
            warnings = [w.strip() for w in content.split("경고")[1].split("\n") if w.strip()]
        
        result = LintResult(
            status="success" if not errors else "failed",
            errors=errors,
            warnings=warnings
        )
        return result.dict()

    async def _arun(self, code: str) -> Dict[str, Any]:
        raise NotImplementedError("lint_verilog does not support async") 