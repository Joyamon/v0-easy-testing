"""
URL configuration for EasyTesting project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from test_manager import views, debug_views
from test_manager import auth_views as custom_auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('test_manager.api.urls')),

    # 主页和仪表盘
    path('dashboard/', views.dashboard, name='dashboard'),

    # 项目相关
    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/edit/', views.project_edit, name='project_edit'),
    path('projects/<int:pk>/delete/', views.project_delete, name='project_delete'),

    # 环境相关
    path('environments/', views.environment_list, name='environment_list'),
    path('environments/create/', views.environment_create, name='environment_create'),
    path('environments/<int:pk>/', views.environment_detail, name='environment_detail'),
    path('environments/<int:pk>/edit/', views.environment_edit, name='environment_edit'),
    path('environments/<int:pk>/delete/', views.environment_delete, name='environment_delete'),

    # 测试用例相关
    path('test-cases/', views.test_case_list, name='test_case_list'),
    path('test-cases/create/', views.test_case_create, name='test_case_create'),
    path('test-cases/<int:pk>/', views.test_case_detail, name='test_case_detail'),
    path('test-cases/<int:pk>/edit/', views.test_case_edit, name='test_case_edit'),
    path('test-cases/<int:pk>/run/', views.test_case_run, name='test_case_run'),

    # 测试套件相关
    path('test-suites/', views.test_suite_list, name='test_suite_list'),
    path('test-suites/create/', views.test_suite_create, name='test_suite_create'),
    path('test-suites/<int:pk>/', views.test_suite_detail, name='test_suite_detail'),
    path('test-suites/<int:pk>/edit/', views.test_suite_edit, name='test_suite_edit'),
    path('test-suites/<int:pk>/run/', views.test_suite_run, name='test_suite_run'),

    # 测试运行相关
    path('test-runs/', views.test_run_list, name='test_run_list'),
    path('test-runs/<int:pk>/', views.test_run_detail, name='test_run_detail'),
    path('test-runs/<int:pk>/delete/', views.test_run_delete, name='test_run_delete'),

    # 认证相关
    path('', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', custom_auth_views.register_view, name='register'),

    # 密码重置
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='auth/password_reset_form.html',
             email_template_name='auth/password_reset_email.html',
             subject_template_name='auth/password_reset_subject.txt'
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='auth/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='auth/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='auth/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    # 密码修改
    path('password-change/',
         auth_views.PasswordChangeView.as_view(
             template_name='auth/password_change_form.html'
         ),
         name='password_change'),
    path('password-change/done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='auth/password_change_done.html'
         ),
         name='password_change_done'),

    # 用户个人资料
    path('profile/', custom_auth_views.profile_view, name='profile'),
    path('profile/edit/', custom_auth_views.edit_profile_view, name='edit_profile'),

    # 邮件配置
    path('email-config/', views.email_config_list, name='email_config_list'),
    path('email-config/create/', views.email_config_create, name='email_config_create'),
    path('email-config/<int:pk>/edit/', views.email_config_edit, name='email_config_edit'),
    path('email-config/<int:pk>/delete/', views.email_config_delete, name='email_config_delete'),
    path('email-config/<int:pk>/test/', views.email_config_test, name='email_config_test'),
    path('email-config/<int:pk>/activate/', views.email_config_activate, name='email_config_activate'),

    path('test-case-groups/', views.test_case_group_list, name='test_case_group_list'),
    path('test-case-groups/create/', views.test_case_group_create, name='test_case_group_create'),
    path('test-case-groups/<int:pk>/edit/', views.test_case_group_edit, name='test_case_group_edit'),
    path('test-case-groups/<int:pk>/delete/', views.test_case_group_delete, name='test_case_group_delete'),

    # 测试套件分组
    path('test-suite-groups/', views.test_suite_group_list, name='test_suite_group_list'),
    path('test-suite-groups/create/', views.test_suite_group_create, name='test_suite_group_create'),
    path('test-suite-groups/<int:pk>/edit/', views.test_suite_group_edit, name='test_suite_group_edit'),
    path('test-suite-groups/<int:pk>/delete/', views.test_suite_group_delete, name='test_suite_group_delete'),

    # 测试报告
    path('reports/', views.test_report_list, name='test_report_list'),
    path('reports/<int:pk>/', views.test_report_detail, name='test_report_detail'),
    path('reports/<int:pk>/delete/', views.test_report_delete, name='test_report_delete'),
    path('test-runs/<int:pk>/generate-report/', views.generate_test_run_report, name='generate_test_run_report'),
    path('test-suite-runs/<int:pk>/generate-report/', views.generate_test_suite_run_report,
         name='generate_test_suite_run_report'),
    # 生成测试数据
    path('mock-data/', views.mock_data_generator, name='mock-data'),
    path('mock-data-list/', views.mock_data_list, name='mock-data-list'),
    path('mock-data/delete/<int:pk>/', views.mock_data_delete, name='mock-data-delete'),
    path('mock-data/export/<int:pk>/', views.mock_data_export, name='mock-data-export'),

# 定时任务相关URL
    path('scheduled-tasks/', views.scheduled_task_list, name='scheduled_task_list'),
    path('scheduled-tasks/create/', views.scheduled_task_create, name='scheduled_task_create'),
    path('scheduled-tasks/<int:pk>/', views.scheduled_task_detail, name='scheduled_task_detail'),
    path('scheduled-tasks/<int:pk>/edit/', views.scheduled_task_edit, name='scheduled_task_edit'),
    path('scheduled-tasks/<int:pk>/delete/', views.scheduled_task_delete, name='scheduled_task_delete'),
    path('scheduled-tasks/<int:pk>/toggle-status/', views.scheduled_task_toggle_status, name='scheduled_task_toggle_status'),
    path('scheduled-tasks/<int:pk>/run-now/', views.scheduled_task_run_now, name='scheduled_task_run_now'),
    path('task-execution-logs/<int:pk>/', views.task_execution_log_detail, name='task_execution_log_detail'),
    # 调试相关URL
    path('debug/task-monitor/', debug_views.task_monitor, name='task_monitor'),
    path('debug/task-monitor-api/', debug_views.task_monitor_api, name='task_monitor_api'),
    path('debug/sync-tasks/', debug_views.sync_tasks_api, name='sync_tasks_api'),
    path('debug/cleanup-tasks/', debug_views.cleanup_tasks_api, name='cleanup_tasks_api'),
    path('debug/sync-task/<int:task_id>/', debug_views.sync_single_task_api, name='sync_single_task_api'),

    path('tools-list/', views.tools, name='tools-list')

]
