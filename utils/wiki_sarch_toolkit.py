from llama_index.core.tools import BaseTool, ToolMetadata,FunctionTool
import wikipedia

class WikipediaSearchTool(BaseTool):
    def __init__(self, lang: str = "zh", top_k: int = 3):
        super().__init__()
        wikipedia.set_lang(lang)
        self.top_k = top_k
        self._metadata = ToolMetadata(  # 使用私有变量存储元数据
            name="wikipedia_search",
            description=(
                "使用维基百科获取关于人物、地点、公司、历史事件等的实时信息。"
                "输入应为明确的搜索查询关键词。"
            )
        )

    @property
    def metadata(self) -> ToolMetadata:  # 实现抽象属性
        return self._metadata

    @classmethod
    def class_name(cls) -> str:
        return "WikipediaSearchTool"

    def _search(self, query: str) -> dict:
        """执行维基百科搜索并返回结构化结果"""
        try:
            search_results = wikipedia.search(query, results=self.top_k)
            results = []
            
            for title in search_results:
                try:
                    page = wikipedia.page(title, auto_suggest=False)
                    results.append({
                        "title": title,
                        "summary": page.summary[:500] + "...",  # 限制摘要长度
                        "url": page.url
                    })
                except wikipedia.exceptions.DisambiguationError as e:
                    # 处理消歧义页面
                    results.append({
                        "title": title,
                        "summary": f"消歧义页：{', '.join(e.options[:3])}...",
                        "url": f"https://{self.lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    })
                except wikipedia.exceptions.PageError:
                    continue
            
            return {
                "query": query,
                "results": results[:self.top_k]
            }
        except Exception as e:
            return {"error": str(e)}

    def __call__(self, query: str) -> dict:
        return self._search(query)

    def as_query_engine(self):
        """适配器方法用于兼容不同接口"""
        return FunctionTool.from_defaults(
            fn=self._search,
            name=self.metadata.name,
            description=self.metadata.description
        )

    async def _acall(self, *args, **kwargs):
        return self._search(*args, **kwargs)