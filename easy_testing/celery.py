import os
from celery import Celery

# 设置默认的Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'easy_testing.settings')

app = Celery('easy_testing')

# 使用Django的设置文件配置Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现任务
app.autodiscover_tasks()

# 定时任务配置
app.conf.beat_schedule = {
    'update-scheduled-tasks-next-run-time': {
        'task': 'test_manager.tasks.update_scheduled_tasks_next_run_time',
        'schedule': 60.0,  # 每分钟执行一次
    },
    'cleanup-old-execution-logs': {
        'task': 'test_manager.tasks.cleanup_old_execution_logs',
        'schedule': 86400.0,  # 每天执行一次
    },
}

app.conf.timezone = 'Asia/Shanghai'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
