import asyncio
import logging
import re
import os
import time
import uuid
import json
from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import Generator, Dict, Any, AsyncIterator, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_community.llms import Ollama
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from utils.date_query_toolkit import DateQueryToolkit
from utils.file_write_toolkit import FileWriteToolkit
from utils.poultry_log_toolkit import PoultryLogToolkit
from utils.weather_toolkit import WeatherToolkit
from utils.wiki_sarch_toolkit import WikipediaSearchTool

from dotenv import load_dotenv

# 初始化日志和环境变量
load_dotenv()
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.DEBUG)

# 初始化 FastAPI 应用
app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上下文变量用于存储请求ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

# 线程池执行同步操作
executor = ThreadPoolExecutor()

sessions: Dict[str, AgentExecutor] = {}
output_dir = os.getenv("OUTPUT_DIR", "./output")

# 存储会话历史
chat_histories: Dict[str, List[Dict[str, str]]] = {}

def clean_ansi(text: str) -> str:
    """清理ANSI转义序列"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

class RequestLogHandler(logging.Handler):
    """自定义日志处理器，用于捕获特定请求的日志"""
    def __init__(self, request_id: str, queue: Queue):
        super().__init__()
        self.request_id = request_id
        self.queue = queue
        self.setFormatter(logging.Formatter('%(message)s'))
        self.action_counter = {}  # 用于跟踪每种行为的计数
        self.current_action = None  # 用于跟踪当前正在处理的动作
        self.buffer = ""  # 用于缓冲消息
        
    def filter(self, record):
        """过滤非当前请求的日志"""
        return getattr(record, 'request_id', "") == self.request_id

    def get_action_id(self, msg_type: str) -> str:
        """获取行为的唯一标识符"""
        if msg_type not in self.action_counter:
            self.action_counter[msg_type] = 0
        self.action_counter[msg_type] += 1
        return f"{msg_type}_{self.action_counter[msg_type]}"

    def parse_agent_message(self, msg: str) -> tuple[str, str, str]:
        """解析agent消息，返回消息类型、内容和唯一标识符"""
        msg = clean_ansi(msg)
        
        # 定义消息类型和对应的前缀
        message_types = {
            "chain_start": ["Entering new AgentExecutor chain"],
            "chain_end": ["Finished chain"],
            "thought": ["Thought:", "思考:"],
            "action": ["Action:", "行动:"],
            "action_input": ["Action Input:", "输入:"],
            "observation": ["Observation:", "结果:"],
            "answer": ["Final Answer:", "回答:"],
            "error": ["Error:", "error:", "Error occurred", "error occurred"]
        }
        
        # 检查消息类型
        for msg_type, prefixes in message_types.items():
            for prefix in prefixes:
                if prefix in msg:
                    # 对于所有消息类型，返回完整消息
                    if msg_type == "chain_start":
                        return msg_type, "Entering new AgentExecutor chain...", self.get_action_id(msg_type)
                    elif msg_type == "thought":
                        return msg_type, msg, self.get_action_id(msg_type)
                    elif msg_type == "action":
                        return msg_type, msg, self.get_action_id(msg_type)
                    elif msg_type == "action_input":
                        return msg_type, msg, self.get_action_id(msg_type)
                    elif msg_type == "observation":
                        return msg_type, msg, self.get_action_id(msg_type)
                    elif msg_type == "answer":
                        # 对于最终答案，移除前缀
                        content = msg.split(prefix, 1)[1].strip() if prefix in msg else msg
                        return msg_type, content, self.get_action_id(msg_type)
                    return msg_type, msg, self.get_action_id(msg_type)
        
        # 如果没有匹配到特定类型，检查是否是工具输出
        if "{" in msg and "}" in msg:
            try:
                # 尝试解析JSON格式的工具输出
                import json
                json.loads(msg)
                action_id = self.get_action_id("tool_output")
                return "tool_output", msg, action_id
            except:
                pass
        
        # 默认返回为普通日志
        action_id = self.get_action_id("log")
        return "log", msg, action_id

    def emit(self, record):
        """将日志放入队列"""
        try:
            record.request_id = self.request_id
            msg = self.format(record)
            
            # 将消息添加到缓冲区
            self.buffer += msg
            
            # 如果缓冲区包含完整的消息（以换行符结束）
            if "\n" in self.buffer:
                # 分割缓冲区中的消息
                messages = self.buffer.split("\n")
                # 处理除最后一个消息外的所有消息
                for message in messages[:-1]:
                    if message.strip():
                        # 解析消息类型、内容和唯一标识符
                        msg_type, content, action_id = self.parse_agent_message(message)
                        
                        # 确保消息内容不为空
                        if content:
                            # 对于所有消息，直接发送完整消息
                            self.queue.put({
                                "type": msg_type,
                                "content": content,  # 不添加换行符，因为前端会处理
                                "action_id": action_id,
                                "timestamp": record.created,
                                "is_complete": True  # 标记为完整消息
                            })
                
                # 保留最后一个不完整的消息在缓冲区中
                self.buffer = messages[-1]
        except Exception:
            self.handleError(record)

class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self, queue: Queue):
        self.queue = queue
        self.action_counter = {}  # 用于跟踪每种行为的计数
        
    def get_action_id(self, msg_type: str) -> str:
        """获取行为的唯一标识符"""
        if msg_type not in self.action_counter:
            self.action_counter[msg_type] = 0
        self.action_counter[msg_type] += 1
        return f"{msg_type}_{self.action_counter[msg_type]}"
        
    def _stream_text(self, text: str, msg_type: str):
        """将文本以打字机效果输出"""
        action_id = self.get_action_id(msg_type)
        
        # 对于最终答案，直接发送内容
        if msg_type == "answer":
            for char in text:
                self.queue.put({
                    "type": msg_type,
                    "content": char,
                    "action_id": action_id
                })
                time.sleep(0.05)
        else:
            # 其他类型的消息，发送完整消息
            for char in text:
                self.queue.put({
                    "type": msg_type,
                    "content": char,
                    "action_id": action_id
                })
                time.sleep(0.05)
            
        # 添加换行符
        self.queue.put({
            "type": msg_type,
            "content": "\n",
            "action_id": action_id
        })

    def on_agent_thought(self, thought: str, **kwargs):
        """处理agent的思考过程"""
        # 直接发送完整消息
        self.queue.put({
            "type": "thought",
            "content": "Thought: " + thought + "\n",
            "action_id": self.get_action_id("thought")
        })
        
    def on_agent_action(self, action, **kwargs):
        """处理agent的行动"""
        # 直接发送完整消息
        self.queue.put({
            "type": "action",
            "content": "Action: " + action.tool + "\n",
            "action_id": self.get_action_id("action")
        })
        self.queue.put({
            "type": "action_input",
            "content": "Action Input: " + str(action.tool_input) + "\n",
            "action_id": self.get_action_id("action_input")
        })
        
    def on_tool_start(self, serialized, input_str, **kwargs):
        """处理工具开始执行"""
        # 直接发送完整消息
        self.queue.put({
            "type": "tool_start",
            "content": "Tool: " + serialized['name'] + "\n",
            "action_id": self.get_action_id("tool_start")
        })
        
    def on_tool_end(self, output, **kwargs):
        """处理工具执行结果"""
        # 如果是JSON格式的输出，尝试格式化显示
        if isinstance(output, dict):
            formatted_output = json.dumps(output, ensure_ascii=False, indent=2)
            self.queue.put({
                "type": "observation",
                "content": "Observation: " + formatted_output + "\n",
                "action_id": self.get_action_id("observation")
            })
        else:
            self.queue.put({
                "type": "observation",
                "content": "Observation: " + str(output) + "\n",
                "action_id": self.get_action_id("observation")
            })
        
    def on_agent_finish(self, finish, **kwargs):
        """处理agent完成"""
        result = finish.return_values["output"]
        # 如果结果已经包含"Final Answer:"，则只取后面的内容
        if "Final Answer:" in result:
            result = result.split("Final Answer:", 1)[1].strip()
        # 直接发送内容，不添加前缀
        self.queue.put({
            "type": "answer",
            "content": result + "\n",
            "action_id": self.get_action_id("answer")
        })
        
    def on_llm_start(self, serialized, prompts, **kwargs):
        pass
        
    def on_llm_new_token(self, token: str, **kwargs):
        action_id = self.get_action_id("token")
        self.queue.put({
            "type": "token",
            "content": token,
            "action_id": action_id
        })
        
    def on_llm_end(self, response, **kwargs):
        pass

class StreamToQueue:
    def __init__(self, queue):
        self.queue = queue
        self.buffer = ""
        self.action_counter = {}  # 用于跟踪每种行为的计数
        self.current_action = None  # 用于跟踪当前正在处理的动作
    
    def get_action_id(self, msg_type: str) -> str:
        """获取行为的唯一标识符"""
        if msg_type not in self.action_counter:
            self.action_counter[msg_type] = 0
        self.action_counter[msg_type] += 1
        return f"{msg_type}_{self.action_counter[msg_type]}"
    
    def write(self, text):
        if text.strip():
            text = clean_ansi(text.strip())
            self.buffer += text
            
            # 如果缓冲区包含完整的消息（以换行符结束）
            if "\n" in self.buffer:
                # 分割缓冲区中的消息
                messages = self.buffer.split("\n")
                # 处理除最后一个消息外的所有消息
                for message in messages[:-1]:
                    if message.strip():
                        # 直接发送消息
                        self.queue.put({
                            "type": "log",
                            "content": message + "\n",
                            "action_id": self.get_action_id("log")
                        })
                
                # 保留最后一个不完整的消息在缓冲区中
                self.buffer = messages[-1]
    
    def flush(self):
        if self.buffer:
            self.queue.put({
                "type": "log",
                "content": self.buffer + "\n",
                "action_id": self.get_action_id("log")
            })
            self.buffer = ""

def initialize_agent() -> AgentExecutor:
    # 初始化工具
    tools = [
        Tool(
            name="get_current_date",
            func=DateQueryToolkit().get_current_date,
            description="获取当前日期"
        ),
        Tool(
            name="write_to_file",
            func=FileWriteToolkit(output_dir=output_dir).write_to_file,
            description="将内容写入文件"
        ),
        Tool(
            name="generate_daily_report",
            func=PoultryLogToolkit().generate_daily_report,
            description="生成每日报告"
        ),
        Tool(
            name="get_weather",
            func=WeatherToolkit().get_weather,
            description="获取天气信息"
        ),
        Tool(
            name="search_wikipedia",
            func=WikipediaSearchTool(lang="zh", top_k=3).as_query_engine(),
            description="搜索维基百科"
        )
    ]

    # 初始化LLM
    llm = Ollama(
        model=os.getenv("MODEL_NAME"),
        base_url=os.getenv("BASE_URL"),
        temperature=0,
        callbacks=[]  # 这里不设置callback，会在运行时动态添加
    )

    # 创建ReAct提示模板
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个有帮助的AI助手。你可以使用以下工具：

{tools}

使用以下格式：

Question: 你需要回答的问题
Thought: 你应该总是思考要做什么
Action: 要采取的行动，应该是[{tool_names}]中的一个
Action Input: 行动的输入
Observation: 行动的结果
... (这个Thought/Action/Action Input/Observation可以重复多次)
Thought: 我现在知道最终答案了
Final Answer: 对原始问题的最终回答

注意事项：
1. 当使用日期相关的工具时：
   - 确保日期格式为 YYYY-MM-DD（例如：2024-04-24）
   - 不要添加引号或其他特殊字符
   - 如果工具返回日期格式错误，检查并清理日期字符串
2. 如果工具返回错误，不要重复相同的操作，而是：
   - 检查输入格式是否正确
   - 尝试清理输入数据
   - 如果问题持续，报告错误并停止
3. 如果遇到循环问题，应该停止并报告错误

之前的对话历史：
{chat_history}"""),
        ("human", "{input}"),
        ("system", "{agent_scratchpad}")
    ])

    # 创建ReAct Agent
    agent = create_react_agent(llm, tools, prompt)
    
    # 创建Agent执行器
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10
    )
    
    return agent_executor

