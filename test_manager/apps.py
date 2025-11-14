from django.apps import AppConfig


class TestManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'test_manager'
    verbose_name = "测试管理"

    def ready(self):
        """应用启动时执行的操作"""
        # 导入信号处理器
        import test_manager.signals

        # 加载邮件配置
        try:
            from test_manager.models import EmailConfig
            EmailConfig.apply_active_config()
        except:
            pass
