import uuid
from django.urls import reverse
from django.db import models
from django.contrib.auth.models import User
import json


class Project(models.Model):
    name = models.CharField(max_length=100, verbose_name="项目名称", db_comment="项目名称")
    description = models.TextField(blank=True, verbose_name="项目描述", db_comment="项目描述")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_projects',
                                   verbose_name="创建人", db_comment="创建人")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "项目"
        verbose_name_plural = verbose_name


class Environment(models.Model):
    name = models.CharField(max_length=100, verbose_name="环境名称", db_comment="环境名称")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='environments', verbose_name="所属项目",
                                db_comment="所属环境")
    base_url = models.URLField(verbose_name="环境URL", db_comment="环境URL")
    variables = models.JSONField(default=dict, blank=True, verbose_name="环境变量", db_comment="环境变量")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    class Meta:
        verbose_name = "环境"
        verbose_name_plural = verbose_name


# 测试用例分组
class TestCaseGroup(models.Model):
    name = models.CharField(max_length=100, verbose_name="分组名称", db_comment="分组名称")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_case_groups',
                                verbose_name="所属项目", db_comment="所属项目")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children',
                               verbose_name="父分组", db_comment="父分组")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_test_case_groups',
                                   verbose_name="创建人", db_comment="创建人")

    def __str__(self):
        if self.parent:
            return f"{self.parent} / {self.name}"
        return self.name

    class Meta:
        unique_together = ('name', 'project', 'parent')
        ordering = ['name']
        verbose_name = "用例分组"
        verbose_name_plural = verbose_name


class TestCase(models.Model):
    REQUEST_BODY_FORMAT_CHOICES = [
        ('json', 'JSON'),
        ('form-data', 'Form Data'),
    ]

    name = models.CharField(max_length=100, verbose_name="用例名称", db_comment="用例名称")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_cases', verbose_name="所属项目",
                                db_comment="所属项目")
    group = models.ForeignKey(TestCaseGroup, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='test_cases', verbose_name="用例分组", db_comment="用例分组")
    description = models.TextField(blank=True, verbose_name="用例描述", db_comment="用例描述")
    request_method = models.CharField(max_length=10, choices=[
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
        ('PATCH', 'PATCH'),
    ], verbose_name="请求方法", db_comment="请求方法")
    request_url = models.CharField(max_length=500, verbose_name="请求URL", db_comment="请求URL")
    request_headers = models.JSONField(default=dict, blank=True, verbose_name="请求头", db_comment="请求头")
    request_body = models.JSONField(default=dict, blank=True, null=True, verbose_name="请求体", db_comment="请求体")
    request_body_format = models.CharField(max_length=20, choices=REQUEST_BODY_FORMAT_CHOICES, default='json',
                                           verbose_name="请求体格式", db_comment="请求体格式")
    expected_status_code = models.IntegerField(default=200, verbose_name="期望状态码", db_comment="期望状态码")
    validation_rules = models.JSONField(default=list, blank=True, verbose_name="验证规则", db_comment="验证规则")
    extract_params = models.JSONField(default=list, blank=True, verbose_name="提取参数",
                                      db_comment="提取参数")  # 新增字段，用于存储提取的参数
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_test_cases',
                                   verbose_name="创建人", db_comment="创建人")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "测试用例"
        verbose_name_plural = verbose_name


# 新增测试套件分组模型
class TestSuiteGroup(models.Model):
    name = models.CharField(max_length=100, verbose_name="分组名称", db_comment="分组名称")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_suite_groups',
                                verbose_name="所属项目", db_comment="所属项目")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children',
                               verbose_name="父分组", db_comment="父分组")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_test_suite_groups',
                                   verbose_name="创建人", db_comment="创建人")

    def __str__(self):
        if self.parent:
            return f"{self.parent} / {self.name}"
        return self.name

    class Meta:
        unique_together = ('name', 'project', 'parent')
        ordering = ['name']
        verbose_name = "套件分组"
        verbose_name_plural = verbose_name


