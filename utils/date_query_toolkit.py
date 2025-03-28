from typing import List
from datetime import datetime

class DateQueryToolkit():
    name = "date_acquisition_tool"
    description = "符合ISO 8601标准的日期时间获取工具"
    
    def get_current_date(self) -> str:
        """获取当前日期（YYYY-MM-DD格式）
        
        Returns:
            当前日期字符串
        """
        return datetime.now().strftime("%Y-%m-%d")
    
    def get_current_timestamp(self) -> str:
        """获取完整时间戳（ISO 8601格式）
        
        Returns:
            当前时间戳字符串
        """
        return datetime.new().isoformat()