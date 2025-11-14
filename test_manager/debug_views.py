让我们更新调试模板，添加强制清理按钮：

```html file="templates/test_manager/debug/scheduled_tasks.html"
[v0-no-op-code-block-prefix]<!DOCTYPE html>
<html>
<head>
    <title>Scheduled Tasks</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.3/dist/umd/popper.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
</head>
<body>
    <div class="container">
        <h1>Scheduled Tasks</h1>
        <p>This page displays the currently scheduled Celery Beat tasks.</p>

        <form id="csrfForm">
            {% csrf_token %}
        </form>

        <table class="table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Task</th>
                    <th>Schedule</th>
                    <th>Args</th>
                    <th>Kwargs</th>
                    <th>Last Run At</th>
                    <th>Total Run Count</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for task in tasks %}
                    <tr>
                        <td>{{ task.id }}</td>
                        <td>{{ task.name }}</td>
                        <td>{{ task.task }}</td>
                        <td>{{ task.schedule }}</td>
                        <td>{{ task.args }}</td>
                        <td>{{ task.kwargs }}</td>
                        <td>{{ task.last_run_at }}</td>
                        <td>{{ task.total_run_count }}</td>
                        <td>{{ task.status }}</td>
                        <!-- 在每个任务行中添加强制清理按钮 -->
                        <td>
                            <div class="btn-group" role="group">
                                <button type="button" class="btn btn-sm btn-primary" onclick="syncTask({{ task.id }})">
                                    同步
                                </button>
                                <button type="button" class="btn btn-sm btn-warning" onclick="forceCleanupTask({{ task.id }})">
                                    强制清理
                                </button>
                                {% if task.status == 'active' %}
                                    <button type="button" class="btn btn-sm btn-secondary" onclick="toggleTaskStatus({{ task.id }})">
                                        暂停
                                    </button>
                                {% else %}
                                    <button type="button" class="btn btn-sm btn-success" onclick="toggleTaskStatus({{ task.id }})">
                                        激活
                                    </button>
                                {% endif %}
                            </div>
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <script>
        function syncTask(taskId) {
            fetch(`/debug/scheduled-tasks/${taskId}/sync/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/json',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(`Task synced successfully: ${data.message}`);
                    location.reload();
                } else {
                    alert(`Task sync failed: ${data.message}`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Task sync request failed');
            });
        }

        function toggleTaskStatus(taskId) {
            fetch(`/debug/scheduled-tasks/${taskId}/toggle/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/json',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(`Task status toggled successfully: ${data.message}`);
                    location.reload();
                } else {
                    alert(`Task status toggle failed: ${data.message}`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Task status toggle request failed');
            });
        }

        // 在JavaScript部分添加强制清理函数
        function forceCleanupTask(taskId) {
            if (!confirm('确定要强制清理这个任务的所有Celery Beat记录吗？')) {
                return;
            }
            
            fetch(`/debug/scheduled-tasks/${taskId}/force-cleanup/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/json',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(`强制清理成功: ${data.message}`);
                    location.reload();
                } else {
                    alert(`强制清理失败: ${data.message}`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('强制清理请求失败');
            });
        }
    </script>
</body>
</html>
