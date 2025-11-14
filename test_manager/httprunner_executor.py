import json
import time
import logging
import requests
import re
from urllib.parse import urljoin
from jsonpath_ng import jsonpath, parse

# 尝试导入 HTTPRunner，如果失败则记录错误但不中断执行
try:
    import httprunner

    # 尝试多种方式获取 HTTPRunner 版本
    if hasattr(httprunner, "__version__"):
        HTTPRUNNER_VERSION = httprunner.__version__
    elif hasattr(httprunner, "__version"):
        HTTPRUNNER_VERSION = httprunner.__version
    elif hasattr(httprunner, "version"):
        HTTPRUNNER_VERSION = httprunner.version
    else:
        # 尝试从包信息获取版本
        try:
            import pkg_resources

            HTTPRUNNER_VERSION = pkg_resources.get_distribution("httprunner").version
        except:
            HTTPRUNNER_VERSION = "unknown"

    # 尝试导入 HttpRunner 类
    try:
        from httprunner.runner import HttpRunner

        HTTPRUNNER_AVAILABLE = True
    except ImportError:
        # 尝试其他可能的导入路径
        try:
            from httprunner.api import HttpRunner

            HTTPRUNNER_AVAILABLE = True
        except ImportError:
            HTTPRUNNER_AVAILABLE = False
except ImportError:
    HTTPRUNNER_AVAILABLE = False
    HTTPRUNNER_VERSION = "not installed"

logger = logging.getLogger(__name__)
logger.info(f"HTTPRunner version: {HTTPRUNNER_VERSION}, Available: {HTTPRUNNER_AVAILABLE}")


def replace_variables(content, variables):
    """
    替换内容中的变量引用
    支持格式: ${variable_name} 或 $variable_name

    Args:
        content: 需要替换变量的内容，可以是字符串、字典、列表或其他基本类型
        variables: 变量字典，键为变量名，值为变量值

    Returns:
        替换变量后的内容
    """
    if not variables or variables is None:
        return content

    # 如果内容为None，直接返回None
    if content is None:
        return None

    # 处理字典类型
    if isinstance(content, dict):
        return {k: replace_variables(v, variables) for k, v in content.items()}

    # 处理列表类型
    elif isinstance(content, list):
        return [replace_variables(item, variables) for item in content]

    # 处理字符串类型
    elif isinstance(content, str):
        # 首先替换 ${variable} 格式的变量
        result = content

        # 使用正则表达式查找所有 ${variable} 格式的变量
        pattern = r'\${([a-zA-Z0-9_]+)}'

        # 查找所有匹配项
        for match in re.finditer(pattern, content):
            var_name = match.group(1)
            if var_name in variables:
                # 获取变量值并转换为字符串
                var_value = variables[var_name]
                if var_value is None:
                    var_value = ""
                elif not isinstance(var_value, str):
                    var_value = str(var_value)

                # 替换变量
                placeholder = f'${{{var_name}}}'
                result = result.replace(placeholder, var_value)

        # 然后替换 $variable 格式的变量
        # 使用更简单的方法，避免使用可变宽度的后向查找
        words = re.findall(r'\$([a-zA-Z0-9_]+)', result)
        for word in words:
            # 检查是否是变量名
            if word in variables:
                # 确保不是已经处理过的 ${var} 格式
                placeholder = f'${word}'
                if f'${{{word}}}' not in content:  # 避免替换已经处理过的 ${var} 格式
                    # 获取变量值并转换为字符串
                    var_value = variables[word]
                    if var_value is None:
                        var_value = ""
                    elif not isinstance(var_value, str):
                        var_value = str(var_value)

                    # 替换变量
                    result = result.replace(placeholder, var_value)

        return result

    # 处理其他类型（数字、布尔值等），直接返回原值
    else:
        return content


