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
        const pluginId = this.getAttribute('data-plugin-id');
        if (pluginId) {
            savePluginConfig(pluginId);
        }
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
    
    let html = '';
    
    pluginsList.forEach(plugin => {
        const statusClass = plugin.enabled ? 'success' : 'secondary';
        const statusText = plugin.enabled ? '已启用' : '已禁用';
        
        html += `
            <div class="plugin-card card ${plugin.enabled ? '' : 'disabled'}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="card-title mb-0">${plugin.name}</h5>
                        <span class="badge bg-${statusClass}">${statusText}</span>
                    </div>
                    <p class="card-text">${plugin.description || '暂无描述'}</p>
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="text-muted small">
                            ${plugin.author || '未知作者'} | v${plugin.version || '1.0.0'}
                        </div>
                        <div class="plugin-actions">
                            <button class="btn btn-sm btn-outline-primary btn-config" data-plugin-id="${plugin.id}" ${!plugin.enabled ? 'disabled' : ''}>
                                <i class="bi bi-gear-fill me-1"></i>配置
                            </button>
                            <div class="form-check form-switch ms-2">
                                <input class="form-check-input plugin-toggle" type="checkbox" id="toggle-${plugin.id}" ${plugin.enabled ? 'checked' : ''} data-plugin-id="${plugin.id}">
                                <label class="form-check-label" for="toggle-${plugin.id}"></label>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    pluginList.innerHTML = html;
    
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
        document.getElementById('plugin-config-title').textContent = `${plugin.name} 配置`;

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

        // 监听模态框显示完成事件
        modalEl.addEventListener('shown.bs.modal', async function onShown() {
            try {
                // 获取配置
                const response = await fetch(`/api/plugin_config?plugin_id=${pluginId}`);
                const data = await response.json();
                
                if (data.success) {
                    renderConfigForm(data.config);
                    document.getElementById('plugin-config-loading').style.display = 'none';
                } else {
                    throw new Error(data.error || '获取配置失败');
                }
            } catch (error) {
                console.error('加载配置失败:', error);
                document.getElementById('plugin-config-loading').style.display = 'none';
                document.getElementById('plugin-config-error').style.display = 'block';
                document.getElementById('plugin-config-error').textContent = `加载配置失败: ${error.message}`;
            }
            
            // 移除事件监听器
            modalEl.removeEventListener('shown.bs.modal', onShown);
        });

        // 显示模态框
        modal.show();
        
    } catch (error) {
        console.error('打开配置失败:', error);
        showToast(`配置界面加载失败: ${error.message}`, 'danger');
    }
}

// 渲染配置表单
function renderConfigForm(config) {
    const formContainer = document.getElementById('plugin-config-form');
    formContainer.innerHTML = '';
    
    if (!config || Object.keys(config).length === 0) {
        formContainer.innerHTML = `
            <div class="alert alert-info">
                <i class="bi bi-info-circle-fill me-2"></i>
                此插件没有可配置的选项
            </div>
        `;
        return;
    }
    
    for (const section in config) {
        const sectionEl = document.createElement('div');
        sectionEl.className = 'plugin-config-section mb-4';
        
        const sectionTitle = document.createElement('h5');
        sectionTitle.className = 'mb-3';
        sectionTitle.textContent = section;
        sectionEl.appendChild(sectionTitle);
        
        for (const key in config[section]) {
            const value = config[section][key];
            const formGroup = document.createElement('div');
            formGroup.className = 'mb-3';
            
            const label = document.createElement('label');
            label.className = 'form-label';
            label.textContent = key;
            formGroup.appendChild(label);
            
            let input;
            
            if (typeof value === 'boolean') {
                // 布尔值使用开关
                const switchDiv = document.createElement('div');
                switchDiv.className = 'form-check form-switch';
                
                input = document.createElement('input');
                input.className = 'form-check-input';
                input.type = 'checkbox';
                input.checked = value;
                input.setAttribute('data-section', section);
                input.setAttribute('data-key', key);
                input.setAttribute('data-type', 'boolean');
                
                switchDiv.appendChild(input);
                formGroup.appendChild(switchDiv);
            } else if (typeof value === 'number') {
                // 数字使用数字输入框
                input = document.createElement('input');
                input.className = 'form-control';
                input.type = 'number';
                input.value = value;
                input.setAttribute('data-section', section);
                input.setAttribute('data-key', key);
                input.setAttribute('data-type', 'number');
                formGroup.appendChild(input);
            } else {
                // 字符串使用文本输入框
                input = document.createElement('input');
                input.className = 'form-control';
                input.type = 'text';
                input.value = value;
                input.setAttribute('data-section', section);
                input.setAttribute('data-key', key);
                input.setAttribute('data-type', 'string');
                formGroup.appendChild(input);
            }
            
            sectionEl.appendChild(formGroup);
        }
        
        formContainer.appendChild(sectionEl);
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
function renderMarketPlugins(plugins) {
    const marketList = document.getElementById('market-list');
    
    if (plugins.length === 0) {
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
    
    let html = '';
    
    plugins.forEach((plugin, index) => {
        // 将标签字符串转换为数组
        const tags = plugin.tags ? plugin.tags.split(',') : [];
        
        // 生成标签HTML
        let tagsHtml = '';
        tags.forEach(tag => {
            tagsHtml += `<span class="plugin-tag">${tag.trim()}</span>`;
        });
        
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
        
        html += `
            <div class="col">
                <div class="card h-100">
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-3">
                            <div class="plugin-icon" style="background: linear-gradient(135deg, ${gradientColors[0]}, ${gradientColors[1]});">
                                <i class="bi bi-puzzle"></i>
                            </div>
                            <div>
                                <h5 class="card-title mb-0">${plugin.name}</h5>
                                <div class="text-muted small">v${plugin.version}</div>
                            </div>
                        </div>
                        <p class="card-text">${plugin.description}</p>
                        <div class="mb-3">
                            ${tagsHtml}
                        </div>
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="text-muted small">
                                <i class="bi bi-person me-1"></i>${plugin.author}
                            </div>
                            <button class="btn btn-sm btn-outline-primary btn-install-plugin" data-plugin-index="${index}">
                                <i class="bi bi-download me-1"></i>安装
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    marketList.innerHTML = html;
    
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
        
        // 发送安装请求到本地后端
        console.log('正在向本地后端发送安装请求...');
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
            // 更新安装状态
            button.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i>已安装`;
            button.classList.remove('btn-outline-primary');
            button.classList.add('btn-outline-success');
            
            // 显示成功提示
            showToast(`插件 ${plugin.name} 安装成功`, 'success');
            
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
    return window.BOT_VERSION || '1.0.0';
}

// 获取平台信息
function getPlatformInfo() {
    return {
        os: navigator.platform,
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

// 保存配置
async function savePluginConfig(pluginId) {
    try {
        const formContainer = document.getElementById('plugin-config-form');
        const config = {};
        
        // 收集所有配置项
        const inputs = formContainer.querySelectorAll('input[data-section]');
        inputs.forEach(input => {
            const section = input.getAttribute('data-section');
            const key = input.getAttribute('data-key');
            const type = input.getAttribute('data-type');
            
            if (!config[section]) {
                config[section] = {};
            }
            
            let value;
            if (type === 'boolean') {
                value = input.checked;
            } else if (type === 'number') {
                value = parseFloat(input.value);
            } else {
                value = input.value;
            }
            
            config[section][key] = value;
        });
        
        // 显示保存中状态
        const saveBtn = document.getElementById('plugin-config-save');
        const originalText = saveBtn.textContent;
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>保存中...';
        
        // 发送保存请求
        const response = await fetch('/api/plugin_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plugin_id: pluginId,
                config: config
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