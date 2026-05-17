import random
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# 设置随机种子以保证可复现
random.seed(42)

# ============================================================
# 基础数据定义
# ============================================================

# 区域和省份映射
REGIONS = {
    "华东": ["上海", "江苏", "浙江", "安徽", "福建", "江西", "山东"],
    "华南": ["广东", "广西", "海南"],
    "华北": ["北京", "天津", "河北", "山西", "内蒙古"],
    "华中": ["河南", "湖北", "湖南"],
    "西南": ["重庆", "四川", "贵州", "云南", "西藏"]
}

# 城市映射
CITIES = {
    "上海": ["上海市"],
    "江苏": ["南京", "苏州", "无锡", "常州"],
    "浙江": ["杭州", "宁波", "温州", "嘉兴"],
    "安徽": ["合肥", "芜湖", "蚌埠"],
    "福建": ["福州", "厦门", "泉州"],
    "江西": ["南昌", "赣州", "九江"],
    "山东": ["济南", "青岛", "烟台"],
    "广东": ["广州", "深圳", "东莞", "佛山"],
    "广西": ["南宁", "柳州", "桂林"],
    "海南": ["海口", "三亚"],
    "北京": ["北京市"],
    "天津": ["天津市"],
    "河北": ["石家庄", "唐山", "保定"],
    "山西": ["太原", "大同"],
    "内蒙古": ["呼和浩特", "包头"],
    "河南": ["郑州", "洛阳", "开封"],
    "湖北": ["武汉", "宜昌", "襄阳"],
    "湖南": ["长沙", "株洲", "湘潭"],
    "重庆": ["重庆市"],
    "四川": ["成都", "绵阳", "德阳"],
    "贵州": ["贵阳", "遵义"],
    "云南": ["昆明", "大理"],
    "西藏": ["拉萨"]
}

# 销售员
SALESPEOPLE = [
    {"id": "EMP-001", "name": "张伟", "department": "华东销售部", "level": "高级", "region": "华东", "target": 8000000},
    {"id": "EMP-002", "name": "李娜", "department": "华东销售部", "level": "资深", "region": "华东", "target": 10000000},
    {"id": "EMP-003", "name": "王强", "department": "华南销售部", "level": "中级", "region": "华南", "target": 6000000},
    {"id": "EMP-004", "name": "刘芳", "department": "华南销售部", "level": "高级", "region": "华南", "target": 7500000},
    {"id": "EMP-005", "name": "陈明", "department": "华北销售部", "level": "初级", "region": "华北", "target": 5000000},
    {"id": "EMP-006", "name": "杨丽", "department": "华北销售部", "level": "中级", "region": "华北", "target": 6500000},
    {"id": "EMP-007", "name": "赵磊", "department": "华中销售部", "level": "高级", "region": "华中", "target": 7000000},
    {"id": "EMP-008", "name": "黄静", "department": "华中销售部", "level": "资深", "region": "华中", "target": 9000000},
    {"id": "EMP-009", "name": "周涛", "department": "西南销售部", "level": "中级", "region": "西南", "target": 5500000},
    {"id": "EMP-010", "name": "吴敏", "department": "西南销售部", "level": "初级", "region": "西南", "target": 4500000}
]

