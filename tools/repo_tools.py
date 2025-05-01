from typing import Dict, Any
from langchain.tools import BaseTool
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

class SaveArtifactTool(BaseTool):
    name = "save_artifact"
    description = "아티팩트(스펙, 코드 등)를 파일로 저장합니다."
    args_schema = SaveArtifactInput

    def _run(self, artifact_type: str, content: str, file_path: str) -> Dict[str, Any]:
        """아티팩트를 파일로 저장합니다."""
        try:
            # 디렉토리가 없으면 생성
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 파일 쓰기
            with open(file_path, 'w') as f:
                f.write(content)
            
            return {
                "status": "success",
                "message": f"{artifact_type} 아티팩트를 {file_path}에 저장했습니다.",
                "file_path": file_path
            }
        except Exception as e:
            return {
                "status": "failed",
                "message": f"아티팩트 저장 중 오류 발생: {str(e)}"
            }

    async def _arun(self, artifact_type: str, content: str, file_path: str) -> Dict[str, Any]:
        raise NotImplementedError("save_artifact does not support async")

class CommitChangesTool(BaseTool):
    name = "commit_changes"
    description = "변경된 파일들을 Git 저장소에 커밋하고 푸시합니다."
    args_schema = CommitChangesInput

    def _run(self, commit_message: str) -> Dict[str, Any]:
        """변경사항을 커밋하고 푸시합니다."""
        try:
            # Git 명령어 실행
            subprocess.run(['git', 'add', '.'], check=True)
            subprocess.run(['git', 'commit', '-m', commit_message], check=True)
            subprocess.run(['git', 'push'], check=True)
            
            return {
                "status": "success",
                "message": "변경사항이 성공적으로 커밋되고 푸시되었습니다."
            }
        except subprocess.CalledProcessError as e:
            return {
                "status": "failed",
                "message": f"Git 작업 중 오류 발생: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "failed",
                "message": f"예상치 못한 오류 발생: {str(e)}"
            }

    async def _arun(self, commit_message: str) -> Dict[str, Any]:
        raise NotImplementedError("commit_changes does not support async") 