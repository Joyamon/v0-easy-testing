from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """在社交账户登录之前执行的操作"""
        # 如果用户是第一次使用这个社交账户登录
        if not sociallogin.is_existing:
            # 如果用户已经登录，则将社交账户连接到当前用户
            if request.user.is_authenticated:
                sociallogin.connect(request, request.user)
                messages.success(request, f"已成功连接 {sociallogin.account.provider.capitalize()} 账户！")
                return
        
        # 如果用户已经存在，但电子邮件不匹配，则尝试通过电子邮件查找用户
        if not sociallogin.is_existing and sociallogin.account.provider == 'google':
            try:
                email = sociallogin.account.extra_data['email']
                from django.contrib.auth.models import User
                user = User.objects.get(email=email)
                sociallogin.connect(request, user)
            except User.DoesNotExist:
                pass