# 产品类别和产品
PRODUCTS = {
    "软件": [
        {"id": "PRD-001", "name": "ERP管理系统", "price": 298000, "cost": 89400},
        {"id": "PRD-002", "name": "CRM客户管理", "price": 198000, "cost": 59400},
        {"id": "PRD-003", "name": "OA办公系统", "price": 158000, "cost": 47400},
        {"id": "PRD-004", "name": "HR人力资源", "price": 128000, "cost": 38400},
        {"id": "PRD-005", "name": "BI数据分析", "price": 258000, "cost": 77400}
    ],
    "硬件": [
        {"id": "PRD-006", "name": "服务器Dell R740", "price": 85000, "cost": 68000},
        {"id": "PRD-007", "name": "交换机Cisco 9300", "price": 45000, "cost": 36000},
        {"id": "PRD-008", "name": "存储设备NetApp", "price": 120000, "cost": 96000},
        {"id": "PRD-009", "name": "工作站HP Z8", "price": 35000, "cost": 28000},
        {"id": "PRD-010", "name": "显示器Dell U2723", "price": 4500, "cost": 3600}
    ],
    "服务": [
        {"id": "PRD-011", "name": "系统集成服务", "price": 150000, "cost": 90000},
        {"id": "PRD-012", "name": "技术支持年费", "price": 50000, "cost": 25000},
        {"id": "PRD-013", "name": "培训服务", "price": 30000, "cost": 15000},
        {"id": "PRD-014", "name": "咨询顾问", "price": 200000, "cost": 120000},
        {"id": "PRD-015", "name": "运维外包", "price": 100000, "cost": 60000}
    ],
    "配件": [
        {"id": "PRD-016", "name": "网线Cat6", "price": 500, "cost": 200},
        {"id": "PRD-017", "name": "电源适配器", "price": 300, "cost": 120},
        {"id": "PRD-018", "name": "键盘鼠标套装", "price": 800, "cost": 320},
        {"id": "PRD-019", "name": "机柜", "price": 5000, "cost": 2500},
        {"id": "PRD-020", "name": "UPS电源", "price": 8000, "cost": 4800}
    ]
}

# 客户
CUSTOMERS = [
    {"id": "CUS-001", "name": "腾讯科技", "industry": "互联网", "scale": "大型", "level": "A"},
    {"id": "CUS-002", "name": "阿里巴巴", "industry": "互联网", "scale": "大型", "level": "A"},
    {"id": "CUS-003", "name": "字节跳动", "industry": "互联网", "scale": "大型", "level": "A"},
    {"id": "CUS-004", "name": "华为技术", "industry": "通信", "scale": "大型", "level": "A"},
    {"id": "CUS-005", "name": "小米科技", "industry": "消费电子", "scale": "大型", "level": "A"},
    {"id": "CUS-006", "name": "京东集团", "industry": "电商", "scale": "大型", "level": "A"},
    {"id": "CUS-007", "name": "美团", "industry": "互联网", "scale": "大型", "level": "B"},
    {"id": "CUS-008", "name": "网易", "industry": "互联网", "scale": "大型", "level": "B"},
    {"id": "CUS-009", "name": "百度", "industry": "互联网", "scale": "大型", "level": "B"},
    {"id": "CUS-010", "name": "中国银行", "industry": "金融", "scale": "大型", "level": "A"},
    {"id": "CUS-011", "name": "工商银行", "industry": "金融", "scale": "大型", "level": "A"},
    {"id": "CUS-012", "name": "建设银行", "industry": "金融", "scale": "大型", "level": "A"},
    {"id": "CUS-013", "name": "平安保险", "industry": "金融", "scale": "大型", "level": "B"},
    {"id": "CUS-014", "name": "中国人寿", "industry": "金融", "scale": "大型", "level": "B"},
    {"id": "CUS-015", "name": "比亚迪", "industry": "汽车", "scale": "大型", "level": "B"},
    {"id": "CUS-016", "name": "吉利汽车", "industry": "汽车", "scale": "大型", "level": "B"},
    {"id": "CUS-017", "name": "海尔集团", "industry": "制造", "scale": "大型", "level": "B"},
    {"id": "CUS-018", "name": "格力电器", "industry": "制造", "scale": "大型", "level": "B"},
    {"id": "CUS-019", "name": "联想集团", "industry": "IT", "scale": "大型", "level": "B"},
    {"id": "CUS-020", "name": "中兴通讯", "industry": "通信", "scale": "大型", "level": "B"},
    {"id": "CUS-021", "name": "万科地产", "industry": "房地产", "scale": "大型", "level": "C"},
    {"id": "CUS-022", "name": "恒大集团", "industry": "房地产", "scale": "大型", "level": "C"},
    {"id": "CUS-023", "name": "碧桂园", "industry": "房地产", "scale": "大型", "level": "C"},
    {"id": "CUS-024", "name": "顺丰速运", "industry": "物流", "scale": "大型", "level": "B"},
    {"id": "CUS-025", "name": "中通快递", "industry": "物流", "scale": "大型", "level": "C"},
    {"id": "CUS-026", "name": "滴滴出行", "industry": "互联网", "scale": "大型", "level": "B"},
    {"id": "CUS-027", "name": "拼多多", "industry": "电商", "scale": "大型", "level": "B"},
    {"id": "CUS-028", "name": "携程旅行", "industry": "互联网", "scale": "大型", "level": "C"},
    {"id": "CUS-029", "name": "新浪", "industry": "互联网", "scale": "中型", "level": "C"},
    {"id": "CUS-030", "name": "搜狐", "industry": "互联网", "scale": "中型", "level": "C"}
]


