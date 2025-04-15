import logging
import re
import os
import time
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama import Ollama

from utils.date_query_toolkit import DateQueryToolkit
from utils.file_write_toolkit import FileWriteToolkit
from utils.poultry_log_toolkit import PoultryLogToolkit
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

sessions = {}
output_dir = os.getenv("OUTPUT_DIR", "./output") 
def initialize_agent():
    save_tool = FunctionTool.from_defaults(fn=FileWriteToolkit(output_dir=output_dir).write_to_file)
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

@app.post("/create_chat", response_model=dict)
def create_session():
    session_id = str(uuid.uuid4())
    agent = initialize_agent()
    sessions[session_id] = agent
    return {"session_id": session_id}

class ChatRequest(BaseModel):
    user_input: str
    session_id: str  # 必须提供会话ID[[5]]

@app.post("/chat", response_model=dict)
def chat_endpoint(request: ChatRequest):
    session_id = request.session_id
    agent = sessions.get(session_id)
    
    if not agent:
        raise HTTPException(
            status_code=404, 
            detail="Session not found"
        )
    
    try:
        start_time = time.time()
        
        if not request.user_input:
            raise HTTPException(status_code=400, detail="Empty input")
        
        response = agent.chat(request.user_input)
        
        clean_response = re.sub(
            r'\n?<think>.*?</think>\n?', 
            '', 
            response.response, 
            flags=re.DOTALL
        )
        
        processing_time = time.time() - start_time
        
        return {
            "response": clean_response,
            "processing_time": round(processing_time, 2),
            "status": "success"
        }
        
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "response": f"Error: {str(e)}",
                "processing_time": 0,
                "status": "error"
            }
        )
@app.delete("/delete_session/{session_id}", response_model=dict)
def delete_session(session_id: str):
    """删除指定会话接口[[1]][[3]]"""
    if session_id in sessions:
        del sessions[session_id]
        return {
            "status": "success",
            "message": f"Session {session_id} deleted successfully"
        }
    else:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)