/**
 * 管理后台 - 企业级架构实现
 * 完全对齐真实后端API结构
 */

const API_BASE = '';
const AUTH_API = `${API_BASE}/api/auth`;
const ADMIN_API = `${API_BASE}/api/admin`;
const EVENTS_API = `${API_BASE}/api/events`;
const PRODUCTS_API = `${API_BASE}/api/products`;
const REPORTS_API = `${API_BASE}/api/reports`;

let AUTH_TOKEN = localStorage.getItem('admin_token') || '';

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    if (AUTH_TOKEN) {
        checkAuth();
    } else {
        showLoginPage();
    }
    initEventListeners();
});

function initEventListeners() {
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('logout-btn').addEventListener('click', handleLogout);
    
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = e.currentTarget.dataset.view;
            switchView(view);
        });
    });
}

// ==================== 认证逻辑 ====================
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    showLoading(true);
    try {
        const response = await fetch(`${AUTH_API}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        if (!response.ok) throw new Error('LOGIN_FAILED');
        
        const data = await response.json();
        AUTH_TOKEN = data.access_token;
        localStorage.setItem('admin_token', AUTH_TOKEN);
        
        showAdminPanel();
        loadDashboard();
        showToast('Login successful', 'success');
    } catch (error) {
        console.error('Login failed:', error);
        showToast('Authentication failed. Check credentials.', 'error');
    } finally {
        showLoading(false);
    }
}

async function checkAuth() {
    try {
        const response = await authFetch(`${ADMIN_API}/status`);
        if (response.ok) {
            showAdminPanel();
            loadDashboard();
        } else {
            throw new Error('AUTH_INVALID');
        }
    } catch (error) {
        localStorage.removeItem('admin_token');
        AUTH_TOKEN = '';
        showLoginPage();
    }
}

function handleLogout() {
    localStorage.removeItem('admin_token');
    AUTH_TOKEN = '';
    showLoginPage();
    showToast('Logged out successfully', 'info');
}

function showLoginPage() {
    document.getElementById('login-page').classList.remove('hidden');
    document.getElementById('admin-panel').classList.add('hidden');
}

function showAdminPanel() {
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('admin-panel').classList.remove('hidden');
}

// ==================== 视图切换 ====================
function switchView(view) {
    document.querySelectorAll('.nav-item').forEach(item => {
        if (item.dataset.view === view) {
            item.classList.add('bg-black', 'text-white');
            item.classList.remove('text-gray-600', 'hover:bg-gray-100', 'hover:text-black');
        } else {
            item.classList.remove('bg-black', 'text-white');
            item.classList.add('text-gray-600', 'hover:bg-gray-100', 'hover:text-black');
        }
    });
    
    document.querySelectorAll('[id^="view-"]').forEach(el => el.classList.add('hidden'));
    document.getElementById(`view-${view}`).classList.remove('hidden');
    
    switch(view) {
        case 'dashboard': loadDashboard(); break;
        case 'events': loadEvents(); break;
        case 'products': loadProducts(); break;
        case 'reports': loadReports(); break;
        case 'tokens': loadTokens(); break;
        case 'settings': loadSettings(); break;
    }
}

// ==================== Dashboard ====================
async function loadDashboard() {
    showLoading(true);
    
    try {
        const response = await authFetch(`${ADMIN_API}/status`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);
        
        const data = await response.json();
        
        const statsHtml = `
            <div class="tech-card p-6">
                <div class="flex justify-between items-start mb-6">
                    <span class="font-mono text-xs text-gray-500 uppercase tracking-widest font-semibold">Total Events</span>
                    <i data-lucide="database" class="w-5 h-5 text-black opacity-80"></i>
                </div>
                <div class="text-4xl font-mono font-light tracking-tighter">${data.database?.events_count || 0}</div>
            </div>
            <div class="tech-card p-6">
                <div class="flex justify-between items-start mb-6">
                    <span class="font-mono text-xs text-gray-500 uppercase tracking-widest font-semibold">Pending Tasks</span>
                    <i data-lucide="clock" class="w-5 h-5 text-black opacity-80"></i>
                </div>
                <div class="text-4xl font-mono font-light tracking-tighter">${data.database?.tasks_pending || 0}</div>
            </div>
            <div class="tech-card p-6">
                <div class="flex justify-between items-start mb-6">
                    <span class="font-mono text-xs text-gray-500 uppercase tracking-widest font-semibold">Products</span>
                    <i data-lucide="package" class="w-5 h-5 text-black opacity-80"></i>
                </div>
                <div class="text-4xl font-mono font-light tracking-tighter">${data.database?.products_count || 0}</div>
            </div>
            <div class="tech-card p-6">
                <div class="flex justify-between items-start mb-6">
                    <span class="font-mono text-xs text-gray-500 uppercase tracking-widest font-semibold">DB Size</span>
                    <i data-lucide="hard-drive" class="w-5 h-5 text-black opacity-80"></i>
                </div>
                <div class="text-4xl font-mono font-light tracking-tighter">${data.database?.size_mb || 0}<span class="text-base text-gray-400">MB</span></div>
            </div>
        `;
        document.getElementById('dashboard-stats').innerHTML = statsHtml;
        
        const statusHtml = `
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">GEE Status</span>
                <span class="font-mono text-xs font-bold ${data.gee?.authenticated ? 'text-green-600' : 'text-red-600'}">${data.gee?.authenticated ? 'CONNECTED' : 'OFFLINE'}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">Scheduler</span>
                <span class="font-mono text-xs font-bold ${data.scheduler?.running ? 'text-green-600' : 'text-red-600'}">${data.scheduler?.running ? 'RUNNING' : 'STOPPED'}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">Locked Tasks</span>
                <span class="font-mono text-xs font-bold">${data.database?.tasks_locked || 0}</span>
            </div>
            <div class="flex justify-between py-3">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">System</span>
                <span class="font-mono text-xs font-bold text-green-600">HEALTHY</span>
            </div>
        `;
        document.getElementById('system-status').innerHTML = statusHtml;
        
        lucide.createIcons();
    } catch (error) {
        console.error('Dashboard load failed:', error);
        showToast('Failed to load dashboard data', 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== Events ====================
async function loadEvents() {
    showLoading(true);
    
    try {
        const response = await authFetch(`${EVENTS_API}?page=1&limit=50`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);
        
        const data = await response.json();
        const events = data.data || [];
        
        const tbody = document.getElementById('events-tbody');
        tbody.innerHTML = events.map(event => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-4 px-6 text-gray-500 font-semibold">${event.event_id}-${event.sub_id}</td>
                <td class="py-4 px-6 font-bold text-black max-w-md truncate">${escapeHtml(event.title)}</td>
                <td class="py-4 px-6 text-gray-600 uppercase">${escapeHtml(event.country || 'N/A')}</td>
                <td class="py-4 px-6"><span class="px-2 py-1 bg-gray-100 text-gray-700 text-[10px] font-bold tracking-wider uppercase">${event.status}</span></td>
                <td class="py-4 px-6"><span class="px-2 py-1 ${getSeverityClass(event.severity)} text-[10px] font-bold tracking-wider uppercase">${event.severity || 'N/A'}</span></td>
                <td class="py-4 px-6 text-right">
                    <button onclick="window.processEvent('${event.uuid}')" class="px-3 py-1 border border-gray-300 hover:border-black hover:bg-black hover:text-white transition-colors font-mono text-[10px] font-bold uppercase">
                        PROCESS
                    </button>
                </td>
            </tr>
        `).join('') || '<tr><td colspan="6" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">NO_EVENTS</td></tr>';
        
        lucide.createIcons();
    } catch (error) {
        console.error('Events load failed:', error);
        showToast('Failed to load events', 'error');
    } finally {
        showLoading(false);
    }
}

