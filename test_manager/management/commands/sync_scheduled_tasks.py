from django.core.management.base import BaseCommand
from django.utils import timezone
from test_manager.scheduler import TaskScheduler
from test_manager.models import ScheduledTask
from django_celery_beat.models import PeriodicTask
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '清理孤立的Celery Beat任务'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只显示将要删除的任务，不实际删除',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制删除所有孤立任务',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        self.stdout.write(
            self.style.SUCCESS(f'开始清理孤立的Celery Beat任务 (dry_run={dry_run})')
        )

        try:
            # 获取所有以scheduled_task_开头的Celery任务
            celery_tasks = PeriodicTask.objects.filter(name__startswith='scheduled_task_')
            self.stdout.write(f'找到 {celery_tasks.count()} 个相关的Celery Beat任务')

            # 获取所有有效的scheduled_task的celery_task_id
            valid_task_ids = set(
                ScheduledTask.objects.exclude(celery_task_id='').values_list('celery_task_id', flat=True)
            )
            self.stdout.write(f'找到 {len(valid_task_ids)} 个有效的任务ID')

            # 找出孤立的任务
            orphaned_tasks = []
            for celery_task in celery_tasks:
                if celery_task.name not in valid_task_ids:
                    orphaned_tasks.append(celery_task)

            self.stdout.write(f'找到 {len(orphaned_tasks)} 个孤立的Celery Beat任务')

            if not orphaned_tasks:
                self.stdout.write(self.style.SUCCESS('没有找到孤立的任务'))
                return

            # 显示孤立的任务
            for task in orphaned_tasks:
                self.stdout.write(f'  - {task.name} (enabled={task.enabled})')

            if dry_run:
                self.stdout.write(self.style.WARNING('这是预览模式，没有实际删除任务'))
                return

            if not force:
                confirm = input(f'确定要删除这 {len(orphaned_tasks)} 个孤立任务吗？ (y/N): ')
                if confirm.lower() != 'y':
                    self.stdout.write('操作已取消')
                    return

            # 删除孤立的任务
            deleted_count = 0
            for task in orphaned_tasks:
                try:
                    task.delete()
                    deleted_count += 1
                    self.stdout.write(f'已删除: {task.name}')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'删除失败 {task.name}: {str(e)}')
                    )

            self.stdout.write(
                self.style.SUCCESS(f'清理完成，删除了 {deleted_count} 个孤立任务')
            )

            # 验证清理结果
            remaining_orphaned = TaskScheduler.cleanup_orphaned_celery_tasks()
            if remaining_orphaned > 0:
                self.stdout.write(
                    self.style.WARNING(f'仍有 {remaining_orphaned} 个孤立任务')
                )
            else:
                self.stdout.write(self.style.SUCCESS('所有孤立任务已清理完成'))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'清理过程中发生错误: {str(e)}')
            )
            logger.error(f"清理命令执行失败: {str(e)}")
