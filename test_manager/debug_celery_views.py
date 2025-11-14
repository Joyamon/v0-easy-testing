from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import traceback
import json

@login_required
@require_GET
def celery_status(request):
    """检查Celery状态"""
    status_info = {
        'celery_available': False,
        'workers': [],
        'registered_tasks': [],
        'broker_status': 'unknown',
        'errors': []
    }
    
    try:
        # 检查Celery是否可用
        from celery import current_app
        from django.conf import settings
        
        status_info['celery_available'] = True
        status_info['broker_url'] = getattr(settings, 'CELERY_BROKER_URL', 'Not configured')
        
        # 检查worker状态
        try:
            i = current_app.control.inspect()
            active_workers = i.active()
            
            if active_workers:
                status_info['workers'] = list(active_workers.keys())
                status_info['broker_status'] = 'connected'
                
                # 获取已注册的任务
                registered_tasks = i.registered()
                if registered_tasks:
                    all_tasks = set()
                    for worker, tasks in registered_tasks.items():
                        all_tasks.update(tasks)
                    status_info['registered_tasks'] = sorted(list(all_tasks))
            else:
                status_info['broker_status'] = 'no_workers'
                status_info['errors'].append('没有活动的Celery worker')
                
        except Exception as inspect_error:
            status_info['broker_status'] = 'error'
            status_info['errors'].append(f'无法检查worker状态: {str(inspect_error)}')
    
    except ImportError as import_error:
        status_info['errors'].append(f'Celery未安装或配置错误: {str(import_error)}')
    except Exception as e:
        status_info['errors'].append(f'检查Celery状态时发生错误: {str(e)}')
    
    # 检查我们的任务是否已注册
    our_tasks = [
        'test_manager.tasks.execute_scheduled_test_suite',
        'test_manager.tasks.send_task_notification_email',
        'test_manager.tasks.cleanup_old_execution_logs',
        'test_manager.tasks.update_scheduled_tasks_next_run_time',
        'test_manager.tasks.run_scheduled_task_now',
        'test_manager.tasks.check_celery_status',
    ]
    
    missing_tasks = []
    for task in our_tasks:
        if task not in status_info['registered_tasks']:
            missing_tasks.append(task)
    
    if missing_tasks:
        status_info['missing_tasks'] = missing_tasks
        status_info['errors'].append(f'以下任务未注册: {", ".join(missing_tasks)}')
    
    return JsonResponse(status_info, json_dumps_params={'indent': 2})


@login_required
@require_GET
def test_task_execution(request):
    """测试任务执行"""
    task_id = request.GET.get('task_id')
    
    if not task_id:
        return JsonResponse({
            'success': False,
            'message': '请提供task_id参数'
        })
    
    try:
        from .models import ScheduledTask
        from .tasks import execute_scheduled_test_suite
        
        # 获取任务
        try:
            task = ScheduledTask.objects.get(id=task_id, created_by=request.user)
        except ScheduledTask.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': f'定时任务不存在: ID={task_id}'
            })
        
        # 尝试异步执行
        try:
            result = execute_scheduled_test_suite.delay(int(task_id))
            return JsonResponse({
                'success': True,
                'message': f'任务已提交到Celery队列',
                'task_id': result.id,
                'scheduled_task_name': task.name
            })
        except Exception as async_error:
            # 尝试同步执行
            try:
                result = execute_scheduled_test_suite(int(task_id))
                return JsonResponse({
                    'success': True,
                    'message': f'任务同步执行完成',
                    'result': result,
                    'scheduled_task_name': task.name,
                    'execution_mode': 'sync'
                })
            except Exception as sync_error:
                return JsonResponse({
                    'success': False,
                    'message': f'任务执行失败',
                    'async_error': str(async_error),
                    'sync_error': str(sync_error),
                    'scheduled_task_name': task.name
                })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'测试任务执行时发生错误: {str(e)}',
            'error': traceback.format_exc()
        })


@login_required
def celery_debug_page(request):
    """Celery调试页面"""
    from .models import ScheduledTask
    
    # 获取用户的定时任务
    tasks = ScheduledTask.objects.filter(created_by=request.user)
    
    context = {
        'tasks': tasks,
    }
    
    return render(request, 'test_manager/debug/celery_debug.html', context)
