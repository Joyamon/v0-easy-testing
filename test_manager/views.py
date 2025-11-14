import datetime
import json
import ast
import traceback
import pytz
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_POST,require_GET

from .async_executor import execute_test_suite_async, execute_test_case_async
from .gen_data import auto_gen_data
from .models import (
    Project, Environment, TestCase, TestSuite,
    TestSuiteCase, TestRun, TestResult, EmailConfig, TestSuiteGroup, TestCaseGroup, TestReport, TestSuiteRun, MockData,
    TaskExecutionLog, ScheduledTask
)
from .forms import (
    ProjectForm, EnvironmentForm, TestCaseForm, TestSuiteForm,
    TestRunForm, EmailConfigForm, TestEmailForm, TestSuiteGroupForm, TestCaseGroupForm, GenerateReportForm,
    MockDataForm, ScheduledTaskForm
)
from .httprunner_executor import execute_test_case, execute_test_suite
from .scheduler import TaskScheduler
from .tasks import execute_scheduled_test_suite

def paginate_queryset(request, queryset, per_page=10):
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, per_page)

    try:
        paginated_queryset = paginator.page(page)
    except PageNotAnInteger:
        paginated_queryset = paginator.page(1)
    except EmptyPage:
        paginated_queryset = paginator.page(paginator.num_pages)

    return paginated_queryset


@login_required
def dashboard(request):
    # 统计数量
    projects_count = Project.objects.count()
    test_cases_count = TestCase.objects.count()
    test_suites_count = TestSuite.objects.count()
    test_runs_count = TestRun.objects.count()
    report_count = TestReport.objects.count()

    # 最近测试记录
    all_test_runs = TestRun.objects.order_by('-created_at')
    recent_test_runs = paginate_queryset(request, all_test_runs, 5)

    tz = pytz.timezone(settings.TIME_ZONE)

    # 获取时间序列数据
    daily_data = generate_time_series_data(mode='daily', tz=tz)
    monthly_data = generate_time_series_data(mode='monthly', tz=tz)
    yearly_data = generate_time_series_data(mode='yearly', tz=tz)

    # 测试运行状态统计
    test_run_stats = {
        'total': test_runs_count,
        'passed': TestRun.objects.filter(status='completed').count(),
        'failed': TestRun.objects.filter(status='failed').count(),
        'pending': TestRun.objects.filter(status='pending').count(),
        'running': TestRun.objects.filter(status='running').count(),
    }

    # 测试结果状态统计
    test_result_stats = {
        'total': TestResult.objects.count(),
        'passed': TestResult.objects.filter(status='passed').count(),
        'failed': TestResult.objects.filter(status='failed').count(),
        'error': TestResult.objects.filter(status='error').count(),
        'skipped': TestResult.objects.filter(status='skipped').count(),
    }

    # 最近活动列表
    recent_activities = []
    activities = TestRun.objects.all().order_by('-created_at')
    for activity in activities:
        action = activity.name.split(': ')[0]
        timestamp = activity.created_at
        description = f"{activity.name} 执行结果为： {activity.status}"
        recent_activities.append({
            'action': action,
            'timestamp': timestamp,
            'description': description
        })

    context = {
        'projects_count': projects_count,
        'test_cases_count': test_cases_count,
        'test_suites_count': test_suites_count,
        'test_runs_count': test_runs_count,
        'report_count': report_count,
        'recent_test_runs': recent_test_runs,
        'test_run_stats': test_run_stats,
        'test_result_stats': test_result_stats,
        'recent_activities': recent_activities,
        'daily_data_json': json.dumps(daily_data),
        'monthly_data_json': json.dumps(monthly_data),
        'yearly_data_json': json.dumps(yearly_data),
    }

    return render(request, 'test_manager/dashboard.html', context)

def generate_time_series_data(mode, tz):
    now = timezone.now().astimezone(tz)


    if mode == 'daily':
        count = 7
        start_date = now - timedelta(days=count - 1)
        end_date = now
        period = 'day'

    elif mode == 'monthly':
        start_date = now.replace(month=1, day=1)
        end_date = now.replace(month=12, day=31)
        count = 12
        period = 'month'

    elif mode == 'yearly':
        current_year = now.year
        start_date = now.replace(year=current_year - 4, month=1, day=1)
        end_date = now.replace(month=12, day=31)
        count = 5
        period = 'year'

    else:
        raise ValueError("Invalid mode")

    labels = generate_date_labels(start_date, period, count)
    data = {
        'projects': get_model_timeseries(Project, start_date, count, period, tz),
        'test_cases': get_model_timeseries(TestCase, start_date, count, period, tz),
        'test_suites': get_model_timeseries(TestSuite, start_date, count, period, tz),
        'test_runs': get_model_timeseries(TestRun, start_date, count, period, tz),
        'test_reports': get_model_timeseries(TestReport, start_date, count, period, tz),
    }
    return {'labels': labels, 'datasets': data}


def generate_date_labels(start_date, period, count):
    labels = []
    current = start_date

    if period == 'day':
        for _ in range(count):
            labels.append(current.strftime('%b %d').lstrip('0').replace(' 0', ' '))
            current += timedelta(days=1)

    elif period == 'month':
        for i in range(count):
            labels.append(f'{i+1}月')

    elif period == 'year':
        for i in range(count):
            labels.append(str(start_date.year + i))

    return labels


def get_model_timeseries(model, start_date, count, period, tz):
    now = timezone.now().astimezone(tz)
    end_date = now

    utc_start = start_date.astimezone(pytz.utc)
    utc_end = end_date.astimezone(pytz.utc)

    results = (
        model.objects
        .filter(created_at__range=(utc_start, utc_end))
        .values_list('created_at', flat=True)
    )

    counts = [0] * count

    for dt in results:
        local_dt = dt.astimezone(tz)

        if period == 'day':
            diff = (local_dt.date() - start_date.date()).days
        elif period == 'month':
            diff = local_dt.month - 1
        elif period == 'year':
            diff = local_dt.year - start_date.year
        else:
            continue

        if 0 <= diff < count:
            counts[diff] += 1

    return counts


# Project views
@login_required
def project_list(request):
    all_projects = Project.objects.all().order_by('-created_at')

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10

    projects = paginate_queryset(request, all_projects, per_page)

    return render(request, 'test_manager/project_list.html', {
        'projects': projects,
        'per_page': per_page
    })


@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            messages.success(request, '项目创建成功')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm()

    return render(request, 'test_manager/project_form.html', {'form': form, 'title': '新增项目'})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 5)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 5

    # 分页获取环境、测试用例、测试套件和测试运行
    all_environments = Environment.objects.filter(project=project)
    all_test_cases = TestCase.objects.filter(project=project)
    all_test_suites = TestSuite.objects.filter(project=project)
    all_test_runs = TestRun.objects.filter(project=project).order_by('-created_at')

    environments = paginate_queryset(request, all_environments, per_page)
    test_cases = paginate_queryset(request, all_test_cases, per_page)
    test_suites = paginate_queryset(request, all_test_suites, per_page)
    test_runs = paginate_queryset(request, all_test_runs, per_page)

    context = {
        'project': project,
        'environments': environments,
        'test_cases': test_cases,
        'test_suites': test_suites,
        'test_runs': test_runs,
        'per_page': per_page,
        'all_environments_count': all_environments.count(),
        'all_test_cases_count': all_test_cases.count(),
        'all_test_suites_count': all_test_suites.count(),
        'all_test_runs_count': all_test_runs.count(),
    }

    return render(request, 'test_manager/project_detail.html', context)


@login_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, '项目更新成功')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)

    return render(request, 'test_manager/project_form.html', {'form': form, 'title': '编辑项目'})


@login_required
def project_delete(request, pk):
    # 删除项目时，检查该项目是否存在关联的测试用例、测试套件或测试运行
    project = get_object_or_404(Project, pk=pk)
    if project.test_runs.exists() or project.test_suites.exists() or project.test_cases.exists():
        messages.warning(request, '无法删除具有关联测试用例、测试套件或测试运行的项目')
        return redirect('project_list')
    if request.method == 'POST':
        project.delete()
        messages.success(request, '项目删除成功')
        return redirect('project_list')

    return render(request, 'test_manager/test_project_confirm_delete.html', {'project': project})


# Environment views
@login_required
def environment_list(request):
    project_id = request.GET.get('project')

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10

    if project_id:
        all_environments = Environment.objects.filter(project_id=project_id).order_by('-created_at')
        project = get_object_or_404(Project, pk=project_id)
        environments = paginate_queryset(request, all_environments, per_page)
        context = {
            'environments': environments,
            'project': project,
            'per_page': per_page,
            'total_count': all_environments.count()
        }
    else:
        all_environments = Environment.objects.all().order_by('-created_at')
        environments = paginate_queryset(request, all_environments, per_page)
        context = {
            'environments': environments,
            'per_page': per_page,
            'total_count': all_environments.count()
        }

    return render(request, 'test_manager/environment_list.html', context)


@login_required
def environment_create(request):
    project_id = request.GET.get('project')

    if request.method == 'POST':
        form = EnvironmentForm(request.POST)
        if form.is_valid():
            environment = form.save()
            messages.success(request, '新增环境成功')
            return redirect('environment_detail', pk=environment.pk)
    else:
        initial = {}
        if project_id:
            initial['project'] = project_id
        form = EnvironmentForm(initial=initial)

    return render(request, 'test_manager/environment_form.html', {'form': form, 'title': '新增环境'})


