import os
import logging
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.response_synthesizers import ResponseMode, get_response_synthesizer
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
import chromadb
from dotenv import load_dotenv
import time

# 配置日志记录
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()
os.environ["TRANSFORMERS_OFFLINE"] = "1"
model_path = os.path.abspath(os.path.join("models", "bge-base-zh-v1.5"))
Settings.embed_model = HuggingFaceEmbedding(
    model_name=model_path,
    device="cpu",  # 可选 "cuda" 强制使用 GPU
    cache_folder="../embedding_cache",  # 自定义缓存目录
)
Settings.llm = Ollama(
    model=os.getenv("MODEL_NAME"),  # 模型名称
    base_url=os.getenv("BASE_URL"),
    request_timeout=120,
)

class QueryEngineToolkit:
    def __init__(self):
        logger.debug("初始化 QueryEngineToolkit ...")
        start_time = time.time()
        
        # 1. 加载文档
        self.documents = SimpleDirectoryReader("./data/").load_data()
        logger.debug(f"加载了 {len(self.documents)} 个文档。")
        
        # 2. 配置向量存储
        db = chromadb.PersistentClient(path="./chroma_db")
        chroma_collection = db.get_or_create_collection("quickstart")
        self.vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        logger.debug("向量存储和存储上下文已配置。")
        
        # 3. 创建索引
        self.index = VectorStoreIndex.from_documents(
            self.documents,
            storage_context=storage_context
        )
        logger.debug("索引已创建。")
        
        # 4. 配置检索器
        self.retriever = VectorIndexRetriever(
            index=self.index,
            similarity_top_k=10
        )
        logger.debug("检索器已配置。")
        
        # 5. 配置响应合成器
        self.response_synthesizer = get_response_synthesizer(
            response_mode=ResponseMode.TREE_SUMMARIZE,
            streaming=False
        )
        logger.debug("响应合成器已配置。")
        
        # 6. 组装查询引擎
        self.query_engine = RetrieverQueryEngine(
            retriever=self.retriever,
            response_synthesizer=self.response_synthesizer,
            node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.5)]
        )
        logger.debug("查询引擎已组装。")
        
        end_time = time.time()
        logger.debug(f"初始化完成，耗时 {end_time - start_time:.2f} 秒。")
    
    def query_tool(self, query: str) -> str:
        """面向生猪养殖领域的智能查询引擎，支持养殖技术、疫病防治、饲料配方等专业知识检索
        参数：
            query (str): 输入的查询请求
        返回：
            str:查询引擎返回的响应内容
        """
        logger.debug(f"处理查询：{query}")
        start_time = time.time()
        response = self.query_engine.query(query)
        end_time = time.time()
        logger.debug(f"响应：{response.response}")
        logger.debug(f"查询处理耗时 {end_time - start_time:.2f} 秒。")
        return response.response
