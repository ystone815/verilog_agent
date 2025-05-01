from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class VerilogModule(BaseModel):
    """Verilog 모듈 코드와 설명을 파싱하기 위한 Pydantic 모델"""
    code: str = Field(description="생성된 Verilog 코드")
    description: str = Field(description="코드에 대한 설명")
    warnings: List[str] = Field(default_factory=list, description="코드 생성 시 주의사항이나 경고")

class Specification(BaseModel):
    """스펙 문서 섹션을 파싱하기 위한 Pydantic 모델"""
    title: str = Field(description="섹션 제목")
    content: str = Field(description="섹션 내용")
    summary: str = Field(description="섹션 요약")

class Testbench(BaseModel):
    """테스트벤치 코드와 설명을 파싱하기 위한 Pydantic 모델"""
    code: str = Field(description="생성된 테스트벤치 코드")
    description: str = Field(description="테스트벤치에 대한 설명")
    test_cases: List[str] = Field(description="포함된 테스트 케이스 목록")

class LintResult(BaseModel):
    """Verilog 린트 결과를 파싱하기 위한 Pydantic 모델"""
    status: str = Field(description="린트 상태 (success/failed)")
    errors: List[str] = Field(default_factory=list, description="에러 메시지 목록")
    warnings: List[str] = Field(default_factory=list, description="경고 메시지 목록")

class SimulationResult(BaseModel):
    """시뮬레이션 결과를 파싱하기 위한 Pydantic 모델"""
    status: str = Field(description="시뮬레이션 상태 (success/failed)")
    log: str = Field(description="시뮬레이션 로그")
    summary: str = Field(description="시뮬레이션 결과 요약") 