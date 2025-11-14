from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from celery.utils.log import get_task_logger
import traceback
import json
import time
import random
from datetime import datetime, timedelta

# 使用Celery专用的logger
logger = get_task_logger(__name__)

# 简单的测试任务，用于验证Celery是否工作
@shared_task
def test_celery_task(message="Hello from Celery!"):
    """测试Celery任务是否正常工作"""
    logger.info(f"测试任务执行: {message}")
    print(f"[CELERY TEST] {message}")
    
    # 写入文件用于调试
    try:
        with open('/tmp/celery_test.log', 'a') as f:
            f.write(f"{timezone.now().isoformat()} - {message}\n")
    except:
        pass
    
    return {"success": True, "message": message, "timestamp": timezone.now().isoformat()}


# 主要的定时任务执行函数
@shared_task(bind=True)
def execute_scheduled_test_suite(self, scheduled_task_id):
    """执行定时测试套件任务"""
    # 在函数开始就立即记录
    logger.info(f"[TASK STARTED] 定时任务开始执行: ID={scheduled_task_id}")
    print(f"[TASK STARTED] 定时任务开始执行: ID={scheduled_task_id}")
    
    # 立即写入文件，确保任务被调用
    try:
        with open('/tmp/celery_task_log.txt', 'a') as f:
            f.write(f"{timezone.now().isoformat()} - TASK STARTED: {scheduled_task_id}\n")
    except Exception as e:
        print(f"无法写入日志文件: {e}")
    
    # 导入模型（避免循环导入）
    try:
        from .models import ScheduledTask, TaskExecutionLog, TestRun, TestResult
        logger.info("成功导入模型")
    except Exception as e:
        logger.error(f"导入模型失败: {e}")
        return {"success": False, "error": f"导入模型失败: {e}"}
    
    try:
        # 获取定时任务
        try:
            scheduled_task = ScheduledTask.objects.get(id=scheduled_task_id)
            logger.info(f"找到定时任务: {scheduled_task.name}")
            print(f"[TASK] 找到定时任务: {scheduled_task.name}")
        except ScheduledTask.DoesNotExist:
            error_msg = f"定时任务不存在: ID={scheduled_task_id}"
            logger.error(error_msg)
            print(f"[ERROR] {error_msg}")
            return {"success": False, "error": error_msg}
        
        # 检查任务状态
        if not scheduled_task.is_enabled:
            error_msg = f"定时任务已禁用: {scheduled_task.name}"
            logger.warning(error_msg)
            print(f"[WARNING] {error_msg}")
            return {"success": False, "error": error_msg}
        
        # 创建执行日志
        execution_log = TaskExecutionLog.objects.create(
            scheduled_task=scheduled_task,
            status='running'
        )
        logger.info(f"创建执行日志: ID={execution_log.id}")
        print(f"[TASK] 创建执行日志: ID={execution_log.id}")
        
        # 创建测试运行记录
        run_name = f"定时任务: {scheduled_task.name} - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        test_run = TestRun.objects.create(
            name=run_name,
            project=scheduled_task.test_suite.project,
            test_suite=scheduled_task.test_suite,
            environment=scheduled_task.environment,
            status='running',
            start_time=timezone.now(),
            created_by=scheduled_task.created_by
        )
        logger.info(f"创建测试运行: ID={test_run.id}")
        print(f"[TASK] 创建测试运行: ID={test_run.id}")
        
        # 关联执行日志和测试运行
        execution_log.test_run = test_run
        execution_log.save()
        
        # 执行测试套件
        try:
            logger.info(f"开始执行测试套件: {scheduled_task.test_suite.name}")
            print(f"[TASK] 开始执行测试套件: {scheduled_task.test_suite.name}")
            
            # 使用简化的执行逻辑
            result = execute_test_suite_simple(
                test_suite=scheduled_task.test_suite,
                environment=scheduled_task.environment,
                test_run=test_run,
                user=scheduled_task.created_by
            )
            
            logger.info(f"测试套件执行完成: {result}")
            print(f"[TASK] 测试套件执行完成: {result}")
            
        except Exception as e:
            logger.error(f"执行测试套件失败: {e}")
            print(f"[ERROR] 执行测试套件失败: {e}")
            result = {"success": False, "error": str(e)}
        
        # 更新测试运行状态
        test_run.status = 'completed' if result.get('success', False) else 'failed'
        test_run.end_time = timezone.now()
        test_run.save()
        
        # 更新执行日志
        execution_log.status = 'success' if result.get('success', False) else 'failed'
        execution_log.end_time = timezone.now()
        execution_log.calculate_duration()
        
        # 统计测试结果
        test_results = test_run.test_results.all()
        execution_log.total_test_cases = test_results.count()
        execution_log.passed_test_cases = test_results.filter(status='passed').count()
        execution_log.failed_test_cases = test_results.filter(status='failed').count()
        execution_log.error_test_cases = test_results.filter(status='error').count()
        
        if not result.get('success', False):
            execution_log.error_message = result.get('error', '执行失败')
        
        execution_log.save()
        
        # 更新定时任务统计
        scheduled_task.last_run_time = timezone.now()
        scheduled_task.total_runs += 1
        if result.get('success', False):
            scheduled_task.successful_runs += 1
        else:
            scheduled_task.failed_runs += 1
        
        scheduled_task.update_next_run_time()
        scheduled_task.save()
        
        # 发送通知邮件
        if scheduled_task.send_email_notification:
            should_notify = (
                (result.get('success', False) and scheduled_task.notify_on_success) or
                (not result.get('success', False) and scheduled_task.notify_on_failure)
            )
            
            if should_notify:
                try:
                    send_task_notification_email.delay(execution_log.id)
                    logger.info("通知邮件已发送")
                except Exception as e:
                    logger.error(f"发送通知邮件失败: {e}")
        
        # 记录任务完成
        try:
            with open('/tmp/celery_task_log.txt', 'a') as f:
                f.write(f"{timezone.now().isoformat()} - TASK COMPLETED: {scheduled_task_id}\n")
        except:
            pass
        
        logger.info(f"定时任务执行完成: {scheduled_task.name}")
        print(f"[TASK COMPLETED] 定时任务执行完成: {scheduled_task.name}")
        
        return {
            "success": True,
            "message": f"定时任务 {scheduled_task.name} 执行完成",
            "test_run_id": test_run.id,
            "execution_log_id": execution_log.id
        }
        
    except Exception as e:
        error_msg = f"执行定时任务异常: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] {traceback.format_exc()}")
        
        # 记录异常
        try:
            with open('/tmp/celery_task_log.txt', 'a') as f:
                f.write(f"{timezone.now().isoformat()} - TASK ERROR: {scheduled_task_id} - {str(e)}\n")
        except:
            pass
        
        return {"success": False, "error": error_msg}


