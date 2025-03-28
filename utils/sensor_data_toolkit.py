from datetime import datetime, timedelta
from random import randint, uniform, choice
from typing import Dict, List, Optional, Union

class SensorDataToolkit():
    name = "sensor_data_provider"
    description = "符合智慧养殖场物联网特征的模拟数据生成器（支持历史数据生成）"
    
    def generate_sensor_data(
        self, 
        farm_id: str,
        shed_id: str,
        date: Optional[Union[datetime, str]] = None
    ) -> Dict:
        """获取养殖场传感器数据（支持指定日期）
        
        Args:
            farm_id: 养殖场ID
            shed_id: 鸡舍编号
            date: 可选日期（datetime对象或YYYY-MM-DD字符串）
            
        Returns:
            包含完整生产指标和环境参数的字典
        """
        # 日期处理逻辑 [[4]]
        if isinstance(date, str):
            base_time = datetime.strptime(date, "%Y-%m-%d")
        elif isinstance(date, datetime):
            base_time = date
        else:
            base_time = datetime.now()
        
        # 生成随机时间戳（指定日期内的随机时间）[[2]]
        random_delta = timedelta(
            hours=randint(0,23),
            minutes=randint(0,59),
            seconds=randint(0,59)
        )
        timestamp = (base_time + random_delta).isoformat()

        # 数值格式统一 [[6]]
        inventory = randint(10000, 15000)
        laying_rate = uniform(85, 95)
        daily_production = round(inventory * laying_rate / 100)
        
        return {
            "farm_id": farm_id,
            "shed_id": shed_id,
            "timestamp": timestamp,
            "stock_quantity": inventory,  # 存储原始数值
            "stock_change": round(uniform(-2.0, 2.0),1),  # 直接存储数值
            "daily_egg_production": daily_production,
            "egg_damage_rate": round(uniform(0.3, 1.0),1),
            "feed_conversion_rate": round(uniform(1.8, 2.2),1),  # 存储数值
            "mortality_rate": round(uniform(0.1, 0.5),2),
            "weekly_mortality_rate": round(uniform(1.0, 2.5),1),
            "feed_inventory": randint(50, 100),
            "feed_expiry_date": (base_time + timedelta(days=randint(30, 180))).strftime("%Y-%m-%d"),
            "water_consumption": randint(20, 30),
            "water_recycling_rate": randint(70, 80),
            "energy_consumption": randint(300, 400),
            "renewable_energy_ratio": randint(30, 50),

            "temperature": round(uniform(20, 25), 1),
            "temperature_fluctuation": round(uniform(1.0, 3.0),1),
            "humidity": randint(50, 70),
            "ventilation_volume": f"{randint(10000, 20000):,}",
            "co2_concentration": randint(800, 1500),
    
            "vaccination_count": randint(0, 500),
            "vaccine_type": choice(["Avian Influenza/H5N1", "Newcastle Disease/LaSota", "Infectious Bronchitis/H120"]),
            "disinfection_count": randint(2, 5),
            "disinfectant_type": choice(["Sodium Hypochlorite", "Peroxyacetic Acid", "Glutaraldehyde"]),
            "abnormal_cases": randint(0, 2),
            "case_handling": "None" if randint(0,5)==0 else "Isolated Treatment"
        }
    
    def generate_batch_data(
        self, 
        farm_id: str, 
        batch_size: int = 5,
        days: int = 1
    ) -> List[Dict]:
        """生成多日批次数据
        
        Args:
            farm_id: 养殖场ID
            batch_size: 鸡舍数量
            days: 生成多少天的数据
            
        Returns:
            包含多日数据的嵌套字典
        """
        base_date = datetime.now() - timedelta(days=days)
        return [
            {
                "date": (base_date + timedelta(days=d)).strftime("%Y-%m-%d"),
                "sheds": [
                    self.generate_sensor_data(
                        farm_id=farm_id,
                        shed_id=f"SHED-{i:03d}",
                        date=base_date + timedelta(days=d)
                    )
                    for i in range(1, batch_size+1)
                ]
            } for d in range(days)
        ]