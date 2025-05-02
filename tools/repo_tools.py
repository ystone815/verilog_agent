from typing import Dict, Any
from langchain.tools import tool
from langchain.pydantic_v1 import BaseModel, Field
import os
import subprocess

class SaveArtifactInput(BaseModel):
    """아티팩트 저장 입력 모델"""
    artifact_type: str = Field(description="저장할 아티팩트 타입 (spec/verilog/testbench)")
    content: str = Field(description="저장할 내용")
    file_path: str = Field(description="저장할 파일 경로")

class CommitChangesInput(BaseModel):
    """변경사항 커밋 입력 모델"""
    commit_message: str = Field(description="커밋 메시지")

@tool(args_schema=SaveArtifactInput)
def save_artifact(artifact_type: str, content: str, file_path: str) -> Dict[str, Any]:
    """아티팩트(스펙, 코드 등)를 지정된 파일 경로에 저장합니다."""
    try:
        # 디렉토리가 없으면 생성
        dir_path = os.path.dirname(file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # 파일 쓰기 (인코딩 명시)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        abs_path = os.path.abspath(file_path) # 절대 경로 반환
        return {
            "status": "success",
            "message": f"{artifact_type} 아티팩트를 {abs_path}에 저장했습니다.",
            "file_path": abs_path
        }
    except Exception as e:
        return {
            "status": "failed",
            "message": f"아티팩트 저장 중 오류 발생: {str(e)}"
        }

@tool(args_schema=CommitChangesInput)
def commit_changes(commit_message: str) -> Dict[str, Any]:
    """현재 작업 디렉토리의 변경사항을 Git 저장소에 커밋하고 푸시합니다."""
    try:
        # Git 명령어 실행 (에러 로깅 추가)
        print(f"Running: git add .")
        subprocess.run(['git', 'add', '.'], check=True, capture_output=True, text=True)
        print(f"Running: git commit -m '{commit_message}'")
        subprocess.run(['git', 'commit', '-m', commit_message], check=True, capture_output=True, text=True)
        print(f"Running: git push")
        subprocess.run(['git', 'push'], check=True, capture_output=True, text=True)

        return {
            "status": "success",
            "message": "변경사항이 성공적으로 커밋되고 푸시되었습니다."
        }
    except subprocess.CalledProcessError as e:
        error_message = f"Git 작업 중 오류 발생: {e.stderr or e.stdout or str(e)}"
        print(error_message)
        return {
            "status": "failed",
            "message": error_message
        }
    except Exception as e:
        error_message = f"Git 작업 중 예상치 못한 오류 발생: {str(e)}"
        print(error_message)
        return {
            "status": "failed",
            "message": error_message
        } 