async function processEvent(uuid) {
    showLoading(true);
    try {
        const response = await authFetch(`${EVENTS_API}/${uuid}/process`, { method: 'POST' });
        if (response.ok) {
            showToast('Event processing initiated', 'success');
            setTimeout(loadEvents, 2000);
        } else {
            showToast('Failed to process event', 'error');
        }
    } catch (error) {
        showToast('Connection error', 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== Products ====================
async function loadProducts() {
    showLoading(true);
    
    try {
        const response = await authFetch(`${PRODUCTS_API}?page=1&limit=50`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);
        
        const data = await response.json();
        const products = data.data || [];
        
        const tbody = document.getElementById('products-tbody');
        tbody.innerHTML = products.map(product => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-4 px-6 text-gray-500 font-mono text-[10px]">${product.uuid.substring(0, 8)}...</td>
                <td class="py-4 px-6 font-bold text-black max-w-sm truncate">${escapeHtml(product.event_title || 'N/A')}</td>
                <td class="py-4 px-6"><span class="px-2 py-1 ${product.summary_generated ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'} text-[10px] font-bold uppercase">${product.summary_generated ? 'YES' : 'NO'}</span></td>
                <td class="py-4 px-6 text-gray-600 text-xs">${formatDate(product.created_at)}</td>
            </tr>
        `).join('') || '<tr><td colspan="4" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">NO_PRODUCTS</td></tr>';
        
    } catch (error) {
        console.error('Products load failed:', error);
        showToast('Failed to load products', 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== Reports ====================
async function loadReports() {
    showLoading(true);
    
    try {
        const response = await authFetch(`${REPORTS_API}?page=1&limit=30`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);
        
        const data = await response.json();
        const reports = data.data || [];
        
        const tbody = document.getElementById('reports-tbody');
        tbody.innerHTML = reports.map(report => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-4 px-6 font-mono font-bold">${report.report_date}</td>
                <td class="py-4 px-6 text-gray-600">${report.event_count || 0}</td>
                <td class="py-4 px-6"><span class="px-2 py-1 ${report.published ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'} text-[10px] font-bold uppercase">${report.published ? 'PUBLISHED' : 'DRAFT'}</span></td>
                <td class="py-4 px-6 text-right">
                    <button onclick="window.viewReport('${report.report_date}')" class="px-3 py-1 border border-gray-300 hover:border-black hover:bg-black hover:text-white transition-colors font-mono text-[10px] font-bold uppercase">
                        VIEW
                    </button>
                </td>
            </tr>
        `).join('') || '<tr><td colspan="4" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">NO_REPORTS</td></tr>';
        
    } catch (error) {
        console.error('Reports load failed:', error);
        showToast('Failed to load reports', 'error');
    } finally {
        showLoading(false);
    }
}

async function generateReport() {
    showLoading(true);
    
    try {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const reportDate = yesterday.toISOString().split('T')[0];
        
        const response = await authFetch(`${REPORTS_API}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: reportDate })
        });
        
        if (response.ok) {
            showToast('Report generation started', 'success');
            setTimeout(loadReports, 2000);
        } else {
            showToast('Failed to generate report', 'error');
        }
    } catch (error) {
        showToast('Connection error', 'error');
    } finally {
        showLoading(false);
    }
}

async function viewReport(date) {
    showLoading(true);
    
    try {
        const response = await authFetch(`${REPORTS_API}/${date}`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);
        
        const data = await response.json();
        showModal(`REPORT_${date}`, `<pre class="font-mono text-xs whitespace-pre-wrap">${escapeHtml(data.report_content || 'No content')}</pre>`);
    } catch (error) {
        showToast('Failed to load report', 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== Tokens ====================
async function loadTokens() {
    showLoading(true);
    
    try {
        const response = await authFetch(`${ADMIN_API}/tokens`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);
        
        const tokens = await response.json();
        
        const tbody = document.getElementById('tokens-tbody');
        tbody.innerHTML = (Array.isArray(tokens) ? tokens : []).map(token => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-4 px-6 font-mono font-bold">${escapeHtml(token.name)}</td>
                <td class="py-4 px-6"><span class="px-2 py-1 ${token.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'} text-[10px] font-bold uppercase">${token.is_active ? 'ENABLED' : 'DISABLED'}</span></td>
                <td class="py-4 px-6 text-gray-600 text-xs">${formatDate(token.created_at)}</td>
            </tr>
        `).join('') || '<tr><td colspan="3" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">NO_TOKENS</td></tr>';
        
    } catch (error) {
        console.error('Tokens load failed:', error);
        showToast('Failed to load tokens', 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== Manual Jobs ====================
async function triggerJob(job) {
    const jobMap = {
        'fetch': 'fetch_rsoe_data',
        'pool': 'process_pool',
        'unlock': 'release_timeout_locks'
    };
    
    const jobId = jobMap[job];
    if (!jobId) return;
    
    showLoading(true);
    try {
        const response = await authFetch(`${ADMIN_API}/jobs/${jobId}/trigger`, { method: 'POST' });
        if (response.ok) {
            showToast(`Job ${jobId} triggered successfully`, 'success');
        } else {
            showToast('Failed to trigger job', 'error');
        }
    } catch (error) {
        showToast('Connection error', 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== 工具函数 ====================
async function authFetch(url, options = {}) {
    return fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            'Authorization': `Bearer ${AUTH_TOKEN}`,
            'Content-Type': 'application/json'
        }
    });
}

function showLoading(show) {
    document.getElementById('loading').classList.toggle('hidden', !show);
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    
    const colors = {
        success: 'border-green-500 bg-green-50',
        error: 'border-red-500 bg-red-50',
        info: 'border-gray-300 bg-white'
    };
    
    toast.className = `toast tech-card p-4 border-l-4 ${colors[type] || colors.info}`;
    toast.innerHTML = `
        <div class="font-mono text-xs font-bold tracking-wider uppercase mb-1">${type.toUpperCase()}</div>
        <div class="font-mono text-xs text-gray-700">${escapeHtml(message)}</div>
    `;
    
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function showModal(title, content) {
    alert(`${title}\n\n${content}`);
}

function getSeverityClass(severity) {
    const map = {
        'extreme': 'bg-red-600 text-white',
        'high': 'bg-orange-500 text-white',
        'medium': 'bg-yellow-500 text-black',
        'low': 'bg-gray-400 text-white'
    };
    return map[severity?.toLowerCase()] || 'bg-gray-300 text-gray-700';
}

function formatDate(timestamp) {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toISOString().split('T')[0];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== Settings ====================

// 当前从服务器加载的原始 settings（用于判断 password 字段是否有变化）
let _settingsCache = {};

async function loadSettings() {
    showLoading(true);
    try {
        const resp = await authFetch(`${ADMIN_API}/settings`);
        if (!resp.ok) throw new Error(`HTTP_${resp.status}`);
        const data = await resp.json();
        _settingsCache = data;
        _fillSettingsForm(data);
        lucide.createIcons();
    } catch (e) {
        showToast('Failed to load settings: ' + e.message, 'error');
    } finally {
        showLoading(false);
    }
}

function _fillSettingsForm(data) {
    document.querySelectorAll('#view-settings [data-key]').forEach(el => {
        const key = el.dataset.key;
        const val = data[key];
        if (val === undefined || val === null) return;

        if (el.tagName === 'SELECT') {
            // bool 值转字符串对比
            el.value = String(val);
        } else if (el.type === 'password') {
            // 脱敏占位符放 placeholder，input 留空（让用户主动填写才提交）
            el.placeholder = val || '';
            el.value = '';
        } else {
            el.value = val;
        }
    });
}

function toggleSection(sectionId) {
    const el = document.getElementById(sectionId);
    const chevron = document.getElementById('chevron-' + sectionId);
    if (!el) return;
    const hidden = el.classList.toggle('hidden');
    if (chevron) {
        chevron.style.transform = hidden ? '' : 'rotate(180deg)';
    }
}

async function saveSettingsGroup(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) return;

    const updates = {};
    section.querySelectorAll('[data-key]').forEach(el => {
        const key = el.dataset.key;
        let value = el.value;

        if (el.type === 'password') {
            // 空 = 未修改，跳过；非空 = 用户输入了新值
            if (!value.trim()) return;
        }
        if (el.tagName === 'SELECT') {
            // bool 字段
            updates[key] = value;
            return;
        }
        if (value === '' && _settingsCache[key] !== undefined) return; // 空且有原始值，跳过
        updates[key] = value;
    });

    if (Object.keys(updates).length === 0) {
        showToast('No changes to save', 'info');
        return;
    }

    showLoading(true);
    try {
        const resp = await authFetch(`${ADMIN_API}/settings`, {
            method: 'PUT',
            body: JSON.stringify(updates),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || resp.statusText);
        }
        const result = await resp.json();
        showToast(result.message || 'Settings saved', 'success');
        // 重新加载以显示最新值
        await loadSettings();
    } catch (e) {
        showToast('Save failed: ' + e.message, 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== 全局导出 ====================
window.processEvent = processEvent;
window.viewReport = viewReport;
window.generateReport = generateReport;
window.loadEvents = loadEvents;
window.loadProducts = loadProducts;
window.loadReports = loadReports;
window.loadTokens = loadTokens;
window.triggerJob = triggerJob;
window.loadSettings = loadSettings;
window.toggleSection = toggleSection;
window.saveSettingsGroup = saveSettingsGroup;