def execute_test_case(test_case, environment, variables=None):
    """
    Execute a single test case using direct HTTP request

    Args:
        test_case: TestCase object
        environment: Environment object
        variables: Dict of variables to use for parameter substitution
    """
    try:
        # 初始化变量字典
        if variables is None:
            variables = {}
        else:
            # 创建一个副本，避免修改原始变量字典
            variables = variables.copy()

        # 合并环境变量
        if hasattr(environment, 'variables') and environment.variables:
            try:
                env_vars = environment.variables
                if isinstance(env_vars, str):
                    env_vars = json.loads(env_vars)
                variables.update(env_vars)
            except Exception as e:
                logger.error(f"Error merging environment variables: {e}")

        # 记录测试开始信息
        logger.info(
            f"Executing test case: {test_case.name} (ID: {test_case.id}) with environment: {environment.name} (ID: {environment.id})")
        logger.info(
            f"Request method: {test_case.request_method}, URL: {test_case.request_url}, Body format: {test_case.request_body_format}")

        # 记录使用的变量
        if variables:
            logger.info(f"Using variables: {variables}")

        start_time = time.time()

        # 直接使用 HTTP 请求执行测试
        result = _execute_with_requests(test_case, environment, variables)

        # 计算响应时间
        end_time = time.time()
        result["response_time"] = (end_time - start_time) * 1000  # 转换为毫秒

        # 在处理响应后，添加参数提取逻辑
        try:
            extracted_params = {}
            if hasattr(test_case, 'extract_params') and test_case.extract_params:
                try:
                    response_body = result['response_body']

                    # 确保响应体是JSON格式
                    if isinstance(response_body, str):
                        try:
                            response_json = json.loads(response_body)
                        except json.JSONDecodeError:
                            # 如果不是JSON，则使用文本响应
                            response_json = {"content": response_body}
                    else:
                        response_json = response_body

                    # 遍历需要提取的参数
                    for extract in test_case.extract_params:
                        try:
                            # 确保extract是字典格式
                            if isinstance(extract, str):
                                try:
                                    extract = json.loads(extract)
                                except json.JSONDecodeError:
                                    logger.error(f"Invalid extract parameter format: {extract}")
                                    continue

                            # 获取参数名和路径
                            param_name = extract.get('name')
                            param_path = extract.get('path')

                            if not param_name or not param_path:
                                logger.error(f"Invalid extract parameter: {extract}")
                                continue

                            # 使用JSONPath提取参数
                            jsonpath_expr = parse(param_path)
                            matches = [match.value for match in jsonpath_expr.find(response_json)]

                            if matches:
                                # 只取第一个匹配结果
                                extracted_params[param_name] = matches[0]
                                logger.info(f"Extracted parameter {param_name} = {matches[0]}")
                        except Exception as e:
                            # 处理提取错误
                            logger.error(
                                f"Error extracting parameter {extract.get('name', 'unknown')} using JSONPath {extract.get('path', 'unknown')}: {e}")
                except Exception as e:
                    # 处理 JSON 解析错误
                    logger.error(f"Error parsing response body for parameter extraction: {e}")

            # 将提取的参数添加到结果中
            result['extracted_params'] = extracted_params
        except Exception as e:
            logger.error(f"Error in parameter extraction process: {e}")
            result['extracted_params'] = {}

        return result

    except Exception as e:
        logger.exception(f"Error executing test case: {e}")
        return {
            "status": "error",
            "request_headers": {},
            "request_body": {},
            "response_time": 0,
            "response_status_code": None,
            "response_headers": {},
            "response_body": {},
            "error_message": str(e),
            "extracted_params": {}
        }


