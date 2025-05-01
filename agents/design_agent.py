from typing import List, Dict, Any
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import BaseTool
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.messages import AIMessage, HumanMessage

class DesignAgent:
    def __init__(self, llm, tools: List[BaseTool], system_prompt: str):
        self.llm = llm
        self.tools = tools
        
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
            k=10  # 최근 10개의 메시지만 유지
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
            handle_parsing_errors=True
        )
    
    def run(self, user_input: str) -> Dict[str, Any]:
        """에이전트를 실행하고 결과를 반환합니다."""
        try:
            response = self.agent_executor.invoke({"input": user_input})
            return {
                "status": "success",
                "response": response["output"],
                "intermediate_steps": response.get("intermediate_steps", [])
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_memory(self) -> List[Dict[str, Any]]:
        """현재 메모리 내용을 반환합니다."""
        return self.memory.chat_memory.messages

# 시스템 프롬프트
SYSTEM_PROMPT = """당신은 Verilog 설계 및 검증을 도와주는 AI 어시스턴트입니다.
다음 규칙을 따라 작업을 수행해주세요:

1. 사용자의 요청을 정확히 이해하고, 필요한 경우 추가 정보를 요청하세요.
2. 각 단계마다 사용자에게 진행 상황을 알리고, 중요한 결정이 필요할 때는 확인을 받으세요.
3. 생성된 코드나 문서는 항상 검토하고, 필요한 경우 수정하세요.
4. 작업이 완료되면 사용자에게 결과를 보여주고, 다음 단계를 제안하세요.

사용 가능한 도구들을 적절히 활용하여 작업을 수행하세요.
""" 