from django.core.management.base import BaseCommand
from test_manager.scheduler import TaskScheduler
from test_manager.models import ScheduledTask
from django_celery_beat.models import PeriodicTask


class Command(BaseCommand):
    help = '同步定时任务到Celery Beat'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='清理孤立的Celery任务',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制重新创建所有任务',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='显示当前状态',
        )

    def handle(self, *args, **options):
        if options['status']:
            self.show_status()
            return
            
        if options['cleanup']:
            self.stdout.write('清理孤立的Celery任务...')
            cleaned = TaskScheduler.cleanup_orphaned_celery_tasks()
            self.stdout.write(
                self.style.SUCCESS(f'清理了 {cleaned} 个孤立任务')
            )
        
        if options['force']:
            self.stdout.write('强制重新创建所有任务...')
            # 删除所有现有的Celery任务
            PeriodicTask.objects.filter(name__startswith='scheduled_task_').delete()
            # 清空所有任务的celery_task_id
            ScheduledTask.objects.update(celery_task_id='')
        
        self.stdout.write('开始同步定时任务...')
        success_count = TaskScheduler.sync_all_tasks()
        
        self.stdout.write(
            self.style.SUCCESS(f'定时任务同步完成，成功同步 {success_count} 个任务')
        )
        
        # 显示最终状态
        self.show_status()
    
    def show_status(self):
        """显示当前状态"""
        self.stdout.write('\n=== 定时任务状态 ===')
        
        # 数据库中的定时任务
        db_tasks = ScheduledTask.objects.filter(is_enabled=True, status='active')
        self.stdout.write(f'数据库中的活动任务: {db_tasks.count()}')
        
        # Celery中的定时任务
        celery_tasks = PeriodicTask.objects.filter(enabled=True, name__startswith='scheduled_task_')
        self.stdout.write(f'Celery中的定时任务: {celery_tasks.count()}')
        
        # 检查Beat状态
        beat_status = TaskScheduler.get_celery_beat_status()
        self.stdout.write(f'Celery Beat状态: {beat_status["status"]}')
        if beat_status['status'] == 'error':
            self.stdout.write(
                self.style.ERROR(f'错误: {beat_status["message"]}')
            )
        
        # 显示具体任务
        self.stdout.write('\n=== 任务详情 ===')
        for task in db_tasks:
            celery_status = "已同步" if task.celery_task_id else "未同步"
            next_run = task.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if task.next_run_time else "未设置"
            self.stdout.write(f'- {task.name}: {celery_status}, 下次执行: {next_run}')