def _execute_with_requests(test_case, environment, variables=None):
    """
    Execute test case using direct HTTP requests

    Args:
        test_case: TestCase object
        environment: Environment object
        variables: Dict of variables to use for parameter substitution
    """
    try:
        # 构建完整 URL，并替换变量
        base_url = environment.base_url.rstrip('/')

        # 替换URL中的变量
        request_url = test_case.request_url
        if request_url:
            request_url = request_url.lstrip('/')
            request_url = replace_variables(request_url, variables)
        else:
            request_url = ""

        full_url = f"{base_url}/{request_url}"
        logger.info(f"Full URL after variable replacement: {full_url}")

        # 准备请求参数
        headers = {}
        if hasattr(test_case, 'request_headers') and test_case.request_headers:
            if isinstance(test_case.request_headers, str):
                try:
                    headers = json.loads(test_case.request_headers)
                except json.JSONDecodeError:
                    logger.error(f"Invalid headers format: {test_case.request_headers}")
            else:
                headers = test_case.request_headers.copy()

        # 替换请求头中的变量
        headers = replace_variables(headers, variables)

        kwargs = {
            "headers": headers,
            "timeout": 30
        }

        # 保存原始请求头和请求体，用于结果记录
        original_headers = headers.copy()
        original_body = None

        # 根据请求体格式处理请求数据
        if hasattr(test_case, 'request_body') and test_case.request_body and test_case.request_method in ['POST', 'PUT',
                                                                                                          'PATCH']:
            request_body = test_case.request_body

            # 如果请求体是字符串，尝试解析为JSON
            if isinstance(request_body, str):
                try:
                    request_body = json.loads(request_body)
                except json.JSONDecodeError:
                    # 如果不是JSON，保持原样
                    pass

            # 保存原始请求体（替换变量前）
            original_body = request_body

            # 替换请求体中的变量
            request_body = replace_variables(request_body, variables)
            print(f"##Request body after variable replacement: {request_body}")

            # 根据请求体格式设置请求参数
            if hasattr(test_case, 'request_body_format'):
                if test_case.request_body_format == 'json':
                    # 确保设置了正确的 Content-Type
                    if 'Content-Type' not in headers:
                        kwargs["headers"]["Content-Type"] = "application/json"

                    # 如果请求体是字典，直接使用
                    if isinstance(request_body, dict) or isinstance(request_body, list):
                        kwargs["json"] = request_body
                    else:
                        # 否则尝试解析为JSON
                        try:
                            kwargs["json"] = json.loads(request_body) if isinstance(request_body, str) else request_body
                        except json.JSONDecodeError:
                            # 如果解析失败，使用原始字符串
                            kwargs["data"] = request_body

                    logger.debug(f"Request body (JSON): {json.dumps(kwargs.get('json', request_body))}")
                elif test_case.request_body_format == 'form-data':
                    # 确保设置了正确的 Content-Type
                    if 'Content-Type' not in headers:
                        kwargs["headers"]["Content-Type"] = "application/x-www-form-urlencoded"

                    # 如果请求体是字典，直接使用
                    if isinstance(request_body, dict):
                        kwargs["data"] = request_body
                    else:
                        # 否则尝试解析为字典
                        try:
                            kwargs["data"] = json.loads(request_body) if isinstance(request_body, str) else request_body
                        except json.JSONDecodeError:
                            # 如果解析失败，使用原始字符串
                            kwargs["data"] = request_body

                    logger.debug(f"Request body (form-data): {kwargs['data']}")
            else:
                # 默认使用JSON格式
                if 'Content-Type' not in headers:
                    kwargs["headers"]["Content-Type"] = "application/json"

                # 如果请求体是字典，直接使用
                if isinstance(request_body, dict) or isinstance(request_body, list):
                    kwargs["json"] = request_body
                else:
                    # 否则尝试解析为JSON
                    try:
                        kwargs["json"] = json.loads(request_body) if isinstance(request_body, str) else request_body
                    except json.JSONDecodeError:
                        # 如果解析失败，使用原始字符串
                        kwargs["data"] = request_body

                logger.debug(f"Request body (default JSON): {json.dumps(kwargs.get('json', request_body))}")

        # 发送请求
        logger.debug(f"Request method: {test_case.request_method}, Headers: {kwargs['headers']}")
        response = requests.request(
            method=test_case.request_method,
            url=full_url,
            **kwargs
        )

        # 处理响应
        logger.debug(f"Response status code: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")

        try:
            response_body = response.json()
            logger.debug("Response body parsed as JSON")
        except ValueError:
            response_body = {"content": response.text}
            logger.debug("Response body parsed as text")

        # 检查状态码是否符合预期
        success = response.status_code == test_case.expected_status_code

        # 验证其他规则
        validation_errors = []
        validators = []

        if hasattr(test_case, 'validation_rules') and test_case.validation_rules:
            validation_rules = test_case.validation_rules

            # 如果验证规则是字符串，尝试解析为JSON
            if isinstance(validation_rules, str):
                try:
                    validation_rules = json.loads(validation_rules)
                except json.JSONDecodeError:
                    logger.error(f"Invalid validation rules format: {validation_rules}")
                    validation_rules = []

            for rule in validation_rules:
                # 简单实现一些基本的验证规则
                if "Equal" in rule:
                    path, expected = rule["Equal"]
                    # 替换预期值中的变量
                    expected = replace_variables(expected, variables)

                    # 简化的 JSONPath 实现，仅支持基本路径
                    if path == "status_code":
                        actual = response.status_code
                    elif path.startswith("$."):
                        # 使用JSONPath解析
                        try:
                            jsonpath_expr = parse(path)
                            matches = [match.value for match in jsonpath_expr.find(response_body)]
                            actual = matches[0] if matches else None
                        except Exception as e:
                            logger.error(f"Error evaluating JSONPath {path}: {e}")
                            actual = None
                    else:
                        actual = None

                    check_result = "pass" if actual == expected else "failed"
                    validators.append({
                        "check": path,
                        "expect": expected,
                        "comparator": "eq",
                        "check_value": actual,
                        "check_result": check_result
                    })

                    if actual != expected:
                        validation_errors.append(f"Validation failed: expected {path} to be {expected}, got {actual}")
                        success = False

                # 添加对 contains 验证规则的支持
                elif "contains" in rule:
                    path, expected = rule["contains"]
                    # 替换预期值中的变量
                    expected = replace_variables(expected, variables)

                    if path == "content" or path == "text":
                        # 检查响应文本是否包含预期字符串
                        actual = response.text
                        check_result = "pass" if expected in actual else "failed"
                        validators.append({
                            "check": path,
                            "expect": expected,
                            "comparator": "contains",
                            "check_value": actual[:100] + "..." if len(actual) > 100 else actual,
                            "check_result": check_result
                        })

                        if expected not in actual:
                            validation_errors.append(f"Validation failed: expected response to contain '{expected}'")
                            success = False
                    elif path.startswith("$."):
                        # 使用JSONPath解析
                        try:
                            jsonpath_expr = parse(path)
                            matches = [match.value for match in jsonpath_expr.find(response_body)]
                            actual = matches[0] if matches else None

                            check_result = "pass" if actual is not None and expected in str(actual) else "failed"
                            validators.append({
                                "check": path,
                                "expect": expected,
                                "comparator": "contains",
                                "check_value": str(actual)[:100] + "..." if actual and len(str(actual)) > 100 else str(
                                    actual),
                                "check_result": check_result
                            })

                            if actual is None or expected not in str(actual):
                                validation_errors.append(f"Validation failed: expected {path} to contain '{expected}'")
                                success = False
                        except Exception as e:
                            logger.error(f"Error evaluating JSONPath {path}: {e}")
                            validators.append({
                                "check": path,
                                "expect": expected,
                                "comparator": "contains",
                                "check_value": None,
                                "check_result": "failed"
                            })
                            validation_errors.append(f"Validation failed: could not evaluate {path}")
                            success = False

        # 确定测试状态
        status = "passed" if success else "failed"
        error_message = "\n".join(validation_errors) if validation_errors else ""

        return {
            "status": status,
            "request_headers": original_headers,  # 保存原始请求头
            "request_body": original_body,  # 保存原始请求体
            "response_status_code": response.status_code,
            "response_headers": dict(response.headers),
            "response_body": response_body,
            "error_message": error_message,
            "validators": validators
        }

    except requests.RequestException as e:
        logger.exception(f"HTTP request error: {e}")
        return {
            "status": "error",
            "request_headers": headers if 'headers' in locals() else {},
            "request_body": original_body if 'original_body' in locals() else {},
            "response_status_code": None,
            "response_headers": {},
            "response_body": {},
            "error_message": f"HTTP request error: {str(e)}"
        }
    except Exception as e:
        logger.exception(f"Unexpected error in direct HTTP request: {e}")
        return {
            "status": "error",
            "request_headers": headers if 'headers' in locals() else {},
            "request_body": original_body if 'original_body' in locals() else {},
            "response_status_code": None,
            "response_headers": {},
            "response_body": {},
            "error_message": f"Unexpected error: {str(e)}"
        }


