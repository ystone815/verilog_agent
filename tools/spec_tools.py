from typing import Dict, Any
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from utils.output_parsers import Specification

class LoadSpecInput(BaseModel):
    """스펙 문서 로드 입력 모델"""
    source: str = Field(description="스펙 문서의 출처 (파일 경로 또는 텍스트)")

class GenerateSpecInput(BaseModel):
    """스펙 생성 입력 모델"""
    requirements: str = Field(description="스펙 생성에 필요한 요구사항 설명")
    section: str = Field(description="생성할 스펙 섹션 (예: 목적, 기능, 인터페이스)")

class LoadSpecificationTool(BaseTool):
    name = "load_specification"
    description = "스펙 문서를 로드하고 분석합니다."
    args_schema = LoadSpecInput

    def _run(self, source: str) -> Dict[str, Any]:
        """스펙 문서를 로드하고 분석합니다."""
        # 실제 구현에서는 파일 읽기 또는 텍스트 처리 로직이 들어감
        return {
            "status": "success",
            "content": f"--- Spec Content from {source} ---",
            "source": source,
            "summary": "스펙 문서가 성공적으로 로드되었습니다."
        }

    async def _arun(self, source: str) -> Dict[str, Any]:
        raise NotImplementedError("load_specification does not support async")

class GenerateSpecificationTool(BaseTool):
    name = "generate_specification"
    description = "요구사항을 바탕으로 스펙 문서의 특정 섹션을 생성합니다."
    args_schema = GenerateSpecInput

    def _run(self, requirements: str, section: str) -> Dict[str, Any]:
        """스펙 섹션을 생성합니다."""
        # 실제 구현에서는 LLM을 사용하여 스펙 생성
        spec = Specification(
            title=section,
            content=f"Generated content for {section} based on: {requirements}",
            summary=f"Summary of {section} section"
        )
        return spec.dict()

    async def _arun(self, requirements: str, section: str) -> Dict[str, Any]:
        raise NotImplementedError("generate_specification does not support async") 