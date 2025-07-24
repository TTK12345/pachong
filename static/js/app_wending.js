// WebSocket连接
const socket = io();

// 全局变量
let isConnected = false;
let crawlerRunning = false;

// DOM元素
const crawlerForm = document.getElementById('crawler-form');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const logContainer = document.getElementById('log-container');
const progressBar = document.getElementById('progress-bar');
const statusBadge = document.getElementById('status-badge');
const connectionStatus = document.getElementById('connection-status');

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    loadFiles();
    updateCrawlerTypeVisibility();
});

// 事件监听器
function initializeEventListeners() {
    // 表单提交
    crawlerForm.addEventListener('submit', handleStartCrawler);
    
    // 停止按钮
    stopBtn.addEventListener('click', handleStopCrawler);
    
    // 清空日志
    document.getElementById('clear-logs').addEventListener('click', clearLogs);
    
    // 刷新文件列表
    document.getElementById('refresh-files').addEventListener('click', loadFiles);
    
    // 打包下载
    document.getElementById('download-all').addEventListener('click', downloadAllFiles);
    
    // 爬虫类型改变
    document.getElementById('crawler-type').addEventListener('change', updateCrawlerTypeVisibility);
}

// WebSocket事件处理
socket.on('connect', function() {
    isConnected = true;
    updateConnectionStatus(true);
    addLogEntry('系统连接成功', 'success');
});

socket.on('disconnect', function() {
    isConnected = false;
    updateConnectionStatus(false);
    addLogEntry('系统连接断开', 'warning');
});

socket.on('log_message', function(data) {
    addLogEntry(data.message, data.level, data.timestamp);
});

socket.on('progress_update', function(data) {
    updateProgress(data);
});

socket.on('crawler_completed', function(data) {
    stopCrawler();
    addLogEntry('爬虫任务完成！', 'success');
    loadFiles(); // 重新加载文件列表
});

// 更新连接状态
function updateConnectionStatus(connected) {
    const statusElement = connectionStatus.querySelector('.bi-circle-fill');
    
    if (connected) {
        statusElement.className = 'bi bi-circle-fill text-success';
        connectionStatus.innerHTML = '<i class="bi bi-circle-fill text-success"></i> 已连接';
    } else {
        statusElement.className = 'bi bi-circle-fill text-danger';
        connectionStatus.innerHTML = '<i class="bi bi-circle-fill text-danger"></i> 连接断开';
    }
}

// 处理开始爬虫
function handleStartCrawler(e) {
    e.preventDefault();
    
    if (!isConnected) {
        showAlert('系统未连接，请刷新页面重试', 'danger');
        return;
    }
    
    if (crawlerRunning) {
        showAlert('爬虫正在运行中', 'warning');
        return;
    }
    
    const crawlerType = document.getElementById('crawler-type').value;
    const maxDocs = document.getElementById('max-docs').value;
    const maxPages = document.getElementById('max-pages').value;
    
    if (!crawlerType) {
        showAlert('请选择爬虫类型', 'warning');
        return;
    }
    
    const requestData = {
        crawler_type: crawlerType,
        max_docs: maxDocs ? parseInt(maxDocs) : null,
        max_pages: maxPages ? parseInt(maxPages) : 10
    };
    
    // 显示加载状态
    startBtn.innerHTML = '<span class="loading-spinner"></span> 启动中...';
    startBtn.disabled = true;
    
    // 发送启动请求
    fetch('/api/start_crawler', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            startCrawler();
            addLogEntry('爬虫启动成功', 'success');
        } else {
            showAlert(data.message, 'danger');
            resetStartButton();
        }
    })
    .catch(error => {
        console.error('启动爬虫时出错:', error);
        showAlert('启动爬虫时出错', 'danger');
        resetStartButton();
    });
}

// 重置启动按钮
function resetStartButton() {
    startBtn.innerHTML = '<i class="bi bi-play-fill"></i> 开始爬取';
    startBtn.disabled = false;
}