class TestSuite(models.Model):
    name = models.CharField(max_length=100, verbose_name="套件名称", db_comment="套件名称")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_suites', verbose_name="所属项目",
                                db_comment="所属项目")
    group = models.ForeignKey(TestSuiteGroup, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='test_suites', verbose_name="套件分组", db_comment="套件分组")
    description = models.TextField(blank=True, verbose_name="套件描述", db_comment="套件描述")
    test_cases = models.ManyToManyField(TestCase, through='TestSuiteCase', verbose_name="关联用例",
                                        db_comment="关联用例")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_test_suites',
                                   verbose_name="创建人", db_comment="创建人")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "测试套件"
        verbose_name_plural = verbose_name


class TestSuiteCase(models.Model):
    test_suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE)
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE)
    environment = models.ForeignKey(Environment, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='test_suite_cases')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']


class TestRun(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    name = models.CharField(max_length=100, verbose_name="运行名称", db_comment="运行名称")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_runs', verbose_name="所属项目",
                                db_comment="所属项目")
    test_suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='test_runs', null=True, blank=True,
                                   verbose_name="测试套件", db_comment="测试套件")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name='test_runs',
                                    verbose_name="运行环境", db_comment="运行环境")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="运行状态",
                              db_comment="运行状态")
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="开始时间", db_comment="开始时间")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="结束时间", db_comment="结束时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_test_runs',
                                   verbose_name="创建人", db_comment="创建人")

    def __str__(self):
        return self.name

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    class Meta:
        verbose_name = "测试运行"
        verbose_name_plural = verbose_name


class TestResult(models.Model):
    STATUS_CHOICES = [
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
        ('skipped', 'Skipped'),
    ]

    test_run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name='test_results',
                                 verbose_name="测试运行", db_comment="测试运行")
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='test_results',
                                  verbose_name="测试用例", db_comment="测试用例")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name='test_results',
                                    verbose_name="运行环境", db_comment="运行环境")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name="运行状态", db_comment="运行状态")
    response_time = models.FloatField(null=True, blank=True, verbose_name="响应时间",
                                      db_comment="响应时间")  # in milliseconds
    response_status_code = models.IntegerField(null=True, blank=True, verbose_name="响应状态码",
                                               db_comment="响应状态码")
    response_headers = models.JSONField(default=dict, blank=True, verbose_name="响应头", db_comment="响应头")
    response_body = models.JSONField(default=dict, blank=True, null=True, verbose_name="响应体", db_comment="响应体")
    request_headers = models.JSONField(default=dict, blank=True, verbose_name="请求头", db_comment="请求头")
    request_body = models.JSONField(default=dict, blank=True, null=True, verbose_name="请求体", db_comment="请求体")
    error_message = models.TextField(blank=True, verbose_name="错误信息", db_comment="错误信息")
    extracted_params = models.JSONField(default=dict, blank=True, verbose_name="提取参数", db_comment="提取参数")
    validators = models.JSONField(default=list, blank=True, verbose_name="验证器", db_comment="验证器")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")

    def __str__(self):
        return f"{self.test_case.name} - {self.status}"

    class Meta:
        verbose_name = "测试结果"
        verbose_name_plural = verbose_name


from django.db import models
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.exceptions import ValidationError
import smtplib
import ssl


