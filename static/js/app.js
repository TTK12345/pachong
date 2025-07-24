// WebSocket连接
const socket = io();

// 多任务状态管理
let allTasks = new Map(); // 存储所有任务
let taskDetailModal = null;
let currentDetailTaskId = null;

// 搜索功能相关变量
let allSummariesData = [];
let allLogsData = [];

// DOM元素缓存
const crawlerForm = document.getElementById('crawler-form');
const startBtn = document.getElementById('start-btn');
const batchStopBtn = document.getElementById('batch-stop-btn');
const connectionStatus = document.getElementById('connection-status');
const tasksContainer = document.getElementById('tasks-container');
const noTasksMessage = document.getElementById('no-tasks-message');

// 统计badge元素
const totalTasksBadge = document.getElementById('total-tasks');
const runningTasksBadge = document.getElementById('running-tasks');
const completedTasksBadge = document.getElementById('completed-tasks');
const errorTasksBadge = document.getElementById('error-tasks');

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    initSearchListeners(); // 初始化搜索功能监听器
    loadFiles(''); // 默认展示全部文件
    initializeCrawlerTypeVisibility(); // 初始化爬虫类型相关的UI
    loadAllTasks(); // 加载所有任务
    
    // 初始化任务详情Modal
    taskDetailModal = new bootstrap.Modal(document.getElementById('task-detail-modal'));
    
    // 只有当页面上有目录选择容器时才加载目录树
    if (document.getElementById('dir-select-container')) {
        loadDirTree();
    }

    // 简化的事件处理 - 处理爬虫类型选择
    document.addEventListener('click', function(e) {
        console.log('页面点击事件:', e.target);
        
        // 检查是否点击了下拉菜单项
        let clickedItem = null;
        
        // 方法1：检查点击的元素本身
        if (e.target.hasAttribute && e.target.hasAttribute('data-value')) {
            clickedItem = e.target;
            console.log('直接点击的元素有data-value:', e.target);
        }
        
        // 方法2：检查父级元素
        if (!clickedItem) {
            clickedItem = e.target.closest('[data-value]');
            if (clickedItem) {
                console.log('父级元素有data-value:', clickedItem);
            }
        }
        
        // 如果找到了有data-value的元素
        if (clickedItem) {
            e.preventDefault();
            e.stopPropagation();
            
            const value = clickedItem.getAttribute('data-value');
            const text = clickedItem.getAttribute('data-text');
            
            console.log('选择了爬虫类型：', value, text);
            
            // 更新隐藏的input值
            const crawlerTypeInput = document.getElementById('crawlerType');
            if (crawlerTypeInput) {
                crawlerTypeInput.value = value;
                console.log('更新input值：', value);
            }
            
            // 更新按钮显示文本 - 包含图标和文本
            const dropdownButton = document.getElementById('crawlerTypeDropdown');
            if (dropdownButton && text) {
                // 根据爬虫类型添加相应的图标，使用柔和的颜色
                let iconHtml = '';
                if (value.startsWith('mem_')) {
                    iconHtml = '<i class="bi bi-shield-check text-soft-blue me-2"></i>';
                } else if (value.startsWith('flk_')) {
                    iconHtml = '<i class="bi bi-journal-bookmark text-soft-green me-2"></i>';
                } else if (value === 'custom') {
                    iconHtml = '<i class="bi bi-globe text-secondary me-2"></i>';
                }
                
                dropdownButton.innerHTML = iconHtml + text;
                console.log('更新按钮文本：', text);
            }
            
            // 关闭所有下拉菜单
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                menu.classList.remove('show');
            });
            
            // 处理显示逻辑
            const maxPagesGroup = document.getElementById('max-pages-group');
            const pageUrlGroup = document.getElementById('page-url-group');
            
            if (value === 'custom') {
                // 自定义页面：隐藏最大页数，显示页面网址
                if (maxPagesGroup) maxPagesGroup.style.display = 'none';
                if (pageUrlGroup) pageUrlGroup.style.display = 'block';
            } else {
                // 其他所有类型：显示最大页数，隐藏页面网址
                if (maxPagesGroup) maxPagesGroup.style.display = 'block';
                if (pageUrlGroup) pageUrlGroup.style.display = 'none';
            }
        }
    });
    
    // 处理移动端子菜单显示
    document.querySelectorAll('.dropdown-submenu > .dropdown-item').forEach(item => {
        item.addEventListener('click', function(e) {
            if (window.innerWidth <= 768) {
                e.preventDefault();
                e.stopPropagation();
                
                const submenu = this.parentElement;
                submenu.classList.toggle('show');
                
                // 关闭其他打开的子菜单
                document.querySelectorAll('.dropdown-submenu.show').forEach(menu => {
                    if (menu !== submenu) {
                        menu.classList.remove('show');
                    }
                });
            }
        });
    });
});

// 统一管理所有事件监听器
function initializeEventListeners() {
    crawlerForm.addEventListener('submit', handleAddTask);
    batchStopBtn.addEventListener('click', handleBatchStop);
    document.getElementById('refresh-files').addEventListener('click', () => loadFiles(currentDirPath));
    document.getElementById('download-all').addEventListener('click', downloadAllFiles);
    // 爬虫类型变化处理由二级下拉菜单处理
    document.getElementById('logs-history-tab').addEventListener('shown.bs.tab', loadLogHistory);
    document.getElementById('task-summary-tab').addEventListener('shown.bs.tab', function() {
        console.log('[DEBUG] 任务总结标签页被激活');
        loadTaskSummaries();
    });
    document.getElementById('detail-stop-btn').addEventListener('click', handleStopTaskFromDetail);
    
    // 知识库上传相关事件
    document.getElementById('upload-to-kb-btn').addEventListener('click', showKnowledgeBaseModal);
    document.getElementById('select-all-files').addEventListener('change', handleSelectAllFiles);
    document.getElementById('start-upload-btn').addEventListener('click', startUploadToKB);
    document.getElementById('kb-select').addEventListener('change', updateUploadButton);
}

// WebSocket事件处理
socket.on('connect', function() {
    updateConnectionStatus(true);
    addSystemMessage('系统连接成功', 'success');
    // 加入全局房间以接收所有任务更新
    socket.emit('join_global_room');
});

socket.on('disconnect', function() {
    updateConnectionStatus(false);
    addSystemMessage('系统连接断开', 'warning');
});