// 处理停止爬虫
function handleStopCrawler() {
    if (!crawlerRunning) {
        showAlert('没有正在运行的爬虫', 'warning');
        return;
    }
    
    stopBtn.innerHTML = '<span class="loading-spinner"></span> 停止中...';
    stopBtn.disabled = true;
    
    fetch('/api/stop_crawler', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            addLogEntry('停止信号已发送', 'warning');
        } else {
            showAlert(data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('停止爬虫时出错:', error);
        showAlert('停止爬虫时出错', 'danger');
    })
    .finally(() => {
        stopBtn.innerHTML = '<i class="bi bi-stop-fill"></i> 停止爬取';
    });
}

// 启动爬虫状态
function startCrawler() {
    crawlerRunning = true;
    startBtn.disabled = true;
    stopBtn.disabled = false;
    
    // 更新状态徽章
    statusBadge.textContent = '运行中';
    statusBadge.className = 'badge bg-success running';
    
    // 更新开始时间
    const startTime = document.getElementById('start-time');
    startTime.textContent = '开始时间: ' + new Date().toLocaleString('zh-CN');
    
    // 重置进度
    updateProgress({current: 0, total: 0, percentage: 0, current_file: '正在启动...'});
    
    // 切换到日志面板
    const logsTab = document.getElementById('logs-tab');
    logsTab.click();
}

// 停止爬虫状态
function stopCrawler() {
    crawlerRunning = false;
    resetStartButton();
    stopBtn.disabled = true;
    stopBtn.innerHTML = '<i class="bi bi-stop-fill"></i> 停止爬取';
    
    // 更新状态徽章
    statusBadge.textContent = '空闲中';
    statusBadge.className = 'badge bg-secondary';
    
    // 更新当前文件显示
    document.getElementById('current-file').textContent = '任务完成';
    
    // 刷新文件列表
    setTimeout(() => {
        loadFiles();
    }, 1000);
}

// 更新进度
function updateProgress(data) {
    const { current, total, percentage, current_file } = data;
    
    // 更新进度条
    progressBar.style.width = percentage + '%';
    progressBar.textContent = percentage + '%';
    progressBar.setAttribute('aria-valuenow', percentage);
    
    // 更新计数
    document.getElementById('current-count').textContent = current;
    document.getElementById('total-count').textContent = total;
    document.getElementById('progress-text').textContent = percentage + '%';
    document.getElementById('current-file').textContent = current_file || '等待开始...';
    
    // 如果进度达到100%，延迟停止爬虫状态
    if (percentage >= 100 && total > 0) {
        setTimeout(() => {
            if (crawlerRunning) {
                stopCrawler();
            }
        }, 3000);
    }
}

