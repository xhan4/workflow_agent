from datetime import datetime
from typing import Any, Union, Dict
from utils.file_write_toolkit import FileWriteToolkit
from dotenv import load_dotenv
load_dotenv()
class PoultryLogToolkit:
    def __init__(self):
        self.write_to_file = FileWriteToolkit(output_dir="./output").write_to_file
        self.report_template = """# 养殖日志 - {date}
## 环境监测数据
- 温度监测：
  - 温度1: {in_temperature1}℃
  - 温度2: {in_temperature2}℃
  - 温度3: {in_temperature3}℃
  - 温度4: {in_temperature4}℃
  - 温度5: {in_temperature5}℃
- 湿度监测：
  - 湿度1: {in_humidity1}%
  - 湿度2: {in_humidity2}%
  - 湿度3: {in_humidity3}%
  - 湿度4: {in_humidity4}%
  - 湿度5: {in_humidity5}%
- 其他环境参数：
  - 风速1: {in_windspeed1}m/s
  - 风速2: {in_windspeed2}m/s
  - 光照强度1: {in_light1}lux
  - 光照强度2: {in_light2}lux
  - 气压: {in_kpa}kPa
  - CO₂浓度1: {in_cardioxide1}ppm
  - CO₂浓度2: {in_cardioxide2}ppm
  - PM10_1: {in_pm10_1}μg/m³
  - PM2.5_1: {in_pm25_1}μg/m³
  - PM10_2: {in_pm10_2}μg/m³
  - PM2.5_2: {in_pm25_2}μg/m³
  - 氨气浓度: {in_ammonia1}ppm
- 设备状态：
  - 电力状态: {in_electric}
  - 水位状态: {in_water}

## 异常预警
{alerts}
"""

    def generate_daily_report(
        self,
        date_str: str,
    ) -> Dict[str, Any]:
        """生成某一天的养殖场日志报告，并保存到文件
        
       参数：
            farm_id: 养殖场编码（GB/T 38156-2019）
            date: 日期（YYYY-MM-DD）

        返回:
            包含文件名、日志内容,及文件存放的路径
        """
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")  # 验证日期格式 [[6]]
        except ValueError:
            return "日期格式错误，请使用YYYY-MM-DD格式 [[6]]"
        
        data = self._fetch_data_by_date(date_str)
        if not data:
            return f"未找到{date_str}的记录"
        
        # 日期格式化 [[5]]
        date_formatted = datetime.strptime(data['add_time'], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        alerts = self._generate_alerts(data)
        
        # 使用Jinja2风格模板渲染 [[6]]
        content = self.report_template.format(
            date=date_formatted,
            **{k: data.get(k, "N/A") for k in [
                'in_temperature1','in_temperature2','in_temperature3',
                'in_temperature4','in_temperature5','in_humidity1',
                'in_humidity2','in_humidity3','in_humidity4','in_humidity5',
                'in_windspeed1','in_windspeed2','in_light1','in_light2',
                'in_kpa','in_cardioxide1','in_cardioxide2','in_pm10_1',
                'in_pm25_1','in_pm10_2','in_pm25_2','in_ammonia1',
                'in_electric','in_water'
            ]},
            alerts=alerts
        )
        
        # 新增文件保存逻辑 [[8]]
        filename = f"养殖日志_{date_formatted}.md"
        self.write_to_file(content.strip(), filename)
        return {
            "filename": filename,
            "content": content.strip(),
            "filepath": f'./output/{filename}',
            "status": 'success'
        }

    def _fetch_data_by_date(self, date_str: str) -> dict:
        """模拟根据传入日期获取数据（此处可替换为真实数据源）"""
        return {
            "id": "1",
            "add_time": f"{date_str} 16:02:57",
            "in_temperature1": "26.520",
            "in_humidity1": "48",
            "in_temperature2": "16.290",
            "in_humidity2": "52",
            "in_temperature3": "17.250",
            "in_humidity3": "47",
            "in_temperature4": "17.400",
            "in_humidity4": "50",
            "in_temperature5": "16.610",
            "in_humidity5": "54",
            "in_windspeed1": "0.490",
            "in_windspeed2": "0.540",
            "in_light1": "218.000",
            "in_light2": "104.000",
            "in_kpa": "-3.530",
            "in_cardioxide1": "600.640",
            "in_cardioxide2": "512.400",
            "in_pm10_1": "48.710",
            "in_pm25_1": "43.700",
            "in_pm10_2": "5.750",
            "in_pm25_2": "7.750",
            "in_ammonia1": "1.090",
            "in_electric": "正常",
            "in_water": "正常"
        }

    def _generate_alerts(self, data: dict) -> str:
        """根据传感器数据生成异常预警"""
        alerts = []
        if float(data.get('in_temperature1',0)) > 25:
            alerts.append("⚠️ 温度1超过安全阈值（>25℃）")
        if float(data.get('in_cardioxide1',0)) > 500:
            alerts.append("⚠️ CO₂浓度1超过安全阈值（>500ppm）")
        if data.get('in_ammonia1') != '0.000':
            alerts.append("⚠️ 检测到氨气浓度异常")
        return '\n'.join(alerts) if alerts else "无异常"

# # 使用示例
# if __name__ == "__main__":
#     report = DailyReportGenerator().generate("2024-03-04")
#     print(report)