class ChatRequest(BaseModel):
    user_input: str
    session_id: str

@app.post("/create_chat", response_model=dict)
def create_session():
    session_id = str(uuid.uuid4())
    agent = initialize_agent()
    sessions[session_id] = agent
    chat_histories[session_id] = []  # 初始化会话历史
    return {"session_id": session_id}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id
    agent = sessions.get(session_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 生成请求ID
    request_id = str(uuid.uuid4())
    
    # 创建请求专用的日志队列和处理器
    log_queue = Queue()
    handler = RequestLogHandler(request_id, log_queue)
    streaming_handler = StreamingCallbackHandler(log_queue)
    
    # 获取langchain的logger并添加处理器
    langchain_logger = logging.getLogger("langchain")
    langchain_logger.addHandler(handler)
    
    # 配置日志级别
    langchain_logger.setLevel(logging.DEBUG)
    logging.getLogger("langchain.agents").setLevel(logging.DEBUG)
    logging.getLogger("langchain.chains").setLevel(logging.DEBUG)
    logging.getLogger("langchain.executors").setLevel(logging.DEBUG)

    # 获取当前会话的历史记录
    chat_history = chat_histories.get(session_id, [])
    
    # 格式化历史记录
    formatted_history = "\n".join([
        f"Human: {msg['human']}\nAssistant: {msg['assistant']}"
        for msg in chat_history[-5:]  # 只保留最近5轮对话
    ])

    async def generate() -> Generator[str, None, None]:
        loop = asyncio.get_event_loop()
        try:
            # Set the current request_id context
            token = request_id_ctx.set(request_id)

            # 重定向标准输出到我们的处理器
            import sys
            old_stdout = sys.stdout
            sys.stdout = StreamToQueue(log_queue)

            # Run the agent in the executor with streaming handler
            future = loop.run_in_executor(
                executor, 
                lambda: agent.invoke(
                    {
                        "input": request.user_input,
                        "agent_scratchpad": [],
                        "chat_history": formatted_history
                    },
                    callbacks=[streaming_handler]
                )
            )

            while True:
                # Process logs
                while not log_queue.empty():
                    log_data = log_queue.get()
                    # 确保所有类型的行为都被正确处理
                    if log_data["type"] in ["chain_start", "chain_end", "thought", "action", "action_input", "tool_start", "observation", "answer", "token", "log", "tool_output", "error"]:
                        # 如果是完整消息，直接发送
                        if log_data.get("is_complete", False):
                            yield f'data: {json.dumps(log_data)}\n\n'
                        else:
                            # 对于每个字符都发送完整的行为信息
                            for char in log_data["content"]:
                                yield f'data: {json.dumps({"type": log_data["type"], "content": char, "action_id": log_data["action_id"]})}\n\n'
                                await asyncio.sleep(0.05)
                    else:
                        yield f'data: {json.dumps(log_data)}\n\n'

                # Check if the task is done
                if future.done():
                    try:
                        response = future.result()
                        if "type" not in response:
                            output = clean_ansi(response["output"])
                            action_id = streaming_handler.get_action_id("answer")
                            # 发送完整的最终答案
                            yield f'data: {json.dumps({"type": "answer", "content": "Final Answer: " + output, "action_id": action_id, "is_complete": True})}\n\n'
                            
                            # 保存对话历史
                            chat_histories[session_id].append({
                                "human": request.user_input,
                                "assistant": output
                            })
                        break
                    except Exception as e:
                        action_id = streaming_handler.get_action_id("error")
                        yield f'data: {json.dumps({"type": "error", "content": str(e), "action_id": action_id, "is_complete": True})}\n\n'
                        break
                else:
                    await asyncio.sleep(0.05)

            yield 'data: {"type": "done"}\n\n'
        finally:
            # Clean up resources
            langchain_logger.removeHandler(handler)
            sys.stdout = old_stdout
            request_id_ctx.reset(token)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

def escape_str(s: str) -> str:
    """转义字符串中的特殊字符"""
    return s.replace('"', '\\"').replace("\n", "\\n")

@app.delete("/delete_session/{session_id}", response_model=dict)
def delete_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
        if session_id in chat_histories:
            del chat_histories[session_id]
        return {"status": "success", "message": f"Session {session_id} deleted"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)