// 添加日志条目
function addLogEntry(message, level = 'info', timestamp = null) {
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${level}`;
    
    const time = timestamp || new Date().toLocaleTimeString('zh-CN');
    logEntry.innerHTML = `
        <span class="log-timestamp">[${time}]</span>
        <span class="log-message">${escapeHtml(message)}</span>
    `;
    
    logContainer.appendChild(logEntry);
    
    // 自动滚动到底部
    logContainer.scrollTop = logContainer.scrollHeight;
    
    // 限制日志条目数量
    while (logContainer.children.length > 1000) {
        logContainer.removeChild(logContainer.firstChild);
    }
}

// 清空日志
function clearLogs() {
    logContainer.innerHTML = '';
    addLogEntry('日志已清空', 'info');
}

// 加载文件列表
function loadFiles() {
    const refreshBtn = document.getElementById('refresh-files');
    const originalText = refreshBtn.innerHTML;
    refreshBtn.innerHTML = '<span class="loading-spinner"></span>';
    refreshBtn.disabled = true;
    
    fetch('/api/get_files')
        .then(response => response.json())
        .then(data => {
            displayFiles(data.files);
            updateFilesCount(data.files.length);
        })
        .catch(error => {
            console.error('加载文件列表时出错:', error);
            showAlert('加载文件列表失败', 'danger');
        })
        .finally(() => {
            refreshBtn.innerHTML = originalText;
            refreshBtn.disabled = false;
        });
}

// 显示文件列表
function displayFiles(files) {
    const tbody = document.getElementById('files-table-body');
    const noFilesMessage = document.getElementById('no-files-message');
    
    tbody.innerHTML = '';
    
    if (files.length === 0) {
        noFilesMessage.style.display = 'block';
        return;
    }
    
    noFilesMessage.style.display = 'none';
    
    files.forEach(file => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    <i class="bi ${getFileIcon(file.name)} me-2"></i>
                    <span title="${escapeHtml(file.name)}">${truncateText(file.name, 40)}</span>
                </div>
            </td>
            <td>
                <span class="badge file-type-badge ${file.type === '规章' ? 'file-type-gz' : 'file-type-law'}">
                    ${file.type}
                </span>
            </td>
            <td>
                <span class="file-size">${formatFileSize(file.size)}</span>
            </td>
            <td>
                <small class="text-muted">${file.mtime}</small>
            </td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="downloadFile('${encodeURIComponent(file.path)}')" 
                        title="下载文件">
                    <i class="bi bi-download"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// 获取文件图标
function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    switch (ext) {
        case 'pdf':
            return 'bi-file-earmark-pdf';
        case 'doc':
        case 'docx':
            return 'bi-file-earmark-word';
        case 'wps':
            return 'bi-file-earmark-text';
        default:
            return 'bi-file-earmark';
    }
}

// 下载单个文件
function downloadFile(filepath) {
    const link = document.createElement('a');
    link.href = `/api/download_file/${filepath}`;
    link.download = '';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 打包下载所有文件
function downloadAllFiles() {
    const downloadBtn = document.getElementById('download-all');
    const originalText = downloadBtn.innerHTML;
    downloadBtn.innerHTML = '<span class="loading-spinner"></span> 打包中...';
    downloadBtn.disabled = true;
    
    const link = document.createElement('a');
    link.href = '/api/download_all';
    link.download = '爬虫下载文件.zip';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    setTimeout(() => {
        downloadBtn.innerHTML = originalText;
        downloadBtn.disabled = false;
    }, 3000);
}

// 更新文件计数
function updateFilesCount(count) {
    document.getElementById('files-count').textContent = count;
}

// 更新爬虫类型相关的UI显示
function updateCrawlerTypeVisibility() {
    const crawlerType = document.getElementById('crawler-type').value;
    const maxPagesGroup = document.getElementById('max-pages-group');
    
    if (crawlerType === 'gz') {
        maxPagesGroup.style.display = 'block';
    } else {
        maxPagesGroup.style.display = 'none';
    }
}

// 工具函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showAlert(message, type = 'info') {
    // 创建临时的alert元素
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 80px; right: 20px; z-index: 9999; min-width: 300px; max-width: 500px;';
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

// 页面可见性变化处理
document.addEventListener('visibilitychange', function() {
    if (!document.hidden && crawlerRunning) {
        // 页面重新变为可见时，检查连接状态
        if (!socket.connected) {
            socket.connect();
        }
    }
});

// 键盘快捷键
document.addEventListener('keydown', function(e) {
    // Ctrl+Enter 开始爬虫
    if (e.ctrlKey && e.key === 'Enter' && !crawlerRunning) {
        e.preventDefault();
        handleStartCrawler(e);
    }
    
    // Esc 停止爬虫
    if (e.key === 'Escape' && crawlerRunning) {
        e.preventDefault();
        handleStopCrawler();
    }
    
    // Ctrl+L 清空日志
    if (e.ctrlKey && e.key === 'l') {
        e.preventDefault();
        clearLogs();
    }
}); 