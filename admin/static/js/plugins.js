// 全局变量
let plugins = [];
let currentPluginId = null;
let currentFilter = 'all';
let configModal = null;
let uploadModal = null;
let marketPlugins = [];

// 一些辅助函数
function getFieldLabel(field) {
    const labels = {
        'name': '插件名称',
        'description': '描述',
        'author': '作者',
        'version': '版本',
        'github_url': 'GitHub链接',
        'icon': '图标'
    };
    return labels[field] || field;
}

// 手动打开模态框
function openModalManually(modalId) {
    try {
        const modalEl = document.getElementById(modalId);
        if (!modalEl) {
            console.error(`找不到模态框: ${modalId}`);
            return false;
        }

        // 使用Bootstrap API
        const modalInstance = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
        modalInstance.show();

        console.log(`使用Bootstrap API打开模态框成功: ${modalId}`);
        return true;
    } catch (error) {
        console.error(`打开模态框失败: ${modalId}`, error);
        return false;
    }
}

// 手动关闭模态框
function closeModalManually(modalId) {
    try {
        const modalEl = document.getElementById(modalId);
        if (!modalEl) {
            console.error(`找不到模态框: ${modalId}`);
            return false;
        }

        // 使用Bootstrap API
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) {
            modalInstance.hide();
        }

        console.log(`使用Bootstrap API关闭模态框成功: ${modalId}`);
        return true;
    } catch (error) {
        console.error(`关闭模态框失败: ${modalId}`, error);
        return false;
    }
}

// 插件市场API配置
const PLUGIN_MARKET_API = {
    BASE_URL: 'http://xianan.xin:1562/api',
    LIST: '/plugins?status=approved',
    SUBMIT: '/plugins',
    INSTALL: '/plugins/install/',
    CACHE_KEY: 'xybot_plugin_market_cache',
    CACHE_EXPIRY: 3600000 // 缓存有效期1小时（毫秒）
};

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('页面加载完成');
    console.log('Bootstrap版本:', typeof bootstrap !== 'undefined' ? (bootstrap.version || '存在但无版本信息') : '未加载');
    console.log('jQuery版本:', typeof $ !== 'undefined' ? ($.fn.jquery || '存在但无版本信息') : '未加载');
    console.log('模态框元素:', document.getElementById('upload-plugin-modal'));

    // 加载插件列表
    loadPlugins();

    // 加载插件市场
    loadPluginMarket();

    // 为刷新市场按钮添加点击事件
    const refreshMarketBtn = document.getElementById('btn-refresh-market');
    if (refreshMarketBtn) {
        refreshMarketBtn.addEventListener('click', function() {
            loadPluginMarket();
        });
    } else {
        console.warn('找不到刷新市场按钮，无法添加事件监听器');
    }

    console.log('提交按钮:', document.getElementById('btn-upload-plugin'));

    // 尝试添加内联点击事件
    console.log('尝试添加内联点击事件');

    // 初始化上传模态框
    initUploadModal();

    console.log('找到提交审核按钮:', document.getElementById('btn-submit-plugin'));

    // 添加提交事件监听器
    const submitBtn = document.getElementById('btn-submit-plugin');
    if (submitBtn) {
        submitBtn.addEventListener('click', function() {
            submitPlugin();
        });
    } else {
        console.error('找不到提交审核按钮，无法添加事件监听器');
    }

    // 添加搜索事件监听器
    const searchInput = document.getElementById('market-search-input');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            searchMarketPlugins(this.value);
        });
    } else {
        console.warn('找不到市场搜索输入框，搜索功能不可用');
    }

    // 检查并处理离线提交的插件
    checkConnection().then(online => {
        if (online) {
            processOfflineQueue();
        }
    });

    // 删除紧急按钮（如果存在）
    const emergencyButton = document.getElementById('emergency-backdrop-cleaner');
    if (emergencyButton) {
        emergencyButton.remove();
    }

    // 配置保存按钮点击事件
    document.getElementById('plugin-config-save').addEventListener('click', function() {
        // 直接调用保存函数，不依赖于pluginId属性
        savePluginConfig();
    });

    // 监听模态框关闭事件
    const configModal = document.getElementById('plugin-config-modal');
    configModal.addEventListener('hidden.bs.modal', function() {
        // 清理表单
        document.getElementById('plugin-config-form').innerHTML = '';
        // 重置错误状态
        document.getElementById('plugin-config-error').style.display = 'none';
    });
});

// 检查网络连接
async function checkConnection() {
    try {
        const response = await fetch(`${PLUGIN_MARKET_API.BASE_URL}/health`, {
            method: 'GET'
        });
        return response.ok;
    } catch (error) {
        console.warn('连接检查失败:', error);
        return false;
    }
}

