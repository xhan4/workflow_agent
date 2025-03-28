from llama_index.core import VectorStoreIndex, SimpleDirectoryReader,StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.response_synthesizers import ResponseMode, get_response_synthesizer 

import chromadb

class QueryEngineToolkit:
    def __init__(self):
        # 1. 加载文档
        self.documents = SimpleDirectoryReader("./data/").load_data()  # 添加self [[4]]

        # 2. 配置向量存储
        db = chromadb.PersistentClient(path="./chroma_db")
        chroma_collection = db.get_or_create_collection("quickstart")
        self.vector_store = ChromaVectorStore(chroma_collection=chroma_collection)  # 添加self
        storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        # 3. 创建索引
        self.index = VectorStoreIndex.from_documents(  # 添加self
            self.documents, 
            storage_context=storage_context
        )

        # 4. 配置检索器
        self.retriever = VectorIndexRetriever(  # 添加self
            index=self.index, 
            similarity_top_k=10
        )

        # 5. 配置响应合成器
        self.response_synthesizer = get_response_synthesizer(
                response_mode=ResponseMode.TREE_SUMMARIZE,
                streaming=False
            )

        # 6. 组装查询引擎
        self.query_engine = RetrieverQueryEngine(  # 添加self
            retriever=self.retriever,
            response_synthesizer=self.response_synthesizer,
            node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.5)]
        )
    
    def query_tool(self, query: str) -> str:  # 修正返回类型为str
        """
        使用查询引擎处理输入查询，并返回响应。

        参数：
        query (str): 用户输入的查询字符串。

        返回：
        Response: 查询引擎返回的响应对象。
        """
        response = self.query_engine.query(query)
        return response.response  # 获取实际响应内容