@login_required
def environment_detail(request, pk):
    environment = get_object_or_404(Environment, pk=pk)

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 5)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 5

    # 分页获取测试运行
    all_test_runs = environment.test_runs.all().order_by('-created_at')
    test_runs = paginate_queryset(request, all_test_runs, per_page)

    context = {
        'environment': environment,
        'test_runs': test_runs,
        'per_page': per_page,
        'total_test_runs': all_test_runs.count()
    }

    return render(request, 'test_manager/environment_detail.html', context)


@login_required
def environment_edit(request, pk):
    environment = get_object_or_404(Environment, pk=pk)

    if request.method == 'POST':
        form = EnvironmentForm(request.POST, instance=environment)
        if form.is_valid():
            form.save()
            messages.success(request, '编辑环境成功')
            return redirect('environment_detail', pk=environment.pk)
    else:
        form = EnvironmentForm(instance=environment)

    return render(request, 'test_manager/environment_form.html', {'form': form, 'title': '编辑环境'})


@login_required
def environment_delete(request, pk):
    # 删除环境时，检查该环境是否存在关联的测试运行
    environment = get_object_or_404(Environment, pk=pk)
    if environment.test_runs.exists():
        messages.warning(request, '不能删除关联测试运行的环境')
        return redirect('environment_list')
    if request.method == 'POST':
        environment.delete()
        messages.success(request, '环境删除成功')
        return redirect('environment_list')

    return render(request, 'test_manager/test_environment_confirm_delete.html', {'environment': environment})


# Test Case views
@login_required
def test_case_list(request):
    project_id = request.GET.get('project')
    group_id = request.GET.get('group')
    search_query = request.GET.get('search', '')

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10

    if project_id:
        project = get_object_or_404(Project, pk=project_id)

        # 构建查询条件
        query = Q(project=project)

        # 如果指定了分组，则只显示该分组下的测试用例
        if group_id:
            group = get_object_or_404(TestCaseGroup, pk=group_id)
            query &= Q(group=group)

            # 获取当前分组的所有子分组
            child_groups = TestCaseGroup.objects.filter(project=project, parent=group)
        else:
            # 获取项目的所有顶级分组
            child_groups = TestCaseGroup.objects.filter(project=project, parent=None)

        # 如果有搜索查询，添加搜索条件
        if search_query:
            query &= (Q(name__icontains=search_query) |
                      Q(description__icontains=search_query) |
                      Q(request_url__icontains=search_query))

        all_test_cases = TestCase.objects.filter(query).order_by('-created_at')
        test_cases = paginate_queryset(request, all_test_cases, per_page)

        context = {
            'test_cases': test_cases,
            'project': project,
            'current_group': group if group_id else None,
            'child_groups': child_groups,
            'per_page': per_page,
            'total_count': all_test_cases.count(),
            'search_query': search_query
        }
    else:
        # 构建查询条件
        query = Q()

        # 如果有搜索查询，添加搜索条件
        if search_query:
            query &= (Q(name__icontains=search_query) |
                      Q(description__icontains=search_query) |
                      Q(request_url__icontains=search_query))

        all_test_cases = TestCase.objects.filter(query).order_by('-created_at')
        test_cases = paginate_queryset(request, all_test_cases, per_page)

        context = {
            'test_cases': test_cases,
            'per_page': per_page,
            'total_count': all_test_cases.count(),
            'search_query': search_query
        }

    return render(request, 'test_manager/test_case_list.html', context)


@login_required
def test_case_create(request):
    project_id = request.GET.get('project')

    if request.method == 'POST':
        form = TestCaseForm(request.POST)
        if form.is_valid():
            test_case = form.save(commit=False)
            test_case.created_by = request.user
            test_case.save()
            messages.success(request, '测试用例新增成功')
            return redirect('test_case_detail', pk=test_case.pk)
    else:
        initial = {}
        if project_id:
            initial['project'] = project_id
        form = TestCaseForm(initial=initial)

    return render(request, 'test_manager/test_case_form.html', {'form': form, 'title': '新增测试用例'})


@login_required
def test_case_detail(request, pk):
    test_case = get_object_or_404(TestCase, pk=pk)

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10

    # 分页获取测试结果
    all_test_results = TestResult.objects.filter(test_case=test_case).order_by('-created_at')
    test_results = paginate_queryset(request, all_test_results, per_page)

    context = {
        'test_case': test_case,
        'test_results': test_results,
        'per_page': per_page,
        'total_results': all_test_results.count()
    }

    return render(request, 'test_manager/test_case_detail.html', context)


@login_required
def test_case_edit(request, pk):
    test_case = get_object_or_404(TestCase, pk=pk)

    if request.method == 'POST':
        form = TestCaseForm(request.POST, instance=test_case)
        if form.is_valid():
            form.save()
            messages.success(request, '测试用例更新成功')
            return redirect('test_case_detail', pk=test_case.pk)
    else:
        form = TestCaseForm(instance=test_case)

    return render(request, 'test_manager/test_case_form.html', {'form': form, 'title': '编辑测试用例'})


@login_required
def test_case_run(request, pk):
    test_case = get_object_or_404(TestCase, pk=pk)

    if request.method == 'POST':
        environment_id = request.POST.get('environment')
        if not environment_id:
            messages.error(request, '请先选择环境')
            return redirect('test_case_detail', pk=test_case.pk)

        environment = get_object_or_404(Environment, pk=environment_id)

        # Create a test run
        test_run = TestRun.objects.create(
            name=f"Single run: {test_case.name}",
            project=test_case.project,
            environment=environment,
            status='running',
            start_time=timezone.now(),
            created_by=request.user
        )

        # 异步执行测试用例
        execute_test_case_async(
            test_case=test_case,
            environment=environment,
            test_run=test_run,
            user=request.user,
            execute_test_case_func=execute_test_case
        )

        messages.success(
            request,
            f'测试用例执行已开始。您可以在测试运行详情页中查看结果'
        )
        return redirect('test_run_detail', pk=test_run.pk)

    environments = Environment.objects.filter(project=test_case.project)
    return render(request, 'test_manager/test_case_run.html', {'test_case': test_case, 'environments': environments})


# Test Suite views
@login_required
def test_suite_list(request):
    project_id = request.GET.get('project')
    group_id = request.GET.get('group')
    search_query = request.GET.get('search', '')

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10

    # 初始化查询条件
    query = Q()

    if project_id:
        project = get_object_or_404(Project, pk=project_id)
        # 添加项目条件
        query &= Q(project=project)

        # 如果指定了分组，则只显示该分组下的测试套件
        if group_id:
            group = get_object_or_404(TestSuiteGroup, pk=group_id)
            query &= Q(group=group)

            # 获取当前分组的所有子分组
            child_groups = TestSuiteGroup.objects.filter(project=project, parent=group)
        else:
            # 获取项目的所有顶级分组
            child_groups = TestSuiteGroup.objects.filter(project=project, parent=None)

        # 如果有搜索查询，添加搜索条件
        if search_query:
            query &= (Q(name__icontains=search_query) |
                      Q(description__icontains=search_query))

        # 应用查询条件
        all_test_suites = TestSuite.objects.filter(query).order_by('-created_at')
        test_suites = paginate_queryset(request, all_test_suites, per_page)

        context = {
            'test_suites': test_suites,
            'project': project,
            'current_group': group if group_id else None,
            'child_groups': child_groups,
            'per_page': per_page,
            'total_count': all_test_suites.count(),
            'search_query': search_query
        }
    else:
        # 如果有搜索查询，添加搜索条件
        if search_query:
            query &= (Q(name__icontains=search_query) |
                      Q(description__icontains=search_query))

        all_test_suites = TestSuite.objects.filter(query).order_by('-created_at')
        test_suites = paginate_queryset(request, all_test_suites, per_page)

        context = {
            'test_suites': test_suites,
            'per_page': per_page,
            'total_count': all_test_suites.count(),
            'search_query': search_query
        }

    return render(request, 'test_manager/test_suite_list.html', context)


@login_required
def test_suite_create(request):
    project_id = request.GET.get('project')

    if request.method == 'POST':
        form = TestSuiteForm(request.POST)
        if form.is_valid():
            test_suite = form.save(commit=False)
            test_suite.created_by = request.user
            test_suite.save()
            messages.success(request, '测试套件创建成功')
            return redirect('test_suite_detail', pk=test_suite.pk)
    else:
        initial = {}
        if project_id:
            initial['project'] = project_id
        form = TestSuiteForm(initial=initial)

    return render(request, 'test_manager/test_suite_form.html', {'form': form, 'title': '新增测试套件'})