socket.on('joined_global_room', function(data) {
    loadAllTasks(); // 重新加载所有任务
    
    // 为所有正在运行的任务加入房间
    setTimeout(() => {
        allTasks.forEach(task => {
            if (task.status === 'running' || task.status === 'starting') {
                socket.emit('join_task_room', { task_id: task.task_id });
            }
        });
    }, 1000); // 延迟1秒确保任务列表加载完成
});

socket.on('joined_task_room', function(data) {
    // 任务房间加入确认
});

socket.on('task_status_change', function(data) {
    // 更新内存中的任务状态
    const task = allTasks.get(data.task_id);
    if (task) {
        task.status = data.status;
        updateTaskStatus(data.task_id, data.status); // 更新单个任务的状态显示
        updateTasksStats(); // 更新统计数据
    } else {
        // 如果是新任务，重新加载所有任务
        loadAllTasks();
    }
    
    // 如果任务开始运行，确保加入房间
    if (data.status === 'running' && data.task_id) {
        socket.emit('join_task_room', { task_id: data.task_id });
    }
    
    if (data.status === 'completed') {
        loadFiles(); // 任务完成时重新加载文件列表
        // 延迟刷新任务总结，确保总结报告已保存
        setTimeout(() => {
            loadTaskSummaries();
        }, 2000);
    }
});



socket.on('log_message', function(data) {
    console.log(`[Task Log] ${data.timestamp || new Date().toLocaleTimeString()} [${data.level.toUpperCase()}] ${data.message}`);
    
    // 将日志存储到对应的任务中
    if (data.task_id && allTasks.has(data.task_id)) {
        const task = allTasks.get(data.task_id);
        if (!task.logs) {
            task.logs = [];
        }
        task.logs.push({
            message: data.message,
            level: data.level,
            timestamp: data.timestamp || new Date().toLocaleTimeString()
        });
        
        // 限制日志条数，避免内存占用过大
        if (task.logs.length > 1000) {
            task.logs = task.logs.slice(-500); // 保留最新的500条
        }
    }
    
    // 如果当前正在查看任务详情，且是对应的任务，则更新详情中的日志
    if (currentDetailTaskId && data.task_id && currentDetailTaskId === data.task_id && 
        document.getElementById('task-detail-modal').classList.contains('show')) {
        addLogToDetail(data.message, data.level, data.timestamp);
    }
});

socket.on('progress_update', function(data) {
    // 更新任务列表中的进度
    if (data.task_id) {
        updateTaskProgress(data.task_id, data);
    }
    // 如果正在查看详情，也更新详情中的进度
    if (currentDetailTaskId && currentDetailTaskId === data.task_id && document.getElementById('task-detail-modal').classList.contains('show')) {
        updateDetailProgress(data);
    }
});



// 更新连接状态
function updateConnectionStatus(connected) {
    const statusText = connectionStatus.querySelector('.status-text');
    if (!statusText) return;

    if (connected) {
        statusText.textContent = '已连接';
        connectionStatus.className = 'connection-status me-3 connected';
    } else {
        statusText.textContent = '连接断开';
        connectionStatus.className = 'connection-status me-3 disconnected';
    }
}

// 添加系统消息
function addSystemMessage(message, level = 'info') {
    // 可以在这里添加全局消息显示逻辑
    console.log(`[${level}] ${message}`);
}

// 处理添加任务
function handleAddTask(e) {
    e.preventDefault();
    
    if (!socket.connected) {
        showAlert('系统未连接，请刷新页面重试', 'error');
        return;
    }

    const crawlerType = document.getElementById('crawlerType').value;
    const maxPages = document.getElementById('max-pages').value;
    const pageUrl = document.getElementById('page-url').value;

    if (!crawlerType) {
        showAlert('请选择爬虫类型', 'error');
        return;
    }

    // 验证自定义页面URL
    if (crawlerType === 'custom') {
        if (!pageUrl || pageUrl.trim() === '') {
            showAlert('请输入页面网址', 'error');
            return;
        }
        
        // 简单的URL格式验证
        const urlPattern = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/;
        const testUrl = pageUrl.startsWith('http') ? pageUrl : 'https://' + pageUrl;
        if (!urlPattern.test(testUrl)) {
            showAlert('请输入有效的网址格式', 'error');
            return;
        }
    }

    // 临时禁用按钮，防止重复提交
    startBtn.disabled = true;
    startBtn.innerHTML = '<i class="bi bi-hourglass-split btn-icon"></i> 创建中...';

    // 构建请求数据
    const requestData = {
        crawler_type: crawlerType,
        max_pages: maxPages !== '' ? parseInt(maxPages) : 10
    };
    
    // 如果是自定义页面，添加页面URL
    if (crawlerType === 'custom') {
        requestData.page_url = pageUrl.trim();
    }

    fetch('/api/start_crawler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.task_id) {
            showAlert(`任务添加成功！任务ID: ${data.task_id}`, 'success');
            
            // 立即加入任务房间以接收实时更新
            socket.emit('join_task_room', { task_id: data.task_id });
            
            // 重新加载任务列表
            loadAllTasks();
            
            // 重置表单
            document.getElementById('crawlerType').value = '';
            document.getElementById('max-pages').value = '';
            document.getElementById('page-url').value = '';
            
            // 重置按钮显示
            const dropdownButton = document.getElementById('crawlerTypeDropdown');
            if (dropdownButton) {
                dropdownButton.innerHTML = '选择爬虫类型';
            }
            
            document.getElementById('max-pages-group').style.display = 'block';
            document.getElementById('page-url-group').style.display = 'none';
        } else {
            showAlert(data.message || '任务创建失败', 'error');
        }
    })
    .catch(error => {
        console.error('创建任务时出错:', error);
        showAlert('创建任务时发生网络错误', 'error');
    })
    .finally(() => {
        // 恢复按钮状态
        startBtn.disabled = false;
        startBtn.innerHTML = '<i class="bi bi-plus-circle btn-icon"></i> 添加任务';
    });
}

