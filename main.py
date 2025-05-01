import streamlit as st
from langchain_openai import ChatOpenAI
from agents.design_agent import DesignAgent, SYSTEM_PROMPT
from tools.spec_tools import LoadSpecificationTool, GenerateSpecificationTool
from tools.verilog_tools import GenerateVerilogTool, LintVerilogTool
from tools.testbench_tools import GenerateTestbenchTool, RunSimulationTool
from tools.repo_tools import SaveArtifactTool, CommitChangesTool
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_spec" not in st.session_state:
    st.session_state.current_spec = None

if "current_verilog" not in st.session_state:
    st.session_state.current_verilog = None

if "current_testbench" not in st.session_state:
    st.session_state.current_testbench = None

# 도구 초기화
tools = [
    LoadSpecificationTool(),
    GenerateSpecificationTool(),
    GenerateVerilogTool(),
    LintVerilogTool(),
    GenerateTestbenchTool(),
    RunSimulationTool(),
    SaveArtifactTool(),
    CommitChangesTool()
]

# LLM 초기화
llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",  # 로컬 서버 URL
    api_key="EMPTY",  # API 키는 비워둠
    model="qwen-3-30b-a3b",
    temperature=0.7
)

# 에이전트 초기화
agent = DesignAgent(llm, tools, SYSTEM_PROMPT)

# 사이드바 설정
st.sidebar.title("Design Mate")
st.sidebar.markdown("Verilog 설계 및 검증을 도와주는 AI 어시스턴트입니다.")

# 메인 컨테이너
st.title("Design Mate")
st.markdown("Verilog 설계 및 검증을 도와주는 AI 어시스턴트입니다.")

# 채팅 인터페이스
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input("무엇을 도와드릴까요?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 에이전트 실행
    with st.chat_message("assistant"):
        response = agent.run(prompt)
        if response["status"] == "success":
            st.markdown(response["response"])
            st.session_state.messages.append({"role": "assistant", "content": response["response"]})
        else:
            st.error(f"오류가 발생했습니다: {response['error']}")

# 현재 작업물 표시
st.sidebar.markdown("---")
st.sidebar.subheader("현재 작업물")

if st.session_state.current_spec:
    with st.sidebar.expander("명세서"):
        st.markdown(st.session_state.current_spec)

if st.session_state.current_verilog:
    with st.sidebar.expander("Verilog 코드"):
        st.code(st.session_state.current_verilog, language="verilog")

if st.session_state.current_testbench:
    with st.sidebar.expander("테스트벤치"):
        st.code(st.session_state.current_testbench, language="verilog") 