class EmailConfig(models.Model):
    """邮件配置模型"""
    EMAIL_BACKEND_CHOICES = [
        ('smtp', 'SMTP'),
        ('sendgrid', 'SendGrid API'),
        ('mailgun', 'Mailgun API'),
    ]

    name = models.CharField(max_length=100, verbose_name="配置名称", db_comment="配置名称")
    is_active = models.BooleanField(default=False, verbose_name="是否激活", db_comment="是否激活")
    email_backend = models.CharField(
        max_length=20,
        choices=EMAIL_BACKEND_CHOICES,
        default='smtp',
        verbose_name="邮件后端",
        db_comment="邮件后端"
    )

    # SMTP 设置
    smtp_host = models.CharField(max_length=255, blank=True, verbose_name="SMTP 服务器", db_comment="SMTP 服务器")
    smtp_port = models.IntegerField(default=587, blank=True, null=True, verbose_name="SMTP 端口",
                                    db_comment="SMTP 端口")
    smtp_username = models.CharField(max_length=255, blank=True, verbose_name="SMTP 用户名", db_comment="SMTP 用户名")
    smtp_password = models.CharField(max_length=255, blank=True, verbose_name="SMTP 密码", db_comment="SMTP 密码")
    smtp_use_tls = models.BooleanField(default=True, verbose_name="使用 TLS", db_comment="使用 TLS")
    smtp_use_ssl = models.BooleanField(default=False, verbose_name="使用 SSL", db_comment="使用 SSL")

    # API 密钥设置
    api_key = models.CharField(max_length=255, blank=True, verbose_name="API 密钥", db_comment="API 密钥")

    # 通用设置
    default_from_email = models.EmailField(verbose_name="默认发件人邮箱", db_comment="默认发件人邮箱")
    default_from_name = models.CharField(max_length=100, verbose_name="默认发件人名称", db_comment="默认发件人名称")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")

    class Meta:
        verbose_name = "邮件配置"
        verbose_name_plural = "邮件配置"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # 如果当前配置被设置为激活，则将其他配置设置为非激活
        if self.is_active:
            EmailConfig.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)

    def clean(self):
        """验证邮件配置"""
        if self.email_backend == 'smtp':
            if not self.smtp_host or not self.smtp_username or not self.smtp_password:
                raise ValidationError("SMTP 配置需要填写服务器、用户名和密码")
        elif self.email_backend in ['sendgrid', 'mailgun']:
            if not self.api_key:
                raise ValidationError(f"{self.get_email_backend_display()} 配置需要填写 API 密钥")

    def test_connection(self):
        """测试邮件连接"""
        if self.email_backend == 'smtp':
            try:
                if self.smtp_use_ssl:
                    server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ssl.create_default_context())
                else:
                    server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                    if self.smtp_use_tls:
                        server.starttls(context=ssl.create_default_context())

                server.login(self.smtp_username, self.smtp_password)
                server.quit()
                return True, "SMTP 连接测试成功"
            except Exception as e:
                return False, f"SMTP 连接测试失败: {str(e)}"
        elif self.email_backend == 'sendgrid':
            # 这里可以添加 SendGrid API 测试代码
            return True, "SendGrid API 配置已保存"
        elif self.email_backend == 'mailgun':
            # 这里可以添加 Mailgun API 测试代码
            return True, "Mailgun API 配置已保存"

        return False, "未知的邮件后端"

    def send_test_email(self, to_email):
        """发送测试邮件"""
        global current_backend, current_host, current_port, current_user, current_password, current_tls, current_ssl, current_from
        subject = "EasyTesting - 测试邮件"
        message = "这是一封测试邮件，用于验证 EasyTesting 的邮件发送功能是否正常工作。"
        from_email = f"{self.default_from_name} <{self.default_from_email}>"

        try:
            # 保存当前设置
            current_backend = settings.EMAIL_BACKEND
            current_host = settings.EMAIL_HOST
            current_port = settings.EMAIL_PORT
            current_user = settings.EMAIL_HOST_USER
            current_password = settings.EMAIL_HOST_PASSWORD
            current_tls = settings.EMAIL_USE_TLS
            current_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
            current_from = settings.DEFAULT_FROM_EMAIL

            # 应用临时设置
            if self.email_backend == 'smtp':
                settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
                settings.EMAIL_HOST = self.smtp_host
                settings.EMAIL_PORT = self.smtp_port
                settings.EMAIL_HOST_USER = self.smtp_username
                settings.EMAIL_HOST_PASSWORD = self.smtp_password
                settings.EMAIL_USE_TLS = self.smtp_use_tls
                settings.EMAIL_USE_SSL = self.smtp_use_ssl
            elif self.email_backend == 'sendgrid':
                settings.EMAIL_BACKEND = 'sendgrid_backend.SendgridBackend'
                settings.SENDGRID_API_KEY = self.api_key
            elif self.email_backend == 'mailgun':
                settings.EMAIL_BACKEND = 'django_mailgun.MailgunBackend'
                settings.MAILGUN_ACCESS_KEY = self.api_key
                settings.MAILGUN_SERVER_NAME = self.smtp_host  # 使用 smtp_host 存储 Mailgun 域名

            settings.DEFAULT_FROM_EMAIL = from_email

            # 发送测试邮件
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_email,
                to=[to_email],
                reply_to=[self.default_from_email],
            )
            email.send(fail_silently=False)

            # 恢复原始设置
            settings.EMAIL_BACKEND = current_backend
            settings.EMAIL_HOST = current_host
            settings.EMAIL_PORT = current_port
            settings.EMAIL_HOST_USER = current_user
            settings.EMAIL_HOST_PASSWORD = current_password
            settings.EMAIL_USE_TLS = current_tls
            settings.EMAIL_USE_SSL = current_ssl
            settings.DEFAULT_FROM_EMAIL = current_from

            return True, "测试邮件发送成功"
        except Exception as e:
            # 恢复原始设置
            settings.EMAIL_BACKEND = current_backend
            settings.EMAIL_HOST = current_host
            settings.EMAIL_PORT = current_port
            settings.EMAIL_HOST_USER = current_user
            settings.EMAIL_HOST_PASSWORD = current_password
            settings.EMAIL_USE_TLS = current_tls
            settings.EMAIL_USE_SSL = current_ssl
            settings.DEFAULT_FROM_EMAIL = current_from

            return False, f"测试邮件发送失败: {str(e)}"

    @classmethod
    def get_active_config(cls):
        """获取当前激活的邮件配置"""
        try:
            return cls.objects.get(is_active=True)
        except cls.DoesNotExist:
            return None

    @classmethod
    def apply_active_config(cls):
        """应用当前激活的邮件配置到 Django 设置"""
        config = cls.get_active_config()
        if not config:
            return False

        if config.email_backend == 'smtp':
            settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
            settings.EMAIL_HOST = config.smtp_host
            settings.EMAIL_PORT = config.smtp_port
            settings.EMAIL_HOST_USER = config.smtp_username
            settings.EMAIL_HOST_PASSWORD = config.smtp_password
            settings.EMAIL_USE_TLS = config.smtp_use_tls
            settings.EMAIL_USE_SSL = config.smtp_use_ssl
        elif config.email_backend == 'sendgrid':
            settings.EMAIL_BACKEND = 'sendgrid_backend.SendgridBackend'
            settings.SENDGRID_API_KEY = config.api_key
        elif config.email_backend == 'mailgun':
            settings.EMAIL_BACKEND = 'django_mailgun.MailgunBackend'
            settings.MAILGUN_ACCESS_KEY = config.api_key
            settings.MAILGUN_SERVER_NAME = config.smtp_host  # 使用 smtp_host 存储 Mailgun 域名

        settings.DEFAULT_FROM_EMAIL = f"{config.default_from_name} <{config.default_from_email}>"
        return True