@login_required
def test_suite_detail(request, pk):
    test_suite = get_object_or_404(TestSuite, pk=pk)

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10

    # 分页获取测试用例和测试运行
    all_test_suite_cases = TestSuiteCase.objects.filter(test_suite=test_suite).order_by('order')
    all_test_runs = TestRun.objects.filter(test_suite=test_suite).order_by('-created_at')

    test_suite_cases = paginate_queryset(request, all_test_suite_cases, per_page)
    test_runs = paginate_queryset(request, all_test_runs, per_page)

    # 获取项目中的所有测试用例，而不仅仅是未添加到套件的测试用例
    project_test_cases = TestCase.objects.filter(project=test_suite.project)

    # 获取项目中的所有测试用例分组
    test_case_groups = TestCaseGroup.objects.filter(project=test_suite.project)

    # 获取每个分组下的测试用例
    grouped_test_cases = {}
    for group in test_case_groups:
        group_test_cases = TestCase.objects.filter(project=test_suite.project, group=group)
        if group_test_cases.exists():
            grouped_test_cases[group.id] = {
                'group': group,
                'test_cases': group_test_cases
            }

    # 获取未分组的测试用例
    ungrouped_test_cases = TestCase.objects.filter(project=test_suite.project, group__isnull=True)

    # 获取已添加到测试套件的测试用例ID列表
    added_test_case_ids = TestSuiteCase.objects.filter(test_suite=test_suite).values_list('test_case_id', flat=True)

    # 获取项目的所有环境
    environments = Environment.objects.filter(project=test_suite.project)

    context = {
        'test_suite': test_suite,
        'test_suite_cases': test_suite_cases,
        'test_runs': test_runs,
        'project_test_cases': project_test_cases,
        'grouped_test_cases': grouped_test_cases,
        'ungrouped_test_cases': ungrouped_test_cases,
        'added_test_case_ids': list(added_test_case_ids),
        'environments': environments,
        'per_page': per_page,
        'total_cases': all_test_suite_cases.count(),
        'total_runs': all_test_runs.count()
    }

    return render(request, 'test_manager/test_suite_detail.html', context)


@login_required
def test_suite_edit(request, pk):
    test_suite = get_object_or_404(TestSuite, pk=pk)

    if request.method == 'POST':
        form = TestSuiteForm(request.POST, instance=test_suite)
        if form.is_valid():
            form.save()
            messages.success(request, '更新测试套件成功')
            return redirect('test_suite_detail', pk=test_suite.pk)
    else:
        form = TestSuiteForm(instance=test_suite)

    return render(request, 'test_manager/test_suite_form.html', {'form': form, 'title': '编辑测试套件'})


@login_required
def test_suite_run(request, pk):
    """
    异步执行测试套件
    """
    test_suite = get_object_or_404(TestSuite, pk=pk)

    if request.method == 'POST':
        environment_id = request.POST.get('environment')
        if not environment_id:
            messages.error(request, '请先选择一个环境')
            return redirect('test_suite_detail', pk=test_suite.pk)

        environment = get_object_or_404(Environment, pk=environment_id)

        # 获取每个测试用例的环境设置
        case_environments = {}
        for key, value in request.POST.items():
            if key.startswith('case_environment_') and value:
                case_id = key.replace('case_environment_', '')
                case_environments[int(case_id)] = int(value)

        # 创建测试运行记录
        test_run = TestRun.objects.create(
            name=request.POST.get('name', f"Suite run: {test_suite.name}"),
            project=test_suite.project,
            test_suite=test_suite,
            environment=environment,
            status='running',  # 初始状态为运行中
            start_time=timezone.now(),
            created_by=request.user
        )

        # 异步执行测试套件
        execute_test_suite_async(
            test_suite=test_suite,
            environment=environment,
            case_environments=case_environments,
            test_run=test_run,
            user=request.user,
            execute_test_suite_func=execute_test_suite
        )

        messages.success(
            request,
            f'测试套件已开始执行。您可以在测试运行详情页中查看结果'
        )
        return redirect('test_run_detail', pk=test_run.pk)

    environments = Environment.objects.filter(project=test_suite.project)
    test_suite_cases = TestSuiteCase.objects.filter(test_suite=test_suite).order_by('order')

    return render(request, 'test_manager/test_suite_run.html', {
        'test_suite': test_suite,
        'environments': environments,
        'test_suite_cases': test_suite_cases
    })


# Test Run views
@login_required
def test_run_list(request):
    project_id = request.GET.get('project')

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10

    if project_id:
        all_test_runs = TestRun.objects.filter(project_id=project_id).order_by('-created_at')
        project = get_object_or_404(Project, pk=project_id)
        test_runs = paginate_queryset(request, all_test_runs, per_page)
        context = {
            'test_runs': test_runs,
            'project': project,
            'per_page': per_page,
            'total_count': all_test_runs.count()

        }
    else:
        all_test_runs = TestRun.objects.all().order_by('-created_at')
        test_runs = paginate_queryset(request, all_test_runs, per_page)
        context = {
            'test_runs': test_runs,
            'per_page': per_page,
            'total_count': all_test_runs.count()
        }

    return render(request, 'test_manager/test_run_list.html', context)


@login_required
def test_run_detail(request, pk):
    test_run = get_object_or_404(TestRun, pk=pk)

    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 10)
    status = request.GET.get('status', '')
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10

    # 分页获取测试结果
    if status:
        all_test_results = TestResult.objects.filter(test_run=test_run, status=status)
    else:
        all_test_results = TestResult.objects.filter(test_run=test_run)
    test_results = paginate_queryset(request, all_test_results, per_page)

    # Calculate statistics
    total_tests = all_test_results.count()
    passed_tests = all_test_results.filter(status='passed').count()
    failed_tests = all_test_results.filter(status='failed').count()
    error_tests = all_test_results.filter(status='error').count()
    skipped_tests = all_test_results.filter(status='skipped').count()

    context = {
        'test_run': test_run,
        'test_results': test_results,
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'failed_tests': failed_tests,
        'error_tests': error_tests,
        'skipped_tests': skipped_tests,
        'per_page': per_page,
        'total_results': total_tests
    }

    return render(request, 'test_manager/test_run_detail.html', context)


@login_required
def test_run_delete(request, pk):
    test_run = get_object_or_404(TestRun, pk=pk)
    if request.method == 'POST':
        test_run.delete()
        messages.success(request, '测试运行删除成功')
        return redirect('test_run_list')
    return render(request, 'test_manager/test_run_confirm_delete.html', {'test_run': test_run})


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse


def is_admin(request, user):
    """检查用户是否是管理员"""
    if user.is_superuser:
        return user.is_superuser
    else:
        messages.error(request, '您不是管理员，无法访问此页面。')
    # return user.is_superuser


@login_required
# @user_passes_test(is_admin)
def email_config_list(request):
    """邮件配置列表视图"""
    configs = EmailConfig.objects.all().order_by('-is_active', '-updated_at')
    return render(request, 'admin/email_config_list.html', {'configs': configs})


@login_required
# @user_passes_test(is_admin)
def email_config_create(request):
    """创建邮件配置视图"""
    if request.method == 'POST':
        form = EmailConfigForm(request.POST)
        if form.is_valid():
            config = form.save()
            messages.success(request, f"邮件配置 '{config.name}' 创建成功")
            return redirect('email_config_list')
    else:
        form = EmailConfigForm()

    return render(request, 'admin/email_config_form.html', {
        'form': form,
        'title': '创建邮件配置',
        'submit_text': '创建',
    })


@login_required
# @user_passes_test(is_admin)
def email_config_edit(request, pk):
    """编辑邮件配置视图"""
    config = get_object_or_404(EmailConfig, pk=pk)

    if request.method == 'POST':
        form = EmailConfigForm(request.POST, instance=config)
        if form.is_valid():
            config = form.save()
            messages.success(request, f"邮件配置 '{config.name}' 更新成功")
            return redirect('email_config_list')
    else:
        form = EmailConfigForm(instance=config)

    return render(request, 'admin/email_config_form.html', {
        'form': form,
        'config': config,
        'title': f"编辑邮件配置: {config.name}",
        'submit_text': '保存',
    })


@login_required
# @user_passes_test(is_admin)
def email_config_delete(request, pk):
    """删除邮件配置视图"""
    config = get_object_or_404(EmailConfig, pk=pk)

    if request.method == 'POST':
        name = config.name
        config.delete()
        messages.success(request, f"邮件配置 '{name}' 已删除")
        return redirect('email_config_list')

    return render(request, 'admin/email_config_delete.html', {'config': config})


@login_required
# @user_passes_test(is_admin)
def email_config_test(request, pk):
    """测试邮件配置视图"""
    config = get_object_or_404(EmailConfig, pk=pk)

    if request.method == 'POST':
        form = TestEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            success, message = config.send_test_email(email)

            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)

            return redirect('email_config_list')
    else:
        form = TestEmailForm()

    return render(request, 'admin/email_config_test.html', {
        'form': form,
        'config': config,
    })


@login_required
# @user_passes_test(is_admin)
def email_config_activate(request, pk):
    """激活邮件配置视图"""
    config = get_object_or_404(EmailConfig, pk=pk)

    # 测试连接
    success, message = config.test_connection()

    if success:
        config.is_active = True
        config.save()  # save 方法会自动将其他配置设置为非激活
        EmailConfig.apply_active_config()  # 应用配置到 Django 设置
        messages.success(request, f"邮件配置 '{config.name}' 已激活: {message}")
    else:
        messages.error(request, f"无法激活邮件配置: {message}")

    return redirect('email_config_list')


# 测试用例分组视图
@login_required
def test_case_group_list(request):
    project_id = request.GET.get('project')

    if project_id:
        project = get_object_or_404(Project, pk=project_id)
        # 获取顶级分组
        root_groups = TestCaseGroup.objects.filter(project=project, parent=None).order_by('name')
        context = {
            'project': project,
            'root_groups': root_groups,
        }
    else:
        # 获取所有项目的顶级分组
        projects = Project.objects.all()
        project_groups = []
        for project in projects:
            root_groups = TestCaseGroup.objects.filter(project=project, parent=None).order_by('name')
            if root_groups.exists():
                project_groups.append({
                    'project': project,
                    'root_groups': root_groups,
                })

        context = {
            'project_groups': project_groups,
        }

    return render(request, 'test_manager/test_case_group_list.html', context)