// 处理批量停止
function handleBatchStop() {
    const runningTasks = Array.from(allTasks.values()).filter(task => task.status === 'running');
    
    if (runningTasks.length === 0) {
        showAlert('没有正在运行的任务', 'warning');
        return;
    }

    if (!confirm(`确定要停止所有 ${runningTasks.length} 个正在运行的任务吗？`)) {
        return;
    }

    const taskIds = runningTasks.map(task => task.task_id);
    
    batchStopBtn.disabled = true;
    batchStopBtn.innerHTML = '<i class="bi bi-hourglass-split btn-icon"></i> 停止中...';

    fetch('/api/stop_multiple_crawlers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_ids: taskIds })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(data.message, 'success');
            loadAllTasks(); // 重新加载任务列表
        } else {
            showAlert(data.message || '批量停止失败', 'error');
        }
    })
    .catch(error => {
        console.error('批量停止时出错:', error);
        showAlert('批量停止时发生网络错误', 'error');
    })
    .finally(() => {
        batchStopBtn.disabled = false;
        batchStopBtn.innerHTML = '<i class="bi bi-stop-circle btn-icon"></i> 停止所有任务';
    });
}

// 加载所有任务
function loadAllTasks() {
    fetch('/api/get_all_tasks')
        .then(response => response.json())
        .then(data => {
            if (data.tasks) {
                // 保存现有任务的日志
                const existingLogs = new Map();
                allTasks.forEach((task, taskId) => {
                    if (task.logs) {
                        existingLogs.set(taskId, task.logs);
                    }
                });
                
                allTasks.clear();
                data.tasks.forEach(task => {
                    // 恢复已存储的日志
                    if (existingLogs.has(task.task_id)) {
                        task.logs = existingLogs.get(task.task_id);
                    }
                    
                    allTasks.set(task.task_id, task);
                    // 对于正在运行的任务，自动加入房间以接收实时更新
                    if (task.status === 'running' || task.status === 'starting') {
                        socket.emit('join_task_room', { task_id: task.task_id });
                    }
                });
                displayTasks();
                updateTasksStats();
            }
        })
        .catch(error => {
            console.error('加载任务列表时出错:', error);
        });
}

// 显示任务列表
function displayTasks() {
    if (allTasks.size === 0) {
        noTasksMessage.style.display = 'block';
        tasksContainer.innerHTML = '';
        return;
    }

    noTasksMessage.style.display = 'none';
    tasksContainer.innerHTML = '';

    Array.from(allTasks.values()).forEach(task => {
        const taskElement = createTaskElement(task);
        tasksContainer.appendChild(taskElement);
    });
}

// 创建任务元素
function createTaskElement(task) {
    const taskDiv = document.createElement('div');
    taskDiv.className = 'task-item border rounded p-3 mb-3';
    taskDiv.setAttribute('data-task-id', task.task_id);

    const statusClass = getStatusClass(task.status);
    const statusText = getStatusText(task.status);
    const progressPercentage = task.progress ? task.progress.percentage : 0;

    taskDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-start mb-2">
            <div>
                <h6 class="mb-1">${task.crawler_name}</h6>
                <small class="text-muted">任务ID: ${task.task_id}</small>
            </div>
            <div class="text-end">
                <span class="badge ${statusClass}">${statusText}</span>
            </div>
        </div>
        
        <div class="row mb-2">
            <div class="col-md-6">
                <small class="text-muted">开始时间: ${task.start_time || 'N/A'}</small>
            </div>
            <div class="col-md-6">
                <small class="text-muted">运行时长: ${task.duration || '0:00:00'}</small>
            </div>
        </div>
        
        <div class="progress mb-2" style="height: 8px;">
            <div class="progress-bar ${task.status === 'running' ? 'progress-bar-striped progress-bar-animated' : ''}" 
                 role="progressbar" style="width: ${progressPercentage}%"></div>
        </div>
        
        <div class="d-flex justify-content-between align-items-center">
            <small class="text-muted">
                ${task.progress ? `${task.progress.current}/${task.progress.total} (${progressPercentage.toFixed(1)}%)` : '0/0 (0%)'}
            </small>
            <div>
                <button class="btn btn-sm btn-outline-primary me-1" onclick="showTaskDetail('${task.task_id}')">
                    <i class="bi bi-eye btn-icon-dark"></i> 详情
                </button>
                ${task.status === 'running' ? `
                    <button class="btn btn-sm btn-outline-danger" onclick="stopTask('${task.task_id}')">
                        <i class="bi bi-stop-circle btn-icon-dark"></i> 停止
                    </button>
                ` : ''}
                ${task.status === 'completed' || task.status === 'error' ? `
                    <button class="btn btn-sm btn-outline-secondary" onclick="deleteTask('${task.task_id}')">
                        <i class="bi bi-trash btn-icon-dark"></i> 删除
                    </button>
                ` : ''}
            </div>
        </div>
    `;

    return taskDiv;
}

// 获取状态样式类
function getStatusClass(status) {
    const statusClasses = {
        'starting': 'bg-info',
        'running': 'bg-success',
        'completed': 'bg-secondary',
        'error': 'bg-danger',
        'stopping': 'bg-warning'
    };
    return statusClasses[status] || 'bg-secondary';
}

// 获取状态文本
function getStatusText(status) {
    const statusTexts = {
        'starting': '启动中',
        'running': '运行中',
        'completed': '已完成',
        'error': '错误',
        'stopping': '停止中'
    };
    return statusTexts[status] || '未知';
}

// 更新任务统计
function updateTasksStats() {
    const stats = {
        total: allTasks.size,
        running: 0,
        completed: 0,
        error: 0
    };

    allTasks.forEach(task => {
        if (task.status === 'running' || task.status === 'starting') {
            stats.running++;
        } else if (task.status === 'completed') {
            stats.completed++;
        } else if (task.status === 'error') {
            stats.error++;
        }
    });

    totalTasksBadge.textContent = stats.total;
    runningTasksBadge.textContent = stats.running;
    completedTasksBadge.textContent = stats.completed;
    errorTasksBadge.textContent = stats.error;
}

// 显示任务详情
function showTaskDetail(taskId) {
    const task = allTasks.get(taskId);
    if (!task) return;

    currentDetailTaskId = taskId;
    
    // 更新详情Modal的内容
    document.getElementById('detail-task-id').textContent = task.task_id;
    document.getElementById('detail-crawler-type').textContent = task.crawler_name;
    document.getElementById('detail-status').innerHTML = `<span class="badge ${getStatusClass(task.status)}">${getStatusText(task.status)}</span>`;
    document.getElementById('detail-start-time').textContent = task.start_time || 'N/A';
    document.getElementById('detail-end-time').textContent = task.end_time || 'N/A';
    document.getElementById('detail-duration').textContent = task.duration || '0:00:00';
    document.getElementById('detail-max-pages').textContent = task.max_pages === 0 ? '无限制' : (task.max_pages || '10');
    
    // 更新进度
    const progressPercentage = task.progress ? task.progress.percentage : 0;
    document.getElementById('detail-progress-bar').style.width = `${progressPercentage}%`;
    document.getElementById('detail-current').textContent = task.progress ? task.progress.current : 0;
    document.getElementById('detail-total').textContent = task.progress ? task.progress.total : 0;
    
    // 清空日志容器，然后显示已存储的日志
    const logContainer = document.getElementById('detail-log-container');
    logContainer.innerHTML = '';
    
    // 显示任务的历史日志
    if (task.logs && task.logs.length > 0) {
        task.logs.forEach(log => {
            addLogToDetail(log.message, log.level, log.timestamp);
        });
    }
    
    // 显示停止按钮
    const stopBtn = document.getElementById('detail-stop-btn');
    if (task.status === 'running') {
        stopBtn.style.display = 'block';
        stopBtn.setAttribute('data-task-id', taskId);
    } else {
        stopBtn.style.display = 'none';
    }
    
    // 加入任务房间以接收实时日志
    socket.emit('join_task_room', { task_id: taskId });
    
    // 显示Modal
    taskDetailModal.show();
}

// 停止任务
function stopTask(taskId) {
    if (!confirm('确定要停止这个任务吗？')) return;

    const button = event.target.closest('button');
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="bi bi-hourglass-split btn-icon-dark"></i> 停止中...';

    fetch('/api/stop_crawler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('停止信号已发送', 'success');
            loadAllTasks(); // 重新加载任务列表
        } else {
            showAlert(data.message || '停止失败', 'error');
        }
    })
    .catch(error => {
        console.error('停止任务时出错:', error);
        showAlert('停止任务时发生网络错误', 'error');
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = originalHtml;
    });
}

// 删除任务
function deleteTask(taskId) {
    if (!confirm('确定要删除这个任务吗？')) return;

    fetch(`/api/delete_task/${taskId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('任务已删除', 'success');
            loadAllTasks(); // 重新加载任务列表
        } else {
            showAlert(data.message || '删除失败', 'error');
        }
    })
    .catch(error => {
        console.error('删除任务时出错:', error);
        showAlert('删除任务时发生网络错误', 'error');
    });
}