class TestSuiteRun(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_suite_runs')
    test_suite = models.ForeignKey(TestSuite, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='test_suite_runs')
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name='test_suite_runs')
    status = models.CharField(max_length=20, choices=TestRun.STATUS_CHOICES, default='pending')
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_test_suite_runs')

    def __str__(self):
        return self.name

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class TestReport(models.Model):
    """测试报告模型"""
    REPORT_TYPE_CHOICES = [
        ('test_run', 'Test Run'),
        ('test_suite_run', 'Test Suite Run'),
        ('custom', 'Custom'),
    ]

    REPORT_FORMAT_CHOICES = [
        ('html', 'HTML'),
        ('pdf', 'PDF'),
        ('json', 'JSON'),
    ]

    name = models.CharField(max_length=255, verbose_name="报告名称", db_comment="报告名称")
    description = models.TextField(null=True, blank=True, verbose_name="报告描述", db_comment="报告描述")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_reports', verbose_name="项目",
                                db_comment="项目")
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='test_run',
                                   verbose_name="报告类型", db_comment="报告类型")
    report_format = models.CharField(max_length=10, choices=REPORT_FORMAT_CHOICES, default='html',
                                     verbose_name="报告格式", db_comment="报告格式")
    content = models.TextField(verbose_name="报告内容", db_comment="报告内容")
    test_run = models.ForeignKey(TestRun, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports',
                                 verbose_name="测试运行", db_comment="测试运行")
    test_suite_run = models.ForeignKey(TestSuiteRun, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='reports', verbose_name="测试套件运行", db_comment="测试套件运行")
    test_results = models.ForeignKey(TestResult, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='reports', verbose_name="测试结果", db_comment="测试结果")
    is_public = models.BooleanField(default=False, verbose_name="公开", db_comment="公开")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='created_test_reports', verbose_name="创建者", db_comment="创建者")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "测试报告"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('test_report_detail', kwargs={'pk': self.pk})

    def get_delete_url(self):
        return reverse('test_report_delete', kwargs={'pk': self.pk})

    def get_summary(self):
        """返回报告的摘要信息"""
        if self.report_format == 'json':
            try:
                data = json.loads(self.content)
                return {
                    'total': data.get('total', 0),
                    'passed': data.get('passed', 0),
                    'failed': data.get('failed', 0),
                    'error': data.get('error', 0),
                    'skipped': data.get('skipped', 0),
                    'success_rate': data.get('success_rate', '0%'),
                }
            except:
                return {}
        return {}


