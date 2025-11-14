import threading
import logging
import traceback
from django.utils import timezone
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

def execute_test_suite_async(test_suite, environment, case_environments, test_run, user, execute_test_suite_func):
    """
    在后台线程中执行测试套件
    
    Args:
        test_suite: 测试套件对象
        environment: 环境对象
        case_environments: 测试用例环境映射字典
        test_run: 测试运行对象
        user: 当前用户
        execute_test_suite_func: 执行测试套件的函数
    """
    thread = threading.Thread(
        target=_execute_test_suite_thread,
        args=(test_suite, environment, case_environments, test_run, user, execute_test_suite_func),
        daemon=True
    )
    thread.start()
    return thread

def _execute_test_suite_thread(test_suite, environment, case_environments, test_run, user, execute_test_suite_func):
    """
    执行测试套件的线程函数
    """
    from django.db import connection
    
    # 在新线程中关闭旧的数据库连接并创建新的连接
    connection.close()
    
    try:
        logger.info(f"开始异步执行测试套件: {test_suite.name} (ID: {test_suite.id})")
        
        # 执行测试套件
        results = execute_test_suite_func(test_suite, environment, case_environments)
        
        # 导入需要的模型
        from django.apps import apps
        TestResult = apps.get_model('test_manager', 'TestResult')
        Environment = apps.get_model('test_manager', 'Environment')
        
        # 创建测试结果
        for result in results:
            # 获取测试用例使用的环境
            env_id = result.get('environment_id', environment.id)
            test_env = get_object_or_404(Environment, id=env_id)
            
            TestResult.objects.create(
                test_run=test_run,
                test_case_id=result['test_case_id'],
                environment=test_env,
                status=result['status'],
                response_time=result.get('response_time'),
                response_status_code=result.get('response_status_code'),
                response_headers=result.get('response_headers', {}),
                response_body=result.get('response_body'),
                request_headers=result.get('request_headers', {}),
                request_body=result.get('request_body'),
                error_message=result.get('error_message', ''),
                extracted_params=result.get('extracted_params', {})
            )
        
        # 更新测试运行状态
        failed_results = [r for r in results if r['status'] != 'passed']
        test_run.status = 'failed' if failed_results else 'completed'
        test_run.end_time = timezone.now()
        test_run.save()
        
        logger.info(
            f"测试套件异步执行完成: {test_suite.name} (ID: {test_suite.id}), "
            f"结果: {len(results) - len(failed_results)}/{len(results)} 通过"
        )
        
    except Exception as e:
        logger.error(f"测试套件异步执行出错: {test_suite.name} (ID: {test_suite.id}), 错误: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 更新测试运行状态为失败
        test_run.status = 'failed'
        test_run.end_time = timezone.now()
        test_run.error_message = f"执行出错: {str(e)}"
        test_run.save()

def execute_test_case_async(test_case, environment, test_run, user, execute_test_case_func):
    """
    在后台线程中执行测试用例
    
    Args:
        test_case: 测试用例对象
        environment: 环境对象
        test_run: 测试运行对象
        user: 当前用户
        execute_test_case_func: 执行测试用例的函数
    """
    thread = threading.Thread(
        target=_execute_test_case_thread,
        args=(test_case, environment, test_run, user, execute_test_case_func),
        daemon=True
    )
    thread.start()
    return thread

def _execute_test_case_thread(test_case, environment, test_run, user, execute_test_case_func):
    """
    执行测试用例的线程函数
    """
    from django.db import connection
    
    # 在新线程中关闭旧的数据库连接并创建新的连接
    connection.close()
    
    try:
        logger.info(f"开始异步执行测试用例: {test_case.name} (ID: {test_case.id})")
        
        # 执行测试用例
        result = execute_test_case_func(test_case, environment)
        
        # 导入需要的模型
        from django.apps import apps
        TestResult = apps.get_model('test_manager', 'TestResult')
        
        # 创建测试结果
        TestResult.objects.create(
            test_run=test_run,
            test_case=test_case,
            environment=environment,
            status=result['status'],
            response_time=result.get('response_time'),
            response_status_code=result.get('response_status_code'),
            response_headers=result.get('response_headers', {}),
            response_body=result.get('response_body'),
            request_headers=result.get('request_headers', {}),
            request_body=result.get('request_body'),
            error_message=result.get('error_message', ''),
            extracted_params=result.get('extracted_params', {}),
            validators=result.get('validators', [])
        )
        
        # 更新测试运行状态
        test_run.status = 'completed' if result['status'] == 'passed' else 'failed'
        test_run.end_time = timezone.now()
        test_run.save()
        
        logger.info(
            f"测试用例异步执行完成: {test_case.name} (ID: {test_case.id}), "
            f"结果: {result['status']}"
        )
        
    except Exception as e:
        logger.error(f"测试用例异步执行出错: {test_case.name} (ID: {test_case.id}), 错误: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 更新测试运行状态为失败
        test_run.status = 'failed'
        test_run.end_time = timezone.now()
        test_run.error_message = f"执行出错: {str(e)}"
        test_run.save()
