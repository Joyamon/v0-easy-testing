from faker import Faker
import random
from typing import List
import json

fake = Faker("zh_CN")

"""
为每个字段设计生成规则
string：随机英文字母、数字组合，可根据 length 指定长度
integer：在 min/max 范围内随机生成
float：指定精度随机生成
email：生成格式化邮箱，如 nameXXXX@test.com
datetime/date：随机生成日期时间
enum/bool：随机选择或取 true/false
...
"""

# 字段定义
fields = [
    {"name": "age", "type": "integer", "min": 18, "max": 60, "required": False},
    {"name": "email", "type": "string", "format": "email", "required": True},
    {"name": "address", "type": "address", "required": False},
    {"name": "phone", "type": "phone", "required": False},
    {"name": "url", "type": "url", "required": False},
    {"name": "city", "type": "city", "required": False},
    {"name": "job", "type": "job", "required": False},
    {"name": "company", "type": "company", "required": False},
    {"name": "username", "type": "username", "required": False},

]


def gen_field(field):
    if field["type"] == "string":
        if field.get("format") == "email":
            return fake.email()
        length = field.get("length", 8)
        return fake.pystr(min_chars=length, max_chars=length)
    elif field["type"] == "integer":
        return random.randint(field.get("min", 0), field.get("max", 100))
    elif field["type"] == "datetime":
        return fake.date_time().isoformat()
    elif field["type"] == "float":
        return round(random.uniform(field.get("min", 0), field.get("max", 100)), field.get("precision", 2))
    elif field["type"] == "bool":
        return random.choice([True, False])
    elif field["type"] == "enum":
        return random.choice(field.get("values", []))
    elif field["type"] == "address":
        return fake.address()
    elif field["type"] == "phone":
        return fake.phone_number()
    elif field["type"] == "url":
        return fake.url()
    elif field["type"] == "city":
        return fake.city()
    elif field["type"] == "job":
        return fake.job()
    elif field["type"] == "company":
        return fake.company()
    elif field["type"] == "website":
        return fake.url()
    elif field["type"] == "username":
        return fake.name()
    else:
        return None


def gen_row(fields: List):
    return {f["name"]: gen_field(f) for f in fields}


def auto_gen_data(fields: List, num: int = 1):
    # 生成num条测试数据
    test_data = [gen_row(fields) for _ in range(num)]
    res = json.dumps(test_data, indent=4, ensure_ascii=False)
    return res


if __name__ == '__main__':
    print(auto_gen_data(fields, 10))