class MockData(models.Model):
    """模拟数据模型"""
    aim = models.CharField(max_length=255, verbose_name="用途", db_comment="用途")
    data = models.TextField(verbose_name="mock数据", db_comment="mock数据")
    description = models.TextField(verbose_name="数据描述", db_comment="数据描述", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_mock_data',
                                   verbose_name="创建人", db_comment="创建人")

    def __str__(self):
        return self.description
    @property
    def count_data(self):
        return len(json.loads(self.data))

    class Meta:
        verbose_name = "模拟数据"
        verbose_name_plural = verbose_name


# 新增定时任务相关模型
class ScheduledTask(models.Model):
    """定时任务模型"""
    SCHEDULE_TYPE_CHOICES = [
        ('once', '单次执行'),
        ('daily', '每日执行'),
        ('weekly', '每周执行'),
        ('monthly', '每月执行'),
        ('cron', 'Cron表达式'),
    ]

    STATUS_CHOICES = [
        ('active', '激活'),
        ('inactive', '停用'),
        ('paused', '暂停'),
    ]

    name = models.CharField(max_length=200, verbose_name="任务名称", db_comment="任务名称")
    description = models.TextField(blank=True, verbose_name="任务描述", db_comment="任务描述")
    test_suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='scheduled_tasks',
                                   verbose_name="测试套件", db_comment="测试套件")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name='scheduled_tasks',
                                    verbose_name="执行环境", db_comment="执行环境",null=True, blank=True)

    # 调度配置
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES, default='daily',
                                     verbose_name="调度类型", db_comment="调度类型")
    cron_expression = models.CharField(max_length=100, blank=True, verbose_name="Cron表达式",
                                       db_comment="Cron表达式", help_text="仅当调度类型为Cron时使用")

    # 时间配置
    scheduled_time = models.TimeField(null=True, blank=True, verbose_name="执行时间",
                                      db_comment="执行时间", help_text="每日/每周/每月执行的具体时间")
    scheduled_date = models.DateField(null=True, blank=True, verbose_name="执行日期",
                                      db_comment="执行日期", help_text="单次执行的日期")
    weekday = models.IntegerField(null=True, blank=True, verbose_name="星期几",
                                  db_comment="星期几", help_text="每周执行时的星期几(1-7)")
    day_of_month = models.IntegerField(null=True, blank=True, verbose_name="每月第几天",
                                       db_comment="每月第几天", help_text="每月执行时的日期(1-31)")

    # 任务状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active',
                              verbose_name="任务状态", db_comment="任务状态")
    is_enabled = models.BooleanField(default=True, verbose_name="是否启用", db_comment="是否启用")

    # 通知配置
    send_email_notification = models.BooleanField(default=True, verbose_name="发送邮件通知",
                                                  db_comment="发送邮件通知")
    notification_emails = models.TextField(blank=True, verbose_name="通知邮箱",
                                           db_comment="通知邮箱", help_text="多个邮箱用逗号分隔")
    notify_on_success = models.BooleanField(default=False, verbose_name="成功时通知",
                                            db_comment="成功时通知")
    notify_on_failure = models.BooleanField(default=True, verbose_name="失败时通知",
                                            db_comment="失败时通知")


    max_retries = models.IntegerField(default=3, verbose_name="最大重试次数", db_comment="最大重试次数")
    retry_delay = models.IntegerField(default=300, verbose_name="重试间隔(秒)", db_comment="重试间隔(秒)")

    # 执行统计
    last_run_time = models.DateTimeField(null=True, blank=True, verbose_name="上次执行时间",
                                         db_comment="上次执行时间")
    next_run_time = models.DateTimeField(null=True, blank=True, verbose_name="下次执行时间",
                                         db_comment="下次执行时间")
    total_runs = models.IntegerField(default=0, verbose_name="总执行次数", db_comment="总执行次数")
    successful_runs = models.IntegerField(default=0, verbose_name="成功次数", db_comment="成功次数")
    failed_runs = models.IntegerField(default=0, verbose_name="失败次数", db_comment="失败次数")

    # Celery任务ID
    celery_task_id = models.CharField(max_length=255, blank=True, verbose_name="Celery任务ID",
                                      db_comment="Celery任务ID")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", db_comment="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间", db_comment="更新时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_scheduled_tasks',
                                   verbose_name="创建人", db_comment="创建人")

    def __str__(self):
        return f"{self.name} - {self.test_suite.name}"

    class Meta:
        verbose_name = "定时任务"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def get_notification_email_list(self):
        """获取通知邮箱列表"""
        if not self.notification_emails:
            return []
        return [email.strip() for email in self.notification_emails.split(',') if email.strip()]

    def calculate_next_run_time(self):
        """计算下次执行时间"""
        from datetime import datetime, timedelta
        import calendar

        now = datetime.now()

        if self.schedule_type == 'once':
            if self.scheduled_date and self.scheduled_time:
                next_run = datetime.combine(self.scheduled_date, self.scheduled_time)
                return next_run if next_run > now else None

        elif self.schedule_type == 'daily':
            if self.scheduled_time:
                next_run = datetime.combine(now.date(), self.scheduled_time)
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run

        elif self.schedule_type == 'weekly':
            if self.weekday and self.scheduled_time:
                days_ahead = self.weekday - now.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                next_run = datetime.combine(now.date(), self.scheduled_time) + timedelta(days=days_ahead)
                return next_run

        elif self.schedule_type == 'monthly':
            if self.day_of_month and self.scheduled_time:
                # 计算下个月的执行时间
                if now.day < self.day_of_month:
                    # 本月还没到执行日期
                    try:
                        next_run = datetime.combine(
                            now.replace(day=self.day_of_month).date(),
                            self.scheduled_time
                        )
                        return next_run
                    except ValueError:
                        # 当月没有这一天，跳到下个月
                        pass

                # 计算下个月
                if now.month == 12:
                    next_year = now.year + 1
                    next_month = 1
                else:
                    next_year = now.year
                    next_month = now.month + 1

                # 确保下个月有这一天
                max_day = calendar.monthrange(next_year, next_month)[1]
                target_day = min(self.day_of_month, max_day)

                next_run = datetime.combine(
                    datetime(next_year, next_month, target_day).date(),
                    self.scheduled_time
                )
                return next_run

        elif self.schedule_type == 'cron' and self.cron_expression:
            # 这里需要使用cron解析库，如croniter
            try:
                from croniter import croniter
                cron = croniter(self.cron_expression, now)
                return cron.get_next(datetime)
            except ImportError:
                # 如果没有安装croniter，返回None
                pass

        return None

    def update_next_run_time(self):
        """更新下次执行时间"""
        self.next_run_time = self.calculate_next_run_time()
        self.save(update_fields=['next_run_time'])

    @property
    def success_rate(self):
        """成功率"""
        if self.total_runs == 0:
            return 0
        return (self.successful_runs / self.total_runs) * 100


