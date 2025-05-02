import streamlit as st
from langchain_openai import ChatOpenAI
from agents.design_agent import DesignAgent, SYSTEM_PROMPT
from utils.status_manager import StatusManager
import os
import io
import zipfile
from datetime import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# --- 상태 관리자 초기화 ---
@st.cache_resource
def get_status_manager():
    return StatusManager()

status_manager = get_status_manager()

# --- LLM 및 에이전트 초기화 ---
llm = ChatOpenAI(
    base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
    model=os.getenv("MODEL_NAME", "qwen-3-30b-a3b"),
    temperature=0.7
)
agent = DesignAgent(llm=llm, status_manager=status_manager, system_prompt=SYSTEM_PROMPT)

# --- 사이드바 설정 ---
st.sidebar.title("Design Mate")
st.sidebar.markdown("Verilog 설계 및 검증 AI 어시스턴트")
st.sidebar.markdown("---")
st.sidebar.subheader("메뉴")

# 뷰 전환 함수 수정
def set_view(view_name):
    status_manager.set_main_view(view_name)

# --- 상태 이모지 결정 로직 ---
def get_artifact_status_emoji(artifact_name: str) -> str:
    emoji_map = {"Not Ready": "⚪️", "Generated": "🟡", "Success": "🟢", "Warning": "🟡", "Failed": "🔴", "Unknown": "⚫️"}
    
    if artifact_name == "chat": return "⚫️" # 채팅은 항상 가능
    elif artifact_name == "spec":
        spec = status_manager.get_current_spec()
        return emoji_map["Generated"] if spec and not spec.startswith("아직") else emoji_map["Not Ready"]
    elif artifact_name == "verilog":
        verilog = status_manager.get_current_verilog()
        return emoji_map["Generated"] if verilog and not verilog.startswith("// 아직") else emoji_map["Not Ready"]
    elif artifact_name == "testbench":
        tb = status_manager.get_current_testbench()
        return emoji_map["Generated"] if tb and not tb.startswith("// 아직") else emoji_map["Not Ready"]
    elif artifact_name == "lint":
        status = status_manager.get_last_lint_status()
        if status == "실행 안됨": return emoji_map["Not Ready"]
        if status == "성공": return emoji_map["Success"]
        if "성공 (경고" in status: return emoji_map["Warning"]
        if status.startswith("실패"): return emoji_map["Failed"]
        return emoji_map["Unknown"]
    elif artifact_name == "sim":
        status = status_manager.get_last_sim_status()
        if status == "실행 안됨": return emoji_map["Not Ready"]
        if status == "성공": return emoji_map["Success"]
        if status.startswith("실패"): return emoji_map["Failed"]
        return emoji_map["Unknown"]
    else:
        return emoji_map["Unknown"]

# --- 사이드바 버튼 (이모지 추가) ---
st.sidebar.button(f"{get_artifact_status_emoji('chat')} 💬 채팅 보기", on_click=set_view, args=("chat",), use_container_width=True)
st.sidebar.button(f"{get_artifact_status_emoji('spec')} 📄 명세서 보기", on_click=set_view, args=("spec",), use_container_width=True)
st.sidebar.button(f"{get_artifact_status_emoji('verilog')} 💻 Verilog 보기/편집", on_click=set_view, args=("verilog",), use_container_width=True)
st.sidebar.button(f"{get_artifact_status_emoji('testbench')} 🔬 테스트벤치 보기/편집", on_click=set_view, args=("testbench",), use_container_width=True)
st.sidebar.button(f"{get_artifact_status_emoji('lint')} 📜 Lint 로그 보기", on_click=set_view, args=("lint_log",), use_container_width=True)
st.sidebar.button(f"{get_artifact_status_emoji('sim')} 📊 Sim 로그 보기", on_click=set_view, args=("sim_log",), use_container_width=True)

# --- 다운로드 버튼 추가 --- 
st.sidebar.markdown("---")