// 从详情Modal中停止任务
function handleStopTaskFromDetail() {
    const taskId = currentDetailTaskId;
    if (!taskId) return;

    if (!confirm('确定要停止这个任务吗？')) return;

    const button = document.getElementById('detail-stop-btn');
    button.disabled = true;
    button.innerHTML = '<i class="bi bi-hourglass-split btn-icon"></i> 停止中...';

    fetch('/api/stop_crawler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('停止信号已发送', 'success');
            loadAllTasks(); // 重新加载任务列表
            taskDetailModal.hide(); // 关闭详情Modal
        } else {
            showAlert(data.message || '停止失败', 'error');
        }
    })
    .catch(error => {
        console.error('停止任务时出错:', error);
        showAlert('停止任务时发生网络错误', 'error');
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = '停止任务';
    });
}

// 更新任务状态
function updateTaskStatus(taskId, status) {
    const taskElement = document.querySelector(`[data-task-id="${taskId}"]`);
    if (!taskElement) {
        return;
    }

    const statusBadge = taskElement.querySelector('.badge');
    const buttonsContainer = taskElement.querySelector('.d-flex.justify-content-between.align-items-center > div:last-child');
    
    if (statusBadge) {
        statusBadge.className = `badge ${getStatusClass(status)}`;
        statusBadge.textContent = getStatusText(status);
    }
    
    if (buttonsContainer) {
        // 重新生成按钮
        const task = allTasks.get(taskId);
        if (task) {
            buttonsContainer.innerHTML = `
                <button class="btn btn-sm btn-outline-primary me-1" onclick="showTaskDetail('${taskId}')">
                    <i class="bi bi-eye btn-icon-dark"></i> 详情
                </button>
                ${status === 'running' ? `
                    <button class="btn btn-sm btn-outline-danger" onclick="stopTask('${taskId}')">
                        <i class="bi bi-stop-circle btn-icon-dark"></i> 停止
                    </button>
                ` : ''}
                ${status === 'completed' || status === 'error' ? `
                    <button class="btn btn-sm btn-outline-secondary" onclick="deleteTask('${taskId}')">
                        <i class="bi bi-trash btn-icon-dark"></i> 删除
                    </button>
                ` : ''}
            `;
        }
    }
}

// 更新任务进度
function updateTaskProgress(taskId, progressData) {
    const taskElement = document.querySelector(`[data-task-id="${taskId}"]`);
    if (!taskElement) {
        // 如果找不到任务元素，重新加载任务列表
        loadAllTasks();
        return;
    }

    const progressBar = taskElement.querySelector('.progress-bar');
    const progressText = taskElement.querySelector('.d-flex.justify-content-between.align-items-center small.text-muted');
    
    if (progressBar) {
        progressBar.style.width = `${progressData.percentage}%`;
        // 如果任务正在运行，添加动画效果
        if (progressData.percentage > 0) {
            progressBar.classList.add('progress-bar-striped', 'progress-bar-animated');
        }
    }
    
    if (progressText) {
        progressText.textContent = `${progressData.current}/${progressData.total} (${progressData.percentage.toFixed(1)}%)`;
    }
    
    // 更新任务在内存中的进度数据
    const task = allTasks.get(taskId);
    if (task) {
        task.progress = progressData;
    }
}

// 更新详情Modal中的进度
function updateDetailProgress(progressData) {
    document.getElementById('detail-progress-bar').style.width = `${progressData.percentage}%`;
    document.getElementById('detail-current').textContent = progressData.current;
    document.getElementById('detail-total').textContent = progressData.total;
}

