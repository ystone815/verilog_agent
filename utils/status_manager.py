import os
from datetime import datetime
from typing import Optional, List, Dict, Any

class StatusManager:
    """애플리케이션의 상태 (UI, 데이터, 작업 디렉토리, 실행 상태)를 관리하는 클래스."""
    def __init__(self):
        # 작업 디렉토리
        self._current_work_dir: Optional[str] = None
        # UI 상태
        self._main_view: str = "chat" # 기본값
        # 채팅 기록
        self._messages: List[Dict[str, Any]] = []
        # 현재 작업물
        self._current_spec: str = "아직 생성된 명세서가 없습니다." # 기본값
        self._current_verilog: str = "// 아직 생성된 Verilog 코드가 없습니다." # 기본값
        self._current_testbench: str = "// 아직 생성된 테스트벤치가 없습니다." # 기본값
        # 마지막 실행 상태 추가
        self._last_lint_status: str = "실행 안됨"
        self._last_lint_exec_dir: Optional[str] = None
        self._last_sim_status: str = "실행 안됨"
        self._last_sim_exec_dir: Optional[str] = None

        print(f"StatusManager initialized with default view: {self._main_view}")

    # --- Work Directory Methods ---
    def get_current_work_dir(self) -> Optional[str]:
        """현재 설정된 작업 디렉토리 경로를 반환합니다."""
        return self._current_work_dir

    def reset_work_dir(self) -> None:
        """현재 작업 디렉토리 설정을 초기화합니다."""
        print(f"Resetting work directory. Previous: {self._current_work_dir}")
        self._current_work_dir = None

    def get_or_create_work_dir(self, base_name: str = "work") -> str:
        """현재 작업 디렉토리를 반환하거나, 없으면 새로 생성하여 반환합니다.

        Args:
            base_name: 새 디렉토리 생성 시 사용할 기본 이름 (예: 'lint', 'sim')

        Returns:
            확보된 작업 디렉토리의 절대 경로.
        """
        if self._current_work_dir and os.path.isdir(self._current_work_dir):
            # print(f"Using existing work directory: {self._current_work_dir}") # 로그 너무 많아질 수 있어 주석처리
            return self._current_work_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_work_dir = "work"
            new_work_dir = os.path.abspath(os.path.join(base_work_dir, f"{base_name}_{timestamp}"))
            try:
                os.makedirs(new_work_dir, exist_ok=True)
                self._current_work_dir = new_work_dir
                print(f"Created and set new work directory: {self._current_work_dir}")
                return self._current_work_dir
            except Exception as e:
                print(f"Error creating work directory {new_work_dir}: {e}")
                # 디렉토리 생성 실패 시 예외 발생 또는 에러 처리 필요
                # 여기서는 일단 에러를 발생시켜 상위 호출자가 처리하도록 함
                raise IOError(f"Failed to create work directory: {new_work_dir}") from e 

    # --- Main View Methods ---
    def get_main_view(self) -> str:
        return self._main_view

    def set_main_view(self, view_name: str) -> None:
        print(f"Setting main view from {self._main_view} to {view_name}")
        self._main_view = view_name

    # --- Messages Methods ---
    def get_messages(self) -> List[Dict[str, Any]]:
        return self._messages

    def add_message(self, message: Dict[str, Any]) -> None:
        self._messages.append(message)
        # print(f"Added message: {message['role']}") # 로그 필요시 주석 해제

    def clear_messages(self) -> None:
        print("Clearing chat messages.")
        self._messages = []

    # --- Current Artifact Methods ---
    def get_current_spec(self) -> str:
        return self._current_spec

    def set_current_spec(self, spec_markdown: str) -> None:
        print("Updating current specification.")
        self._current_spec = spec_markdown

    def get_current_verilog(self) -> str:
        return self._current_verilog

    def set_current_verilog(self, code: str) -> None:
        print("Updating current Verilog code.")
        self._current_verilog = code

    def get_current_testbench(self) -> str:
        return self._current_testbench

    def set_current_testbench(self, code: str) -> None:
        print("Updating current testbench code.")
        self._current_testbench = code 

    # --- Last Run Status Methods ---
    def get_last_lint_status(self) -> str:
        return self._last_lint_status

    def get_last_lint_exec_dir(self) -> Optional[str]:
        return self._last_lint_exec_dir

    def set_last_lint_result(self, result: Dict[str, Any]) -> None:
        """LintResult 딕셔너리를 받아 마지막 린트 상태를 업데이트합니다."""
        lint_status = result.get("status", "unknown").lower()
        warnings = result.get("warnings", [])
        errors = result.get("errors", [])
        exec_dir = result.get("exec_dir")

        if lint_status == "success":
            if warnings:
                self._last_lint_status = f"성공 (경고 {len(warnings)}개)"
            else:
                self._last_lint_status = "성공"
        elif lint_status == "failed":
             self._last_lint_status = f"실패 (에러 {len(errors)}개)"
        else:
             self._last_lint_status = "알 수 없음"

        self._last_lint_exec_dir = exec_dir
        print(f"Updated last lint status: {self._last_lint_status}, exec_dir: {self._last_lint_exec_dir}")

    def get_last_sim_status(self) -> str:
        return self._last_sim_status

    def get_last_sim_exec_dir(self) -> Optional[str]:
        return self._last_sim_exec_dir

    def set_last_sim_result(self, result: Dict[str, Any]) -> None:
        """SimulationResult 딕셔너리를 받아 마지막 시뮬레이션 상태를 업데이트합니다."""
        sim_status = result.get("status", "unknown").lower()
        errors = result.get("errors", []) # 시뮬레이션 에러 필드 사용
        exec_dir = result.get("exec_dir")

        # 상태 문자열 개선
        if sim_status == "success":
            self._last_sim_status = "성공"
        elif sim_status == "failed":
            if errors:
                 self._last_sim_status = f"실패 (에러 {len(errors)}개)"
            else:
                 # 로그에서 실패 원인 찾아보기 (간단 예시)
                 log_summary = result.get("summary", "")
                 if "FAIL" in log_summary or "fail" in log_summary:
                     self._last_sim_status = "실패 (로그 확인 필요)"
                 else:
                     self._last_sim_status = "실패 (원인 불명)"
        else:
            self._last_sim_status = "알 수 없음"

        self._last_sim_exec_dir = exec_dir
        print(f"Updated last simulation status: {self._last_sim_status}, exec_dir: {self._last_sim_exec_dir}") 