# ZIP 생성 함수
def create_work_dir_zip(work_dir_path: str) -> Optional[bytes]:
    if not work_dir_path or not os.path.isdir(work_dir_path):
        return None
    
    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(work_dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # ZIP 파일 내 경로: work_dir 기준 상대 경로
                    arcname = os.path.relpath(file_path, work_dir_path)
                    zipf.write(file_path, arcname)
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
    except Exception as e:
        st.error(f"ZIP 파일 생성 중 오류: {e}")
        return None

# 다운로드 가능 상태 확인 함수
def check_all_ok_status() -> bool:
    work_dir_ok = status_manager.get_current_work_dir() is not None and os.path.isdir(status_manager.get_current_work_dir())
    spec_ok = get_artifact_status_emoji("spec") == "🟡"
    verilog_ok = get_artifact_status_emoji("verilog") == "🟡"
    tb_ok = get_artifact_status_emoji("testbench") == "🟡"
    lint_ok = get_artifact_status_emoji("lint") in ["🟢", "🟡"] # 성공 또는 경고 시 OK
    sim_ok = get_artifact_status_emoji("sim") == "🟢" # 시뮬레이션은 반드시 성공해야 OK
    
    return work_dir_ok and spec_ok and verilog_ok and tb_ok and lint_ok and sim_ok

# 다운로드 버튼 표시
all_ok = check_all_ok_status()
zip_data = None
if all_ok:
    current_work_dir = status_manager.get_current_work_dir()
    zip_data = create_work_dir_zip(current_work_dir)
    
# 버튼 비활성화 로직 추가
st.download_button(
    label="💾 결과 다운로드 (.zip)",
    data=zip_data if zip_data else b"", # 데이터 없으면 빈 바이트 전달
    file_name=f"design_mate_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip" if all_ok and zip_data else "results.zip",
    mime="application/zip",
    disabled=not all_ok or zip_data is None, # 모든 상태 OK이고 ZIP 생성 성공 시 활성화
    use_container_width=True,
    help="모든 단계(Spec, Verilog, TB 생성, Lint, Sim)가 성공적으로 완료되면 활성화됩니다." if not all_ok else "현재 작업 폴더의 모든 내용을 ZIP 파일로 다운로드합니다."
)

# --- 마지막 실행 상태 표시 (추가) ---
st.sidebar.markdown("---")
st.sidebar.subheader("최근 실행 상태")

last_lint_status = status_manager.get_last_lint_status()
last_lint_dir = status_manager.get_last_lint_exec_dir()
st.sidebar.text(f"Lint: {last_lint_status}")
if last_lint_dir:
    st.sidebar.caption(f"로그: {last_lint_dir}") # caption으로 작게 표시

last_sim_status = status_manager.get_last_sim_status()
last_sim_dir = status_manager.get_last_sim_exec_dir()
st.sidebar.text(f"Sim: {last_sim_status}")
if last_sim_dir:
    st.sidebar.caption(f"로그: {last_sim_dir}")

# --- 메인 영역 ---
st.title("Design Mate")

# --- 메인 뷰 렌더링 (StatusManager 사용) ---
current_view = status_manager.get_main_view()

if current_view == "chat":
    st.subheader("채팅")
    # 채팅 기록 로드
    messages = status_manager.get_messages()
    chat_container = st.container(height=600)
    with chat_container:
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # 사용자 입력 처리
    if prompt := st.chat_input("무엇을 도와드릴까요?"):
        # 사용자 메시지 추가 (StatusManager 사용)
        user_message = {"role": "user", "content": prompt}
        status_manager.add_message(user_message)

        # 사용자 메시지 UI 업데이트 (즉시 반영 위해 컨테이너 재활용)
        with chat_container:
            with st.chat_message(user_message["role"]):
                st.markdown(user_message["content"])

        # --- 에이전트 입력에 컨텍스트 추가 --- 
        agent_input = prompt # 기본 입력은 사용자 프롬프트
        current_view = status_manager.get_main_view()
        
        if current_view == "spec":
            current_spec = status_manager.get_current_spec()
            if current_spec and not current_spec.startswith("아직") : # 기본 메시지가 아닐 경우
                agent_input = f"User prompt: {prompt}\n\n[Current Specification Context]\n```markdown\n{current_spec}\n```"
                print("Prepending spec context to agent input.") # 디버깅 로그
        elif current_view == "verilog":
            current_verilog = status_manager.get_current_verilog()
            if current_verilog and not current_verilog.startswith("// 아직") : # 기본 메시지가 아닐 경우
                agent_input = f"User prompt: {prompt}\n\n[Current Verilog Code Context]\n```verilog\n{current_verilog}\n```"
                print("Prepending Verilog code context to agent input.") # 디버깅 로그
        elif current_view == "testbench":
            current_testbench = status_manager.get_current_testbench()
            if current_testbench and not current_testbench.startswith("// 아직") : # 기본 메시지가 아닐 경우
                agent_input = f"User prompt: {prompt}\n\n[Current Testbench Code Context]\n```verilog\n{current_testbench}\n```"
                print("Prepending testbench code context to agent input.") # 디버깅 로그

        # 에이전트 실행 및 응답 처리
        with chat_container:
             with st.spinner("Thinking..."):
                with st.chat_message("assistant"):
                    # 에이전트 실행 (수정된 agent_input 사용)
                    response_data = agent.run(agent_input)
                    response_content = ""

                    if response_data["status"] == "success":
                        response_content = response_data["response"]
                        st.markdown(response_content)
                        # 어시스턴트 메시지 추가
                        assistant_message = {"role": "assistant", "content": response_content}
                        status_manager.add_message(assistant_message)

                        # --- 에이전트 결과 기반 상태 업데이트 --- 
                        intermediate_steps = response_data.get("intermediate_steps", [])
                        if intermediate_steps: # 중간 단계가 있는 경우
                             # 마지막 도구 실행 결과 분석 (ReAct 에이전트는 보통 마지막 단계가 최종 결과)
                             last_step = intermediate_steps[-1]
                             action, observation = last_step # action: AgentAction, observation: 도구 실행 결과(dict)
                             tool_name = action.tool
                             tool_output = observation # observation이 도구 결과 dict라고 가정

                             print(f"Agent used tool: {tool_name}, Output: {tool_output}") # 디버깅 로그

                             # 각 도구 결과에 따른 상태 업데이트
                             if isinstance(tool_output, dict) and tool_output.get("status") == "success":
                                 if tool_name == "generate_specification":
                                     spec_md = tool_output.get("specification_markdown")
                                     if spec_md:
                                         status_manager.set_current_spec(spec_md)
                                 elif tool_name == "generate_verilog":
                                     code = tool_output.get("code")
                                     if code:
                                         status_manager.set_current_verilog(code)
                                 elif tool_name == "generate_testbench":
                                     code = tool_output.get("code")
                                     if code:
                                         status_manager.set_current_testbench(code)
                                 elif tool_name == "lint_verilog":
                                     status_manager.set_last_lint_result(tool_output)
                                 elif tool_name == "run_simulation":
                                     status_manager.set_last_sim_result(tool_output)
                                 # TODO: save_specification, save_artifact 등 다른 도구 결과 처리 추가

                    else:
                        response_content = f"오류가 발생했습니다: {response_data['error']}"
                        st.error(response_content)
                        # 오류 메시지도 채팅 기록에 추가
                        error_message = {"role": "assistant", "content": response_content}
                        status_manager.add_message(error_message)

elif current_view == "spec":
    st.subheader("명세서")
    current_spec = status_manager.get_current_spec() # StatusManager 사용
    st.markdown(current_spec)
    # 명세서 편집 기능은 아직 없음

elif current_view == "verilog":
    st.subheader("Verilog 코드 편집")
    # 현재 코드 가져오기 (StatusManager 사용)
    verilog_code = status_manager.get_current_verilog()
    edited_verilog = st.text_area(
        "Verilog Code",
        value=verilog_code, # 현재 값 표시
        height=400,
        key="verilog_editor"
    )
    if st.button("Verilog 코드 변경사항 저장"):
        # 변경사항 저장 (StatusManager 사용)
        status_manager.set_current_verilog(edited_verilog)
        st.success("Verilog 코드가 저장되었습니다.")
        # 저장 후 UI 즉시 업데이트 위해 rerun (선택적)
        # st.rerun()

elif current_view == "testbench":
    st.subheader("테스트벤치 코드 편집")
    # 현재 코드 가져오기 (StatusManager 사용)
    testbench_code = status_manager.get_current_testbench()
    edited_testbench = st.text_area(
        "Testbench Code",
        value=testbench_code, # 현재 값 표시
        height=400,
        key="testbench_editor"
    )
    if st.button("테스트벤치 코드 변경사항 저장"):
        # 변경사항 저장 (StatusManager 사용)
        status_manager.set_current_testbench(edited_testbench)
        st.success("테스트벤치 코드가 저장되었습니다.")
        # 저장 후 UI 즉시 업데이트 위해 rerun (선택적)
        # st.rerun() 

# --- 로그 보기 뷰 추가 ---
elif current_view == "lint_log":
    st.subheader("최근 Lint 로그")
    exec_dir = status_manager.get_last_lint_exec_dir()
    if exec_dir and os.path.isdir(exec_dir):
        log_file = os.path.join(exec_dir, "lint.log")
        err_file = os.path.join(exec_dir, "lint.err")
        st.markdown(f"**로그 디렉토리:** `{exec_dir}`")
        
        log_content = ""
        err_content = ""
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()
            if os.path.exists(err_file):
                 with open(err_file, 'r', encoding='utf-8') as f:
                     err_content = f.read()
        except Exception as e:
            st.error(f"로그 파일 읽기 오류: {e}")

        if log_content or err_content:
            if log_content:
                 with st.expander("Lint Output (stdout)", expanded=True):
                      st.code(log_content, language='log')
            if err_content:
                 with st.expander("Lint Errors/Warnings (stderr)", expanded=True):
                      st.code(err_content, language='log')
            if not log_content and not err_content:
                 st.info("로그 파일은 존재하지만 내용이 비어 있습니다.")
        else:
            st.warning("로그 파일을 찾을 수 없거나 내용이 없습니다.")
            
    else:
        st.info("아직 실행된 린트 작업이 없거나 로그 디렉토리를 찾을 수 없습니다.")

elif current_view == "sim_log":
    st.subheader("최근 Simulation 로그")
    exec_dir = status_manager.get_last_sim_exec_dir()
    if exec_dir and os.path.isdir(exec_dir):
        log_file = os.path.join(exec_dir, "sim.log")
        err_file = os.path.join(exec_dir, "sim.err")
        st.markdown(f"**로그 디렉토리:** `{exec_dir}`")
        
        log_content = ""
        err_content = ""
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()
            if os.path.exists(err_file):
                 with open(err_file, 'r', encoding='utf-8') as f:
                     err_content = f.read()
        except Exception as e:
            st.error(f"로그 파일 읽기 오류: {e}")

        if log_content or err_content:
            if log_content:
                 with st.expander("Simulation Output (stdout)", expanded=True):
                      st.code(log_content, language='log')
            if err_content:
                 with st.expander("Simulation Errors (stderr)", expanded=True):
                      st.code(err_content, language='log')
            if not log_content and not err_content:
                 st.info("로그 파일은 존재하지만 내용이 비어 있습니다.")
        else:
            st.warning("로그 파일을 찾을 수 없거나 내용이 없습니다.")
    else:
        st.info("아직 실행된 시뮬레이션 작업이 없거나 로그 디렉토리를 찾을 수 없습니다.") 