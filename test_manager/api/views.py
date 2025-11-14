from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from test_manager.models import (
    Project, Environment, TestCase, TestSuite,
    TestSuiteCase, TestRun, TestResult
)
from .serializers import (
    ProjectSerializer, EnvironmentSerializer, TestCaseSerializer,
    TestSuiteSerializer, TestSuiteCaseSerializer, TestRunSerializer,
    TestResultSerializer
)
from test_manager.httprunner_executor import execute_test_case, execute_test_suite


# 自定义分页类
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Project.objects.all().order_by('-created_at')


class EnvironmentViewSet(viewsets.ModelViewSet):
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        project_id = self.request.query_params.get('project', None)
        if project_id:
            return Environment.objects.filter(project_id=project_id).order_by('-created_at')
        return Environment.objects.all().order_by('-created_at')


class TestCaseViewSet(viewsets.ModelViewSet):
    queryset = TestCase.objects.all()
    serializer_class = TestCaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        project_id = self.request.query_params.get('project', None)
        if project_id:
            return TestCase.objects.filter(project_id=project_id).order_by('-created_at')
        return TestCase.objects.all().order_by('-created_at')

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        test_case = self.get_object()
        environment_id = request.data.get('environment_id')

        if not environment_id:
            return Response({"error": "Environment ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        environment = get_object_or_404(Environment, id=environment_id)

        # Create a test run
        test_run = TestRun.objects.create(
            name=f"Single run: {test_case.name}",
            project=test_case.project,
            environment=environment,
            status='running',
            start_time=timezone.now(),
            created_by=request.user
        )

        # Execute the test case
        result = execute_test_case(test_case, environment)

        # Update test run
        test_run.status = 'completed' if result['status'] == 'passed' else 'failed'
        test_run.end_time = timezone.now()
        test_run.save()

        # Create test result
        test_result = TestResult.objects.create(
            test_run=test_run,
            test_case=test_case,
            environment=environment,
            status=result['status'],
            request_headers=result.get('request_headers', {}),  # 保存请求头
            request_body=result.get('request_body'),  # 保存请求体
            response_time=result.get('response_time'),
            response_status_code=result.get('response_status_code'),
            response_headers=result.get('response_headers', {}),
            response_body=result.get('response_body'),
            error_message=result.get('error_message', ''),
            extracted_params=result.get('extracted_params', {}),
            validators=result.get('validators', [])
        )

        serializer = TestResultSerializer(test_result)
        return Response(serializer.data)


class TestSuiteViewSet(viewsets.ModelViewSet):
    queryset = TestSuite.objects.all()
    serializer_class = TestSuiteSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        project_id = self.request.query_params.get('project', None)
        if project_id:
            return TestSuite.objects.filter(project_id=project_id).order_by('-created_at')
        return TestSuite.objects.all().order_by('-created_at')

    @action(detail=True, methods=['post'])
    def add_test_case(self, request, pk=None):
        test_suite = self.get_object()
        test_case_id = request.data.get('test_case_id')
        environment_id = request.data.get('environment_id')
        order = request.data.get('order', 0)

        if not test_case_id:
            return Response({"error": "Test case ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        test_case = get_object_or_404(TestCase, id=test_case_id)

        # Check if test case is already in the suite
        if TestSuiteCase.objects.filter(test_suite=test_suite, test_case=test_case).exists():
            return Response({"error": "Test case already in suite"}, status=status.HTTP_400_BAD_REQUEST)

        # 创建测试套件用例关联，并设置环境（如果提供）
        test_suite_case_data = {
            'test_suite': test_suite,
            'test_case': test_case,
            'order': order
        }

        if environment_id:
            environment = get_object_or_404(Environment, id=environment_id)
            test_suite_case_data['environment'] = environment

        test_suite_case = TestSuiteCase.objects.create(**test_suite_case_data)

        serializer = TestSuiteCaseSerializer(test_suite_case)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_test_case_environment(self, request, pk=None):
        test_suite = self.get_object()
        test_case_id = request.data.get('test_case_id')
        environment_id = request.data.get('environment_id')

        if not test_case_id:
            return Response({"error": "Test case ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        test_suite_case = get_object_or_404(TestSuiteCase, test_suite=test_suite, test_case_id=test_case_id)

        if environment_id:
            environment = get_object_or_404(Environment, id=environment_id)
            test_suite_case.environment = environment
        else:
            test_suite_case.environment = None

        test_suite_case.save()

        serializer = TestSuiteCaseSerializer(test_suite_case)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def remove_test_case(self, request, pk=None):
        test_suite = self.get_object()
        test_case_id = request.data.get('test_case_id')

        if not test_case_id:
            return Response({"error": "Test case ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        test_suite_case = get_object_or_404(TestSuiteCase, test_suite=test_suite, test_case_id=test_case_id)
        test_suite_case.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        test_suite = self.get_object()
        default_environment_id = request.data.get('environment_id')

        if not default_environment_id:
            return Response({"error": "Default environment ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        default_environment = get_object_or_404(Environment, id=default_environment_id)

        # 获取每个测试用例的环境设置
        case_environments = {}
        for key, value in request.data.items():
            if key.startswith('case_environment_') and value:
                case_id = key.replace('case_environment_', '')
                case_environments[int(case_id)] = int(value)

        # Create a test run
        test_run = TestRun.objects.create(
            name=request.data.get('name', f"Suite run: {test_suite.name}"),
            project=test_suite.project,
            test_suite=test_suite,
            environment=default_environment,  # 默认环境
            status='running',
            start_time=timezone.now(),
            created_by=request.user
        )

        # Execute the test suite with custom environments
        results = execute_test_suite(test_suite, default_environment, case_environments)

        # Create test results
        for result in results:
            # 获取测试用例使用的环境
            environment_id = result.get('environment_id', default_environment_id)
            environment = get_object_or_404(Environment, id=environment_id)

            TestResult.objects.create(
                test_run=test_run,
                test_case_id=result['test_case_id'],
                environment=environment,
                status=result['status'],
                response_time=result.get('response_time'),
                response_status_code=result.get('response_status_code'),
                response_headers=result.get('response_headers', {}),
                response_body=result.get('response_body'),
                error_message=result.get('error_message', ''),
                extracted_params=result.get('extracted_params', {})
            )

        # Update test run
        failed_results = [r for r in results if r['status'] != 'passed']
        test_run.status = 'failed' if failed_results else 'completed'
        test_run.end_time = timezone.now()
        test_run.save()

        serializer = TestRunSerializer(test_run)
        return Response(serializer.data)


class TestRunViewSet(viewsets.ModelViewSet):
    queryset = TestRun.objects.all()
    serializer_class = TestRunSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        project_id = self.request.query_params.get('project', None)
        if project_id:
            return TestRun.objects.filter(project_id=project_id).order_by('-created_at')
        return TestRun.objects.all().order_by('-created_at')

    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        test_run = self.get_object()
        results = TestResult.objects.filter(test_run=test_run)

        # 使用分页
        paginator = StandardResultsSetPagination()
        paginated_results = paginator.paginate_queryset(results, request)

        serializer = TestResultSerializer(paginated_results, many=True)
        return paginator.get_paginated_response(serializer.data)


class TestResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TestResult.objects.all()
    serializer_class = TestResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        test_run_id = self.request.query_params.get('test_run', None)
        if test_run_id:
            return TestResult.objects.filter(test_run_id=test_run_id).order_by('-created_at')
        return TestResult.objects.all().order_by('-created_at')