// 处理离线队列
async function processOfflineQueue() {
    const offlineQueue = JSON.parse(localStorage.getItem('xybot_offline_plugins') || '[]');

    if (offlineQueue.length === 0) return;

    let successCount = 0;
    let failCount = 0;

    for (const item of offlineQueue) {
        try {
            const response = await fetch(`${PLUGIN_MARKET_API.BASE_URL}${PLUGIN_MARKET_API.SUBMIT}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': getBotClientId(),
                    'X-Submission-Id': item.id
                },
                body: JSON.stringify(item.data)
            });

            const data = await response.json();

            if (data.success) {
                successCount++;
            } else {
                failCount++;
                console.error('同步提交失败:', data.error);
            }
        } catch (error) {
            failCount++;
            console.error('同步提交出错:', error);
        }
    }

    // 清空已处理的队列
    localStorage.removeItem('xybot_offline_plugins');

    if (successCount > 0) {
        showToast(`成功同步${successCount}个离线提交的插件`, 'success');
    }

    return { successCount, failCount };
}

// 加载插件列表
async function loadPlugins() {
    const pluginList = document.getElementById('plugin-list');

    try {
        pluginList.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-3 text-muted">加载插件中...</p>
            </div>
        `;

        const response = await fetch('/api/plugins');
        const data = await response.json();

        if (data.success) {
            plugins = data.data.plugins;
            console.log('插件信息:', plugins); // 调试输出
            document.getElementById('plugin-count').textContent = plugins.length;
            filterPlugins(currentFilter);
        } else {
            throw new Error(data.error || '加载插件失败');
        }
    } catch (error) {
        console.error('加载插件列表失败:', error);
        pluginList.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                加载插件列表失败: ${error.message}
            </div>
        `;
    }
}

// 过滤插件
function filterPlugins(filter) {
    let filteredPlugins = [];

    if (filter === 'all') {
        filteredPlugins = plugins;
    } else if (filter === 'enabled') {
        filteredPlugins = plugins.filter(plugin => plugin.enabled);
    } else if (filter === 'disabled') {
        filteredPlugins = plugins.filter(plugin => !plugin.enabled);
    }

    renderPluginList(filteredPlugins);
}

// 渲染插件列表
function renderPluginList(pluginsList) {
    const pluginList = document.getElementById('plugin-list');

    if (pluginsList.length === 0) {
        pluginList.innerHTML = `
            <div class="alert alert-info text-center">
                <i class="bi bi-info-circle-fill me-2"></i>
                未找到匹配的插件
            </div>
        `;
        return;
    }

    // 清空容器，保留plugin-grid类以使用CSS网格布局
    pluginList.innerHTML = '';

    // 为每个插件创建卡片并添加到网格布局中
    pluginsList.forEach(plugin => {
        const statusClass = plugin.enabled ? 'success' : 'secondary';
        const statusText = plugin.enabled ? '已启用' : '已禁用';

        // 根据插件名生成稳定的渐变色
        const colors = [
            ['#1abc9c', '#16a085'], // 绿松石
            ['#3498db', '#2980b9'], // 蓝色
            ['#9b59b6', '#8e44ad'], // 紫色
            ['#e74c3c', '#c0392b'], // 红色
            ['#f1c40f', '#f39c12'], // 黄色
            ['#2ecc71', '#27ae60']  // 绿色
        ];
        const colorIndex = Math.abs(hashCode(plugin.name) % colors.length);
        const gradientColors = colors[colorIndex];

        // 创建卡片元素
        const cardElement = document.createElement('div');
        cardElement.className = 'card h-100 shadow border-0 rounded-4 overflow-hidden';
        if (!plugin.enabled) {
            cardElement.classList.add('disabled');
        }

        // 生成卡片HTML
        cardElement.innerHTML = `
            <div class="card-header p-3 pt-4 pb-4 bg-gradient-light border-0 position-relative" style="background: linear-gradient(135deg, #f8f9fa, #e9ecef);">
                <div class="plugin-status-container">
                    <span class="badge bg-${statusClass} status-badge">${statusText}</span>
                    <div class="form-check form-switch plugin-switch ms-2">
                        <input class="form-check-input plugin-toggle" type="checkbox" id="toggle-${plugin.id}" ${plugin.enabled ? 'checked' : ''} data-plugin-id="${plugin.id}">
                        <label class="form-check-label visually-hidden" for="toggle-${plugin.id}">启用/禁用</label>
                    </div>
                </div>
                <div class="d-flex align-items-center">
                    <div class="plugin-icon rounded-circle shadow-sm" style="background: linear-gradient(135deg, ${gradientColors[0]}, ${gradientColors[1]});">
                        <i class="bi bi-puzzle"></i>
                    </div>
                    <div class="ms-3" style="min-width: 0; flex: 1;">
                        <h5 class="card-title mb-0 fw-bold text-truncate" title="${plugin.name}">${plugin.name}</h5>
                        <div class="text-muted small">v${plugin.version || '1.0.0'}</div>
                    </div>
                </div>
            </div>
            <div class="card-body p-3 d-flex flex-column">
                <p class="card-text text-truncate-2" title="${plugin.description}">${plugin.description || '暂无描述'}</p>
                <div class="mt-auto pt-3">
                    <div class="text-muted small text-truncate mb-2" title="${plugin.author || '未知作者'}">
                        <i class="bi bi-person me-1"></i>${plugin.author || '未知作者'}
                    </div>
                    <div class="d-flex flex-wrap gap-2 justify-content-start align-items-center">
                        <div class="d-flex gap-1">
                            <button class="btn btn-sm btn-outline-secondary rounded-pill btn-readme" data-plugin-id="${plugin.id}">
                                <i class="bi bi-book me-1"></i>说明
                            </button>
                            <button class="btn btn-sm btn-outline-primary rounded-pill btn-config" data-plugin-id="${plugin.id}" ${!plugin.enabled ? 'disabled' : ''}>
                                <i class="bi bi-gear-fill me-1"></i>配置
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 直接添加到插件列表容器（使用grid布局）
        pluginList.appendChild(cardElement);
    });

    // 添加CSS样式
    if (!document.querySelector('#plugin-list-styles')) {
        const styleEl = document.createElement('style');
        styleEl.id = 'plugin-list-styles';
        styleEl.textContent = `
            #plugin-list {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 1.5rem;
                width: 100%;
            }
            .text-truncate-2 {
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
                text-overflow: ellipsis;
                max-height: 3em;
            }
            #plugin-list .plugin-icon {
                width: 45px;
                height: 45px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 1.2rem;
                flex-shrink: 0;
                border-radius: 50%;
                overflow: hidden;
                box-shadow: 0 3px 6px rgba(0,0,0,0.1);
            }
            #plugin-list .card {
                height: 100%;
                transition: transform 0.3s, box-shadow 0.3s;
                box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            }
            #plugin-list .card:hover {
                transform: translateY(-5px);
                box-shadow: 0 15px 30px rgba(0,0,0,0.1) !important;
            }
            #plugin-list .badge {
                font-weight: 500;
                padding: 0.4em 0.8em;
            }
            #plugin-list .btn-sm {
                padding: 0.25rem 0.75rem;
                font-size: 0.75rem;
                white-space: nowrap;
            }
            #plugin-list .plugin-status-container {
                position: absolute;
                top: 12px;
                right: 12px;
                display: flex;
                align-items: center;
                z-index: 10;
                background-color: rgba(255, 255, 255, 0.8);
                border-radius: 20px;
                padding: 2px 4px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            #plugin-list .plugin-switch {
                position: relative;
                margin: 0;
                padding: 0;
            }
            #plugin-list .form-check-input {
                cursor: pointer;
                width: 2.5em;
                height: 1.25em;
                margin: 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            #plugin-list .status-badge {
                font-size: 0.7rem;
                padding: 0.25em 0.6em;
                font-weight: 500;
                border-radius: 20px;
                vertical-align: middle;
                display: inline-block;
                min-width: 60px;
                text-align: center;
            }
            #plugin-list .text-truncate {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                max-width: 100%;
            }
            #plugin-list .card-title.text-truncate {
                max-width: 100%;
                display: block;
            }
            #plugin-list .d-flex.align-items-center {
                width: 100%;
            }
            #plugin-list .gap-1 {
                gap: 0.25rem !important;
            }
            #plugin-list .gap-2 {
                gap: 0.5rem !important;
            }
            #plugin-list .disabled {
                opacity: 0.7;
            }
            .bg-gradient-light {
                background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            }

            /* 响应式布局 */
            @media (min-width: 1400px) {
                #plugin-list {
                    grid-template-columns: repeat(4, 1fr);
                }
            }
            @media (min-width: 992px) and (max-width: 1399px) {
                #plugin-list {
                    grid-template-columns: repeat(3, 1fr);
                }
            }
            @media (min-width: 768px) and (max-width: 991px) {
                #plugin-list {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
            @media (max-width: 767px) {
                #plugin-list {
                    grid-template-columns: 1fr;
                }
            }
        `;
        document.head.appendChild(styleEl);
    }

    // 绑定事件
    document.querySelectorAll('.plugin-toggle').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const pluginId = this.getAttribute('data-plugin-id');
            togglePlugin(pluginId);
        });
    });

    document.querySelectorAll('.btn-config').forEach(button => {
        button.addEventListener('click', function() {
            const pluginId = this.getAttribute('data-plugin-id');
            openConfigModal(pluginId);
        });
    });

    document.querySelectorAll('.btn-readme').forEach(button => {
        button.addEventListener('click', function() {
            const pluginId = this.getAttribute('data-plugin-id');
            openReadmeModal(pluginId);
        });
    });
}

