from typing import List, Dict, Any, Sequence, Tuple, Optional, Union
from langchain.agents import AgentExecutor, create_react_agent, AgentOutputParser
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import BaseTool, Tool
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.language_models import BaseLanguageModel
from pydantic import create_model

# 도구 함수 임포트
from tools.repo_tools import save_artifact, commit_changes
from tools.spec_tools import load_specification, generate_specification, save_specification
from tools.verilog_tools import generate_verilog, lint_verilog
from tools.testbench_tools import generate_testbench, run_simulation

# StatusManager 임포트
from utils.status_manager import StatusManager

# # work_dir 주입을 위한 CustomAgentExecutor (래핑 방식으로 대체됨)
# class CustomAgentExecutor(AgentExecutor):
#     status_manager: StatusManager
#     # ... (구현 생략)

class DesignAgent:
    def __init__(self, llm: BaseLanguageModel, status_manager: StatusManager, system_prompt: str):
        self.llm = llm
        self.status_manager = status_manager # StatusManager 저장

        # 사용 가능한 도구 함수 목록 (@tool 데코레이터는 BaseTool 객체를 반환)
        available_tools: List[BaseTool] = [
            save_artifact, commit_changes,
            load_specification, generate_specification, save_specification,
            generate_verilog, lint_verilog,
            generate_testbench, run_simulation
        ]

        # work_dir가 필요한 도구를 위한 래퍼 생성
        wrapped_tools: List[BaseTool] = []
        for tool_instance in available_tools:
            if tool_instance.name in ["lint_verilog", "run_simulation"]:
                original_args_schema = tool_instance.args_schema

                # work_dir 필드를 제외한 새 스키마 생성 (Agent가 work_dir 인자를 모르게 하기 위함)
                fields_without_workdir = {
                    k: (v.outer_type_, v.default) 
                    for k, v in original_args_schema.__fields__.items() 
                    if k != 'work_dir'
                }
                # 새 스키마 이름 충돌 방지
                new_schema_name = f'{tool_instance.name}AgentInput'
                new_args_schema = create_model(new_schema_name, **fields_without_workdir)

                # 래퍼 함수 생성
                def create_wrapper(tool_to_wrap: BaseTool, sm: StatusManager, schema_for_agent: BaseModel):
                    
                    # 래핑된 함수 정의 (Agent가 호출할 함수)
                    def wrapped_func(*args, **kwargs):
                        # StatusManager에서 work_dir 가져오기
                        base_name = tool_to_wrap.name.split('_')[0] # 'lint' or 'sim'
                        work_dir = sm.get_or_create_work_dir(base_name=base_name)
                        
                        # 원래 도구 실행 (_run 호출)
                        # kwargs에 work_dir 추가하여 전달
                        kwargs['work_dir'] = work_dir
                        # 원래 도구의 _run 메서드를 호출해야 함
                        # BaseTool의 run 메서드를 사용하여 인자 자동 매핑 활용
                        return tool_to_wrap.run(tool_input=kwargs, verbose=False, start_color=None, color=None)
                        # return tool_to_wrap._run(*args, **kwargs) # 직접 _run 호출 시 인자 순서 문제 발생 가능

                    # 래핑된 함수를 기반으로 새로운 Tool 객체 생성
                    wrapped_tool = Tool(
                        name=tool_to_wrap.name,
                        func=wrapped_func, # 실제 실행될 래퍼 함수
                        description=tool_to_wrap.description,
                        args_schema=schema_for_agent, # Agent에게 노출될 스키마 (work_dir 제외)
                        # return_direct=tool_to_wrap.return_direct # 필요한 경우 설정
                        # coroutine= # 비동기 필요시 설정
                    )
                    return wrapped_tool

                wrapped_tools.append(create_wrapper(tool_instance, self.status_manager, new_args_schema))
            else:
                # 다른 도구들은 그대로 추가
                wrapped_tools.append(tool_instance)

        self.tools = wrapped_tools # 래핑된 도구 리스트 사용

        # 프롬프트 템플릿 설정
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 메모리 설정
        self.memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            k=10
        )

        # 에이전트 생성
        self.agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )

        # 에이전트 실행기 생성
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10 # 반복 제한 증가 (복잡한 작업 고려)
        )

    def run(self, user_input: str) -> Dict[str, Any]:
        """에이전트를 실행하고 결과를 반환합니다."""
        try:
            # invoke 전에 chat_history 로드 (AgentExecutor memory가 처리하지만 명시적 확인)
            # current_memory = self.memory.load_memory_variables({})
            # print(f"Memory before invoke: {current_memory}")
            
            response = self.agent_executor.invoke({"input": user_input})

            # print(f"Memory after invoke: {self.memory.load_memory_variables({})}")
            
            return {
                "status": "success",
                "response": response["output"],
                "intermediate_steps": response.get("intermediate_steps", [])
            }
        except Exception as e:
            print(f"Agent execution error: {e}") # 에러 로깅 추가
            # 에러 발생 시 상세 정보 포함
            import traceback
            tb_str = traceback.format_exc()
            print(f"Traceback: {tb_str}")
            return {
                "status": "error",
                "error": str(e),
                "traceback": tb_str
            }

    def get_memory(self) -> List[BaseMessage]: # 반환 타입 수정
        """현재 메모리 내용을 BaseMessage 리스트로 반환합니다."""
        return self.memory.chat_memory.messages

# 시스템 프롬프트 (work_dir 관련 지침 수정)
SYSTEM_PROMPT = """당신은 Verilog 설계 및 검증을 도와주는 AI 어시스턴트입니다.
다음 규칙을 따라 작업을 수행해주세요:

1. 사용자의 요청을 정확히 이해하고, 필요한 경우 추가 정보를 요청하세요.
2. 각 단계마다 사용자에게 진행 상황을 알리고, 중요한 결정이 필요할 때는 확인을 받으세요.
3. 생성된 코드나 문서는 항상 검토하고, 필요한 경우 수정하세요.
4. 작업이 완료되면 사용자에게 결과를 보여주고, 다음 단계를 제안하세요.
5. 'lint_verilog' 또는 'run_simulation' 도구를 사용할 때는 내부적으로 필요한 작업 디렉토리가 자동으로 관리됩니다. 해당 도구들에 작업 디렉토리 경로를 직접 전달할 필요는 없습니다.

사용 가능한 도구들을 적절히 활용하여 작업을 수행하세요.
""" 