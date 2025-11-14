from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from .models import ScheduledTask
from .scheduler import TaskScheduler
import json


@login_required
def task_monitor(request):
    """任务监控页面"""
    return render(request, 'debug/task_monitor.html')


@login_required
def task_monitor_api(request):
    """任务监控API"""
    try:
        # 获取数据库中的任务
        db_tasks = ScheduledTask.objects.filter(is_enabled=True, status='active')

        # 获取Celery中的任务
        celery_tasks = PeriodicTask.objects.filter(enabled=True, name__startswith='scheduled_task_')

        # 获取Beat状态
        beat_status = TaskScheduler.get_celery_beat_status()

        # 构建任务列表
        tasks_data = []
        for task in db_tasks:
            tasks_data.append({
                'id': task.id,
                'name': task.name,
                'schedule_type': task.schedule_type,
                'schedule_type_display': task.get_schedule_type_display(),
                'next_run_time': task.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if task.next_run_time else None,
                'last_run_time': task.last_run_time.strftime('%Y-%m-%d %H:%M:%S') if task.last_run_time else None,
                'success_rate': task.success_rate,
                'celery_synced': bool(task.celery_task_id),
                'celery_task_id': task.celery_task_id,
            })

        return JsonResponse({
            'success': True,
            'db_tasks_count': db_tasks.count(),
            'celery_tasks_count': celery_tasks.count(),
            'beat_status': beat_status,
            'tasks': tasks_data,
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def sync_tasks_api(request):
    """同步所有任务API"""
    try:
        success_count = TaskScheduler.sync_all_tasks()
        return JsonResponse({
            'success': True,
            'message': f'成功同步 {success_count} 个任务'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'同步失败: {str(e)}'
        })


@login_required
@require_POST
def cleanup_tasks_api(request):
    """清理孤立任务API"""
    try:
        cleaned_count = TaskScheduler.cleanup_orphaned_celery_tasks()
        return JsonResponse({
            'success': True,
            'message': f'清理了 {cleaned_count} 个孤立任务'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'清理失败: {str(e)}'
        })


@login_required
@require_POST
def sync_single_task_api(request, task_id):
    """同步单个任务API"""
    try:
        task = get_object_or_404(ScheduledTask, id=task_id)
        result = TaskScheduler.create_or_update_celery_task(task)

        if result:
            task.update_next_run_time()
            return JsonResponse({
                'success': True,
                'message': f'任务 {task.name} 同步成功'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'任务 {task.name} 同步失败'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'同步失败: {str(e)}'
        })