@login_required
def test_case_group_create(request):
    project_id = request.GET.get('project')
    parent_id = request.GET.get('parent')

    if not project_id:
        messages.error(request, 'Project ID is required.')
        return redirect('project_list')

    project = get_object_or_404(Project, pk=project_id)

    if request.method == 'POST':
        form = TestCaseGroupForm(request.POST, project_id=project_id)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            messages.success(request, 'Test case group created successfully.')
            return redirect('test_case_list')
    else:
        initial = {'project': project}
        if parent_id:
            parent = get_object_or_404(TestCaseGroup, pk=parent_id)
            initial['parent'] = parent

        form = TestCaseGroupForm(initial=initial, project_id=project_id)

    return render(request, 'test_manager/test_case_group_form.html', {
        'form': form,
        'title': '新增测试用例分组',
        'project': project,
    })


@login_required
def test_case_group_edit(request, pk):
    group = get_object_or_404(TestCaseGroup, pk=pk)
    project = group.project

    if request.method == 'POST':
        form = TestCaseGroupForm(request.POST, instance=group, project_id=project.id)
        if form.is_valid():
            form.save()
            messages.success(request, 'Test case group updated successfully.')
            return redirect('test_case_list')
    else:
        form = TestCaseGroupForm(instance=group, project_id=project.id)

    return render(request, 'test_manager/test_case_group_form.html', {
        'form': form,
        'title': '编辑测试用例分组',
        'project': project,
        'group': group,
    })


@login_required
def test_case_group_delete(request, pk):
    group = get_object_or_404(TestCaseGroup, pk=pk)
    project_id = group.project.id

    # 检查是否有子分组或测试用例
    if TestCaseGroup.objects.filter(parent=group).exists() or TestCase.objects.filter(group=group).exists():
        messages.warning(request, 'Cannot delete group with child groups or test cases.')
    else:
        group.delete()
        messages.success(request, 'Test case group deleted successfully.')

    return redirect('test_case_list')


# 测试套件分组视图
@login_required
def test_suite_group_list(request):
    project_id = request.GET.get('project')

    if project_id:
        project = get_object_or_404(Project, pk=project_id)
        # 获取顶级分组
        root_groups = TestSuiteGroup.objects.filter(project=project, parent=None).order_by('name')
        context = {
            'project': project,
            'root_groups': root_groups,
        }
    else:
        # 获取所有项目的顶级分组
        projects = Project.objects.all()
        project_groups = []
        for project in projects:
            root_groups = TestSuiteGroup.objects.filter(project=project, parent=None).order_by('name')
            if root_groups.exists():
                project_groups.append({
                    'project': project,
                    'root_groups': root_groups,
                })

        context = {
            'project_groups': project_groups,
        }

    return render(request, 'test_manager/test_suite_group_list.html', context)


@login_required
def test_suite_group_create(request):
    project_id = request.GET.get('project')
    parent_id = request.GET.get('parent')

    if not project_id:
        messages.error(request, 'Project ID is required.')
        return redirect('project_list')

    project = get_object_or_404(Project, pk=project_id)

    if request.method == 'POST':
        form = TestSuiteGroupForm(request.POST, project_id=project_id)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            messages.success(request, 'Test suite group created successfully.')
            return redirect('test_suite_list')
    else:
        initial = {'project': project}
        if parent_id:
            parent = get_object_or_404(TestSuiteGroup, pk=parent_id)
            initial['parent'] = parent

        form = TestSuiteGroupForm(initial=initial, project_id=project_id)

    return render(request, 'test_manager/test_suite_group_form.html', {
        'form': form,
        'title': '创建测试套件分组',
        'project': project,
    })


@login_required
def test_suite_group_edit(request, pk):
    group = get_object_or_404(TestSuiteGroup, pk=pk)
    project = group.project

    if request.method == 'POST':
        form = TestSuiteGroupForm(request.POST, instance=group, project_id=project.id)
        if form.is_valid():
            form.save()
            messages.success(request, 'Test suite group updated successfully.')
            return redirect('test_suite_list')
    else:
        form = TestSuiteGroupForm(instance=group, project_id=project.id)

    return render(request, 'test_manager/test_suite_group_form.html', {
        'form': form,
        'title': '编辑测试套件分组',
        'project': project,
        'group': group,
    })


@login_required
def test_suite_group_delete(request, pk):
    group = get_object_or_404(TestSuiteGroup, pk=pk)
    project_id = group.project.id

    # 检查是否有子分组或测试套件
    if TestSuiteGroup.objects.filter(parent=group).exists() or TestSuite.objects.filter(group=group).exists():
        messages.warning(request, 'Cannot delete group with child groups or test suites.')
    else:
        group.delete()
        messages.success(request, 'Test suite group deleted successfully.')

    return redirect('test_suite_list')


# 获取测试用例分组数据的API
@login_required
def get_test_case_groups_data(request, project_id):
    """获取项目的测试用例分组数据，用于前端展示"""
    project = get_object_or_404(Project, pk=project_id)

    # 获取所有分组
    groups = TestCaseGroup.objects.filter(project=project)

    # 构建分组树
    group_tree = []
    group_dict = {}

    # 先创建所有分组的字典
    for group in groups:
        group_data = {
            'id': group.id,
            'name': group.name,
            'parent_id': group.parent_id,
            'children': [],
            'test_cases': []
        }
        group_dict[group.id] = group_data

    # 构建分组树
    for group_id, group_data in group_dict.items():
        if group_data['parent_id'] is None:
            # 顶级分组
            group_tree.append(group_data)
        else:
            # 子分组
            parent_data = group_dict.get(group_data['parent_id'])
            if parent_data:
                parent_data['children'].append(group_data)

    # 获取每个分组下的测试用例
    for group in groups:
        test_cases = TestCase.objects.filter(project=project, group=group)
        group_data = group_dict.get(group.id)
        if group_data:
            for test_case in test_cases:
                group_data['test_cases'].append({
                    'id': test_case.id,
                    'name': test_case.name,
                    'method': test_case.request_method,
                    'url': test_case.request_url
                })

    # 获取未分组的测试用例
    ungrouped_test_cases = TestCase.objects.filter(project=project, group__isnull=True)
    ungrouped_data = {
        'id': 0,
        'name': 'Ungrouped',
        'parent_id': None,
        'children': [],
        'test_cases': []
    }

    for test_case in ungrouped_test_cases:
        ungrouped_data['test_cases'].append({
            'id': test_case.id,
            'name': test_case.name,
            'method': test_case.request_method,
            'url': test_case.request_url
        })

    # 如果有未分组的测试用例，添加到结果中
    if ungrouped_data['test_cases']:
        group_tree.append(ungrouped_data)

    return JsonResponse({
        'groups': group_tree
    })


