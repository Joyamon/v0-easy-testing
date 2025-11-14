## 定时任务功能

### 安装Redis
\`\`\`bash
# Ubuntu/Debian
sudo apt-get install redis-server

# CentOS/RHEL
sudo yum install redis

# macOS
brew install redis
\`\`\`

### 启动服务
1. 启动Redis服务：
\`\`\`bash
redis-server
\`\`\`

2. 启动Django应用：
\`\`\`bash
python manage.py runserver
\`\`\`

3. 启动Celery Worker（新终端）：
\`\`\`bash
celery -A easy_testing worker --loglevel=info
\`\`\`

4. 启动Celery Beat（新终端）：
\`\`\`bash
celery -A easy_testing beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
\`\`\`

### 同步定时任务
如果定时任务没有执行，可以手动同步：
\`\`\`bash
python manage.py sync_scheduled_tasks --cleanup
\`\`\`

### 调试定时任务
访问 `/debug/scheduled-tasks/` 查看定时任务状态（需要超级用户权限）
