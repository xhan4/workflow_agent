from collections import defaultdict
import re
from typing import Dict, List, Any
from datetime import datetime

from utils.file_write_toolkit import FileWriteToolkit
from utils.sensor_data_toolkit import SensorDataToolkit

class PoultryLogToolkit():
    name = "poultry_log_tool"
    description = "符合农业农村部规范的智能化养鸡场日志生成工具"
    
    def __init__(self):
        self.data_provider = SensorDataToolkit()
        self.write_to_file = FileWriteToolkit(output_dir="./output").write_to_file
        # 新增日志存储
        self.log_entries = []

    def generate_log_entry(
        self,
        timestamp: str,
        activity: str,
        issues: List[str],
        measures: List[str],
        responsibler: str,
        log_level: str = "INFO"
    ) -> str:
        """生成单条日志条目（符合现代化日志规范

        Args:
            timestamp: ISO8601格式时间戳（如2025-03-23T14:30:00）
            activity: 养殖活动类型（如环境控制/喂养管理）
            issues: 发现的问题列表
            measures: 采取的措施列表
            responsibler: 责任人姓名
            log_level: 日志级别（DEBUG/INFO/WARN/ERROR）

        Returns:
            格式化日志字符串
        """
        return (
            f"[{timestamp}] [{log_level}] [PoultryFarm] "
            f"Activity: {activity} | "
            f"Issues: {'; '.join(issues) if issues else '无'} | "
            f"Measures: {'; '.join(measures)} | "
            f"Responsibler: {responsibler}"
        )
    
    def generate_daily_report(
        self,
        farm_id: str,
        date: str,
    ) -> Dict[str, Any]:
        """生成某一天的养殖场日志报告，并保存到文件
        
        Args:
            farm_id: 养殖场编码（GB/T 38156-2019）
            date: 日期（YYYY-MM-DD）

        Returns:
            包含文件名、日志内容,及文件存放的路径，此时已成功生成日志
            
        Raises:
            ValueError: 日期格式或日志格式校验失败
        """
        # 参数校验增强 [[9]]
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
            raise ValueError("日期格式必须为YYYY-MM-DD")
        # 初始化日志条目 [[3]]
        log_entries = []
        metrics = self.data_provider.generate_sensor_data(farm_id, "鸡舍001", date)
        
        # 自动预警逻辑增强
        if metrics.get('temperature', 0) > 25:
            log_entries.append(self.generate_log_entry(
                timestamp=datetime.now().isoformat(),
                activity="环境控制",
                issues=["温度异常"],
                measures=["启动应急通风"],
                responsibler="系统自动",
                log_level="WARN"
            ))
            
        # 添加手动日志（示例）
        log_entries.extend(self.log_entries)  # 使用类属性存储日志

        # 日志解析逻辑优化 [[4]]
        log_categories = defaultdict(lambda: defaultdict(list))
        for entry in log_entries:
            match = re.match(
                r'^\[(?P<timestamp>[\d-]+T[\d:]+)\]\s*'
                r'\[(?P<level>\w+)\]\s*'
                r'\[PoultryFarm\]\s*'
                r'Activity:\s*(?P<activity>.*?)\s*\|\s*'
                r'Issues:\s*(?P<issues>.*?)\s*\|\s*'
                r'Measures:\s*(?P<measures>.*?)\s*\|\s*'
                r'Responsibler:\s*(?P<responsibler>.+)$',
                entry
            )
            if not match:
                raise ValueError(f"日志格式错误: {entry}")
                
            data = match.groupdict()
            category = data['activity']
            level = data['level']
            log = (
                f"{data['timestamp']} | "
                f"Issues: {data['issues']} | "
                f"Measures: {data['measures']} | "
                f"By: {data['responsibler']}"
            )
            log_categories[category][level].append(log)
        stock_change = metrics.get('stock_change', 0)  # 默认值改为0
        egg_damage_rate = metrics.get('egg_damage_rate', 0.0)

        content = f"""# {farm_id} 养殖日志 - {date}
## 生产运营指标
- 存栏量：{metrics.get('stock_quantity', 0)}羽（环比{stock_change:.1f}%）
- 当日产蛋：{metrics.get('daily_egg_production', 0)}枚（破损率{egg_damage_rate:.1f}%）
- 饲料转化率：{metrics.get('feed_conversion_rate', 0.0):.2f}kg/kg
- 死亡率：{metrics.get('mortality_rate', 0.0):.2f}%（周累计{metrics.get('weekly_mortality_rate', 0.0):.1f}%）

## 资源管理
- 饲料库存：{metrics.get('feed_inventory', 0)}吨（有效期至{metrics.get('feed_expiry_date', 'N/A')}）
- 水耗：{metrics.get('water_consumption', 0)}m³（循环率{metrics.get('water_recycling_rate', 0)}%）
- 能源消耗：{metrics.get('energy_consumption', 0)}kWh（绿能占比{metrics.get('renewable_energy_ratio', 0)}%）

## 环境监测
- 温度：{metrics.get('temperature', 0)}℃（波动±{metrics.get('temperature_fluctuation', 0.0):.1f}℃）
- 湿度：{metrics.get('humidity', 0)}%RH
- 通风量：{metrics.get('ventilation_volume', 0)}m³/h（CO₂浓度{metrics.get('co2_concentration', 0)}ppm）

## 生物安全
- 疫苗接种：{metrics.get('vaccination_count', 0)}剂次（类型{metrics.get('vaccine_type', 'N/A')}）
- 消毒记录：{metrics.get('disinfection_count', 0)}次（药剂{metrics.get('disinfectant_type', 'N/A')}）
- 异常病例：{metrics.get('abnormal_cases', 0)}例（处理{metrics.get('case_handling', '无')}）

## 操作日志（PDCA循环记录）
{self._format_log_sections(log_categories)}
"""     
        
        filename = f"{farm_id}_日志_{date}.md"
        self.write_to_file(content.strip(),filename)
        return {
            "filename": filename,
            "content": content.strip(),
            "filepath":f'./output/{filename}'
        }
        
    def _format_log_sections(self, log_categories: Dict) -> str:
        """格式化日志章节（策略模式优化） [[10]]"""
        if not log_categories:
            return "无记录"
            
        sections = []
        for category, levels in log_categories.items():
            section = f"### {category}\n"
            for level, logs in levels.items():
                section += f"#### {level}级别\n" + '\n'.join([f"- {log}" for log in logs])
            sections.append(section)
        return '\n'.join(sections)