@login_required
def test_report_list(request):
    """测试报告列表页面"""
    project_id = request.GET.get('project')
    search_query = request.GET.get('q', '')

    reports = TestReport.objects.all()

    if project_id:
        reports = reports.filter(project_id=project_id)

    if search_query:
        reports = reports.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # 分页
    paginator = Paginator(reports, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 获取所有项目，用于筛选
    projects = Project.objects.all()

    context = {
        'page_obj': page_obj,
        'projects': projects,
        'selected_project': project_id,
        'search_query': search_query,
    }

    return render(request, 'test_manager/test_report_list.html', context)


@login_required
def test_report_detail(request, pk):
    """测试报告详情页面"""
    report = get_object_or_404(TestReport, pk=pk)

    context = {
        'report': report,
    }

    if report.report_format == 'html':
        # 如果是HTML格式，直接渲染内容
        context['report_content'] = report.content
    elif report.report_format == 'json':
        # 如果是JSON格式，解析并格式化显示
        try:
            context['report_content'] = json.loads(report.content)
        except:
            context['report_content'] = report.content
    else:
        context['report_content'] = report.content

    return render(request, 'test_manager/test_report_detail.html', context)


@login_required
def test_report_delete(request, pk):
    """删除测试报告"""
    report = get_object_or_404(TestReport, pk=pk)

    if request.method == 'POST':
        project_id = report.project.id
        report.delete()
        messages.success(request, f'测试报告 "{report.name}" 已成功删除')
        return redirect('test_report_list')

    return render(request, 'test_manager/test_report_confirm_delete.html', {'report': report})


@login_required
def generate_test_run_report(request, pk):
    """从测试运行生成测试报告"""
    test_run = get_object_or_404(TestRun, pk=pk)

    if request.method == 'POST':
        form = GenerateReportForm(request.POST)
        if form.is_valid():
            # 创建测试报告
            report = TestReport(
                name=form.cleaned_data['name'],
                description=form.cleaned_data['description'],
                project=test_run.project,  # 直接使用test_run.project
                report_type='test_run',
                report_format=form.cleaned_data['report_format'],
                test_run=test_run,
                is_public=form.cleaned_data['is_public'],
                created_by=request.user
            )

            # 生成报告内容
            if form.cleaned_data['report_format'] == 'json':
                # 生成JSON格式的报告
                content = {
                    'id': str(test_run.id),
                    'name': test_run.name,
                    'project': {
                        'id': str(test_run.project.id),
                        'name': test_run.project.name,
                    },
                    'environment': {
                        'id': str(test_run.environment.id),
                        'name': test_run.environment.name,
                        'base_url': test_run.environment.base_url,
                    },
                    'status': test_run.status,
                    'start_time': test_run.start_time.isoformat() if test_run.start_time else None,
                    'end_time': test_run.end_time.isoformat() if test_run.end_time else None,
                    'duration': test_run.duration,
                    'results': []
                }

                # 添加测试套件信息（如果有）
                if test_run.test_suite:
                    content['test_suite'] = {
                        'id': str(test_run.test_suite.id),
                        'name': test_run.test_suite.name,
                    }

                # 添加测试结果
                for result in test_run.test_results.all():
                    result_data = {
                        'id': str(result.id),
                        'status': result.status,
                        'response_status_code': result.response_status_code,
                        'response_time': result.response_time,
                        'test_case': {
                            'id': str(result.test_case.id),
                            'name': result.test_case.name,
                            'request_method': result.test_case.request_method,
                            'request_url': result.test_case.request_url,
                        }
                    }

                    # 添加可选字段
                    if hasattr(result, 'response_headers') and result.response_headers:
                        result_data['response_headers'] = result.response_headers

                    if hasattr(result, 'response_body') and result.response_body:
                        result_data['response_body'] = result.response_body

                    if hasattr(result, 'request_headers') and result.request_headers:
                        result_data['request_headers'] = result.request_headers

                    if hasattr(result, 'request_body') and result.request_body:
                        result_data['request_body'] = result.request_body

                    if hasattr(result, 'error_message') and result.error_message:
                        result_data['error_message'] = result.error_message

                    content['results'].append(result_data)

                report.content = json.dumps(content, indent=2)
            else:
                # 生成HTML格式的报告
                html_content = f"""
                <div class="test-report">
                    <h1>{test_run.name} - 测试运行报告</h1>
                    <div class="report-meta">
                        <p><strong>项目:</strong> {test_run.project.name}</p>
                        <p><strong>环境:</strong> {test_run.environment.name}</p>
                        <p><strong>状态:</strong> <span class="status-{test_run.status.lower()}">{test_run.status}</span></p>
                        <p><strong>开始时间:</strong> {test_run.start_time}</p>
                        <p><strong>结束时间:</strong> {test_run.end_time}</p>
                        <p><strong>持续时间:</strong> {test_run.duration} 秒</p>
                """

                # 添加测试套件信息（如果有）
                if test_run.test_suite:
                    html_content += f"""
                        <p><strong>测试套件:</strong> {test_run.test_suite.name}</p>
                    """

                html_content += """
                    </div>

                    <h2>测试结果</h2>
                """

                # 添加测试结果
                for result in test_run.test_results.all():
                    html_content += f"""
                    <div class="test-result">
                        <h3>{result.test_case.name}</h3>
                        <p><strong>状态:</strong> <span class="status-{result.status.lower()}">{result.status}</span></p>
                        <p><strong>请求方法:</strong> {result.test_case.request_method}</p>
                        <p><strong>请求URL:</strong> {result.test_case.request_url}</p>
                        <p><strong>响应状态码:</strong> {result.response_status_code}</p>
                        <p><strong>响应时间:</strong> {result.response_time} 毫秒</p>

                        <div class="collapsible">
                            <h4>请求头</h4>
                            <pre>{json.dumps(result.request_headers, indent=2) if hasattr(result, 'request_headers') and result.request_headers else '无数据'}</pre>
                        </div>

                        <div class="collapsible">
                            <h4>请求体</h4>
                            <pre>{result.request_body if hasattr(result, 'request_body') and result.request_body else '无数据'}</pre>
                        </div>

                        <div class="collapsible">
                            <h4>响应头</h4>
                            <pre>{json.dumps(result.response_headers, indent=2) if hasattr(result, 'response_headers') and result.response_headers else '无数据'}</pre>
                        </div>

                        <div class="collapsible">
                            <h4>响应体</h4>
                            <pre>{result.response_body if hasattr(result, 'response_body') and result.response_body else '无数据'}</pre>
                        </div>

                        {f'<div class="error-message"><h4>错误信息</h4><pre>{result.error_message}</pre></div>' if hasattr(result, 'error_message') and result.error_message else ''}
                    </div>
                    """

                html_content += """
                </div>
                <style>
                    .test-report {
                        font-family: Arial, sans-serif;
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 20px;
                    }
                    .report-meta {
                        background-color: #f5f5f5;
                        padding: 15px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                    }
                    .test-result {
                        background-color: #f9f9f9;
                        padding: 15px;
                        border-radius: 5px;
                        margin-bottom: 15px;
                        border-left: 5px solid #ddd;
                    }
                    .collapsible {
                        margin-top: 10px;
                    }
                    .collapsible h4 {
                        cursor: pointer;
                        background-color: #eee;
                        padding: 8px;
                        border-radius: 3px;
                    }
                    .collapsible pre {
                        background-color: #f5f5f5;
                        padding: 10px;
                        border-radius: 3px;
                        overflow-x: auto;
                        white-space: pre-wrap;
                    }
                    .status-pass, .status-success, .status-completed {
                        color: green;
                        font-weight: bold;
                    }
                    .status-fail, .status-failure, .status-error, .status-failed {
                        color: red;
                        font-weight: bold;
                    }
                    .error-message {
                        background-color: #ffeeee;
                        padding: 10px;
                        border-radius: 3px;
                        margin-top: 10px;
                    }
                    .error-message h4 {
                        color: red;
                    }
                </style>
                <script>
                    document.addEventListener('DOMContentLoaded', function() {
                        const collapsibles = document.querySelectorAll('.collapsible h4');
                        collapsibles.forEach(function(collapsible) {
                            collapsible.addEventListener('click', function() {
                                this.nextElementSibling.style.display = 
                                    this.nextElementSibling.style.display === 'none' ? 'block' : 'none';
                            });
                            // 初始隐藏
                            collapsible.nextElementSibling.style.display = 'none';
                        });
                    });
                </script>
                """

                report.content = html_content

            report.save()
            messages.success(request, f'测试报告 "{report.name}" 已成功生成')
            return redirect('test_report_detail', pk=report.pk)
    else:
        # 默认报告名称
        default_name = f"{test_run.name} - 测试报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        form = GenerateReportForm(initial={'name': default_name, 'report_format': 'html'})

    return render(request, 'test_manager/generate_test_report.html', {
        'form': form,
        'test_run': test_run,
    })


@login_required
def generate_test_suite_run_report(request, pk):
    """从测试套件运行生成测试报告"""
    test_suite_run = get_object_or_404(TestSuiteRun, pk=pk)

    if request.method == 'POST':
        form = GenerateReportForm(request.POST)
        if form.is_valid():
            # 创建测试报告
            report = TestReport(
                name=form.cleaned_data['name'],
                description=form.cleaned_data['description'],
                project=test_suite_run.project,
                report_type='test_suite_run',
                report_format=form.cleaned_data['report_format'],
                test_suite_run=test_suite_run,
                is_public=form.cleaned_data['is_public']
            )

            # 计算持续时间（如果可能）
            duration = None
            if test_suite_run.start_time and test_suite_run.end_time:
                duration = (test_suite_run.end_time - test_suite_run.start_time).total_seconds()

            # 生成报告内容
            if form.cleaned_data['report_format'] == 'json':
                # 生成JSON格式的报告
                content = {
                    'id': str(test_suite_run.id),
                    'test_suite': {
                        'id': str(test_suite_run.test_suite.id),
                        'name': test_suite_run.test_suite.name,
                    },
                    'environment': {
                        'id': str(test_suite_run.environment.id),
                        'name': test_suite_run.environment.name,
                        'base_url': test_suite_run.environment.base_url,
                    },
                    'status': test_suite_run.status,
                    'start_time': test_suite_run.start_time.isoformat() if test_suite_run.start_time else None,
                    'end_time': test_suite_run.end_time.isoformat() if test_suite_run.end_time else None,
                    'duration': duration,
                    'test_runs': []
                }

                # 添加测试运行
                for test_run in test_suite_run.test_runs.all():
                    # 计算测试运行的持续时间（如果可能）
                    run_duration = None
                    if test_run.start_time and test_run.end_time:
                        run_duration = (test_run.end_time - test_run.start_time).total_seconds()

                    run_data = {
                        'id': str(test_run.id),
                        'name': test_run.name,
                        'status': test_run.status,
                        'start_time': test_run.start_time.isoformat() if test_run.start_time else None,
                        'end_time': test_run.end_time.isoformat() if test_run.end_time else None,
                        'duration': run_duration,
                        'results': []
                    }

                    # 添加测试结果
                    for result in test_run.test_results.all():
                        result_data = {
                            'id': str(result.id),
                            'status': result.status,
                            'response_status_code': result.response_status_code,
                            'response_time': result.response_time,
                            'test_case': {
                                'id': str(result.test_case.id),
                                'name': result.test_case.name,
                                'request_method': result.test_case.request_method,
                                'request_url': result.test_case.request_url,
                            }
                        }

                        if hasattr(result, 'error_message') and result.error_message:
                            result_data['error_message'] = result.error_message

                        run_data['results'].append(result_data)

                    content['test_runs'].append(run_data)

                # 计算统计信息
                total_runs = len(content['test_runs'])
                passed_runs = sum(1 for run in content['test_runs'] if run['status'] == 'completed')
                failed_runs = sum(1 for run in content['test_runs'] if run['status'] == 'failed')
                error_runs = sum(1 for run in content['test_runs'] if
                                 run['status'] not in ['completed', 'failed', 'pending', 'running'])

                content['summary'] = {
                    'total': total_runs,
                    'passed': passed_runs,
                    'failed': failed_runs,
                    'error': error_runs,
                    'success_rate': f"{(passed_runs / total_runs * 100) if total_runs > 0 else 0:.2f}%"
                }

                report.content = json.dumps(content, indent=2)
            else:
                # 生成HTML格式的报告
                # 计算统计信息
                total_runs = test_suite_run.test_runs.count()
                passed_runs = test_suite_run.test_runs.filter(status='completed').count()
                failed_runs = test_suite_run.test_runs.filter(status='failed').count()
                error_runs = test_suite_run.test_runs.exclude(
                    status__in=['completed', 'failed', 'pending', 'running']).count()
                success_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0

                html_content = f"""
                <div class="test-report">
                    <h1>{test_suite_run.test_suite.name} - 测试套件运行报告</h1>
                    <div class="report-meta">
                        <p><strong>测试套件:</strong> {test_suite_run.test_suite.name}</p>
                        <p><strong>环境:</strong> {test_suite_run.environment.name}</p>
                        <p><strong>状态:</strong> <span class="status-{test_suite_run.status.lower()}">{test_suite_run.status}</span></p>
                        <p><strong>开始时间:</strong> {test_suite_run.start_time}</p>
                        <p><strong>结束时间:</strong> {test_suite_run.end_time}</p>
                """

                # 只有在有开始和结束时间时才显示持续时间
                if duration is not None:
                    html_content += f"""
                        <p><strong>持续时间:</strong> {duration} 秒</p>
                    """

                html_content += """
                    </div>

                    <div class="summary">
                        <h2>测试摘要</h2>
                        <div class="summary-stats">
                            <div class="stat">
                                <div class="stat-value">{total_runs}</div>
                                <div class="stat-label">总计</div>
                            </div>
                            <div class="stat stat-success">
                                <div class="stat-value">{passed_runs}</div>
                                <div class="stat-label">通过</div>
                            </div>
                            <div class="stat stat-failure">
                                <div class="stat-value">{failed_runs}</div>
                                <div class="stat-label">失败</div>
                            </div>
                            <div class="stat stat-error">
                                <div class="stat-value">{error_runs}</div>
                                <div class="stat-label">错误</div>
                            </div>
                            <div class="stat">
                                <div class="stat-value">{success_rate:.2f}%</div>
                                <div class="stat-label">成功率</div>
                            </div>
                        </div>
                    </div>

                    <h2>测试用例结果</h2>
                    <table class="test-cases-table">
                        <thead>
                            <tr>
                                <th>测试用例</th>
                                <th>方法</th>
                                <th>URL</th>
                                <th>状态</th>
                                <th>持续时间</th>
                            </tr>
                        </thead>
                        <tbody>
                """

                for test_run in test_suite_run.test_runs.all():
                    # 计算测试运行的持续时间（如果可能）
                    run_duration = None
                    if test_run.start_time and test_run.end_time:
                        run_duration = (test_run.end_time - test_run.start_time).total_seconds()

                    # 获取第一个测试结果（如果有）
                    first_result = test_run.test_results.first()

                    if first_result:
                        html_content += f"""
                        <tr class="test-case-row status-{test_run.status.lower()}">
                            <td>{first_result.test_case.name}</td>
                            <td>{first_result.test_case.request_method}</td>
                            <td>{first_result.test_case.request_url}</td>
                            <td><span class="status-badge status-{test_run.status.lower()}">{test_run.status}</span></td>
                            <td>{run_duration} 秒</td>
                        </tr>
                        <tr class="test-case-details">
                            <td colspan="5">
                                <div class="details-content">
                        """

                        for result in test_run.test_results.all():
                            html_content += f"""
                                    <div class="result-item">
                                        <h4>响应详情</h4>
                                        <p><strong>状态码:</strong> {result.response_status_code}</p>
                            """

                            # 只有在有响应时间时才显示
                            if result.response_time is not None:
                                html_content += f"""
                                        <p><strong>响应时间:</strong> {result.response_time} 毫秒</p>
                                """

                            html_content += f"""
                                        <div class="collapsible">
                                            <h5>请求头</h5>
                                            <pre>{json.dumps(result.request_headers, indent=2) if hasattr(result, 'request_headers') and result.request_headers else '无数据'}</pre>
                                        </div>

                                        <div class="collapsible">
                                            <h5>请求体</h5>
                                            <pre>{result.request_body if hasattr(result, 'request_body') and result.request_body else '无数据'}</pre>
                                        </div>

                                        <div class="collapsible">
                                            <h5>响应头</h5>
                                            <pre>{json.dumps(result.response_headers, indent=2) if hasattr(result, 'response_headers') and result.response_headers else '无数据'}</pre>
                                        </div>

                                        <div class="collapsible">
                                            <h5>响应体</h5>
                                            <pre>{result.response_body if hasattr(result, 'response_body') and result.response_body else '无数据'}</pre>
                                        </div>

                                        {f'<div class="error-message"><h5>错误信息</h5><pre>{result.error_message}</pre></div>' if hasattr(result, 'error_message') and result.error_message else ''}
                                    </div>
                            """

                        html_content += """
                                </div>
                            </td>
                        </tr>
                        """

                html_content += """
                        </tbody>
                    </table>
                </div>
                <style>
                    .test-report {
                        font-family: Arial, sans-serif;
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 20px;
                    }
                    .report-meta {
                        background-color: #f5f5f5;
                        padding: 15px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                    }
                    .summary {
                        margin-bottom: 30px;
                    }
                    .summary-stats {
                        display: flex;
                        justify-content: space-between;
                        flex-wrap: wrap;
                        gap: 15px;
                        margin-top: 15px;
                    }
                    .stat {
                        background-color: #f5f5f5;
                        border-radius: 5px;
                        padding: 15px;
                        text-align: center;
                        flex: 1;
                        min-width: 100px;
                    }
                    .stat-value {
                        font-size: 24px;
                        font-weight: bold;
                        margin-bottom: 5px;
                    }
                    .stat-label {
                        font-size: 14px;
                        color: #666;
                    }
                    .stat-success {
                        background-color: #e6f7e6;
                    }
                    .stat-success .stat-value {
                        color: #2e7d32;
                    }
                    .stat-failure {
                        background-color: #fde9e8;
                    }
                    .stat-failure .stat-value {
                        color: #c62828;
                    }
                    .stat-error {
                        background-color: #fff3e0;
                    }
                    .stat-error .stat-value {
                        color: #e65100;
                    }
                    .test-cases-table {
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 20px;
                    }
                    .test-cases-table th, .test-cases-table td {
                        padding: 10px;
                        text-align: left;
                        border-bottom: 1px solid #ddd;
                    }
                    .test-cases-table th {
                        background-color: #f5f5f5;
                        font-weight: bold;
                    }
                    .test-case-row {
                        cursor: pointer;
                    }
                    .test-case-row:hover {
                        background-color: #f9f9f9;
                    }
                    .test-case-row.status-completed {
                        background-color: #f0fff0;
                    }
                    .test-case-row.status-failed {
                        background-color: #fff0f0;
                    }
                    .test-case-row.status-error {
                        background-color: #fffaf0;
                    }
                    .status-badge {
                        display: inline-block;
                        padding: 3px 8px;
                        border-radius: 3px;
                        font-size: 12px;
                        font-weight: bold;
                    }
                    .status-badge.status-completed {
                        background-color: #e6f7e6;
                        color: #2e7d32;
                    }
                    .status-badge.status-failed {
                        background-color: #fde9e8;
                        color: #c62828;
                    }
                    .status-badge.status-error {
                        background-color: #fff3e0;
                        color: #e65100;
                    }
                    .test-case-details {
                        display: none;
                    }
                    .details-content {
                        padding: 15px;
                        background-color: #f9f9f9;
                    }
                    .result-item {
                        margin-bottom: 15px;
                        padding-bottom: 15px;
                        border-bottom: 1px solid #eee;
                    }
                    .result-item:last-child {
                        margin-bottom: 0;
                        padding-bottom: 0;
                        border-bottom: none;
                    }
                    .collapsible {
                        margin-top: 10px;
                    }
                    .collapsible h5 {
                        cursor: pointer;
                        background-color: #eee;
                        padding: 8px;
                        border-radius: 3px;
                        margin: 0;
                    }
                    .collapsible pre {
                        background-color: #f5f5f5;
                        padding: 10px;
                        border-radius: 3px;
                        overflow-x: auto;
                        white-space: pre-wrap;
                        margin-top: 5px;
                    }
                    .status-pass, .status-success, .status-completed, .status-passed {
                        color: green;
                        font-weight: bold;
                    }
                    .status-fail, .status-failure, .status-error, .status-failed {
                        color: red;
                        font-weight: bold;
                    }
                    .error-message {
                        background-color: #ffeeee;
                        padding: 10px;
                        border-radius: 3px;
                        margin-top: 10px;
                    }
                    .error-message h5 {
                        color: red;
                        margin-top: 0;
                    }
                </style>
                <script>
                    document.addEventListener('DOMContentLoaded', function() {
                        // 折叠/展开详情
                        const testCaseRows = document.querySelectorAll('.test-case-row');
                        testCaseRows.forEach(function(row) {
                            row.addEventListener('click', function() {
                                const detailsRow = this.nextElementSibling;
                                detailsRow.style.display = 
                                    detailsRow.style.display === 'table-row' ? 'none' : 'table-row';
                            });
                        });

                        // 折叠/展开可折叠内容
                        const collapsibles = document.querySelectorAll('.collapsible h5');
                        collapsibles.forEach(function(collapsible) {
                            collapsible.addEventListener('click', function(e) {
                                e.stopPropagation();
                                this.nextElementSibling.style.display = 
                                    this.nextElementSibling.style.display === 'none' ? 'block' : 'none';
                            });
                            // 初始隐藏
                            collapsible.nextElementSibling.style.display = 'none';
                        });
                    });
                </script>
                """

                report.content = html_content

            report.save()
            messages.success(request, f'测试报告 "{report.name}" 已成功生成')
            return redirect('test_report_detail', pk=report.pk)
    else:
        # 默认报告名称
        default_name = f"{test_suite_run.test_suite.name} - 测试报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        form = GenerateReportForm(initial={'name': default_name, 'report_format': 'html'})

    return render(request, 'test_manager/generate_test_report.html', {
        'form': form,
        'test_suite_run': test_suite_run,
    })


@login_required
def mock_data_generator(request):
    data_list = request.POST.get('data')
    num = request.POST.get('num')
    if request.method == 'POST':
        form = MockDataForm(request.POST)
        if form.is_valid():
            mock_data = form.save(commit=False)
            mock_data.data = auto_gen_data(fields=ast.literal_eval(data_list), num=int(num))
            mock_data.created_by = request.user
            mock_data.save()
            messages.success(request, '数据生成成功')
            return redirect('mock-data-list')
    else:

        form = MockDataForm()
    return render(request, 'test_manager/mock_data_form.html', {'form': form, 'title': '生成数据'})


def mock_data_list(request):
    all_mock_data = MockData.objects.all().order_by('-created_at')
    # 获取每页显示的记录数
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    mock_data_list = paginate_queryset(request, all_mock_data, per_page)
    return render(request, 'test_manager/mock_data.html', {'mock_data_list': mock_data_list})


def mock_data_delete(request, pk):
    mock_data = get_object_or_404(MockData, pk=pk)
    if request.method == 'POST':
        mock_data.delete()
        messages.success(request, '数据删除成功')
        return redirect('mock-data-list')
    return render(request, 'test_manager/mock_data_delete.html', {'mock_data': mock_data})


def mock_data_export(request, pk):
    data = MockData.objects.get(pk=pk)
    data = json.loads(data.data)
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    # 创建响应对象
    response = HttpResponse(json_str, content_type='application/json')
    # 设置Content-Disposition为附件下载，并指定文件名
    response['Content-Disposition'] = 'attachment; filename="mock_data.json"'
    return response


@login_required
def scheduled_task_list(request):
    """定时任务列表"""
    test_suite_id = request.GET.get('test_suite')
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    tasks = ScheduledTask.objects.filter(created_by=request.user)

    if test_suite_id:
        tasks = tasks.filter(test_suite_id=test_suite_id)
        test_suite = get_object_or_404(TestSuite, pk=test_suite_id)
    else:
        test_suite = None

    if search_query:
        tasks = tasks.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(test_suite__name__icontains=search_query)
        )

    if status_filter:
        tasks = tasks.filter(status=status_filter)

    # 分页
    paginator = Paginator(tasks, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'test_suite': test_suite,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': ScheduledTask.STATUS_CHOICES,
    }

    return render(request, 'test_manager/scheduled_task_list.html', context)


