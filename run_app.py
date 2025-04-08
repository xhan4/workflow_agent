import logging
import re
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama  import Ollama

from utils.date_query_toolkit import DateQueryToolkit
from utils.file_write_toolkit import FileWriteToolkit
from utils.poultry_log_toolkit import PoultryLogToolkit
from utils.query_engine_toolkit import QueryEngineToolkit 
from prompt import gen_prompt

from dotenv import load_dotenv

# 初始化日志和环境变量
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
load_dotenv()

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

# 初始化工具和模型
def initialize_agent():
    save_tool = FunctionTool.from_defaults(fn=FileWriteToolkit(output_dir="./output").write_to_file)
    date_tool = FunctionTool.from_defaults(fn=DateQueryToolkit().get_current_date)
    log_tool = FunctionTool.from_defaults(fn=PoultryLogToolkit().generate_daily_report)
    
    llm = Ollama(
        model=os.getenv("MODEL_NAME"),
        base_url=os.getenv("BASE_URL"), 
        request_timeout=120,
    )
    
    return ReActAgent.from_tools(
        [save_tool, date_tool, log_tool],
        llm=llm,
        verbose=True,
        max_iterations=10,
        context=gen_prompt()
    )

# 在应用启动时初始化 agent
agent = initialize_agent()

# 请求响应模型
class ChatRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = None  # 可选的会话ID用于扩展会话管理

class ChatResponse(BaseModel):
    response: str
    processing_time: float
    status: str = "success"

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        start_time = time.time()
        
        # 处理用户输入
        if not request.user_input:
            raise HTTPException(status_code=400, detail="Empty input")
        
        # 调用 agent
        response = agent.chat(request.user_input)
        
        # 清理响应
        clean_response = re.sub(
            r'\n?<think>.*?</think>\n?', 
            '', 
            response.response, 
            flags=re.DOTALL
        )
        
        processing_time = time.time() - start_time
        
        return ChatResponse(
            response=clean_response,
            processing_time=round(processing_time, 2)
        )
        
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ChatResponse(
                response=f"Error: {str(e)}",
                processing_time=0,
                status="error"
            )
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)