class TaskExecutionLog(models.Model):
    """任务执行日志"""
    STATUS_CHOICES = [
        ('running', '运行中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('timeout', '超时'),
        ('cancelled', '已取消'),
    ]

    scheduled_task = models.ForeignKey(ScheduledTask, on_delete=models.CASCADE, related_name='execution_logs',
                                       verbose_name="定时任务", db_comment="定时任务")
    test_run = models.ForeignKey(TestRun, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='task_execution_logs', verbose_name="测试运行", db_comment="测试运行")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running',
                              verbose_name="执行状态", db_comment="执行状态")
    start_time = models.DateTimeField(auto_now_add=True, verbose_name="开始时间", db_comment="开始时间")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="结束时间", db_comment="结束时间")
    duration = models.FloatField(null=True, blank=True, verbose_name="执行时长(秒)", db_comment="执行时长(秒)")

    # 执行结果统计
    total_test_cases = models.IntegerField(default=0, verbose_name="总测试用例数", db_comment="总测试用例数")
    passed_test_cases = models.IntegerField(default=0, verbose_name="通过用例数", db_comment="通过用例数")
    failed_test_cases = models.IntegerField(default=0, verbose_name="失败用例数", db_comment="失败用例数")
    error_test_cases = models.IntegerField(default=0, verbose_name="错误用例数", db_comment="错误用例数")

    error_message = models.TextField(blank=True, verbose_name="错误信息", db_comment="错误信息")
    retry_count = models.IntegerField(default=0, verbose_name="重试次数", db_comment="重试次数")

    # 通知状态
    email_sent = models.BooleanField(default=False, verbose_name="邮件已发送", db_comment="邮件已发送")
    email_sent_time = models.DateTimeField(null=True, blank=True, verbose_name="邮件发送时间",
                                           db_comment="邮件发送时间")

    def __str__(self):
        return f"{self.scheduled_task.name} - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = "任务执行日志"
        verbose_name_plural = verbose_name
        ordering = ['-start_time']

    @property
    def success_rate(self):
        """成功率"""
        if self.total_test_cases == 0:
            return 0
        return (self.passed_test_cases / self.total_test_cases) * 100

    def calculate_duration(self):
        """计算执行时长"""
        if self.start_time and self.end_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
            return self.duration
        return None
