import re
import ast
from django import template
from django.utils.safestring import mark_safe
import json
import pprint

register = template.Library()


@register.filter
def pprint(value):
    """
    Pretty print JSON or dict objects
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except:
            pass

    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return value


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using the key
    """
    if not dictionary:
        return None

    if isinstance(dictionary, str):
        try:
            dictionary = json.loads(dictionary)
        except:
            return None

    return dictionary.get(key)


@register.filter
def percentage(value, total):
    """Calculate percentage of value from total"""
    if total == 0:
        return 0
    return (value / total) * 100


@register.filter
def multiply(value, arg):
    """将值乘以参数"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def extract_title(content):
    """从报告内容中提取标题"""
    match = re.search(r'Single run: (.+)', content)
    if match:
        return match.group(1)
    return "测试报告"


@register.filter
def extract_environment(content):
    """从报告内容中提取环境信息"""
    match = re.search(r'环境: (\w+)', content)
    if match:
        return match.group(1)
    return "未指定"


@register.filter
def extract_status(content):
    """从报告内容中提取状态"""
    match = re.search(r'状态: (\w+)', content)
    if match:
        return match.group(1)
    return "未知"


@register.filter
def extract_start_time(content):
    """从报告内容中提取开始时间"""
    match = re.search(r'开始时间: (.+?)(?=\n|$)', content)
    if match:
        return match.group(1)
    return "未知"


@register.filter
def extract_end_time(content):
    """从报告内容中提取结束时间"""
    match = re.search(r'结束时间: (.+?)(?=\n|$)', content)
    if match:
        return match.group(1)
    return "未知"


@register.filter
def extract_duration(content):
    """从报告内容中提取持续时间"""
    match = re.search(r'持续时间: (.+?)(?=\n|$|秒)', content)
    if match:
        return match.group(1) + " 秒"
    return "未知"


@register.filter
def extract_test_name(content):
    """从报告内容中提取测试用例名称"""
    match = re.search(r'测试结果.*?\n(.*?)(?=\n|$)', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return "未知测试用例"


@register.filter
def extract_test_status(content):
    """从报告内容中提取测试用例状态"""
    match = re.search(r'状态: (\w+)', content)
    if match:
        return match.group(1)
    return "未知"


@register.filter
def extract_request_method(content):
    """从报告内容中提取请求方法"""
    match = re.search(r'请求方法: (\w+)', content)
    if match:
        return match.group(1)
    return "GET"


@register.filter
def extract_request_url(content):
    """从报告内容中提取请求URL"""
    match = re.search(r'请求URL: (.+?)(?=\n|$)', content)
    if match:
        return match.group(1)
    return ""


@register.filter
def extract_request_headers(content):
    """从报告内容中提取请求头"""
    match = re.search(r'请求头:(.*?)(?=请求体:|响应头:|$)', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


@register.filter
def extract_request_body(content):
    """从报告内容中提取请求体"""
    match = re.search(r'请求体:(.*?)(?=响应头:|响应体:|$)', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


@register.filter
def extract_response_headers(content):
    """从报告内容中提取响应头"""
    match = re.search(r'响应头:(.*?)(?=响应体:|$)', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


@register.filter
def extract_response_body(content):
    """从报告内容中提取响应体"""
    match = re.search(r'响应体:(.*?)(?=错误信息:|$)', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


@register.filter
def extract_error_message(content):
    """从报告内容中提取错误信息"""
    match = re.search(r'错误信息:(.*?)(?=$)', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


@register.filter
def pprint(value):
    """美化打印JSON"""
    try:
        if isinstance(value, str):
            parsed = json.loads(value)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        return json.dumps(value, indent=2, ensure_ascii=False)
    except:
        return value


@register.filter
def trans_type(value):
    # 将字符串转换为字典或列表
    return ast.literal_eval(value)