@login_required
def scheduled_task_create(request):
    """创建定时任务 - 优化版本，确保立即同步到Celery Beat"""
    import logging
    logger = logging.getLogger(__name__)

    test_suite_id = request.GET.get('test_suite')

    if request.method == 'POST':
        form = ScheduledTaskForm(request.POST, test_suite_id=test_suite_id)
        if form.is_valid():
            try:
                # 保存定时任务
                task = form.save(commit=False)
                task.created_by = request.user
                task.save()

                logger.info(f"定时任务已保存到数据库: {task.name} (ID: {task.id})")

                # 立即同步到Celery Beat
                try:
                    # 计算下次执行时间
                    task.update_next_run_time()
                    logger.info(f"下次执行时间已计算: {task.next_run_time}")

                    # 创建Celery Beat任务
                    celery_task = TaskScheduler.create_or_update_celery_task(task)

                    if celery_task:
                        logger.info(f"Celery Beat任务创建成功: {task.celery_task_id}")
                        messages.success(
                            request,
                            f'定时任务 "{task.name}" 创建成功，已同步到调度器。下次执行时间: {task.next_run_time}'
                        )
                    else:
                        logger.warning(f"Celery Beat任务创建失败: {task.name}")
                        messages.warning(
                            request,
                            f'定时任务 "{task.name}" 创建成功，但同步到调度器失败。请检查Celery Beat服务状态。'
                        )

                    # 验证同步结果
                    from django_celery_beat.models import PeriodicTask
                    if task.celery_task_id and PeriodicTask.objects.filter(name=task.celery_task_id).exists():
                        logger.info(f"验证成功: Celery Beat任务已存在于数据库")
                        messages.info(request, f'调度器同步验证成功')
                    else:
                        logger.error(f"验证失败: Celery Beat任务不存在于数据库")
                        messages.error(request, f'调度器同步验证失败，任务可能无法按时执行')

                except Exception as sync_error:
                    logger.error(f"同步到Celery Beat失败: {str(sync_error)}")
                    logger.error(f"同步错误详情: {traceback.format_exc()}")
                    messages.error(
                        request,
                        f'定时任务创建成功，但同步到调度器失败: {str(sync_error)}'
                    )

                return redirect('scheduled_task_detail', pk=task.pk)

            except Exception as e:
                logger.error(f"创建定时任务失败: {str(e)}")
                logger.error(f"创建错误详情: {traceback.format_exc()}")
                messages.error(request, f'创建定时任务失败: {str(e)}')

    else:
        initial = {}
        if test_suite_id:
            initial['test_suite'] = test_suite_id
        form = ScheduledTaskForm(initial=initial, test_suite_id=test_suite_id)

    return render(request, 'test_manager/scheduled_task_form.html', {
        'form': form,
        'title': '创建定时任务'
    })


