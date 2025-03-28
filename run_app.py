import re
import os
import time

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama  import Ollama

from utils.date_query_toolkit import DateQueryToolkit
from utils.file_write_toolkit import FileWriteToolkit
from utils.poultry_log_toolkit import PoultryLogToolkit
from utils.query_engine_toolkit import QueryEngineToolkit 
from prompt import gen_prompt

from dotenv import load_dotenv

load_dotenv()
def main():
    save_tool = FunctionTool.from_defaults(fn=FileWriteToolkit(output_dir="./output").write_to_file)
    date_tool = FunctionTool.from_defaults(fn=DateQueryToolkit().get_current_date)
    log_tool = FunctionTool.from_defaults(fn=PoultryLogToolkit().generate_daily_report)
    query_tool = FunctionTool.from_defaults(fn=QueryEngineToolkit().query_tool)
    llm = Ollama(
        model=os.getenv("MODEL_NAME"),  # 模型名称
        base_url=os.getenv("BASE_URL"), 
        request_timeout=120,
    )
    agent = ReActAgent.from_tools(
        [save_tool,date_tool,log_tool,query_tool], 
        llm=llm, 
        verbose=False,   # 打印详细日志
        max_iterations=10,  # 最大循环次数 
        context=gen_prompt()
        )
   
        # 多轮对话循环
    while True:
        user_input = input("请输入指令（输入'exit'退出）: ")
        if user_input.lower() == 'exit':
            break
        start_time = time.time()
        response = agent.chat(user_input)
        for msg in agent.memory.get(): 
         print(f"{msg.role}: {msg.content}")
        clean_response = re.sub(r'\n?<think>.*?</think>\n?', '', response.response, flags=re.DOTALL)
        end_time = time.time()
        print(f"\033[94mAnswer({end_time-start_time:.2f}s): {clean_response}\033[0m")

if __name__ == "__main__":
    main()