#
#
# # 信号处理器
# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver
#
#
# @receiver(post_save, sender=ScheduledTask)
# def handle_scheduled_task_save(sender, instance, created, **kwargs):
#     """处理定时任务保存信号"""
#     from .scheduler import TaskScheduler
#
#     # 创建或更新Celery任务
#     TaskScheduler.create_or_update_celery_task(instance)
#
#
# @receiver(post_delete, sender=ScheduledTask)
# def handle_scheduled_task_delete(sender, instance, **kwargs):
#     """处理定时任务删除信号 - 优化版本"""
#     import logging
#     logger = logging.getLogger(__name__)
#
#     try:
#         logger.info(f"信号处理器: 开始处理定时任务删除 - {instance.name}")
#
#         # 删除对应的Celery任务
#         if instance.celery_task_id:
#             try:
#                 from django_celery_beat.models import PeriodicTask
#                 celery_task = PeriodicTask.objects.get(name=instance.celery_task_id)
#                 celery_task.delete()
#                 logger.info(f"信号处理器: 成功删除Celery Beat任务 - {instance.celery_task_id}")
#             except PeriodicTask.DoesNotExist:
#                 logger.warning(f"信号处理器: Celery Beat任务不存在 - {instance.celery_task_id}")
#             except Exception as e:
#                 logger.error(f"信号处理器: 删除Celery Beat任务失败 - {str(e)}")
#         else:
#             logger.info(f"信号处理器: 任务没有关联的Celery Beat任务 - {instance.name}")
#
#     except Exception as e:
#         logger.error(f"信号处理器: 处理定时任务删除失败 - {str(e)}")