@login_required
def scheduled_task_detail(request, pk):
    """定时任务详情"""
    task = get_object_or_404(ScheduledTask, pk=pk, created_by=request.user)

    # 获取执行日志
    logs = TaskExecutionLog.objects.filter(scheduled_task=task).order_by('-start_time')

    # 分页
    paginator = Paginator(logs, 10)
    page_number = request.GET.get('page')
    logs_page = paginator.get_page(page_number)

    context = {
        'task': task,
        'logs_page': logs_page,
    }

    return render(request, 'test_manager/scheduled_task_detail.html', context)


@login_required
def scheduled_task_edit(request, pk):
    """编辑定时任务 - 优化版本，确保立即同步到Celery Beat"""
    import logging
    logger = logging.getLogger(__name__)

    task = get_object_or_404(ScheduledTask, pk=pk, created_by=request.user)

    if request.method == 'POST':
        form = ScheduledTaskForm(request.POST, instance=task, test_suite_id=task.test_suite.id)
        if form.is_valid():
            try:
                # 保存原始的celery_task_id，用于删除旧任务
                old_celery_task_id = task.celery_task_id

                # 保存定时任务
                task = form.save()
                logger.info(f"定时任务已更新到数据库: {task.name} (ID: {task.id})")

                # 立即同步到Celery Beat
                try:
                    # 如果有旧的Celery任务，先删除
                    if old_celery_task_id:
                        try:
                            from django_celery_beat.models import PeriodicTask
                            old_task = PeriodicTask.objects.get(name=old_celery_task_id)
                            old_task.delete()
                            logger.info(f"已删除旧的Celery Beat任务: {old_celery_task_id}")
                        except PeriodicTask.DoesNotExist:
                            logger.warning(f"旧的Celery Beat任务不存在: {old_celery_task_id}")

                    # 计算下次执行时间
                    task.update_next_run_time()
                    logger.info(f"下次执行时间已更新: {task.next_run_time}")

                    # 创建新的Celery Beat任务
                    celery_task = TaskScheduler.create_or_update_celery_task(task)

                    if celery_task:
                        logger.info(f"Celery Beat任务更新成功: {task.celery_task_id}")
                        messages.success(
                            request,
                            f'定时任务 "{task.name}" 更新成功，已同步到调度器。下次执行时间: {task.next_run_time}'
                        )
                    else:
                        logger.warning(f"Celery Beat任务更新失败: {task.name}")
                        messages.warning(
                            request,
                            f'定时任务 "{task.name}" 更新成功，但同步到调度器失败。请检查Celery Beat服务状态。'
                        )

                    # 验证同步结果
                    from django_celery_beat.models import PeriodicTask
                    if task.celery_task_id and PeriodicTask.objects.filter(name=task.celery_task_id).exists():
                        logger.info(f"验证成功: Celery Beat任务已存在于数据库")
                        messages.info(request, f'调度器同步验证成功')
                    else:
                        logger.error(f"验证失败: Celery Beat任务不存在于数据库")
                        messages.error(request, f'调度器同步验证失败，任务可能无法按时执行')

                except Exception as sync_error:
                    logger.error(f"同步到Celery Beat失败: {str(sync_error)}")
                    logger.error(f"同步错误详情: {traceback.format_exc()}")
                    messages.error(
                        request,
                        f'定时任务更新成功，但同步到调度器失败: {str(sync_error)}'
                    )

                return redirect('scheduled_task_detail', pk=task.pk)

            except Exception as e:
                logger.error(f"更新定时任务失败: {str(e)}")
                logger.error(f"更新错误详情: {traceback.format_exc()}")
                messages.error(request, f'更新定时任务失败: {str(e)}')

    else:
        form = ScheduledTaskForm(instance=task, test_suite_id=task.test_suite.id)

    return render(request, 'test_manager/scheduled_task_form.html', {
        'form': form,
        'task': task,
        'title': f'编辑定时任务: {task.name}'
    })


