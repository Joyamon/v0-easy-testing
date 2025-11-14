from rest_framework import serializers
from django.contrib.auth.models import User
from test_manager.models import (
    Project, Environment, TestCase, TestSuite,
    TestSuiteCase, TestRun, TestResult
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class ProjectSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['created_by']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class EnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Environment
        fields = '__all__'


class TestCaseSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = TestCase
        fields = '__all__'
        read_only_fields = ['created_by']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class TestSuiteCaseSerializer(serializers.ModelSerializer):
    test_case_details = TestCaseSerializer(source='test_case', read_only=True)

    class Meta:
        model = TestSuiteCase
        fields = ['id', 'test_case', 'test_case_details', 'order']


class TestSuiteSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    test_suite_cases = TestSuiteCaseSerializer(source='testsuitecase_set', many=True, read_only=True)

    class Meta:
        model = TestSuite
        fields = ['id', 'name', 'project', 'description', 'created_at', 'updated_at', 'created_by', 'test_suite_cases']
        read_only_fields = ['created_by']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class TestRunSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = TestRun
        fields = '__all__'
        read_only_fields = ['created_by', 'status', 'start_time', 'end_time']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        validated_data['status'] = 'pending'
        return super().create(validated_data)


class TestResultSerializer(serializers.ModelSerializer):
    test_case_details = TestCaseSerializer(source='test_case', read_only=True)

    class Meta:
        model = TestResult
        fields = '__all__'
