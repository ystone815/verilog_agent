from typing import Dict, Any
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from utils.output_parsers import Testbench, SimulationResult
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

class GenerateTestbenchInput(BaseModel):
    """테스트벤치 생성 입력 모델"""
    verilog_code: str = Field(description="테스트할 Verilog 모듈 코드")
    test_cases: str = Field(description="테스트 케이스 설명")

class RunSimulationInput(BaseModel):
    """시뮬레이션 실행 입력 모델"""
    verilog_code: str = Field(description="시뮬레이션할 Verilog 모듈 코드")
    testbench_code: str = Field(description="테스트벤치 코드")

class GenerateTestbenchTool(BaseTool):
    name = "generate_testbench"
    description = "Verilog 모듈에 대한 테스트벤치 코드를 생성합니다."
    args_schema = GenerateTestbenchInput

    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
            model=os.getenv("MODEL_NAME", "qwen-3-30b-a3b"),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7"))
        )

    def _run(self, verilog_code: str, test_cases: str) -> Dict[str, Any]:
        """테스트벤치 코드를 생성합니다."""
        prompt = f"""
        다음 Verilog 모듈에 대한 테스트벤치를 생성해주세요:
        
        Verilog 모듈 코드:
        ```verilog
        {verilog_code}
        ```
        
        테스트 케이스:
        {test_cases}
        
        다음 형식으로 응답해주세요:
        1. 코드 블록에 테스트벤치 코드를 작성
        2. 테스트벤치 설명
        3. 포함된 테스트 케이스 목록
        """
        
        response = self.llm.invoke(prompt)
        code = response.content.split("```")[1].strip()
        description = response.content.split("```")[2].strip()
        test_cases_list = [tc.strip() for tc in description.split("\n") if tc.strip()]
        
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
    description = "Verilog 모듈과 테스트벤치를 시뮬레이션합니다."
    args_schema = RunSimulationInput

    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(
            base_url="http://localhost:8000/v1",
            api_key="EMPTY",
            model="qwen-3-30b-a3b",
            temperature=0.7
        )

    def _run(self, verilog_code: str, testbench_code: str) -> Dict[str, Any]:
        """시뮬레이션을 실행합니다."""
        prompt = f"""
        다음 Verilog 모듈과 테스트벤치를 시뮬레이션하고 결과를 분석해주세요:
        
        Verilog 모듈 코드:
        ```verilog
        {verilog_code}
        ```
        
        테스트벤치 코드:
        ```verilog
        {testbench_code}
        ```
        
        다음 형식으로 응답해주세요:
        1. 시뮬레이션 상태 (성공/실패)
        2. 시뮬레이션 로그
        3. 시뮬레이션 결과 요약
        """
        
        response = self.llm.invoke(prompt)
        content = response.content
        
        status = "success" if "성공" in content else "failed"
        log = content.split("로그")[1].split("요약")[0].strip() if "로그" in content else ""
        summary = content.split("요약")[1].strip() if "요약" in content else ""
        
        result = SimulationResult(
            status=status,
            log=log,
            summary=summary
        )
        return result.dict()

    async def _arun(self, verilog_code: str, testbench_code: str) -> Dict[str, Any]:
        raise NotImplementedError("run_simulation does not support async") 