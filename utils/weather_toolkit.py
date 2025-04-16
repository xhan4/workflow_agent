from fastapi import requests


class WeatherToolkit:
     def get_weather(query: str) -> str:
        """天气查询工具，查询指定城市的当天的天气信息
        
        Args:
            name: 要查询天气的城市名称（例如：北京、上海等）
            
        Returns:
            包含天气指标的字典
        """
        api_key = "7d816ca88f33edc160a2ff6dd7002642"
        weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
        try:
            params = {
                "key": api_key,
                "city": query,
                "extensions": "base",
                "output": "json",
            }
            response = requests.get(weather_url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "1" or not data.get("lives"):
                return f"未找到 '{query}' 的天气信息。"
            weather_info = data["lives"][0]
            print(weather_info,'weather_info')
            return weather_info
        except Exception as e:
            return f"查询天气时出错：{str(e)}"  