// 添加日志到详情Modal
function addLogToDetail(message, level = 'info', timestamp = null) {
    const logContainer = document.getElementById('detail-log-container');
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${level}`;
    const time = timestamp || new Date().toLocaleTimeString('zh-CN');
    logEntry.innerHTML = `<span class="log-timestamp">[${time}]</span> <span class="log-message">${escapeHtml(message)}</span>`;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// 定期更新任务状态
setInterval(loadAllTasks, 5000); // 每5秒更新一次

// 原有的文件管理功能保持不变
function loadFiles(dirPath = '') {
    const refreshBtn = document.getElementById('refresh-files');
    const originalText = refreshBtn.innerHTML;
    refreshBtn.innerHTML = '<img src="/static/icons/arrow-clockwise.svg" class="btn-icon-dark me-1 rotating" alt="刷新"> 刷新中...';
    refreshBtn.disabled = true;
    
    const url = dirPath ? `/api/get_files?dir=${encodeURIComponent(dirPath)}` : '/api/get_files';
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.files) {
                displayFiles(data.files);
                updateFilesCount(data.files.length);
            } else if (data.error) {
                showAlert(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('加载文件时出错:', error);
            showAlert('加载文件时发生网络错误', 'error');
        })
        .finally(() => {
            refreshBtn.innerHTML = originalText;
            refreshBtn.disabled = false;
        });
}

function displayFiles(files) {
    const tableBody = document.getElementById('files-table-body');
    const noFilesMessage = document.getElementById('no-files-message');
    
    if (files.length === 0) {
        tableBody.innerHTML = '';
        noFilesMessage.style.display = 'block';
        updateFileSelectionUI();
        return;
    }
    
    noFilesMessage.style.display = 'none';
    tableBody.innerHTML = files.map(file => `
        <tr>
            <td>
                <input type="checkbox" class="form-check-input file-checkbox" 
                       data-file-path="${escapeHtml(file.path)}" 
                       data-file-name="${escapeHtml(file.name)}"
                       onchange="updateFileSelectionUI()">
            </td>
            <td>
                <i class="bi ${getFileIcon(file.name)} me-2"></i>
                ${truncateText(file.name, 40)}
            </td>
            <td><span class="badge ${getBadgeClass(file.type)}">${file.type}</span></td>
            <td>${formatFileSize(file.size)}</td>
            <td>${file.mtime}</td> 
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="downloadFile('${file.path}')">
                    <i class="bi bi-download btn-icon-dark"></i> 下载
                </button>
            </td>
        </tr>
    `).join('');
    updateFileSelectionUI();
}



function getBadgeClass(type) {
    // 只分两大类，使用柔和的颜色
    if (type && type.startsWith('应急部-')) {
        // 应急管理部 - 柔和的蓝灰色
        return 'bg-info-subtle text-info-emphasis';
    } else if (type && type.startsWith('法规库-')) {
        // 法规数据库 - 柔和的绿色
        return 'bg-success-subtle text-success-emphasis';
    } else if (type === '自定义页面') {
        // 自定义页面 - 柔和的灰色
        return 'bg-secondary-subtle text-secondary-emphasis';
    }
    
    // 默认
    return 'bg-light text-dark';
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        'pdf': 'bi-file-earmark-pdf',
        'doc': 'bi-file-earmark-word',
        'docx': 'bi-file-earmark-word',
        'txt': 'bi-file-earmark-text',
        'html': 'bi-file-earmark-code'
    };
    return icons[ext] || 'bi-file-earmark';
}

function downloadFile(filepath) {
    window.open(`/api/download_file/${filepath}`, '_blank');
}

function downloadAllFiles() {
    window.open('/api/download_all', '_blank');
}

function updateFilesCount(count) {
    document.getElementById('files-count').textContent = count;
}

// 初始化爬虫类型相关的UI显示
function initializeCrawlerTypeVisibility() {
    const maxPagesGroup = document.getElementById('max-pages-group');
    const pageUrlGroup = document.getElementById('page-url-group');
    
    // 默认显示最大页数输入框，隐藏页面网址输入框
    if (maxPagesGroup) {
        maxPagesGroup.style.display = 'block';
    }
    if (pageUrlGroup) {
        pageUrlGroup.style.display = 'none';
    }
}

// UI显示逻辑已整合到点击处理器中

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateText(text, maxLength) {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showAlert(message, type = 'info') {
    // 创建简单的通知显示
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertDiv);
    
    // 自动移除
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.parentNode.removeChild(alertDiv);
        }
    }, 5000);
}

function loadLogHistory() {
    const refreshBtn = document.getElementById('refresh-logs');
    const originalText = refreshBtn.innerHTML;
    refreshBtn.innerHTML = '<img src="/static/icons/arrow-clockwise.svg" class="btn-icon-dark me-1 rotating" alt="刷新"> 刷新中...';
    refreshBtn.disabled = true;
    
    fetch('/api/get_logs')
        .then(response => response.json())
        .then(data => {
            if (data.logs) {
                allLogsData = data.logs; // 保存原始数据
                applyLogsHistoryFilter(); // 应用当前搜索过滤
            } else if (data.error) {
                showAlert(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('加载日志历史时出错:', error);
            showAlert('加载日志历史时发生网络错误', 'error');
        })
        .finally(() => {
            refreshBtn.innerHTML = originalText;
            refreshBtn.disabled = false;
        });
}

function displayLogHistory(logs) {
    const tableBody = document.getElementById('logs-history-table-body');
    const noLogsMessage = document.getElementById('no-logs-message');

    if (logs.length === 0) {
        tableBody.innerHTML = '';
        noLogsMessage.style.display = 'block';
        return;
    }
    
    noLogsMessage.style.display = 'none';
    tableBody.innerHTML = logs.map(log => `
        <tr>
            <td>${log.name}</td>
            <td>${formatFileSize(log.size)}</td>
            <td>${log.mtime}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary me-1" onclick="viewLogContent('${log.name}')">
                    <i class="bi bi-eye btn-icon-dark"></i> 查看
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteLog('${log.name}', this)">
                    <i class="bi bi-trash btn-icon-dark"></i> 删除
                </button>
            </td>
        </tr>
    `).join('');
}

function deleteLog(filename, buttonElement) {
    if (!confirm(`确定要删除日志文件 "${filename}" 吗？`)) return;
    
        fetch(`/api/delete_log/${filename}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                loadLogHistory(); // 重新加载日志列表
            } else {
                showAlert(data.message || '删除失败', 'error');
            }
        })
        .catch(error => {
            console.error('删除日志时出错:', error);
            showAlert('删除日志时发生网络错误', 'error');
        });
}

function viewLogContent(filename) {
    fetch(`/api/get_log_content/${filename}`)
        .then(response => response.json())
        .then(data => {
            if (data.content) {
                document.getElementById('logViewerModalLabel').textContent = `查看日志 - ${data.name}`;
                document.getElementById('log-modal-content').textContent = data.content;
                const logModal = new bootstrap.Modal(document.getElementById('log-viewer-modal'));
                logModal.show();
            } else {
                showAlert(data.error || '获取日志内容失败', 'error');
            }
        })
        .catch(error => {
            console.error('获取日志内容时出错:', error);
            showAlert('获取日志内容时发生网络错误', 'error');
        });
}

