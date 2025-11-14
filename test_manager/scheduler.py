import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from .models import ScheduledTask
from .tasks import execute_scheduled_test_suite
import json

logger = logging.getLogger(__name__)


class TaskScheduler:
    """定时任务调度器"""

    @staticmethod
    def create_or_update_celery_task(scheduled_task):
        """创建或更新Celery定时任务"""
        try:
            logger.info(f"开始创建/更新Celery任务: {scheduled_task.name}")

            # 删除旧的Celery任务（如果存在）
            if scheduled_task.celery_task_id:
                try:
                    old_task = PeriodicTask.objects.get(name=scheduled_task.celery_task_id)
                    old_task.delete()
                    logger.info(f"删除旧任务: {scheduled_task.celery_task_id}")
                except PeriodicTask.DoesNotExist:
                    logger.warning(f"旧任务不存在: {scheduled_task.celery_task_id}")

            # 清理可能存在的同名任务（防止重复）
            existing_tasks = PeriodicTask.objects.filter(
                name__startswith=f"scheduled_task_{scheduled_task.id}_"
            )
            if existing_tasks.exists():
                logger.info(f"清理 {existing_tasks.count()} 个可能重复的任务")
                existing_tasks.delete()

            # 如果任务被禁用或状态不是激活，不创建Celery任务
            if not scheduled_task.is_enabled or scheduled_task.status != 'active':
                scheduled_task.celery_task_id = ''
                scheduled_task.save(update_fields=['celery_task_id'])
                logger.info(f"任务已禁用或非激活状态，跳过创建: {scheduled_task.name}")
                return None

            # 生成唯一的任务名称
            task_name = f"scheduled_task_{scheduled_task.id}_{int(timezone.now().timestamp())}"

            # 根据调度类型创建不同的调度配置
            periodic_task = None

            if scheduled_task.schedule_type == 'once':
                # 单次执行
                if scheduled_task.scheduled_date and scheduled_task.scheduled_time:
                    eta = datetime.combine(scheduled_task.scheduled_date, scheduled_task.scheduled_time)
                    eta = timezone.make_aware(eta) if timezone.is_naive(eta) else eta

                    # 如果执行时间已过，不创建任务
                    if eta <= timezone.now():
                        logger.warning(f"单次任务执行时间已过: {scheduled_task.name}")
                        return None

                    periodic_task = PeriodicTask.objects.create(
                        name=task_name,
                        task='test_manager.tasks.execute_scheduled_test_suite',
                        args=json.dumps([scheduled_task.id]),
                        one_off=True,
                        start_time=eta,
                        enabled=True,
                    )
                    logger.info(f"创建单次任务: {task_name}, 执行时间: {eta}")

            elif scheduled_task.schedule_type == 'daily':
                # 每日执行
                if scheduled_task.scheduled_time:
                    crontab, created = CrontabSchedule.objects.get_or_create(
                        minute=scheduled_task.scheduled_time.minute,
                        hour=scheduled_task.scheduled_time.hour,
                        day_of_week='*',
                        day_of_month='*',
                        month_of_year='*',
                        timezone=timezone.get_current_timezone()
                    )

                    periodic_task = PeriodicTask.objects.create(
                        name=task_name,
                        task='test_manager.tasks.execute_scheduled_test_suite',
                        args=json.dumps([scheduled_task.id]),
                        crontab=crontab,
                        enabled=True,
                    )
                    logger.info(f"创建每日任务: {task_name}, 时间: {scheduled_task.scheduled_time}")

            elif scheduled_task.schedule_type == 'weekly':
                # 每周执行
                if scheduled_task.weekday and scheduled_task.scheduled_time:
                    # Django的weekday: 0=Sunday, 1=Monday, ..., 6=Saturday
                    # 我们的weekday: 1=Monday, 2=Tuesday, ..., 7=Sunday
                    django_weekday = scheduled_task.weekday % 7

                    crontab, created = CrontabSchedule.objects.get_or_create(
                        minute=scheduled_task.scheduled_time.minute,
                        hour=scheduled_task.scheduled_time.hour,
                        day_of_week=str(django_weekday),
                        day_of_month='*',
                        month_of_year='*',
                        timezone=timezone.get_current_timezone()
                    )

                    periodic_task = PeriodicTask.objects.create(
                        name=task_name,
                        task='test_manager.tasks.execute_scheduled_test_suite',
                        args=json.dumps([scheduled_task.id]),
                        crontab=crontab,
                        enabled=True,
                    )
                    logger.info(
                        f"创建每周任务: {task_name}, 星期{scheduled_task.weekday}, 时间: {scheduled_task.scheduled_time}")

            elif scheduled_task.schedule_type == 'monthly':
                # 每月执行
                if scheduled_task.day_of_month and scheduled_task.scheduled_time:
                    crontab, created = CrontabSchedule.objects.get_or_create(
                        minute=scheduled_task.scheduled_time.minute,
                        hour=scheduled_task.scheduled_time.hour,
                        day_of_week='*',
                        day_of_month=str(scheduled_task.day_of_month),
                        month_of_year='*',
                        timezone=timezone.get_current_timezone()
                    )

                    periodic_task = PeriodicTask.objects.create(
                        name=task_name,
                        task='test_manager.tasks.execute_scheduled_test_suite',
                        args=json.dumps([scheduled_task.id]),
                        crontab=crontab,
                        enabled=True,
                    )
                    logger.info(
                        f"创建每月任务: {task_name}, 日期: {scheduled_task.day_of_month}, 时间: {scheduled_task.scheduled_time}")

            elif scheduled_task.schedule_type == 'cron':
                # Cron表达式
                if scheduled_task.cron_expression:
                    try:
                        # 解析cron表达式
                        parts = scheduled_task.cron_expression.split()
                        if len(parts) == 5:
                            minute, hour, day_of_month, month_of_year, day_of_week = parts

                            crontab, created = CrontabSchedule.objects.get_or_create(
                                minute=minute,
                                hour=hour,
                                day_of_week=day_of_week,
                                day_of_month=day_of_month,
                                month_of_year=month_of_year,
                                timezone=timezone.get_current_timezone()
                            )

                            periodic_task = PeriodicTask.objects.create(
                                name=task_name,
                                task='test_manager.tasks.execute_scheduled_test_suite',
                                args=json.dumps([scheduled_task.id]),
                                crontab=crontab,
                                enabled=True,
                            )
                            logger.info(f"创建Cron任务: {task_name}, 表达式: {scheduled_task.cron_expression}")
                        else:
                            logger.error(f"无效的Cron表达式: {scheduled_task.cron_expression}")
                            return None
                    except Exception as e:
                        logger.error(f"解析Cron表达式失败: {e}")
                        return None
            else:
                logger.error(f"不支持的调度类型: {scheduled_task.schedule_type}")
                return None

            if periodic_task:
                # 更新scheduled_task的celery_task_id
                scheduled_task.celery_task_id = task_name
                scheduled_task.save()

                logger.info(f"成功创建Celery定时任务: {task_name}")
                return periodic_task
            else:
                logger.error(f"创建Celery任务失败: {scheduled_task.name}")
                return None

        except Exception as e:
            logger.error(f"创建Celery定时任务失败: {e}")
            return None

    @staticmethod
    def delete_celery_task(scheduled_task):
        """删除Celery定时任务"""
        if scheduled_task.celery_task_id:
            try:
                periodic_task = PeriodicTask.objects.get(name=scheduled_task.celery_task_id)
                periodic_task.delete()
                logger.info(f"成功删除Celery定时任务: {scheduled_task.celery_task_id}")
            except PeriodicTask.DoesNotExist:
                logger.warning(f"Celery定时任务不存在: {scheduled_task.celery_task_id}")

            scheduled_task.celery_task_id = ''
            scheduled_task.save()

    @staticmethod
    def sync_all_tasks():
        """同步所有定时任务到Celery Beat"""
        logger.info("开始同步所有定时任务到Celery Beat")

        active_tasks = ScheduledTask.objects.filter(is_enabled=True, status='active')

        success_count = 0
        for task in active_tasks:
            try:
                result = TaskScheduler.create_or_update_celery_task(task)
                if result:
                    success_count += 1
                    task.update_next_run_time()
                    logger.info(f"同步任务成功: {task.name}")
                else:
                    logger.warning(f"同步任务失败: {task.name}")
            except Exception as e:
                logger.error(f"同步任务异常: {task.name}, 错误: {e}")

        logger.info(f"同步完成，成功: {success_count}/{active_tasks.count()}")
        return success_count

    @staticmethod
    def cleanup_orphaned_celery_tasks():
        """清理孤立的Celery任务"""
        logger.info("开始清理孤立的Celery任务")

        # 获取所有以scheduled_task_开头的Celery任务
        celery_tasks = PeriodicTask.objects.filter(name__startswith='scheduled_task_')

        # 获取所有有效的scheduled_task的celery_task_id
        valid_task_ids = set(
            ScheduledTask.objects.exclude(celery_task_id='').values_list('celery_task_id', flat=True)
        )

        # 删除孤立的任务
        orphaned_count = 0
        for celery_task in celery_tasks:
            if celery_task.name not in valid_task_ids:
                celery_task.delete()
                orphaned_count += 1
                logger.info(f"删除孤立任务: {celery_task.name}")

        logger.info(f"清理了 {orphaned_count} 个孤立的Celery任务")
        return orphaned_count

    @staticmethod
    def get_celery_beat_status():
        """获取Celery Beat状态"""
        try:
            from celery import current_app

            # 检查Beat调度器
            i = current_app.control.inspect()

            # 获取活动的任务
            active_tasks = i.active()
            scheduled_tasks = i.scheduled()

            # 获取数据库中的定时任务
            db_tasks = PeriodicTask.objects.filter(enabled=True).count()

            return {
                'status': 'ok',
                'active_workers': list(active_tasks.keys()) if active_tasks else [],
                'scheduled_tasks_count': len(scheduled_tasks) if scheduled_tasks else 0,
                'db_tasks_count': db_tasks,
                'message': 'Celery Beat状态正常'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Celery Beat状态检查失败: {str(e)}'
            }