@login_required
def scheduled_task_delete(request, pk):
    """删除定时任务 - 优化版本，确保同步删除Celery Beat任务"""
    import logging
    logger = logging.getLogger(__name__)

    task = get_object_or_404(ScheduledTask, pk=pk, created_by=request.user)

    if request.method == 'POST':
        task_name = task.name
        celery_task_id = task.celery_task_id

        try:
            logger.info(f"开始删除定时任务: {task_name} (ID: {task.id})")

            # 先删除Celery Beat任务
            if celery_task_id:
                try:
                    from django_celery_beat.models import PeriodicTask
                    celery_task = PeriodicTask.objects.get(name=celery_task_id)
                    celery_task.delete()
                    logger.info(f"成功删除Celery Beat任务: {celery_task_id}")
                    messages.info(request, f'已删除调度器中的任务: {celery_task_id}')
                except PeriodicTask.DoesNotExist:
                    logger.warning(f"Celery Beat任务不存在: {celery_task_id}")
                    messages.warning(request, f'调度器中的任务不存在: {celery_task_id}')
                except Exception as celery_error:
                    logger.error(f"删除Celery Beat任务失败: {str(celery_error)}")
                    logger.error(f"Celery删除错误详情: {traceback.format_exc()}")
                    messages.error(request, f'删除调度器任务失败: {str(celery_error)}')
            else:
                logger.info(f"任务没有关联的Celery Beat任务: {task_name}")

            # 删除数据库中的定时任务
            task.delete()
            logger.info(f"成功删除数据库中的定时任务: {task_name}")

            # 验证删除结果
            try:
                if celery_task_id:
                    from django_celery_beat.models import PeriodicTask
                    if not PeriodicTask.objects.filter(name=celery_task_id).exists():
                        logger.info(f"验证成功: Celery Beat任务已从数据库中删除")
                        messages.success(request, f'定时任务 "{task_name}" 已完全删除（包括调度器任务）')
                    else:
                        logger.error(f"验证失败: Celery Beat任务仍存在于数据库中")
                        messages.warning(request, f'定时任务 "{task_name}" 已删除，但调度器任务可能仍然存在')
                else:
                    messages.success(request, f'定时任务 "{task_name}" 已删除')
            except Exception as verify_error:
                logger.error(f"验证删除结果失败: {str(verify_error)}")
                messages.success(request, f'定时任务 "{task_name}" 已删除')

            return redirect('scheduled_task_list')

        except Exception as e:
            logger.error(f"删除定时任务失败: {str(e)}")
            logger.error(f"删除错误详情: {traceback.format_exc()}")
            messages.error(request, f'删除定时任务失败: {str(e)}')
            return redirect('scheduled_task_detail', pk=pk)

    return render(request, 'test_manager/scheduled_task_confirm_delete.html', {'task': task})


@login_required
@require_POST
def scheduled_task_toggle_status(request, pk):
    """切换定时任务状态 - 优化版本，确保立即同步到Celery Beat"""
    import logging
    logger = logging.getLogger(__name__)

    task = get_object_or_404(ScheduledTask, pk=pk, created_by=request.user)
    old_status = task.status

    try:
        if task.status == 'active':
            task.status = 'paused'
            message = f'定时任务 "{task.name}" 已暂停'
        else:
            task.status = 'active'
            task.update_next_run_time()
            message = f'定时任务 "{task.name}" 已激活'

        task.save()
        logger.info(f"任务状态已更新: {task.name} - {old_status} -> {task.status}")

        # 立即同步到Celery Beat
        try:
            if task.status == 'active':
                # 激活任务 - 创建Celery Beat任务
                celery_task = TaskScheduler.create_or_update_celery_task(task)
                if celery_task:
                    logger.info(f"Celery Beat任务已激活: {task.celery_task_id}")
                    message += f"，下次执行时间: {task.next_run_time}"
                else:
                    logger.warning(f"Celery Beat任务激活失败: {task.name}")
                    message += "，但调度器同步失败"
            else:
                # 暂停任务 - 删除Celery Beat任务
                TaskScheduler.delete_celery_task(task)
                logger.info(f"Celery Beat任务已暂停: {task.name}")

        except Exception as sync_error:
            logger.error(f"状态切换同步失败: {str(sync_error)}")
            message += f"，但调度器同步失败: {str(sync_error)}"

        messages.success(request, message)

        return JsonResponse({
            'success': True,
            'status': task.status,
            'message': message,
            'next_run_time': task.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if task.next_run_time else None
        })

    except Exception as e:
        logger.error(f"切换任务状态失败: {str(e)}")
        logger.error(f"状态切换错误详情: {traceback.format_exc()}")

        return JsonResponse({
            'success': False,
            'message': f'切换任务状态失败: {str(e)}',
            'error': str(e)
        })


# @login_required
@require_POST
def scheduled_task_run_now(request, pk):
    """立即执行定时任务"""
    try:
        task = get_object_or_404(ScheduledTask, pk=pk)
        print(f'[DEBUG] scheduled_task_run_now - 找到任务: {task.name} (ID: {task.id})')

        # 检查任务状态
        if not task.is_enabled:
            messages.error(request, f'定时任务 "{task.name}" 已禁用，无法执行')
            return JsonResponse({
                'success': False,
                'message': f'定时任务 "{task.name}" 已禁用，无法执行'
            })

        # 检查Celery是否可用
        try:
            from celery import current_app
            i = current_app.control.inspect()
            active_workers = i.active()

            if not active_workers:
                print('[ERROR] 没有活动的Celery worker')
                messages.error(request, 'Celery服务未运行，无法执行定时任务')
                return JsonResponse({
                    'success': False,
                    'message': 'Celery服务未运行，无法执行定时任务'
                })

            print(f'[DEBUG] 找到活动的Celery worker: {list(active_workers.keys())}')

        except Exception as celery_check_error:
            print(f'[ERROR] Celery状态检查失败: {str(celery_check_error)}')
            # 继续执行，可能是检查方法的问题

        # 尝试异步执行任务
        try:
            from .tasks import execute_scheduled_test_suite
            print(f'[DEBUG] 准备异步执行任务: {task.id}')
            result = execute_scheduled_test_suite.delay(task.id)
            print(f'[DEBUG] 任务已提交到Celery队列，task_id: {result.id}')

            messages.success(request, f'定时任务 "{task.name}" 已开始执行')

            return JsonResponse({
                'success': True,
                'message': f'定时任务 "{task.name}" 已开始执行',
                'task_id': result.id
            })

        except Exception as celery_error:
            print(f'[ERROR] Celery任务提交失败: {str(celery_error)}')
            print(f'[ERROR] 错误详情: {traceback.format_exc()}')

            # 尝试直接执行任务（同步方式）
            try:
                print(f'[DEBUG] 尝试同步执行任务: {task.id}')
                from .tasks import execute_scheduled_test_suite

                # 在后台线程中执行，避免阻塞请求
                import threading

                def run_task_sync():
                    try:
                        result = execute_scheduled_test_suite(task.id)
                        print(f'[DEBUG] 同步任务执行完成: {result}')
                    except Exception as sync_error:
                        print(f'[ERROR] 同步任务执行失败: {str(sync_error)}')
                        print(f'[ERROR] 同步任务错误详情: {traceback.format_exc()}')

                thread = threading.Thread(target=run_task_sync)
                thread.daemon = True
                thread.start()

                messages.success(request, f'定时任务 "{task.name}" 已开始执行（同步模式）')

                return JsonResponse({
                    'success': True,
                    'message': f'定时任务 "{task.name}" 已开始执行（同步模式）',
                    'task_id': 'sync_execution'
                })

            except Exception as sync_error:
                print(f'[ERROR] 同步执行也失败: {str(sync_error)}')
                print(f'[ERROR] 同步执行错误详情: {traceback.format_exc()}')

                messages.error(request, f'定时任务 "{task.name}" 执行失败: {str(sync_error)}')

                return JsonResponse({
                    'success': False,
                    'message': f'定时任务 "{task.name}" 执行失败: {str(sync_error)}',
                    'error': str(sync_error)
                })

    except Exception as e:
        print(f'[ERROR] scheduled_task_run_now 视图异常: {str(e)}')
        print(f'[ERROR] 视图异常详情: {traceback.format_exc()}')

        messages.error(request, f'执行定时任务时发生错误: {str(e)}')

        return JsonResponse({
            'success': False,
            'message': f'执行定时任务时发生错误: {str(e)}',
            'error': str(e)
        })


# @login_required
def task_execution_log_detail(request, pk):
    """任务执行日志详情"""
    log = get_object_or_404(TaskExecutionLog, pk=pk)
    print(f'[DEBUG] 找到任务执行日志: ',log)

    context = {
        'log': log,
    }

    return render(request, 'test_manager/task_execution_log_detail.html', context)


def tools(request):
    return render(request, 'test_manager/tools.html')