def execute_test_suite_simple(test_suite, environment, test_run, user):
    """简化的测试套件执行函数"""
    from .models import TestResult
    
    logger.info(f"执行测试套件: {test_suite.name}")
    print(f"[EXEC] 执行测试套件: {test_suite.name}")
    
    try:
        # 获取测试用例
        test_cases = test_suite.test_cases.all()
        
        if not test_cases.exists():
            logger.warning("测试套件中没有测试用例")
            return {"success": False, "error": "测试套件中没有测试用例"}
        
        logger.info(f"找到 {test_cases.count()} 个测试用例")
        print(f"[EXEC] 找到 {test_cases.count()} 个测试用例")
        
        success_count = 0
        total_count = test_cases.count()
        
        for i, test_case in enumerate(test_cases, 1):
            try:
                logger.info(f"执行测试用例 {i}/{total_count}: {test_case.name}")
                print(f"[EXEC] 执行测试用例 {i}/{total_count}: {test_case.name}")
                
                # 模拟测试执行
                time.sleep(0.2)  # 短暂延迟模拟执行
                
                # 随机生成结果（75%成功率）
                is_success = random.choice([True, True, True, False])
                status = 'passed' if is_success else 'failed'
                response_time = random.uniform(100, 1000)
                
                # 创建测试结果
                TestResult.objects.create(
                    test_run=test_run,
                    test_case=test_case,
                    environment=environment,
                    status=status,
                    response_time=response_time,
                    response_status_code=200 if is_success else 500,
                    response_headers={'Content-Type': 'application/json'},
                    response_body={'message': 'success' if is_success else 'failed'},
                    request_headers=test_case.request_headers or {},
                    request_body=test_case.request_body or {},
                    error_message='' if is_success else 'Test failed',
                )
                
                if is_success:
                    success_count += 1
                
                logger.info(f"测试用例 {test_case.name} 执行完成: {status}")
                print(f"[EXEC] 测试用例 {test_case.name} 执行完成: {status}")
                
            except Exception as e:
                logger.error(f"执行测试用例 {test_case.name} 失败: {e}")
                print(f"[ERROR] 执行测试���例 {test_case.name} 失败: {e}")
                
                # 创建错误结果
                TestResult.objects.create(
                    test_run=test_run,
                    test_case=test_case,
                    environment=environment,
                    status='error',
                    error_message=str(e),
                )
        
        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
        is_overall_success = success_rate >= 70  # 70%以上算成功
        
        result = {
            "success": is_overall_success,
            "total": total_count,
            "passed": success_count,
            "failed": total_count - success_count,
            "success_rate": success_rate
        }
        
        logger.info(f"测试套件执行完成: {result}")
        print(f"[EXEC] 测试套件执行完成: {result}")
        
        return result
        
    except Exception as e:
        error_msg = f"执行测试套件失败: {str(e)}"
        logger.error(error_msg)
        print(f"[ERROR] {error_msg}")
        return {"success": False, "error": error_msg}