def get_region_for_province(province: str) -> str:
    """根据省份获取区域"""
    for region, provinces in REGIONS.items():
        if province in provinces:
            return region
    return "华东"


def get_random_city(province: str) -> str:
    """获取省份下的随机城市"""
    cities = CITIES.get(province, ["未知城市"])
    return random.choice(cities)


def generate_sales_detail(num_records: int = 500) -> pd.DataFrame:
    """生成销售明细数据"""
    records = []

    # 生成2024年全年的日期
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)

    for i in range(num_records):
        # 随机选择销售员（根据区域权重）
        salesperson = random.choice(SALESPEOPLE)
        region = salesperson["region"]

        # 随机选择省份和城市
        province = random.choice(REGIONS[region])
        city = get_random_city(province)

        # 随机选择产品
        category = random.choice(list(PRODUCTS.keys()))
        product = random.choice(PRODUCTS[category])

        # 随机选择客户
        customer = random.choice(CUSTOMERS)

        # 随机日期（Q4权重更高）
        if random.random() < 0.35:  # 35%概率在Q4
            month = random.randint(10, 12)
        else:
            month = random.randint(1, 9)
        day = random.randint(1, 28)
        date = datetime(2024, month, day)

        # 随机数量
        quantity = random.randint(1, 20)

        # 计算金额
        unit_price = product["price"]
        # 添加一些价格波动
        unit_price = int(unit_price * random.uniform(0.9, 1.1))
        sales_amount = unit_price * quantity
        cost = product["cost"] * quantity
        profit = sales_amount - cost

        # 生成订单号
        order_no = f"ORD-{date.strftime('%Y%m%d')}-{i+1:04d}"

        records.append({
            "订单号": order_no,
            "日期": date.strftime("%Y-%m-%d"),
            "销售员": salesperson["name"],
            "区域": region,
            "省份": province,
            "城市": city,
            "客户名称": customer["name"],
            "产品类别": category,
            "产品名称": product["name"],
            "数量": quantity,
            "单价": unit_price,
            "销售额": sales_amount,
            "成本": cost,
            "利润": profit
        })

    return pd.DataFrame(records)


def generate_salesperson_info() -> pd.DataFrame:
    """生成销售员信息"""
    records = []
    for sp in SALESPEOPLE:
        records.append({
            "销售员ID": sp["id"],
            "姓名": sp["name"],
            "部门": sp["department"],
            "职级": sp["level"],
            "入职日期": f"20{random.randint(15, 22)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
            "负责区域": sp["region"],
            "目标金额": sp["target"],
            "联系电话": f"1{random.choice(['38', '39', '58', '59', '86', '87'])}{random.randint(10000000, 99999999)}"
        })
    return pd.DataFrame(records)


