from django.urls import path
from . import views
from . import debug_views  # Import debug views

urlpatterns = [
    path('', views.test_list, name='test_list'),
    path('create/', views.test_create, name='test_create'),
    path('<int:pk>/', views.test_detail, name='test_detail'),
    path('<int:pk>/update/', views.test_update, name='test_update'),
    path('<int:pk>/delete/', views.test_delete, name='test_delete'),
    path('run/<int:pk>/', views.run_test, name='run_test'),
    path('results/<int:test_id>/', views.test_results, name='test_results'),
    path('scheduled-tasks/', views.scheduled_task_list, name='scheduled_task_list'),
    path('scheduled-tasks/create/', views.scheduled_task_create, name='scheduled_task_create'),
    path('scheduled-tasks/<int:pk>/', views.scheduled_task_detail, name='scheduled_task_detail'),
    path('scheduled-tasks/<int:pk>/update/', views.scheduled_task_update, name='scheduled_task_update'),
    path('scheduled-tasks/<int:pk>/delete/', views.scheduled_task_delete, name='scheduled_task_delete'),
    path('scheduled-tasks/<int:task_id>/run/', views.run_scheduled_task, name='run_scheduled_task'),

    # 调试相关URL
    path('debug/scheduled-tasks/<int:task_id>/force-cleanup/', debug_views.force_cleanup_task, name='debug_force_cleanup_task'),
]