// ---------------- 多级目录下拉框逻辑 ----------------
let dirTree = [];
let currentDirPath = '';

// 加载目录树并初始化下拉框
function loadDirTree() {
    fetch('/api/get_dir_tree')
        .then(resp => resp.json())
        .then(data => {
            dirTree = data.tree || [];
            renderDirSelect(0, dirTree);
        })
        .catch(err => console.error('加载目录树失败:', err));
}

// 在指定层级渲染下拉框
function renderDirSelect(level, nodes) {
    const container = document.getElementById('dir-select-container');
    if (!container) return; // 如果容器不存在则跳过
    
    // 移除该层级及之后的所有下拉框
    Array.from(container.children).forEach(el => {
        if (parseInt(el.dataset.level, 10) >= level) {
            el.remove();
        }
    });

    if (!nodes || nodes.length === 0) {
        // 没有更多子目录，结束
        // 注意：文件已经在目录选择时加载，这里不需要重复加载
        return;
    }

    // 创建下拉框
    const select = document.createElement('select');
    select.className = 'form-select form-select-sm';
    select.dataset.level = level;

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = level === 0 ? '全部' : '请选择';
    select.appendChild(placeholder);

    nodes.forEach(node => {
        const option = document.createElement('option');
        option.value = node.path;
        option.textContent = node.name;
        option.dataset.hasChildren = node.children && node.children.length > 0 ? '1' : '0';
        select.appendChild(option);
    });

    select.addEventListener('change', (e) => {
        const selectedValue = e.target.value;
        if (!selectedValue) {
            // 未选择具体目录，回到"全部文件"视图
            currentDirPath = '';
            loadFiles(''); // 立即加载全部文件
            renderDirSelect(level + 1, []); // 清除后续层级的下拉框
            return;
        }

        currentDirPath = selectedValue;

        // 立即加载选中目录的文件
        loadFiles(selectedValue);

        // 寻找对应节点以渲染其子目录
        const node = findNodeByPath(dirTree, selectedValue);
        if (node && node.children && node.children.length > 0) {
            // 渲染子级下拉框
            renderDirSelect(level + 1, node.children);
        } else {
            // 没有子目录，移除后续层级的下拉框
            renderDirSelect(level + 1, []);
        }
    });

    container.appendChild(select);
}

// 深度优先搜索节点
function findNodeByPath(nodes, path) {
    for (const node of nodes) {
        if (node.path === path) return node;
        if (node.children && node.children.length > 0) {
            const found = findNodeByPath(node.children, path);
            if (found) return found;
        }
    }
    return null;
}

