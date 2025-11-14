from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet, EnvironmentViewSet, TestCaseViewSet,
    TestSuiteViewSet, TestRunViewSet, TestResultViewSet
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'environments', EnvironmentViewSet)
router.register(r'test-cases', TestCaseViewSet)
router.register(r'test-suites', TestSuiteViewSet)
router.register(r'test-runs', TestRunViewSet)
router.register(r'test-results', TestResultViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls')),
]
