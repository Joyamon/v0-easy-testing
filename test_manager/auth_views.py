from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.models import User
from django import forms


class CustomUserCreationForm(UserCreationForm):
    """扩展默认的用户创建表单，添加电子邮件字段"""
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


def register_view(request):
    """用户注册视图"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # 自动登录新注册的用户
            login(request, user)
            messages.success(request, f"账户创建成功！欢迎 {user.username}！")
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'auth/register.html', {'form': form})


def profile_view(request):
    """用户个人资料视图"""
    return render(request, 'auth/profile.html')


class UserProfileForm(forms.ModelForm):
    """用户个人资料表单"""
    first_name = forms.CharField(max_length=30, required=False, label='名字')
    last_name = forms.CharField(max_length=30, required=False, label='姓氏')
    email = forms.EmailField(required=True, label='电子邮件')

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


def edit_profile_view(request):
    """编辑用户个人资料视图"""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '个人资料已更新！')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'auth/edit_profile.html', {'form': form})
