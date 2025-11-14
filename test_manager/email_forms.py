from django import forms
from .email_config import EmailConfig

class EmailConfigForm(forms.ModelForm):
    """邮件配置表单"""
    
    class Meta:
        model = EmailConfig
        fields = [
            'name', 'is_active', 'email_backend',
            'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
            'smtp_use_tls', 'smtp_use_ssl',
            'api_key',
            'default_from_email', 'default_from_name',
        ]
        widgets = {
            'smtp_password': forms.PasswordInput(render_value=True),
            'api_key': forms.PasswordInput(render_value=True),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 添加帮助文本
        self.fields['smtp_host'].help_text = "例如: smtp.gmail.com, smtp.qq.com"
        self.fields['smtp_port'].help_text = "常见端口: 25, 465(SSL), 587(TLS)"
        self.fields['api_key'].help_text = "如果使用 SendGrid 或 Mailgun，请输入 API 密钥"
        self.fields['default_from_email'].help_text = "发件人邮箱地址"
        self.fields['default_from_name'].help_text = "发件人显示名称"
        
        # 设置必填字段
        self.fields['name'].required = True
        self.fields['default_from_email'].required = True
        self.fields['default_from_name'].required = True

class TestEmailForm(forms.Form):
    """测试邮件表单"""
    email = forms.EmailField(label="测试邮箱", help_text="用于接收测试邮件的邮箱地址")
