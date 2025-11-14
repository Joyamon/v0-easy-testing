from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """当新用户注册时发送欢迎邮件"""
    if created and instance.email:
        try:
            # 准备邮件内容
            context = {
                'user': instance,
                'site_name': 'EasyTesting',
                'site_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000',
            }
            html_message = render_to_string('emails/welcome_email.html', context)
            plain_message = strip_tags(html_message)

            # 发送邮件
            send_mail(
                subject='欢迎加入 EasyTesting',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception as e:
            # 记录错误但不中断用户创建流程
            print(f"发送欢迎邮件失败: {str(e)}")