def execute_test_suite(test_suite, default_environment, case_environments=None):
    """
    Execute a test suite (multiple test cases) using direct HTTP requests

    Args:
        test_suite: TestSuite object
        default_environment: Default Environment object to use
        case_environments: Dict mapping test case IDs to environment IDs
    """
    results = []
    case_environments = case_environments or {}
    extracted_variables = {}  # 存储提取的变量，用于后续测试用例

    # 获取套件中的所有测试用例，按顺序排列
    test_suite_cases = test_suite.testsuitecase_set.all().order_by('order')

    logger.info(
        f"Executing test suite: {test_suite.name} (ID: {test_suite.id}) with {test_suite_cases.count()} test cases")

    for test_suite_case in test_suite_cases:
        test_case = test_suite_case.test_case

        # 确定使用哪个环境
        environment = default_environment
        environment_id = default_environment.id

        # 首先检查测试套件用例是否有指定环境
        if hasattr(test_suite_case, 'environment') and test_suite_case.environment:
            environment = test_suite_case.environment
            environment_id = environment.id
        # 然后检查运行时是否指定了环境
        elif test_case.id in case_environments:
            environment_id = case_environments[test_case.id]
            from django.apps import apps
            Environment = apps.get_model('test_manager', 'Environment')
            try:
                environment = Environment.objects.get(id=environment_id)
            except Environment.DoesNotExist:
                logger.error(f"Environment with ID {environment_id} does not exist, using default environment")
                environment = default_environment
                environment_id = default_environment.id

        logger.info(
            f"Executing test case {test_case.name} (ID: {test_case.id}) from suite with environment: {environment.name} (ID: {environment.id})")
        logger.info(f"Using variables: {extracted_variables}")

        # 执行测试用例，传递之前提取的变量
        result = execute_test_case(test_case, environment, extracted_variables)
        result['test_case_id'] = test_case.id
        result['environment_id'] = environment_id

        # 存储提取的变量，用于后续测试用例
        if 'extracted_params' in result and result['extracted_params']:
            extracted_variables.update(result['extracted_params'])
            logger.info(f"Updated variables after test case: {extracted_variables}")

        results.append(result)
        logger.info(f"Test case {test_case.name} execution result: {result['status']}")

    logger.info(
        f"Test suite execution completed. Total: {len(results)}, Passed: {sum(1 for r in results if r['status'] == 'passed')}")

    return results