def generate_product_info() -> pd.DataFrame:
    """生成产品信息"""
    records = []
    product_lines = {
        "软件": ["企业级应用", "数据分析", "办公协同"],
        "硬件": ["服务器", "网络设备", "终端设备"],
        "服务": ["专业服务", "技术支持", "咨询服务"],
        "配件": ["网络配件", "电源设备", "外设配件"]
    }

    for category, products in PRODUCTS.items():
        for product in products:
            records.append({
                "产品ID": product["id"],
                "产品名称": product["name"],
                "产品类别": category,
                "产品线": random.choice(product_lines[category]),
                "标准价格": product["price"],
                "成本价格": product["cost"],
                "库存数量": random.randint(10, 500),
                "上市日期": f"20{random.randint(18, 23)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
            })
    return pd.DataFrame(records)


def generate_region_targets() -> pd.DataFrame:
    """生成区域目标数据"""
    records = []
    for region, provinces in REGIONS.items():
        for province in provinces:
            # 根据区域设置不同的目标
            base_target = {
                "华东": 2000000,
                "华南": 1500000,
                "华北": 1200000,
                "华中": 1000000,
                "西南": 800000
            }[region]

            # 省份间有差异
            province_factor = random.uniform(0.5, 1.5)
            annual_target = int(base_target * province_factor)

            # 季度目标分配（Q4略高）
            q1 = int(annual_target * 0.22)
            q2 = int(annual_target * 0.23)
            q3 = int(annual_target * 0.23)
            q4 = annual_target - q1 - q2 - q3

            # 找到对应的负责人
            region_sales = [sp for sp in SALESPEOPLE if sp["region"] == region]
            manager = random.choice(region_sales)["name"] if region_sales else "待定"

            records.append({
                "区域": region,
                "省份": province,
                "年度目标": annual_target,
                "Q1目标": q1,
                "Q2目标": q2,
                "Q3目标": q3,
                "Q4目标": q4,
                "负责人": manager
            })
    return pd.DataFrame(records)


def generate_customer_info() -> pd.DataFrame:
    """生成客户信息"""
    records = []
    for customer in CUSTOMERS:
        # 随机分配区域和省份
        region = random.choice(list(REGIONS.keys()))
        province = random.choice(REGIONS[region])

        records.append({
            "客户ID": customer["id"],
            "客户名称": customer["name"],
            "行业": customer["industry"],
            "规模": customer["scale"],
            "区域": region,
            "省份": province,
            "合作开始日期": f"20{random.randint(15, 23)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
            "客户等级": customer["level"]
        })
    return pd.DataFrame(records)


def main():
    """生成Mock数据文件"""
    output_dir = Path(__file__).parent
    output_file = output_dir / "企业销售数据.xlsx"

    print("开始生成Mock数据...")

    # 生成各个Sheet的数据
    print("  生成销售明细数据...")
    df_sales = generate_sales_detail(500)

    print("  生成销售员信息...")
    df_salesperson = generate_salesperson_info()

    print("  生成产品信息...")
    df_product = generate_product_info()

    print("  生成区域目标数据...")
    df_target = generate_region_targets()

    print("  生成客户信息...")
    df_customer = generate_customer_info()

    # 写入Excel文件
    print("  写入Excel文件...")
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df_sales.to_excel(writer, sheet_name="销售明细", index=False)
        df_salesperson.to_excel(writer, sheet_name="销售员信息", index=False)
        df_product.to_excel(writer, sheet_name="产品信息", index=False)
        df_target.to_excel(writer, sheet_name="区域目标", index=False)
        df_customer.to_excel(writer, sheet_name="客户信息", index=False)

    print(f"Mock数据已生成: {output_file}")
    print(f"  - 销售明细: {len(df_sales)} 条记录")
    print(f"  - 销售员信息: {len(df_salesperson)} 条记录")
    print(f"  - 产品信息: {len(df_product)} 条记录")
    print(f"  - 区域目标: {len(df_target)} 条记录")
    print(f"  - 客户信息: {len(df_customer)} 条记录")


if __name__ == "__main__":
    main()