// 切换插件状态
async function togglePlugin(pluginId) {
    const plugin = plugins.find(p => p.id === pluginId);
    if (!plugin) return;

    try {
        const action = plugin.enabled ? 'disable' : 'enable';
        const response = await fetch(`/api/plugins/${pluginId}/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
            // 更新本地状态
            plugin.enabled = !plugin.enabled;

            // 刷新UI
            filterPlugins(currentFilter);

            // 显示提示
            showToast(`插件已${action === 'enable' ? '启用' : '禁用'}`, 'success');
        } else {
            throw new Error(result.error || `操作失败`);
        }
    } catch (error) {
        console.error('切换插件状态失败:', error);
        showToast(`操作失败: ${error.message}`, 'danger');
    }
}

// 打开README模态框
async function openReadmeModal(pluginId) {
    try {
        console.log(`正在获取插件 ${pluginId} 的README.md内容`);

        const plugin = plugins.find(p => p.id === pluginId);
        if (!plugin) {
            showToast('插件不存在', 'danger');
            return;
        }

        // 获取模态框元素
        const modalEl = document.getElementById('plugin-readme-modal');
        if (!modalEl) {
            throw new Error('找不到README模态框元素');
        }

        // 重置状态
        document.getElementById('plugin-readme-loading').style.display = 'block';
        document.getElementById('plugin-readme-error').classList.add('d-none');
        document.getElementById('plugin-readme-content').innerHTML = '';

        // 设置标题
        document.getElementById('plugin-readme-title').textContent = `${plugin.name} 使用说明`;

        // 确保销毁旧的模态框实例
        const oldModal = bootstrap.Modal.getInstance(modalEl);
        if (oldModal) {
            oldModal.dispose();
        }

        // 创建新的模态框实例
        const modal = new bootstrap.Modal(modalEl);

        // 显示模态框
        modal.show();

        // 获取README内容
        console.log(`发送请求到 /api/plugin_readme?plugin_id=${encodeURIComponent(pluginId)}`);
        const response = await fetch(`/api/plugin_readme?plugin_id=${encodeURIComponent(pluginId)}`);
        const data = await response.json();

        console.log(`插件 ${pluginId} 的README.md响应:`, data);

        // 隐藏加载状态
        document.getElementById('plugin-readme-loading').style.display = 'none';

        if (data.success) {
            console.log(`成功获取插件 ${pluginId} 的README.md内容，长度: ${data.readme.length}`);
            // 使用marked将Markdown渲染为HTML
            const readmeHtml = marked.parse(data.readme);
            document.getElementById('plugin-readme-content').innerHTML = readmeHtml;
        } else {
            console.error(`获取插件 ${pluginId} 的README.md失败:`, data.message || data.error);
            // 显示错误信息
            const errorEl = document.getElementById('plugin-readme-error');
            errorEl.classList.remove('d-none');
            errorEl.querySelector('span').textContent = data.message || data.error || '该插件暂无使用说明';
        }
    } catch (error) {
        console.error(`打开插件 ${pluginId} 的README模态框失败:`, error);

        // 隐藏加载状态
        document.getElementById('plugin-readme-loading').style.display = 'none';

        // 显示错误信息
        const errorEl = document.getElementById('plugin-readme-error');
        errorEl.classList.remove('d-none');
        errorEl.querySelector('span').textContent = error.message || '该插件暂无使用说明';
    }
}

// 打开配置模态框
async function openConfigModal(pluginId) {
    try {
        const plugin = plugins.find(p => p.id === pluginId);
        if (!plugin) {
            showToast('插件不存在', 'danger');
            return;
        }

        // 获取模态框元素
        const modalEl = document.getElementById('plugin-config-modal');
        if (!modalEl) {
            throw new Error('找不到配置模态框元素');
        }

        // 重置表单状态
        document.getElementById('plugin-config-loading').style.display = 'block';
        document.getElementById('plugin-config-error').style.display = 'none';
        document.getElementById('plugin-config-form').innerHTML = '';

        // 设置标题
        document.getElementById('plugin-config-title').textContent = `${plugin.name} 配置文件`;

        // 确保销毁旧的模态框实例
        const oldModal = bootstrap.Modal.getInstance(modalEl);
        if (oldModal) {
            oldModal.dispose();
        }

        // 创建新的模态框实例
        const modal = new bootstrap.Modal(modalEl, {
            backdrop: 'static',
            keyboard: true
        });

        // 显示模态框
        modal.show();

        try {
            // 获取配置文件路径
            const response = await fetch(`/api/plugin_config_file?plugin_id=${pluginId}`);
            const data = await response.json();

            if (data.success && data.config_file) {
                // 获取文件内容
                const contentResponse = await fetch(`/api/files/read?path=${encodeURIComponent(data.config_file)}`);
                const contentData = await contentResponse.json();

                if (contentData.success) {
                    // 创建文本编辑器
                    const formContainer = document.getElementById('plugin-config-form');
                    formContainer.innerHTML = `
                        <div class="alert alert-info mb-3">
                            <i class="bi bi-info-circle-fill me-2"></i>
                            正在编辑: ${data.config_file}
                        </div>
                        <div class="mb-3">
                            <textarea id="config-editor" class="form-control" style="min-height: 300px; font-family: monospace;">${contentData.content}</textarea>
                        </div>
                    `;

                    // 存储当前配置文件路径，用于保存
                    document.getElementById('plugin-config-save').setAttribute('data-config-file', data.config_file);
                    document.getElementById('plugin-config-save').textContent = '保存';

                    document.getElementById('plugin-config-loading').style.display = 'none';
                } else {
                    throw new Error(contentData.error || '无法读取配置文件内容');
                }
            } else {
                throw new Error(data.error || '无法获取配置文件');
            }
        } catch (error) {
            console.error('加载配置文件失败:', error);
            document.getElementById('plugin-config-loading').style.display = 'none';
            document.getElementById('plugin-config-error').style.display = 'block';
            document.getElementById('plugin-config-error').querySelector('span').textContent = `加载配置失败: ${error.message}`;
        }
    } catch (error) {
        console.error('打开配置失败:', error);
        showToast(`配置界面加载失败: ${error.message}`, 'danger');
    }
}

// 保存配置
async function savePluginConfig() {
    try {
        // 获取配置文件路径
        const configFile = document.getElementById('plugin-config-save').getAttribute('data-config-file');
        if (!configFile) {
            throw new Error('未找到配置文件路径');
        }

        // 获取编辑器内容
        const content = document.getElementById('config-editor').value;

        // 显示保存中状态
        const saveBtn = document.getElementById('plugin-config-save');
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>保存中...';

        // 发送保存请求
        const response = await fetch('/api/files/write', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                path: configFile,
                content: content
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('配置已保存', 'success');
            // 关闭模态框
            const modalEl = document.getElementById('plugin-config-modal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            modalInstance.hide();
        } else {
            throw new Error(data.error || '保存失败');
        }
    } catch (error) {
        console.error('保存配置失败:', error);
        showToast(`保存配置失败: ${error.message}`, 'danger');
    } finally {
        // 恢复保存按钮状态
        const saveBtn = document.getElementById('plugin-config-save');
        saveBtn.disabled = false;
        saveBtn.textContent = '保存';
    }
}

// 监听原生配置界面
function setupConfigContainerObserver() {
    // 监听配置容器的变化
    const configContainer = document.querySelector('#config-container');
    if (configContainer) {
        console.log('已找到配置容器');
    }
}

// 显示提示
function showToast(message, type = 'info') {
    // 查找或创建toast容器
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }

    // 创建toast
    const id = 'toast-' + Date.now();
    const html = `
        <div id="${id}" class="toast align-items-center text-white bg-${type}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML('beforeend', html);

    // 显示toast
    const toastEl = document.getElementById(id);
    const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 3000 });
    toast.show();

    // 清理
    toastEl.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

// 搜索插件
function searchPlugins(keyword) {
    if (!keyword.trim()) {
        filterPlugins(currentFilter);
        return;
    }

    const lowerKeyword = keyword.toLowerCase().trim();
    const results = plugins.filter(plugin => {
        return (
            plugin.name.toLowerCase().includes(lowerKeyword) ||
            (plugin.description && plugin.description.toLowerCase().includes(lowerKeyword)) ||
            (plugin.author && plugin.author.toLowerCase().includes(lowerKeyword))
        );
    });

    renderPluginList(results);
}

// 加载插件市场
async function loadPluginMarket() {
    const marketList = document.getElementById('market-list');

    try {
        // 先显示加载中的状态
        marketList.innerHTML = `
            <div class="col">
                <div class="text-center py-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-3 text-muted">加载插件市场中...</p>
                </div>
            </div>
        `;

        console.log('开始加载插件市场数据');

        // 检查网络连接
        const online = await checkConnection();

        if (!online) {
            // 如果离线，尝试加载缓存数据
            const loaded = loadCachedPluginMarket();
            if (!loaded) {
                throw new Error('无法连接到插件市场服务器，且没有缓存数据');
            }
            return;
        }

        console.log('API端点:', `${PLUGIN_MARKET_API.BASE_URL}${PLUGIN_MARKET_API.LIST}`);

        // 获取插件市场数据
        const response = await fetch(`${PLUGIN_MARKET_API.BASE_URL}${PLUGIN_MARKET_API.LIST}`);

        console.log('服务器响应状态:', response.status);

        if (!response.ok) {
            throw new Error(`服务器返回错误: ${response.status}`);
        }

        const data = await response.json();
        console.log('服务器返回数据:', data);

        // 将API响应转换为我们需要的格式
        marketPlugins = data.plugins.map(plugin => {
            return {
                id: plugin.id,
                name: plugin.name,
                description: plugin.description,
                author: plugin.author,
                version: plugin.version,
                github_url: plugin.github_url,
                tags: plugin.tags.map(tag => tag.name).join(', ')
            };
        });

        // 缓存数据
        cachePluginMarketData(marketPlugins);

        // 渲染插件
        renderMarketPlugins(marketPlugins);
    } catch (error) {
        console.error('加载插件市场失败:', error);

        // 尝试从缓存加载
        const loaded = loadCachedPluginMarket();

        if (!loaded) {
            // 显示错误信息
            marketList.innerHTML = `
                <div class="col">
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        加载插件市场失败: ${error.message}
                    </div>
                </div>
            `;
        }
    }
}

// 缓存插件市场数据
function cachePluginMarketData(plugins) {
    const cacheData = {
        timestamp: Date.now(),
        plugins: plugins
    };

    localStorage.setItem(PLUGIN_MARKET_API.CACHE_KEY, JSON.stringify(cacheData));
}

// 加载缓存的插件市场数据
function loadCachedPluginMarket() {
    try {
        const cacheData = localStorage.getItem(PLUGIN_MARKET_API.CACHE_KEY);
        if (!cacheData) {
            const marketList = document.getElementById('market-list');
            marketList.innerHTML = `
                <div class="col">
                    <div class="alert alert-info text-center">
                        <i class="bi bi-info-circle-fill me-2"></i>
                        没有可用的缓存数据，请检查网络连接并刷新
                    </div>
                </div>
            `;
            return false;
        }

        const parsedData = JSON.parse(cacheData);
        const cacheAge = Date.now() - parsedData.timestamp;

        marketPlugins = parsedData.plugins;
        renderMarketPlugins(marketPlugins);

        // 显示缓存提示
        const marketList = document.getElementById('market-list');
        if (marketList.children.length > 0) {
            const alertDiv = document.createElement('div');
            alertDiv.className = 'col-12 mb-3';

            if (cacheAge > PLUGIN_MARKET_API.CACHE_EXPIRY) {
                alertDiv.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        显示的是缓存数据 (${formatTimeAgo(parsedData.timestamp)})，可能已过期
                    </div>
                `;
            } else {
                alertDiv.innerHTML = `
                    <div class="alert alert-info">
                        <i class="bi bi-info-circle-fill me-2"></i>
                        显示的是缓存数据 (${formatTimeAgo(parsedData.timestamp)})
                    </div>
                `;
            }

            marketList.insertBefore(alertDiv, marketList.firstChild);
        }

        return true;
    } catch (error) {
        console.error('加载缓存数据失败:', error);
        const marketList = document.getElementById('market-list');
        marketList.innerHTML = `
            <div class="col">
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    缓存数据加载失败: ${error.message}
                </div>
            </div>
        `;
        return false;
    }
}

// 渲染插件市场列表
function renderMarketPlugins(marketPluginsList) {
    const marketList = document.getElementById('market-list');

    if (marketPluginsList.length === 0) {
        marketList.innerHTML = `
            <div class="col">
                <div class="alert alert-info text-center">
                    <i class="bi bi-info-circle-fill me-2"></i>
                    暂无插件，请点击"提交插件"按钮添加新插件
                </div>
            </div>
        `;
        return;
    }

    // 重置市场列表HTML
    marketList.innerHTML = '';

    // 创建一个网格容器
    const gridContainer = document.createElement('div');
    gridContainer.id = 'market-grid';
    marketList.appendChild(gridContainer);

    marketPluginsList.forEach((plugin, index) => {
        // 将标签字符串转换为数组
        const tags = plugin.tags ? plugin.tags.split(',') : [];

        // 生成标签HTML
        let tagsHtml = '';
        if (tags.length > 0) {
            tagsHtml = '<div class="plugin-tags mb-2 d-flex flex-wrap">';
            tags.forEach(tag => {
                if (tag.trim()) {
                    tagsHtml += `<span class="badge bg-light text-dark me-1 mb-1">${tag.trim()}</span>`;
                }
            });
            tagsHtml += '</div>';
        }

        // 检查插件是否已安装
        const isInstalled = plugins && Array.isArray(plugins) && plugins.some(p => p.name === plugin.name);

        // 生成渐变色背景（根据插件名生成一个稳定的颜色）
        const colors = [
            ['#1abc9c', '#16a085'], // 绿松石
            ['#3498db', '#2980b9'], // 蓝色
            ['#9b59b6', '#8e44ad'], // 紫色
            ['#e74c3c', '#c0392b'], // 红色
            ['#f1c40f', '#f39c12'], // 黄色
            ['#2ecc71', '#27ae60']  // 绿色
        ];
        const colorIndex = Math.abs(hashCode(plugin.name) % colors.length);
        const gradientColors = colors[colorIndex];

        // 创建卡片元素
        const cardElement = document.createElement('div');
        cardElement.className = 'market-card';

        // 生成卡片HTML
        cardElement.innerHTML = `
            <div class="card h-100 shadow border-0 rounded-4 overflow-hidden">
                <div class="card-header p-3 bg-gradient-light border-0" style="background: linear-gradient(135deg, #f8f9fa, #e9ecef);">
                    <div class="d-flex align-items-center">
                        <div class="plugin-icon rounded-circle shadow-sm" style="background: linear-gradient(135deg, ${gradientColors[0]}, ${gradientColors[1]});">
                            <i class="bi bi-puzzle"></i>
                        </div>
                        <div class="ms-3" style="min-width: 0; flex: 1;">
                            <h5 class="card-title mb-0 fw-bold text-truncate" title="${plugin.name}">${plugin.name}</h5>
                            <div class="text-muted small">v${plugin.version}</div>
                        </div>
                        ${isInstalled ? '<span class="badge bg-success ms-auto">已安装</span>' : ''}
                    </div>
                </div>
                <div class="card-body p-3 d-flex flex-column">
                    <p class="card-text text-truncate-2" title="${plugin.description}">${plugin.description}</p>
                    ${tagsHtml}
                    <div class="mt-auto pt-3">
                        <div class="text-muted small text-truncate mb-2" title="${plugin.author}">
                            <i class="bi bi-person me-1"></i>${plugin.author}
                        </div>
                        <div class="d-flex justify-content-end">
                            <button class="btn ${isInstalled ? 'btn-outline-primary' : 'btn-primary'} btn-sm rounded-pill btn-install-plugin" data-plugin-index="${index}">
                                <i class="bi ${isInstalled ? 'bi-arrow-repeat' : 'bi-download'} me-1"></i>${isInstalled ? '重新安装' : '安装'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 添加到网格容器
        gridContainer.appendChild(cardElement);
    });

    // 添加CSS样式
    const styleEl = document.createElement('style');
    styleEl.textContent = `
        #market-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1.5rem;
            width: 100%;
        }
        .text-truncate-2 {
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            text-overflow: ellipsis;
            max-height: 3em;
        }
        #market-list .plugin-icon {
            width: 45px;
            height: 45px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.2rem;
            flex-shrink: 0;
            border-radius: 50%;
            overflow: hidden;
            box-shadow: 0 3px 6px rgba(0,0,0,0.1);
        }
        #market-list .card {
            transition: transform 0.3s, box-shadow 0.3s;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }
        #market-list .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.1) !important;
        }
        #market-list .plugin-tags {
            min-height: 28px;
            display: flex;
            flex-wrap: wrap;
        }
        #market-list .badge {
            font-weight: 500;
            padding: 0.4em 0.8em;
        }
        #market-list .btn-sm {
            padding: 0.25rem 0.75rem;
            font-size: 0.75rem;
            white-space: nowrap;
        }
        #market-list .text-truncate {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 100%;
        }
        #market-list .card-title.text-truncate {
            max-width: 100%;
            display: block;
        }
        #market-list .d-flex.align-items-center {
            width: 100%;
        }
        .bg-gradient-light {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        }
    `;
    document.head.appendChild(styleEl);

    // 绑定安装按钮事件
    document.querySelectorAll('.btn-install-plugin').forEach(button => {
        button.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-plugin-index'));
            const plugin = marketPlugins[index];
            if (plugin) {
                installPlugin(plugin);
            }
        });
    });
}

// 搜索插件市场
function searchMarketPlugins(keyword) {
    if (!keyword) {
        renderMarketPlugins(marketPlugins);
        return;
    }

    const searchTerm = keyword.toLowerCase();
    const filteredPlugins = marketPlugins.filter(plugin => {
        return (
            plugin.name.toLowerCase().includes(searchTerm) ||
            plugin.description.toLowerCase().includes(searchTerm) ||
            plugin.author.toLowerCase().includes(searchTerm) ||
            (plugin.tags && plugin.tags.toLowerCase().includes(searchTerm))
        );
    });

    renderMarketPlugins(filteredPlugins);
}

// 提交插件到市场
async function submitPlugin() {
    console.log('==================== 开始提交流程 ====================');
    console.log('提交审核按钮被点击');
    const submitBtn = document.getElementById('btn-submit-plugin');
    const spinner = submitBtn.querySelector('.spinner-border');
    if (spinner) {
        spinner.classList.remove('d-none');
    }
    const errorDiv = document.getElementById('upload-error');

    // 显示加载状态
    submitBtn.disabled = true;

    try {
        const form = document.getElementById('upload-plugin-form');

        // 验证表单
        if (!validatePluginForm(form)) {
            console.log('表单验证失败');
            submitBtn.disabled = false;
            if (spinner) {
                spinner.classList.add('d-none');
            }
            return;
        }

        console.log('表单验证通过，准备提交');

        // 获取表单数据
        const formData = new FormData(form);

        // 转换为JSON对象
        const pluginData = {
            name: formData.get('name'),
            description: formData.get('description'),
            author: formData.get('author'),
            version: formData.get('version'),
            github_url: formData.get('github_url'),
            tags: formData.get('tags') ? formData.get('tags').split(',').map(tag => tag.trim()) : [],
            requirements: formData.get('requirements') ? formData.get('requirements').split(',').map(req => req.trim()) : [],
            icon: null // 图标将作为Base64处理
        };

        // 处理图标文件
        const iconFile = formData.get('icon');
        if (iconFile && iconFile.size > 0) {
            const iconBase64 = await readFileAsDataURL(iconFile);
            pluginData.icon = iconBase64;
        }

        console.log('正在提交插件数据:', pluginData);

        // 发送到服务器，使用PLUGIN_MARKET_API配置
        const response = await fetch(`${PLUGIN_MARKET_API.BASE_URL}${PLUGIN_MARKET_API.SUBMIT}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(pluginData),
            credentials: 'omit',  // 使用omit模式避免凭证问题
            signal: AbortSignal.timeout(10000) // 10秒超时
        });

        console.log('服务器响应:', response.status);
        let responseText = '';
        let responseData = null;

        try {
            responseText = await response.text();
            responseData = responseText ? JSON.parse(responseText) : {};
            console.log('响应数据:', responseData);
        } catch (e) {
            console.error('解析响应失败:', e, '原始文本:', responseText);
        }

        if (response.ok && responseData && responseData.success) {
            console.log('提交成功');

            // 使用统一的模态窗口管理方式关闭模态框
            const modalEl = document.getElementById('upload-plugin-modal');
            if (modalEl) {
                const modalInstance = bootstrap.Modal.getInstance(modalEl);
                if (modalInstance) {
                    modalInstance.hide();
                    // 等待模态窗口完全关闭后再重置表单
                    modalEl.addEventListener('hidden.bs.modal', function onHidden() {
                        // 重置表单
                        form.reset();
                        // 移除事件监听器
                        modalEl.removeEventListener('hidden.bs.modal', onHidden);
                    });
                }
            }

            // 提示成功
            showToast('插件提交成功，等待审核', 'success');

            // 刷新插件市场
            setTimeout(() => loadPluginMarket(), 1000);
        } else {
            throw new Error(responseData?.error || '提交失败');
        }
    } catch (error) {
        console.error('提交插件失败:', error);

        // 显示错误信息
        errorDiv.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                提交失败: ${error.message}
            </div>
        `;
        errorDiv.style.display = 'block';
    } finally {
        // 恢复按钮状态
        submitBtn.disabled = false;
        if (spinner) {
            spinner.classList.add('d-none');
        }
    }
}

// 验证插件表单
function validatePluginForm(form) {
    console.log('开始验证表单字段...');
    console.log('表单元素:', form);
    const errorDiv = document.getElementById('upload-error');
    console.log('错误显示区域:', errorDiv);

    // 基本字段验证
    const requiredFields = ['name', 'description', 'author', 'version', 'github_url'];
    console.log('检查必填字段:', requiredFields);

    for (const field of requiredFields) {
        const input = form.querySelector(`[name="${field}"]`);
        console.log(`检查字段 ${field}:`, input ? '找到元素' : '未找到元素');

        if (!input) {
            console.error(`表单中缺少字段: ${field}`);
            errorDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    表单缺少必要字段: ${getFieldLabel(field)}
                </div>
            `;
            errorDiv.style.display = 'block';
            return false;
        }

        console.log(`字段 ${field} 的值:`, input.value);
        if (!input.value.trim()) {
            console.log(`字段 ${field} 为空，验证失败`);
            errorDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    ${getFieldLabel(field)}不能为空
                </div>
            `;
            errorDiv.style.display = 'block';
            return false;
        }
    }

    // 版本格式验证
    const versionInput = form.querySelector('[name="version"]');
    if (versionInput) {
        const version = versionInput.value.trim();
        const versionPattern = /^\d+(\.\d+)*$/;  // 例如: 1.0.0, 2.1, 1
        if (!versionPattern.test(version)) {
            console.log('版本格式不正确:', version);
            errorDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    版本格式不正确，应为数字和点组成，如: 1.0.0
                </div>
            `;
            errorDiv.style.display = 'block';
            return false;
        }
    }

    // GitHub URL验证
    const githubUrlInput = form.querySelector('[name="github_url"]');
    const githubUrl = githubUrlInput ? githubUrlInput.value.trim() : '';
    console.log('GitHub URL:', githubUrl);

    if (!githubUrl.startsWith('https://github.com/') && !githubUrl.startsWith('https://raw.githubusercontent.com/')) {
        console.log('GitHub URL格式不正确');
        errorDiv.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                GitHub链接必须以 https://github.com/ 或 https://raw.githubusercontent.com/ 开头
            </div>
        `;
        errorDiv.style.display = 'block';
        return false;
    }

    console.log('表单验证通过');
    return true;
}

// 存储离线提交的插件
function storeOfflineSubmission(pluginData, tempId) {
    let offlineQueue = JSON.parse(localStorage.getItem('xybot_offline_plugins') || '[]');

    offlineQueue.push({
        id: tempId,
        data: pluginData,
        timestamp: Date.now()
    });

    localStorage.setItem('xybot_offline_plugins', JSON.stringify(offlineQueue));
}

// 安装插件
async function installPlugin(plugin) {
    const button = document.querySelector(`.btn-install-plugin[data-plugin-index="${marketPlugins.indexOf(plugin)}"]`);
    const originalText = button.innerHTML;

    // 显示加载状态
    button.disabled = true;
    button.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>正在安装...`;

    try {
        // 获取 GitHub URL
        const githubUrl = plugin.github_url;
        if (!githubUrl) {
            throw new Error('插件缺少 GitHub 地址');
        }

        // 处理 GitHub URL
        let cleanGithubUrl = githubUrl;
        // 移除 .git 后缀（如果存在）
        if (cleanGithubUrl.endsWith('.git')) {
            cleanGithubUrl = cleanGithubUrl.slice(0, -4);
        }

        // 检查是否已安装（重新安装）
        const isReinstall = plugins && Array.isArray(plugins) && plugins.some(p => p.name === plugin.name);

        // 发送安装请求到本地后端
        console.log(`正在向本地后端发送${isReinstall ? '重新' : ''}安装请求...`);
        const response = await fetch('/api/plugin_market/install', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                plugin_id: plugin.name,
                plugin_data: {
                    name: plugin.name,
                    description: plugin.description,
                    author: plugin.author,
                    version: plugin.version,
                    github_url: cleanGithubUrl,
                    config: {},
                    requirements: []
                }
            })
        });

        if (!response.ok) {
            throw new Error(`安装失败: HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            // 更新按钮状态
            button.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i>${isReinstall ? '已重新安装' : '已安装'}`;
            button.classList.remove('btn-primary');
            button.classList.add('btn-outline-success');

            // 显示成功提示
            showToast(`插件 ${plugin.name} ${isReinstall ? '重新' : ''}安装成功`, 'success');

            // 重置按钮状态并重新显示重新安装按钮
            setTimeout(() => {
                button.innerHTML = `<i class="bi bi-arrow-repeat me-1"></i>重新安装`;
                button.classList.remove('btn-outline-success');
                button.classList.add('btn-outline-primary');
                button.disabled = false;
            }, 3000);

            // 刷新本地插件列表
            setTimeout(() => {
                loadPlugins();
            }, 1000);
        } else {
            throw new Error(result.error || '安装失败');
        }
    } catch (error) {
        console.error('安装插件失败:', error);

        // 恢复按钮状态
        button.disabled = false;
        button.innerHTML = originalText;

        // 显示错误提示
        showToast(`安装失败: ${error.message}`, 'danger');
    }
}

// 获取客户端唯一标识
function getBotClientId() {
    let clientId = localStorage.getItem('xybot_client_id');

    if (!clientId) {
        // 生成UUID v4
        clientId = 'xxxxxxxxxxxx4xxxyxxxxxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
        localStorage.setItem('xybot_client_id', clientId);
    }

    return clientId;
}

// 获取Bot版本信息
function getBotVersion() {
    // 从页面元数据或全局变量获取
    return document.querySelector('meta[name="bot-version"]')?.content || '1.0.0';
}

// 获取平台信息
function getPlatformInfo() {
    return {
        os: navigator.userAgent.includes('Win') ? 'Windows' :
           navigator.userAgent.includes('Mac') ? 'MacOS' :
           navigator.userAgent.includes('Linux') ? 'Linux' : 'Unknown',
        browser: navigator.userAgent
    };
}

// 格式化时间为多久以前
function formatTimeAgo(timestamp) {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);

    const intervals = {
        年: 31536000,
        月: 2592000,
        周: 604800,
        天: 86400,
        小时: 3600,
        分钟: 60,
        秒: 1
    };

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval > 1) {
            return `${interval} ${unit}前`;
        }
    }

    return '刚刚';
}

// 辅助函数：字符串转简单哈希码
function hashCode(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) - hash) + str.charCodeAt(i);
        hash = hash & hash; // 转换为32位整数
    }
    return hash;
}

// 初始化上传模态框
function initUploadModal() {
    console.log('初始化上传模态框');
    const uploadModalEl = document.getElementById('upload-plugin-modal');
    console.log('上传模态框元素:', uploadModalEl);

    try {
        // 如果已存在实例，先销毁
        const existingModal = bootstrap.Modal.getInstance(uploadModalEl);
        if (existingModal) {
            existingModal.dispose();
        }

        // 初始化模态窗口
        uploadModal = new bootstrap.Modal(uploadModalEl, {
            backdrop: true,
            keyboard: true
        });

        console.log('上传模态框初始化成功');

        // 为模态窗口添加事件
        uploadModalEl.addEventListener('hidden.bs.modal', function() {
            console.log('上传模态窗口已隐藏，重置表单');
            // 重置表单
            const form = document.getElementById('upload-plugin-form');
            if (form) form.reset();
        });
    } catch (error) {
        console.error('上传模态框初始化失败:', error);
    }

    // 绑定事件
    const uploadButton = document.getElementById('btn-upload-plugin');
    if (uploadButton) {
        // 清除可能存在的旧事件
        const newUploadButton = uploadButton.cloneNode(true);
        uploadButton.parentNode.replaceChild(newUploadButton, uploadButton);

        // 添加新事件
        newUploadButton.addEventListener('click', function(e) {
            console.log('点击提交插件按钮');
            e.preventDefault();

            // 使用Bootstrap API显示模态窗口
            if (uploadModal) {
                uploadModal.show();
            } else {
                console.error('模态窗口实例不存在');
                // 尝试重新初始化
                uploadModal = new bootstrap.Modal(uploadModalEl);
                uploadModal.show();
            }
        });
    } else {
        console.error('找不到上传插件按钮');
    }
}