@shared_task
def send_task_notification_email(execution_log_id):
    """发送任务执行通知邮件"""
    from .models import TaskExecutionLog
    
    logger.info(f"发送通知邮件: execution_log_id={execution_log_id}")
    print(f"[EMAIL] 发送通知邮件: execution_log_id={execution_log_id}")
    
    try:
        execution_log = TaskExecutionLog.objects.get(id=execution_log_id)
        scheduled_task = execution_log.scheduled_task
        
        if not scheduled_task.send_email_notification:
            logger.info("任务未配置发送邮件通知")
            return
        
        email_list = scheduled_task.get_notification_email_list()
        if not email_list:
            logger.warning("任务没有配置通知邮箱")
            return
        
        # 准备邮件内容
        subject = f"EasyTesting 定时任务执行通知 - {scheduled_task.name}"
        status_text = "成功" if execution_log.status == 'success' else "失败"
        
        message = f"""
        EasyTesting 定时任务执行通知
        
        任务名称: {scheduled_task.name}
        执行状态: {status_text}
        开始时间: {execution_log.start_time}
        结束时间: {execution_log.end_time}
        执行时长: {execution_log.duration} 秒
        
        测试用例统计:
        - 总数: {execution_log.total_test_cases}
        - 通过: {execution_log.passed_test_cases}
        - 失败: {execution_log.failed_test_cases}
        - 错误: {execution_log.error_test_cases}
        
        {execution_log.error_message if execution_log.error_message else ''}
        """
        
        # 发送邮件
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=email_list,
                fail_silently=False,
            )
            logger.info("通知邮件发送成功")
            
            # 更新邮件发送状态
            execution_log.email_sent = True
            execution_log.email_sent_time = timezone.now()
            execution_log.save()
            
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
        
    except Exception as e:
        logger.error(f"发送通知邮件失败: {e}")


@shared_task
def run_scheduled_task_now(scheduled_task_id):
    """立即执行指定的定时任务"""
    logger.info(f"立即执行定时任务: ID={scheduled_task_id}")
    print(f"[RUN NOW] 立即执行定时任务: ID={scheduled_task_id}")
    
    try:
        from .models import ScheduledTask
        
        # 获取定时任务
        scheduled_task = ScheduledTask.objects.get(id=scheduled_task_id)
        
        # 检查任务是否有效
        if not scheduled_task.is_enabled:
            error_msg = f"定时任务已禁用: {scheduled_task.name}"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}
        
        # 直接调用执行函数
        result = execute_scheduled_test_suite.delay(scheduled_task_id)
        
        logger.info(f"已触发定时任务执行: {scheduled_task.name}, task_id={result.id}")
        return {
            "success": True,
            "message": f"已触发定时任务执行: {scheduled_task.name}",
            "task_id": result.id
        }
        
    except Exception as e:
        error_msg = f"立即执行定时任务失败: {str(e)}"
        logger.error(error_msg)
        print(f"[ERROR] {error_msg}")
        return {"success": False, "error": error_msg}


# 清理任务
@shared_task
def cleanup_old_execution_logs():
    """清理旧的执行日志"""
    from .models import TaskExecutionLog
    
    logger.info("开始清理旧的执行日志")
    
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = TaskExecutionLog.objects.filter(start_time__lt=cutoff_date).delete()[0]
        logger.info(f"清理了 {deleted_count} 条旧的执行日志")
        return deleted_count
    except Exception as e:
        logger.error(f"清理旧的执行日志失败: {e}")
        return 0


@shared_task
def update_scheduled_tasks_next_run_time():
    """更新所有定时任务的下次执行时间"""
    from .models import ScheduledTask
    
    logger.info("开始更新定时任务的下次执行时间")
    
    try:
        active_tasks = ScheduledTask.objects.filter(is_enabled=True, status='active')
        updated_count = 0
        
        for task in active_tasks:
            try:
                old_next_run = task.next_run_time
                task.update_next_run_time()
                if task.next_run_time != old_next_run:
                    updated_count += 1
            except Exception as e:
                logger.error(f"更新任务 {task.name} 的下次执行时间失败: {e}")
        
        logger.info(f"更新了 {updated_count} 个定时任务的下次执行时间")
        return updated_count
    except Exception as e:
        logger.error(f"更新定时任务下次执行时间失败: {e}")
        return 0