// 加载任务总结（使用专门的总结报告数据结构）
function loadTaskSummaries() {
    console.log('[DEBUG] 开始加载任务总结');
    const refreshBtn = document.getElementById('refresh-summaries');
    const originalText = refreshBtn.innerHTML;
    refreshBtn.innerHTML = '<img src="/static/icons/arrow-clockwise.svg" class="btn-icon-dark me-1 rotating" alt="刷新"> 刷新中...';
    refreshBtn.disabled = true;
    
    fetch('/api/get_task_summaries')
        .then(response => {
            console.log('[DEBUG] 收到响应，状态:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('[DEBUG] 解析数据:', data);
            console.log('[DEBUG] 总结数量:', data.summaries ? data.summaries.length : 0);
            if (data.summaries) {
                allSummariesData = data.summaries; // 保存原始数据
                applyTaskSummaryFilter(); // 应用当前搜索过滤
            } else if (data.error) {
                showAlert(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('[DEBUG] 加载任务总结时出错:', error);
            showAlert('加载任务总结时发生网络错误', 'error');
        })
        .finally(() => {
            refreshBtn.innerHTML = originalText;
            refreshBtn.disabled = false;
        });
}

function displayTaskSummaries(summaries) {
    const tableBody = document.getElementById('summaries-table-body');
    const noSummariesMessage = document.getElementById('no-summaries-message');
    
    if (summaries.length === 0) {
        tableBody.innerHTML = '';
        noSummariesMessage.style.display = 'block';
        return;
    }
    
    noSummariesMessage.style.display = 'none';
    tableBody.innerHTML = summaries.map(summary => `
        <tr>
            <td>${summary.task_id}</td>
            <td><span class="badge ${getBadgeClass(summary.crawler_name)}">${summary.crawler_name}</span></td>
            <td>${summary.end_time || '未完成'}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary me-1" onclick="viewSummaryContent('${summary.task_id}')">
                    <i class="bi bi-eye btn-icon-dark"></i> 查看
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteSummary('${summary.task_id}', this)">
                    <i class="bi bi-trash btn-icon-dark"></i> 删除
                </button>
            </td>
        </tr>
    `).join('');
}

function viewSummaryContent(taskId) {
    fetch(`/api/get_summary_content/${taskId}`)
        .then(response => response.json())
        .then(data => {
            if (data.content) {
                document.getElementById('logViewerModalLabel').textContent = data.name || `任务总结 - ${taskId}`;
                document.getElementById('log-modal-content').textContent = data.content;
                const logModal = new bootstrap.Modal(document.getElementById('log-viewer-modal'));
                logModal.show();
            } else {
                showAlert(data.error || '获取总结内容失败', 'error');
            }
        })
        .catch(error => {
            console.error('获取总结内容时出错:', error);
            showAlert('获取总结内容时发生网络错误', 'error');
        });
}

function deleteSummary(taskId, buttonElement) {
    if (!confirm(`确定要删除任务总结 "${taskId}" 吗？`)) return;
    
    fetch(`/api/delete_summary/${taskId}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                loadTaskSummaries(); // 重新加载列表
            } else {
                showAlert(data.message || '删除失败', 'error');
            }
        })
        .catch(error => {
            console.error('删除总结时出错:', error);
            showAlert('删除总结时发生网络错误', 'error');
        });
}

// 应用任务总结搜索过滤
function applyTaskSummaryFilter() {
    const searchTerm = document.getElementById('task-summary-search')?.value.toLowerCase() || '';
    let filteredSummaries = allSummariesData;
    
    if (searchTerm) {
        filteredSummaries = allSummariesData.filter(summary => 
            summary.task_id.toLowerCase().includes(searchTerm)
        );
    }
    
    displayTaskSummaries(filteredSummaries);
}

// 应用历史日志搜索过滤
function applyLogsHistoryFilter() {
    const searchTerm = document.getElementById('logs-history-search')?.value.toLowerCase() || '';
    let filteredLogs = allLogsData;
    
    if (searchTerm) {
        // 日志文件名通常包含任务ID，格式如：crawler_任务ID.log
        filteredLogs = allLogsData.filter(log => 
            log.name.toLowerCase().includes(searchTerm)
        );
    }
    
    displayLogHistory(filteredLogs);
}

// 清除任务总结搜索
function clearSummarySearch() {
    const searchInput = document.getElementById('task-summary-search');
    if (searchInput) {
        searchInput.value = '';
        applyTaskSummaryFilter();
    }
}

// 清除历史日志搜索
function clearLogsSearch() {
    const searchInput = document.getElementById('logs-history-search');
    if (searchInput) {
        searchInput.value = '';
        applyLogsHistoryFilter();
    }
}

// 初始化搜索框事件监听器
function initSearchListeners() {
    // 任务总结搜索框
    const summarySearchInput = document.getElementById('task-summary-search');
    if (summarySearchInput) {
        summarySearchInput.addEventListener('input', function() {
            applyTaskSummaryFilter();
        });
        
        summarySearchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                applyTaskSummaryFilter();
            }
        });
    }
    
    // 历史日志搜索框
    const logsSearchInput = document.getElementById('logs-history-search');
    if (logsSearchInput) {
        logsSearchInput.addEventListener('input', function() {
            applyLogsHistoryFilter();
        });
        
        logsSearchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                applyLogsHistoryFilter();
            }
        });
    }
}

// 页面可见性变化处理，用于断线重连
document.addEventListener('visibilitychange', function() {
    if (!document.hidden && !socket.connected) {
        socket.connect();
    }
});

// 注：目录树的初始化已经在主DOMContentLoaded事件中处理了

// 调试函数：手动测试任务总结API
function debugTaskSummaries() {
    console.log('=== 调试任务总结功能 ===');
    
    fetch('/api/get_task_summaries')
        .then(response => {
            console.log('API响应状态:', response.status);
            return response.text();
        })
        .then(text => {
            console.log('API原始响应:', text);
            try {
                const data = JSON.parse(text);
                console.log('API解析后数据:', data);
                console.log('总结数量:', data.summaries ? data.summaries.length : 0);
            } catch (e) {
                console.error('JSON解析失败:', e);
            }
        })
        .catch(error => {
            console.error('API请求失败:', error);
        });
}

// ==================== 知识库功能 ====================

// 全选/取消全选文件
function handleSelectAllFiles(e) {
    const checkboxes = document.querySelectorAll('.file-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = e.target.checked;
    });
    updateFileSelectionUI();
}

// 更新文件选择UI状态
function updateFileSelectionUI() {
    const checkboxes = document.querySelectorAll('.file-checkbox');
    const checkedBoxes = document.querySelectorAll('.file-checkbox:checked');
    const selectAllCheckbox = document.getElementById('select-all-files');
    const uploadBtn = document.getElementById('upload-to-kb-btn');
    
    if (!selectAllCheckbox || !uploadBtn) return; // 防止元素不存在错误
    
    // 更新全选按钮状态
    if (checkboxes.length === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    } else if (checkedBoxes.length === checkboxes.length) {
        selectAllCheckbox.checked = true;
        selectAllCheckbox.indeterminate = false;
    } else if (checkedBoxes.length > 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = true;
    } else {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    }
    
    // 更新上传按钮状态
    if (checkedBoxes.length > 0) {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = `<img src="/static/icons/cloud-upload.svg" class="btn-icon-dark me-1" alt="上传"> 上传到知识库 (${checkedBoxes.length})`;
    } else {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<img src="/static/icons/cloud-upload.svg" class="btn-icon-dark me-1" alt="上传"> 上传到知识库';
    }
}

// 显示知识库上传Modal
function showKnowledgeBaseModal() {
    const checkedBoxes = document.querySelectorAll('.file-checkbox:checked');
    if (checkedBoxes.length === 0) {
        showAlert('请先选择要上传的文件', 'warning');
        return;
    }
    
    // 更新选中文件列表
    updateSelectedFilesList();
    
    // 加载知识库列表
    loadKnowledgeBases();
    
    // 显示Modal
    const modal = new bootstrap.Modal(document.getElementById('upload-kb-modal'));
    modal.show();
}

// 更新选中文件列表显示
function updateSelectedFilesList() {
    const checkedBoxes = document.querySelectorAll('.file-checkbox:checked');
    const filesList = document.getElementById('selected-files-list');
    const filesCount = document.getElementById('selected-files-count');
    
    if (filesCount) filesCount.textContent = checkedBoxes.length;
    
    if (checkedBoxes.length === 0) {
        if (filesList) filesList.innerHTML = '<div class="text-muted">尚未选择任何文件</div>';
        return;
    }
    
    const filesHtml = Array.from(checkedBoxes).map(checkbox => {
        const fileName = checkbox.getAttribute('data-file-name');
        return `<div class="d-flex align-items-center mb-1">
            <i class="bi ${getFileIcon(fileName)} me-2"></i>
            <span class="small">${truncateText(fileName, 50)}</span>
        </div>`;
    }).join('');
    
    if (filesList) filesList.innerHTML = filesHtml;
}

// 加载知识库列表
function loadKnowledgeBases() {
    const kbSelect = document.getElementById('kb-select');
    if (!kbSelect) return;
    
    kbSelect.innerHTML = '<option value="">加载中...</option>';
    
    fetch('/api/get_knowledge_bases')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.kbs) {
                kbSelect.innerHTML = '<option value="">请选择知识库...</option>';
                data.kbs.forEach(kb => {
                    const option = document.createElement('option');
                    option.value = kb.id;
                    option.textContent = `${kb.name} (${kb.doc_num}个文档)`;
                    kbSelect.appendChild(option);
                });
            } else {
                kbSelect.innerHTML = '<option value="">加载失败</option>';
                showAlert(data.message || '获取知识库列表失败', 'error');
            }
        })
        .catch(error => {
            console.error('加载知识库列表失败:', error);
            kbSelect.innerHTML = '<option value="">加载失败</option>';
            showAlert('获取知识库列表时发生网络错误', 'error');
        });
}

// 更新上传按钮状态
function updateUploadButton() {
    const kbSelect = document.getElementById('kb-select');
    const startUploadBtn = document.getElementById('start-upload-btn');
    const checkedBoxes = document.querySelectorAll('.file-checkbox:checked');
    
    if (startUploadBtn) {
        startUploadBtn.disabled = !kbSelect?.value || checkedBoxes.length === 0;
    }
}

// 开始上传到知识库
function startUploadToKB() {
    const kbSelect = document.getElementById('kb-select');
    const checkedBoxes = document.querySelectorAll('.file-checkbox:checked');
    
    if (!kbSelect?.value) {
        showAlert('请选择知识库', 'warning');
        return;
    }
    
    if (checkedBoxes.length === 0) {
        showAlert('请选择要上传的文件', 'warning');
        return;
    }
    
    // 获取上传选项
    const uploadOption = document.querySelector('input[name="upload-option"]:checked')?.value || 'upload-only';
    const shouldParse = uploadOption === 'upload-and-parse';
    
    // 准备上传
    const kbId = kbSelect.value;
    const kbName = kbSelect.options[kbSelect.selectedIndex].text;
    const files = Array.from(checkedBoxes).map(checkbox => ({
        path: checkbox.getAttribute('data-file-path'),
        name: checkbox.getAttribute('data-file-name')
    }));
    
    // 显示进度区域
    const progressSection = document.getElementById('upload-progress-section');
    const startUploadBtn = document.getElementById('start-upload-btn');
    if (progressSection) progressSection.style.display = 'block';
    if (startUploadBtn) startUploadBtn.disabled = true;
    
    // 开始批量上传
    uploadFilesToKB(kbId, kbName, files, shouldParse);
}

// 批量上传文件到知识库
async function uploadFilesToKB(kbId, kbName, files, shouldParse = false) {
    const progressBar = document.getElementById('upload-progress-bar');
    const uploadStatus = document.getElementById('upload-status');
    
    let successCount = 0;
    let failCount = 0;
    let uploadedDocIds = []; // 存储成功上传的文档ID，用于解析
    
    // 计算总步骤数：上传 + (可选)解析
    const totalSteps = shouldParse ? files.length * 2 : files.length;
    let currentStep = 0;
    
    // 第一阶段：上传文件
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        currentStep++;
        const progress = (currentStep / totalSteps) * 100;
        
        if (progressBar) progressBar.style.width = `${progress}%`;
        if (uploadStatus) {
            const action = shouldParse ? '上传' : '上传';
            uploadStatus.textContent = `正在${action}: ${file.name} (${i + 1}/${files.length})`;
        }
        
        try {
            const result = await uploadSingleFileToKB(kbId, file);
            if (result.success) {
                successCount++;
                // 如果需要解析，收集文档ID
                if (shouldParse && result.data && result.data.length > 0) {
                    uploadedDocIds.push(result.data[0].id);
                }
            } else {
                failCount++;
                console.error(`上传失败 ${file.name}:`, result.message);
            }
        } catch (error) {
            failCount++;
            console.error(`上传失败 ${file.name}:`, error);
        }
    }
    
    // 第二阶段：解析文档（如果选择了解析选项）
    if (shouldParse && uploadedDocIds.length > 0) {
        if (uploadStatus) uploadStatus.textContent = `开始解析 ${uploadedDocIds.length} 个文档...`;
        
        try {
            const parseResult = await parseDocuments(uploadedDocIds);
            currentStep = totalSteps; // 解析完成，进度到100%
            if (progressBar) progressBar.style.width = '100%';
            
            if (parseResult.success) {
                if (uploadStatus) uploadStatus.textContent = `解析完成！共处理 ${uploadedDocIds.length} 个文档`;
            } else {
                if (uploadStatus) uploadStatus.innerHTML = `解析失败: ${parseResult.message}`;
                console.error('文档解析失败:', parseResult.message);
            }
        } catch (error) {
            if (uploadStatus) uploadStatus.innerHTML = `解析出错: ${error.message}`;
            console.error('文档解析出错:', error);
        }
    }
    
    // 上传完成
    if (progressBar) progressBar.style.width = '100%';
    if (uploadStatus) {
        uploadStatus.innerHTML = `
            上传完成! 
            <span class="text-success">成功: ${successCount}</span>
            ${failCount > 0 ? `<span class="text-danger">失败: ${failCount}</span>` : ''}
        `;
    }
    
    // 显示结果通知
    if (failCount === 0) {
        if (shouldParse) {
            showAlert(`所有 ${successCount} 个文件已成功上传并${uploadedDocIds.length > 0 ? '开始解析' : '尝试解析'}到知识库 "${kbName}"`, 'success');
        } else {
            showAlert(`所有 ${successCount} 个文件已成功上传到知识库 "${kbName}"`, 'success');
        }
    } else {
        const parseInfo = shouldParse ? '，部分文件已开始解析' : '';
        showAlert(`上传完成: ${successCount} 个成功, ${failCount} 个失败${parseInfo}`, 'warning');
    }
    
    // 重置UI
    setTimeout(() => {
        const modal = bootstrap.Modal.getInstance(document.getElementById('upload-kb-modal'));
        if (modal) modal.hide();
        
        // 清除选择状态
        document.querySelectorAll('.file-checkbox:checked').forEach(checkbox => {
            checkbox.checked = false;
        });
        updateFileSelectionUI();
        
        // 重置Modal状态
        const progressSection = document.getElementById('upload-progress-section');
        const startUploadBtn = document.getElementById('start-upload-btn');
        if (progressSection) progressSection.style.display = 'none';
        if (startUploadBtn) startUploadBtn.disabled = false;
        if (progressBar) progressBar.style.width = '0%';
        if (uploadStatus) uploadStatus.textContent = '准备上传...';
    }, 3000);
}

// 上传单个文件到知识库
function uploadSingleFileToKB(kbId, file) {
    return new Promise((resolve, reject) => {
        fetch('/api/upload_to_knowledge_base', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                kb_id: kbId,
                file_path: file.path,
                file_name: file.name
            })
        })
        .then(response => response.json())
        .then(data => {
            resolve(data);
        })
        .catch(error => {
            reject(error);
        });
    });
}

// 解析文档
function parseDocuments(docIds) {
    return new Promise((resolve, reject) => {
        fetch('/api/parse_documents', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                doc_ids: docIds
            })
        })
        .then(response => response.json())
        .then(data => {
            resolve(data);
        })
        .catch(error => {
            reject(error);
        });
    });
} 