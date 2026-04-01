/**
 * 管理后台 - 企业级架构实现
 * 完全对齐真实后端API结构
 */

const API_BASE = '';
const AUTH_API = `${API_BASE}/api/auth`;
const ADMIN_API = `${API_BASE}/api/admin`;
const EVENTS_API = `${API_BASE}/api/events`;
const POOL_API = `${API_BASE}/api/pool`;
const PRODUCTS_API = `${API_BASE}/api/products`;
const REPORTS_API = `${API_BASE}/api/reports`;
const TASKS_API = `${ADMIN_API}/tasks`;

let AUTH_TOKEN = localStorage.getItem('admin_token') || '';

// 分页状态
let _eventsPage = 1;
let _rawPoolPage = 1;
let _trackPage = 1;
let _tasksPage = 1;
let _productsPage = 1;
let _reportsPage = 1;

const STATUS_LABELS = {
    pending: '待处理',
    pool: '事件池',
    checked: '已质检',
    queued: '已入队',
    processing: '处理中',
    completed: '已完成',
    failed: '失败'
};

const SEVERITY_LABELS = {
    extreme: '极高',
    high: '高',
    medium: '中',
    low: '低'
};

const TOAST_TYPE_LABELS = {
    success: '成功',
    error: '错误',
    info: '提示'
};

const TASK_STATUS_LABELS = {
    pending: '待执行',
    running: '执行中',
    paused: '已暂停',
    pause_requested: '暂停中',
    completed: '已完成',
    failed: '已停止'
};

const TASK_STAGE_LABELS = {
    queued: '等待 Latest Model 队列',
    preparing: '准备影像',
    submitted: 'Latest Model 任务已提交',
    polling: '轮询 Latest Model 结果',
    paused: '已暂停',
    pause_requested: '暂停请求中',
    completed: '已完成',
    failed: '已停止'
};

const JOB_LABELS = {
    fetch_rsoe_data: '抓取 RSOE 数据',
    fetch_event_details: '补抓事件详情',
    process_pool: '处理事件池',
    process_inference_queue: '执行推理队列',
    recheck_imagery: '重新检查影像'
};

const VIEW_LABELS = {
    dashboard: '系统概览',
    pool: '事件池',
    events: '事件管理',
    tasks: '任务进度',
    products: '成品池',
    reports: '灾害日报',
    settings: '系统配置',
    workflow: '工作流',
};

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    initDefaultDates();
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
    document.getElementById('sidebar-toggle-btn')?.addEventListener('click', openSidebar);
    document.getElementById('sidebar-close-btn')?.addEventListener('click', closeSidebar);
    document.getElementById('sidebar-backdrop')?.addEventListener('click', closeSidebar);
    window.addEventListener('resize', handleViewportChange);
    document.addEventListener('keydown', handleGlobalKeydown);

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = e.currentTarget.dataset.view;
            switchView(view);
        });
    });
}

function initDefaultDates() {
    const reportDateInput = document.getElementById('report-generate-date');
    if (reportDateInput && !reportDateInput.value) {
        const date = new Date();
        date.setDate(date.getDate() - 1);
        reportDateInput.value = formatDateInput(date);
    }
    const dateLabel = document.getElementById('topbar-date');
    if (dateLabel) {
        const now = new Date();
        dateLabel.textContent = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    }
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
        showToast('登录成功', 'success');
    } catch (error) {
        console.error('Login failed:', error);
        showToast('登录失败，请检查用户名和密码', 'error');
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
    showToast('已退出登录', 'info');
}

function showLoginPage() {
    document.getElementById('login-page').classList.remove('hidden');
    document.getElementById('admin-panel').classList.add('hidden');
    document.body.classList.remove('sidebar-open');
}

function showAdminPanel() {
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('admin-panel').classList.remove('hidden');
    document.getElementById('admin-panel').classList.add('flex');
    updateViewTitle('dashboard');
    handleViewportChange();
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
    updateViewTitle(view);
    if (window.innerWidth < 1024) closeSidebar();

    switch(view) {
        case 'dashboard': loadDashboard(); break;
        case 'pool': loadPool(); break;
        case 'events': loadEvents(1); break;
        case 'tasks': loadTaskProgress(1); break;
        case 'products': loadProducts(); break;
        case 'reports': loadReports(); break;
        case 'settings': loadSettings(); break;
        case 'workflow': initWorkflow(); break;
    }
}

function openSidebar() {
    const sidebar = document.getElementById('admin-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!sidebar || window.innerWidth >= 1024) return;
    sidebar.classList.remove('-translate-x-full');
    backdrop?.classList.remove('hidden');
    document.body.classList.add('sidebar-open');
}

function closeSidebar() {
    const sidebar = document.getElementById('admin-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!sidebar || window.innerWidth >= 1024) return;
    sidebar.classList.add('-translate-x-full');
    backdrop?.classList.add('hidden');
    document.body.classList.remove('sidebar-open');
}

function handleViewportChange() {
    const sidebar = document.getElementById('admin-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!sidebar) return;
    if (window.innerWidth >= 1024) {
        sidebar.classList.remove('-translate-x-full');
        backdrop?.classList.add('hidden');
        document.body.classList.remove('sidebar-open');
    } else {
        sidebar.classList.add('-translate-x-full');
    }
}

function updateViewTitle(view) {
    const label = VIEW_LABELS[view] || '管理后台';
    const topbarTitle = document.getElementById('topbar-title');
    const sidebarTitle = document.getElementById('sidebar-current-view');
    if (topbarTitle) topbarTitle.textContent = label;
    if (sidebarTitle) sidebarTitle.textContent = label;
}

function handleGlobalKeydown(event) {
    if (event.key === 'Escape') {
        document.getElementById('detail-modal')?.remove();
        closeSidebar();
    }
}

// ==================== Dashboard ====================
async function loadDashboard() {
    showLoading(true);

    try {
        const [statusResp, statsResp] = await Promise.all([
            authFetch(`${ADMIN_API}/status`),
            authFetch(`${EVENTS_API}/stats`),
        ]);

        if (!statusResp.ok) throw new Error(`HTTP_${statusResp.status}`);
        const data = await statusResp.json();
        const stats = statsResp.ok ? await statsResp.json() : null;

        const trackingCount = stats?.by_imagery_status?.post_pending ?? '—';

        const statsHtml = `
            <div class="tech-card p-5">
                <div class="flex justify-between items-start mb-4">
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">事件总数</span>
                    <i data-lucide="database" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${data.database?.events_count || 0}</div>
            </div>
            <div class="tech-card p-5">
                <div class="flex justify-between items-start mb-4">
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">待推理任务</span>
                    <i data-lucide="clock" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${data.database?.tasks_pending || 0}</div>
            </div>
            <div class="tech-card p-5">
                <div class="flex justify-between items-start mb-4">
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">影像追踪中</span>
                    <i data-lucide="satellite-dish" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${trackingCount}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">灾后影像待获取</div>
            </div>
            <div class="tech-card p-5">
                <div class="flex justify-between items-start mb-4">
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">成品数量</span>
                    <i data-lucide="package" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${data.database?.products_count || 0}</div>
            </div>
            <div class="tech-card p-5">
                <div class="flex justify-between items-start mb-4">
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">数据库大小</span>
                    <i data-lucide="hard-drive" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${data.database?.size_mb || 0}<span class="text-sm text-gray-400">MB</span></div>
            </div>
        `;
        document.getElementById('dashboard-stats').innerHTML = statsHtml;

        const statusHtml = `
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">运行环境</span>
                <span class="font-mono text-xs font-bold">${escapeHtml(data.system?.env || '暂无')}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">系统版本</span>
                <span class="font-mono text-xs font-bold">${escapeHtml(data.system?.version || '暂无')}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">GEE 状态</span>
                <span class="font-mono text-xs font-bold ${data.gee?.authenticated ? 'text-green-600' : 'text-red-600'}">${data.gee?.authenticated ? '已连接' : '离线'}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">GEE 运行任务</span>
                <span class="font-mono text-xs font-bold">${data.gee?.running_tasks ?? 0}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">配额告警</span>
                <span class="font-mono text-xs font-bold ${data.gee?.quota_warning ? 'text-orange-600' : 'text-green-600'}">${data.gee?.quota_warning ? '有告警' : '正常'}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">调度器</span>
                <span class="font-mono text-xs font-bold ${data.scheduler?.running ? 'text-green-600' : 'text-red-600'}">${data.scheduler?.running ? '运行中' : '已停止'}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">运行中任务</span>
                <span class="font-mono text-xs font-bold">${data.database?.tasks_running || 0}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">待补抓详情</span>
                <span class="font-mono text-xs font-bold">${data.database?.details_pending || 0}</span>
            </div>
            <div class="flex justify-between py-3 border-b border-gray-100">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">详情 404</span>
                <span class="font-mono text-xs font-bold">${data.database?.details_not_found || 0}</span>
            </div>
            <div class="flex justify-between py-3">
                <span class="font-mono text-xs uppercase tracking-wider text-gray-500">系统</span>
                <span class="font-mono text-xs font-bold text-green-600">健康</span>
            </div>
            ${(data.scheduler?.next_jobs?.length ?? 0) > 0 ? `
            <div class="border-t border-gray-100 pt-4">
                <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest mb-2">下一批调度任务</div>
                <div class="space-y-2">
                    ${data.scheduler.next_jobs.slice(0, 4).map(job => `
                        <div class="flex justify-between gap-3 font-mono text-[10px]">
                            <span class="text-gray-500">${escapeHtml(job.job_id)}</span>
                            <span class="text-black">${formatDateTime(job.next_run)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>` : ''}
        `;
        document.getElementById('system-status').innerHTML = statusHtml;

        lucide.createIcons();
    } catch (error) {
        console.error('Dashboard load failed:', error);
        showToast('加载系统概览失败', 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== Event Pool ====================
async function loadPool() {
    await Promise.all([loadPoolStats(), loadRawPool(1)]);
}

async function loadPoolStats() {
    try {
        const [poolResp, evResp] = await Promise.all([
            authFetch(`${POOL_API}/stats`),
            authFetch(`${EVENTS_API}/stats`),
        ]);
        const ps = poolResp.ok ? await poolResp.json() : {};
        const es = evResp.ok ? await evResp.json() : {};

        const imgStatus = es.by_imagery_status || {};
        const evByStatus = es.by_status || {};

        document.getElementById('pool-stats-row').innerHTML = `
            <div class="tech-card p-5">
                <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-3">原始池总量</div>
                <div class="text-3xl font-mono font-light tracking-tighter">${ps.total_events ?? '—'}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">活跃: ${ps.active_events ?? '—'}</div>
            </div>
            <div class="tech-card p-5">
                <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-3">处理中</div>
                <div class="text-3xl font-mono font-light tracking-tighter">${(evByStatus.pending||0) + (evByStatus.pool||0)}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">待处理 + 事件池</div>
            </div>
            <div class="tech-card p-5">
                <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-3">影像追踪</div>
                <div class="text-3xl font-mono font-light tracking-tighter">${imgStatus.post_pending ?? '—'}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">灾后影像待追踪</div>
            </div>
            <div class="tech-card p-5">
                <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-3">双影像就绪</div>
                <div class="text-3xl font-mono font-light tracking-tighter">${imgStatus.both_ready ?? '—'}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">灾前 + 灾后已下载</div>
            </div>
        `;
        syncCategoryOptions('pool-filter-category', ps.by_category || {});
        lucide.createIcons();
    } catch(e) {
        console.error('Pool stats failed:', e);
    }
}

function switchPoolTab(tab) {
    const tabs = ['raw', 'track'];
    tabs.forEach(t => {
        const btn = document.getElementById(`pool-tab-${t}`);
        const panel = document.getElementById(`pool-panel-${t}`);
        if (t === tab) {
            btn.classList.remove('border-transparent', 'text-gray-500');
            btn.classList.add('border-black', 'text-black');
            panel.classList.remove('hidden');
        } else {
            btn.classList.remove('border-black', 'text-black');
            btn.classList.add('border-transparent', 'text-gray-500');
            panel.classList.add('hidden');
        }
    });
    if (tab === 'track') loadTrack(1);
    if (tab === 'raw') loadRawPool(1);
}

async function loadRawPool(page = 1) {
    _rawPoolPage = page;
    const category = document.getElementById('pool-filter-category')?.value || '';
    const severity = document.getElementById('pool-filter-severity')?.value || '';
    const country = document.getElementById('pool-filter-country')?.value || '';
    const activeOnly = document.getElementById('pool-filter-active')?.checked ?? true;

    let url = `${POOL_API}?page=${page}&limit=50`;
    if (category) url += `&category=${encodeURIComponent(category)}`;
    if (severity) url += `&severity=${encodeURIComponent(severity)}`;
    if (country) url += `&country=${encodeURIComponent(country)}`;
    url += `&active_only=${activeOnly}`;

    try {
        const resp = await authFetch(url);
        if (!resp.ok) throw new Error(`HTTP_${resp.status}`);
        const data = await resp.json();
        const items = data.data || [];

        document.getElementById('raw-pool-tbody').innerHTML = items.map(ev => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-3 px-4 text-gray-500">${ev.event_id}-${ev.sub_id}</td>
                <td class="py-3 px-4 font-semibold max-w-xs truncate" title="${escapeHtml(ev.title)}">${escapeHtml(ev.title)}</td>
                <td class="py-3 px-4 text-gray-600">${escapeHtml(ev.category_name || ev.category || '暂无')}</td>
                <td class="py-3 px-4 text-gray-600 uppercase">${escapeHtml(ev.country || '暂无')}</td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 ${getSeverityClass(ev.severity)} text-[10px] font-bold uppercase">${labelSeverity(ev.severity)}</span></td>
                <td class="py-3 px-4 text-gray-500">${formatDate(ev.last_seen)}</td>
                <td class="py-3 px-4 text-gray-600">${ev.fetch_count}</td>
                <td class="py-3 px-4 text-right">
                    <button onclick="window.showPoolEventDetail(${ev.event_id}, ${ev.sub_id ?? 0})" class="px-2 py-1 border border-gray-200 hover:border-black font-mono text-[10px] font-bold uppercase">详情</button>
                </td>
            </tr>
        `).join('') || '<tr><td colspan="8" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">暂无数据</td></tr>';

        renderPagination('raw-pool-pagination', data.page, data.pages, loadRawPool);
    } catch(e) {
        console.error('Raw pool failed:', e);
        showToast('加载原始事件池失败', 'error');
    }
}

async function showPoolEventDetail(eventId, subId = 0) {
    showLoading(true);
    try {
        const response = await authFetch(`${POOL_API}/${eventId}/${subId}`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);
        const ev = await response.json();
        const content = `
            <div class="space-y-4 font-mono text-xs">
                <div class="grid grid-cols-2 gap-3">
                    <div><span class="text-gray-500 uppercase">事件 ID</span><div class="font-bold mt-1">${ev.event_id}-${ev.sub_id}</div></div>
                    <div><span class="text-gray-500 uppercase">状态</span><div class="font-bold mt-1">${ev.is_active ? '活跃' : '已失活'}</div></div>
                    <div><span class="text-gray-500 uppercase">类别</span><div class="font-bold mt-1">${escapeHtml(ev.category_name || ev.category || '暂无')}</div></div>
                    <div><span class="text-gray-500 uppercase">严重程度</span><div class="font-bold mt-1 ${getSeverityClass(ev.severity)} px-2 py-0.5 inline-block uppercase text-[10px]">${labelSeverity(ev.severity)}</div></div>
                    <div><span class="text-gray-500 uppercase">国家</span><div class="font-bold mt-1">${escapeHtml(ev.country || '暂无')}</div></div>
                    <div><span class="text-gray-500 uppercase">坐标</span><div class="font-bold mt-1">${ev.longitude?.toFixed(4) ?? '—'}, ${ev.latitude?.toFixed(4) ?? '—'}</div></div>
                    <div><span class="text-gray-500 uppercase">首次发现</span><div class="font-bold mt-1">${formatDateTime(ev.first_seen)}</div></div>
                    <div><span class="text-gray-500 uppercase">最后出现</span><div class="font-bold mt-1">${formatDateTime(ev.last_seen)}</div></div>
                </div>
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">标题</div>
                    <div class="leading-6">${escapeHtml(ev.title || '暂无')}</div>
                </div>
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">附加信息</div>
                    <div class="grid grid-cols-2 gap-3">
                        <div><span class="text-gray-500 uppercase">地址</span><div class="font-bold mt-1">${escapeHtml(ev.address || '暂无')}</div></div>
                        <div><span class="text-gray-500 uppercase">抓取次数</span><div class="font-bold mt-1">${ev.fetch_count ?? 0}</div></div>
                        <div><span class="text-gray-500 uppercase">事件日期</span><div class="font-bold mt-1">${formatDateTime(ev.event_date)}</div></div>
                        <div><span class="text-gray-500 uppercase">最后更新</span><div class="font-bold mt-1">${formatDateTime(ev.last_update)}</div></div>
                    </div>
                </div>
            </div>
        `;
        showModal(`事件池详情 ${ev.event_id}-${ev.sub_id}`, content);
    } catch (error) {
        showToast('加载事件池详情失败', 'error');
    } finally {
        showLoading(false);
    }
}

async function loadTrack(page = 1) {
    _trackPage = page;
    const status = document.getElementById('track-filter-status')?.value || '';
    const severity = document.getElementById('track-filter-severity')?.value || '';
    const imageryOpen = document.getElementById('track-filter-imagery-open')?.checked ?? false;

    let url = `${EVENTS_API}?page=${page}&limit=50`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (severity) url += `&severity=${encodeURIComponent(severity)}`;
    if (imageryOpen) url += `&imagery_open=true`;

    try {
        const resp = await authFetch(url);
        if (!resp.ok) throw new Error(`HTTP_${resp.status}`);
        const data = await resp.json();
        const events = data.data || [];

        document.getElementById('track-tbody').innerHTML = events.map(ev => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-3 px-4 font-semibold max-w-xs truncate" title="${escapeHtml(ev.title)}">${escapeHtml(ev.title)}</td>
                <td class="py-3 px-4 text-gray-600 uppercase">${escapeHtml(ev.country || '暂无')}</td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 bg-gray-100 text-gray-700 text-[10px] font-bold uppercase">${labelStatus(ev.status)}</span></td>
                <td class="py-3 px-4">${formatImageryStatus(ev)}</td>
                <td class="py-3 px-4">${formatImageryCounts(ev)}</td>
                <td class="py-3 px-4">${renderImageryEntry(ev)}</td>
                <td class="py-3 px-4 text-right">
                    ${renderProcessButton(ev)}
                </td>
            </tr>
        `).join('') || '<tr><td colspan="7" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">暂无数据</td></tr>';

        renderPagination('track-pagination', data.page, data.pages, loadTrack);
    } catch(e) {
        console.error('Track load failed:', e);
        showToast('加载处理追踪失败', 'error');
    }
}

// ==================== Events ====================
async function loadEvents(page = 1) {
    _eventsPage = page;
    showLoading(true);

    const status = document.getElementById('ev-filter-status')?.value || '';
    const severity = document.getElementById('ev-filter-severity')?.value || '';
    const country = document.getElementById('ev-filter-country')?.value || '';
    const imageryOpen = document.getElementById('ev-filter-imagery-open')?.checked ?? false;

    let url = `${EVENTS_API}?page=${page}&limit=50`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (severity) url += `&severity=${encodeURIComponent(severity)}`;
    if (country) url += `&country=${encodeURIComponent(country)}`;
    if (imageryOpen) url += `&imagery_open=true`;

    try {
        const [response, statsResponse] = await Promise.all([
            authFetch(url),
            authFetch(`${EVENTS_API}/stats`)
        ]);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);

        const data = await response.json();
        const stats = statsResponse.ok ? await statsResponse.json() : null;
        const events = data.data || [];

        renderEventStatsRow(stats);

        const tbody = document.getElementById('events-tbody');
        tbody.innerHTML = events.map(event => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-3 px-4 font-semibold max-w-xs truncate" title="${escapeHtml(event.title)}">${escapeHtml(event.title)}</td>
                <td class="py-3 px-4 text-gray-600 uppercase">${escapeHtml(event.country || '暂无')}</td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 bg-gray-100 text-gray-700 text-[10px] font-bold uppercase">${labelStatus(event.status)}</span></td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 ${getSeverityClass(event.severity)} text-[10px] font-bold uppercase">${labelSeverity(event.severity)}</span></td>
                <td class="py-3 px-4">${formatImageryStatus(event)}</td>
                <td class="py-3 px-4">${formatImageryCounts(event)}</td>
                <td class="py-3 px-4">${renderImageryEntry(event)}</td>
                <td class="py-3 px-4 text-right">
                    <button onclick="window.showEventDetail('${event.uuid}')" class="px-2 py-1 border border-gray-200 hover:border-black font-mono text-[10px] font-bold uppercase mr-1">详情</button>
                    ${renderProcessButton(event)}
                </td>
            </tr>
        `).join('') || '<tr><td colspan="8" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">暂无事件</td></tr>';

        renderPagination('events-pagination', data.page, data.pages, loadEvents);
        lucide.createIcons();
    } catch (error) {
        console.error('Events load failed:', error);
        showToast('加载事件列表失败', 'error');
    } finally {
        showLoading(false);
    }
}

async function showEventDetail(uuid) {
    showLoading(true);
    try {
        const [evResp, geeResp] = await Promise.all([
            authFetch(`${EVENTS_API}/${uuid}`),
            authFetch(`${EVENTS_API}/${uuid}/gee-tasks`),
        ]);
        if (!evResp.ok) throw new Error(`HTTP_${evResp.status}`);
        const ev = await evResp.json();
        const geeData = geeResp.ok ? await geeResp.json() : { data: [] };

        const preStatus = ev.pre_image_downloaded
            ? `<span class="text-green-600 font-bold">✓ 已下载</span> (${ev.pre_image_source || '暂无'}, ${ev.pre_window_days} 天窗口)`
            : ev.pre_imagery_exhausted
                ? `<span class="text-red-600 font-bold">✗ 已穷尽</span> (已达到最大窗口)`
                : `<span class="text-yellow-600 font-bold">⏳ 搜索中</span> (${ev.pre_window_days} 天窗口)`;

        const postStatus = ev.post_image_downloaded
            ? `<span class="text-green-600 font-bold">✓ 已下载</span> (${ev.post_image_source || '暂无'}, ${ev.post_window_days} 天窗口)`
            : ev.post_imagery_open === false
                ? `<span class="text-red-600 font-bold">✗ 已停止</span> (已达到最大窗口)`
                : `<span class="text-yellow-600 font-bold">⏳ 追踪中</span> (${ev.post_window_days} 天窗口，已检查 ${ev.imagery_check_count ?? 0} 次${ev.post_imagery_last_check ? '，最近: ' + formatDate(ev.post_imagery_last_check) : ''})`;

        const preCount = ev.pre_imagery_count ?? (ev.pre_image_downloaded ? 1 : 0);
        const postCount = ev.post_imagery_count ?? (ev.post_image_downloaded ? 1 : 0);

        const imageSection = `
        <div class="border-t border-gray-100 pt-4">
            <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">
                卫星影像预览
                <span class="text-gray-400 font-normal ml-2">灾前 ${preCount} 张 / 灾后 ${postCount} 张</span>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <div class="font-mono text-[10px] text-gray-500 uppercase mb-2">灾前影像</div>
                    ${ev.has_pre_image
                        ? `<img src="/api/public/image/${encodeURIComponent(ev.uuid)}/pre"
                                class="w-full border border-gray-200 bg-gray-50"
                                style="max-height:220px;object-fit:contain;" loading="lazy"
                                onerror="this.outerHTML='<div class=\\'text-red-500 text-[10px] p-2 border border-red-200\\'>加载失败</div>'">`
                        : `<div class="border border-gray-200 bg-gray-50 flex items-center justify-center h-28 text-gray-400 text-[10px]">无影像</div>`}
                </div>
                <div>
                    <div class="font-mono text-[10px] text-gray-500 uppercase mb-2">灾后影像</div>
                    ${ev.has_post_image
                        ? `<img src="/api/public/image/${encodeURIComponent(ev.uuid)}/post"
                                class="w-full border border-gray-200 bg-gray-50"
                                style="max-height:220px;object-fit:contain;" loading="lazy"
                                onerror="this.outerHTML='<div class=\\'text-red-500 text-[10px] p-2 border border-red-200\\'>加载失败</div>'">`
                        : `<div class="border border-gray-200 bg-gray-50 flex items-center justify-center h-28 text-gray-400 text-[10px]">无影像</div>`}
                </div>
            </div>
        </div>`;

        const geeTasks = geeData.data || [];
        const geeSection = `
        <div class="border-t border-gray-100 pt-4">
            <div class="flex items-center justify-between mb-3">
                <div class="font-bold uppercase tracking-widest text-gray-600">GEE 任务历史 (${geeTasks.length} 条)</div>
                <button onclick="window.exportGeeTasksCsv()" class="px-2 py-1 border border-gray-200 hover:border-black font-mono text-[10px] font-bold uppercase transition-colors">导出全部</button>
            </div>
            ${geeTasks.length === 0
                ? `<div class="text-gray-400 text-[10px]">暂无记录</div>`
                : `<div class="overflow-x-auto">
                    <table class="w-full text-[10px]">
                        <thead><tr class="border-b border-gray-200 bg-gray-50">
                            <th class="py-2 px-2 text-left font-bold uppercase text-gray-500">类型</th>
                            <th class="py-2 px-2 text-left font-bold uppercase text-gray-500">状态</th>
                            <th class="py-2 px-2 text-left font-bold uppercase text-gray-500">日期范围</th>
                            <th class="py-2 px-2 text-left font-bold uppercase text-gray-500">影像日期</th>
                            <th class="py-2 px-2 text-left font-bold uppercase text-gray-500">来源</th>
                            <th class="py-2 px-2 text-left font-bold uppercase text-gray-500">重试</th>
                            <th class="py-2 px-2 text-left font-bold uppercase text-gray-500">失败原因</th>
                        </tr></thead>
                        <tbody>
                            ${geeTasks.map(t => `
                            <tr class="border-b border-gray-100 hover:bg-gray-50">
                                <td class="py-2 px-2">${t.task_type === 'pre_disaster' ? '灾前' : '灾后'}</td>
                                <td class="py-2 px-2"><span class="${geeStatusClass(t.status)} px-1.5 py-0.5 font-bold">${t.status}</span></td>
                                <td class="py-2 px-2 whitespace-nowrap">${escapeHtml(t.start_date || '—')} ~ ${escapeHtml(t.end_date || '—')}</td>
                                <td class="py-2 px-2 whitespace-nowrap">${formatDate(t.image_date)}</td>
                                <td class="py-2 px-2">${escapeHtml(t.image_source || '—')}</td>
                                <td class="py-2 px-2">${t.retry_count}/${t.max_retries}</td>
                                <td class="py-2 px-2 text-red-600 max-w-[140px] truncate" title="${escapeHtml(t.failure_reason || '')}">${escapeHtml(t.failure_reason || '—')}</td>
                            </tr>`).join('')}
                        </tbody>
                    </table>
                </div>`}
        </div>`;

        const content = `
            <div class="space-y-4 font-mono text-xs">
                <div class="grid grid-cols-2 gap-3">
                    <div><span class="text-gray-500 uppercase">状态</span><div class="font-bold mt-1">${labelStatus(ev.status)}</div></div>
                    <div><span class="text-gray-500 uppercase">严重程度</span><div class="font-bold mt-1 ${getSeverityClass(ev.severity)} px-2 py-0.5 inline-block uppercase text-[10px]">${labelSeverity(ev.severity)}</div></div>
                    <div><span class="text-gray-500 uppercase">国家</span><div class="font-bold mt-1 uppercase">${ev.country || '暂无'}</div></div>
                    <div><span class="text-gray-500 uppercase">类别</span><div class="font-bold mt-1">${ev.category_name || ev.category || '暂无'}</div></div>
                    <div><span class="text-gray-500 uppercase">坐标</span><div class="font-bold mt-1">${ev.longitude?.toFixed(4) ?? '—'}, ${ev.latitude?.toFixed(4) ?? '—'}</div></div>
                    <div><span class="text-gray-500 uppercase">事件日期</span><div class="font-bold mt-1">${formatDate(ev.event_date)}</div></div>
                    <div><span class="text-gray-500 uppercase">地址</span><div class="font-bold mt-1">${escapeHtml(ev.address || '暂无')}</div></div>
                    <div><span class="text-gray-500 uppercase">最近更新</span><div class="font-bold mt-1">${formatDateTime(ev.last_update)}</div></div>
                </div>
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">影像追踪</div>
                    <div class="space-y-2">
                        <div class="flex gap-3 items-start"><span class="text-gray-500 w-14 shrink-0">灾前:</span><span>${preStatus}</span></div>
                        <div class="flex gap-3 items-start"><span class="text-gray-500 w-14 shrink-0">灾后:</span><span>${postStatus}</span></div>
                    </div>
                </div>
                ${imageSection}
                ${geeSection}
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">推理任务</div>
                    <button onclick="window.jumpToTaskProgress('${ev.uuid}')" class="px-2 py-1 border border-gray-300 hover:border-black hover:bg-gray-100 transition-colors font-mono text-[10px] font-bold uppercase">查看任务进度</button>
                </div>
                ${ev.quality_checked ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">质量评估</div>
                    <div>得分: <span class="font-bold">${ev.quality_score ?? '暂无'}</span> / 结果: <span class="font-bold ${ev.quality_pass ? 'text-green-600' : 'text-red-600'}">${ev.quality_pass ? '通过' : '未通过'}</span></div>
                </div>` : ''}
                ${ev.source_url ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">来源链接</div>
                    <a href="${escapeHtml(ev.source_url)}" target="_blank" rel="noopener noreferrer" class="text-blue-600 break-all underline">${escapeHtml(ev.source_url)}</a>
                </div>` : ''}
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">详情补抓状态</div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono text-[10px]">
                        <div>状态: <span class="font-bold">${escapeHtml(ev.detail_fetch_status || 'pending')}</span></div>
                        <div>尝试次数: <span class="font-bold">${Number(ev.detail_fetch_attempts || 0)}</span></div>
                        <div>HTTP 状态: <span class="font-bold">${ev.detail_fetch_http_status ?? '暂无'}</span></div>
                        <div>最后尝试: <span class="font-bold">${formatDateTime(ev.detail_fetch_last_attempt)}</span></div>
                        <div>完成时间: <span class="font-bold">${formatDateTime(ev.detail_fetch_completed_at)}</span></div>
                        <div class="md:col-span-2">错误信息: <span class="font-bold ${ev.detail_fetch_error ? 'text-red-600' : 'text-gray-400'}">${escapeHtml(ev.detail_fetch_error || '无')}</span></div>
                    </div>
                </div>
                ${ev.details_json ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">原始详情</div>
                    <pre class="whitespace-pre-wrap bg-gray-50 border border-gray-200 p-3 rounded-sm">${escapeHtml(stringifyData(ev.details_json))}</pre>
                </div>` : ''}
            </div>
        `;
        showModal(ev.title, content);
    } catch(e) {
        showToast('加载事件详情失败', 'error');
    } finally {
        showLoading(false);
    }
}

function renderEventStatsRow(stats) {
    const el = document.getElementById('events-stats-row');
    if (!el) return;
    const byStatus = stats?.by_status || {};
    el.innerHTML = [
        ['全部事件', stats?.total_events ?? '—'],
        ['待处理', byStatus.pending ?? 0],
        ['事件池', byStatus.pool ?? 0],
        ['已质检', byStatus.checked ?? 0],
        ['处理中', byStatus.processing ?? 0],
        ['已完成', byStatus.completed ?? 0],
        ['失败停住', byStatus.failed ?? 0],
    ].map(([label, value]) => `
        <div class="tech-card p-4">
            <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-2">${label}</div>
            <div class="text-2xl font-mono font-light tracking-tighter">${value}</div>
        </div>
    `).join('');
}

function geeStatusClass(status) {
    const map = {
        COMPLETED: 'bg-green-100 text-green-700',
        FAILED: 'bg-red-100 text-red-700',
        PENDING: 'bg-gray-100 text-gray-600',
        RUNNING: 'bg-blue-100 text-blue-700',
    };
    return map[status] || 'bg-gray-100 text-gray-600';
}

function formatImageryStatus(event) {
    const preOk = event.pre_image_downloaded;
    const postOk = event.post_image_downloaded;
    const postOpen = event.post_imagery_open !== false;
    const preExhausted = event.pre_imagery_exhausted;
    const preWin = event.pre_window_days ?? 7;
    const postWin = event.post_window_days ?? 7;

    const preBadge = preOk
        ? `<span class="px-1.5 py-0.5 bg-green-100 text-green-700 text-[9px] font-bold">前✓</span>`
        : preExhausted
            ? `<span class="px-1.5 py-0.5 bg-red-100 text-red-700 text-[9px] font-bold">前✗</span>`
            : `<span class="px-1.5 py-0.5 bg-yellow-100 text-yellow-700 text-[9px] font-bold">前⏳${preWin}天</span>`;

    const postBadge = postOk
        ? `<span class="px-1.5 py-0.5 bg-green-100 text-green-700 text-[9px] font-bold">后✓</span>`
        : !postOpen
            ? `<span class="px-1.5 py-0.5 bg-red-100 text-red-700 text-[9px] font-bold">后✗</span>`
            : `<span class="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[9px] font-bold">后⏳${postWin}天</span>`;

    return `<div class="flex gap-1">${preBadge}${postBadge}</div>`;
}

function formatImageryCounts(event) {
    const checks = event.imagery_check_count ?? 0;
    const preCount = event.pre_imagery_count ?? (event.pre_image_downloaded ? 1 : 0);
    const postCount = event.post_imagery_count ?? (event.post_image_downloaded ? 1 : 0);
    return `
        <div class="font-mono text-[10px] leading-5 text-gray-600">
            <div>检查: <span class="font-bold text-gray-800">${checks}</span> 次</div>
            <div>抓取: <span class="font-bold text-gray-800">前 ${preCount}</span> / <span class="font-bold text-gray-800">后 ${postCount}</span></div>
        </div>
    `;
}

function renderImageryEntry(event) {
    const preLink = event?.has_pre_image
        ? `<a href="/api/public/image/${encodeURIComponent(event.uuid)}/pre" target="_blank" rel="noopener noreferrer" class="inline-flex px-2 py-1 border border-gray-300 hover:border-black hover:bg-gray-100 transition-colors font-mono text-[10px] font-bold uppercase mr-1">前图</a>`
        : `<span class="inline-flex px-2 py-1 border border-gray-200 text-gray-400 font-mono text-[10px] font-bold uppercase mr-1">前图无</span>`;

    const postLink = event?.has_post_image
        ? `<a href="/api/public/image/${encodeURIComponent(event.uuid)}/post" target="_blank" rel="noopener noreferrer" class="inline-flex px-2 py-1 border border-gray-300 hover:border-black hover:bg-gray-100 transition-colors font-mono text-[10px] font-bold uppercase">后图</a>`
        : `<span class="inline-flex px-2 py-1 border border-gray-200 text-gray-400 font-mono text-[10px] font-bold uppercase">后图无</span>`;

    return `<div class="whitespace-nowrap">${preLink}${postLink}</div>`;
}

function canProcessEvent(status) {
    return ['pending', 'pool', 'checked'].includes(String(status || '').toLowerCase());
}

function renderProcessButton(event) {
    if (!canProcessEvent(event?.status)) {
        return '<span title="当前状态由调度器自动流转" class="inline-flex px-2 py-1 border border-gray-200 text-gray-400 font-mono text-[10px] font-bold uppercase cursor-not-allowed">自动流转</span>';
    }
    return `<button title="手动触发一次该事件的处理流程（pending/pool/checked）" onclick="window.processEvent('${event.uuid}', '${event.status}')" class="px-2 py-1 border border-gray-300 hover:border-black hover:bg-black hover:text-white transition-colors font-mono text-[10px] font-bold uppercase">触发处理</button>`;
}

async function processEvent(uuid, status = '') {
    if (!canProcessEvent(status)) {
        showToast(`当前状态 ${labelStatus(status)} 由系统自动流转，无需手动触发`, 'info');
        return;
    }
    showLoading(true);
    try {
        const response = await authFetch(`${EVENTS_API}/${uuid}/process`, { method: 'POST' });
        if (response.ok) {
            showToast('已手动触发处理流程', 'success');
            setTimeout(() => loadEvents(_eventsPage), 2000);
        } else {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(err.detail || response.statusText);
        }
    } catch (error) {
        showToast('触发处理失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== Task Progress ====================
async function loadTaskProgress(page = 1) {
    _tasksPage = page;
    showLoading(true);

    const status = document.getElementById('task-filter-status')?.value || '';
    const keyword = document.getElementById('task-filter-keyword')?.value?.trim() || '';

    let url = `${TASKS_API}?page=${page}&limit=20`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;

    try {
        const [response, statsResponse] = await Promise.all([
            authFetch(url),
            authFetch(`${TASKS_API}/stats`)
        ]);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);

        const data = await response.json();
        const stats = statsResponse.ok ? await statsResponse.json() : null;
        const tasks = data.data || [];

        renderTaskStatsRow(stats);

        const tbody = document.getElementById('tasks-tbody');
        tbody.innerHTML = tasks.map(task => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-3 px-4 align-top">
                    <div class="font-semibold max-w-xs truncate" title="${escapeHtml(task.event_title || task.uuid)}">${escapeHtml(task.event_title || '未命名事件')}</div>
                    <div class="text-[10px] text-gray-500 mt-1">${escapeHtml(task.uuid)}</div>
                    <div class="text-[10px] text-gray-400 mt-1">${escapeHtml(task.event_country || '暂无国家')} / ${escapeHtml(task.event_category || '暂无类别')}</div>
                </td>
                <td class="py-3 px-4 align-top">${renderTaskStatusCell(task)}</td>
                <td class="py-3 px-4 align-top">${renderTaskStageCell(task)}</td>
                <td class="py-3 px-4 align-top">${renderTaskProgressCell(task)}</td>
                <td class="py-3 px-4 align-top">${renderTaskWorkerCell(task)}</td>
                <td class="py-3 px-4 align-top">${renderTaskRetryCell(task)}</td>
                <td class="py-3 px-4 align-top text-gray-600">
                    <div>${formatDateTime(task.updated_at)}</div>
                    <div class="text-[10px] text-gray-400 mt-1">创建: ${formatDateTime(task.created_at)}</div>
                </td>
                <td class="py-3 px-4 align-top text-right whitespace-nowrap">
                    <button onclick="window.showTaskProgressDetail('${task.uuid}')" class="px-2 py-1 border border-gray-200 hover:border-black font-mono text-[10px] font-bold uppercase mr-1">详情</button>
                    ${task.can_pause ? `<button onclick="window.pauseTaskProgress('${task.uuid}')" class="px-2 py-1 border border-amber-300 text-amber-700 hover:border-amber-500 hover:bg-amber-50 font-mono text-[10px] font-bold uppercase mr-1">暂停</button>` : ''}
                    ${task.can_resume ? `<button onclick="window.resumeTaskProgress('${task.uuid}')" class="px-2 py-1 border border-green-300 text-green-700 hover:border-green-500 hover:bg-green-50 font-mono text-[10px] font-bold uppercase">${task.task_status === 'pause_requested' ? '取消暂停' : '继续'}</button>` : ''}
                </td>
            </tr>
        `).join('') || '<tr><td colspan="8" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">暂无任务</td></tr>';

        renderPagination('tasks-pagination', data.page, data.pages, loadTaskProgress);
        lucide.createIcons();
    } catch (error) {
        console.error('Task progress load failed:', error);
        showToast('加载任务进度失败', 'error');
    } finally {
        showLoading(false);
    }
}

function renderTaskStatsRow(stats) {
    const el = document.getElementById('tasks-stats-row');
    if (!el) return;
    const byStatus = stats?.by_status || {};
    el.innerHTML = [
        ['全部任务', stats?.total ?? '—'],
        ['活跃中', stats?.active ?? 0],
        ['运行中', byStatus.running ?? 0],
        ['待处理', byStatus.pending ?? 0],
        ['已停止', stats?.failed ?? byStatus.failed ?? 0],
    ].map(([label, value]) => `
        <div class="tech-card p-4">
            <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-2">${label}</div>
            <div class="text-2xl font-mono font-light tracking-tighter">${value}</div>
        </div>
    `).join('');
}

function renderTaskStatusCell(task) {
    const statusClass = getTaskStatusClass(task.task_status);
        const detail = task.event_status ? `事件: ${labelStatus(task.event_status)}` : '内部推理队列';
    return `
        <div class="space-y-2">
            <span class="px-2 py-1 ${statusClass} text-[10px] font-bold uppercase inline-flex">${labelTaskStatus(task.task_status)}</span>
            <div class="text-[10px] text-gray-500 leading-5">${escapeHtml(detail)}</div>
        </div>
    `;
}

function renderTaskStageCell(task) {
    const running = task.running_task_label
        ? `<div class="text-[10px] text-blue-600 mt-1">当前子任务: ${escapeHtml(task.running_task_label)}</div>`
        : '';
    const failure = task.failure_reason
        ? `<div class="text-[10px] text-red-600 mt-1" title="${escapeHtml(task.failure_reason)}">${escapeHtml(task.failure_reason)}</div>`
        : '';
    return `
        <div class="max-w-xs">
            <div class="font-semibold">${escapeHtml(labelTaskStage(task.progress_stage))}</div>
            <div class="text-[10px] text-gray-500 mt-1 leading-5">${escapeHtml(task.progress_message || '等待执行')}</div>
            ${running}
            ${failure}
        </div>
    `;
}

function renderTaskProgressCell(task) {
    const percent = Math.max(0, Math.min(100, Number(task.progress_percent || 0)));
    const currentStep = Number(task.current_step || 0);
    const totalSteps = Number(task.total_steps || 0);
    return `
        <div class="min-w-[180px]">
            <div class="flex items-center justify-between text-[10px] text-gray-500 mb-1">
                <span>${currentStep} / ${totalSteps || '—'} 步</span>
                <span class="font-bold text-gray-700">${percent}%</span>
            </div>
            <div class="w-full h-2 bg-gray-100 border border-gray-200 overflow-hidden">
                <div class="h-full bg-black transition-all" style="width:${percent}%"></div>
            </div>
            <div class="text-[10px] text-gray-400 mt-2">
                推理子任务: ${task.completed_task_count || 0}/${task.task_count || 0}
                ${task.failed_task_count ? ` · 失败 ${task.failed_task_count}` : ''}
            </div>
        </div>
    `;
}

function renderTaskWorkerCell(task) {
    return `
        <div class="text-[10px] leading-5 text-gray-600">
            <div>执行器: <span class="font-bold text-gray-800">${escapeHtml(task.locked_by || '内部调度')}</span></div>
            <div>最近更新: <span class="font-bold text-gray-800">${formatDateTime(task.heartbeat)}</span></div>
            <div>完成时间: <span class="font-bold text-gray-800">${formatDateTime(task.completed_at)}</span></div>
        </div>
    `;
}

function renderTaskRetryCell(task) {
    const resumeCount = Number(task.manual_resume_count || 0);
    return `
        <div class="text-[10px] leading-5 text-gray-600">
            <div>自动重试: <span class="font-bold text-gray-800">${task.retry_count || 0}/${task.max_retries || 3}</span></div>
            <div>人工继续: <span class="font-bold text-gray-800">${resumeCount}</span> 次</div>
        </div>
    `;
}

async function showTaskProgressDetail(uuid) {
    showLoading(true);
    try {
        const response = await authFetch(`${TASKS_API}/${uuid}`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);

        const task = await response.json();
        const stepDetails = task.step_details || {};
        const pipeline = Array.isArray(stepDetails.pipeline) ? stepDetails.pipeline : [];
        const inferenceTasks = Array.isArray(stepDetails.inference_tasks) ? stepDetails.inference_tasks : [];

        const content = `
            <div class="space-y-5 font-mono text-xs">
                <div class="flex flex-wrap gap-2">
                    <span class="px-2 py-1 ${getTaskStatusClass(task.task_status)} text-[10px] font-bold uppercase">${escapeHtml(labelTaskStatus(task.task_status))}</span>
                    <span class="px-2 py-1 border border-gray-200 text-[10px] font-bold uppercase">${escapeHtml(labelTaskStage(task.progress_stage))}</span>
                    <span class="px-2 py-1 border border-gray-200 text-[10px] font-bold uppercase">进度 ${task.progress_percent || 0}%</span>
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div><span class="text-gray-500 uppercase">事件标题</span><div class="font-bold mt-1">${escapeHtml(task.event_title || '暂无')}</div></div>
                    <div><span class="text-gray-500 uppercase">事件状态</span><div class="font-bold mt-1">${escapeHtml(labelStatus(task.event_status))}</div></div>
                    <div><span class="text-gray-500 uppercase">任务 UUID</span><div class="font-bold mt-1 break-all">${escapeHtml(task.uuid)}</div></div>
                    <div><span class="text-gray-500 uppercase">执行器</span><div class="font-bold mt-1">${escapeHtml(task.locked_by || '内部调度')}</div></div>
                    <div><span class="text-gray-500 uppercase">当前阶段</span><div class="font-bold mt-1">${escapeHtml(labelTaskStage(task.progress_stage))}</div></div>
                    <div><span class="text-gray-500 uppercase">步骤进度</span><div class="font-bold mt-1">${task.current_step || 0} / ${task.total_steps || 0}</div></div>
                    <div><span class="text-gray-500 uppercase">自动重试</span><div class="font-bold mt-1">${task.retry_count || 0} / ${task.max_retries || 3}</div></div>
                    <div><span class="text-gray-500 uppercase">人工继续</span><div class="font-bold mt-1">${task.manual_resume_count || 0} 次</div></div>
                </div>

                <div class="border border-gray-200 p-4 bg-gray-50">
                    <div class="flex items-center justify-between text-[10px] text-gray-500 mb-2">
                        <span>当前说明</span>
                        <span class="font-bold text-gray-700">${task.progress_percent || 0}%</span>
                    </div>
                    <div class="w-full h-2 bg-white border border-gray-200 overflow-hidden mb-3">
                        <div class="h-full bg-black transition-all" style="width:${Math.max(0, Math.min(100, Number(task.progress_percent || 0)))}%"></div>
                    </div>
                    <div class="leading-6 text-gray-700">${escapeHtml(task.progress_message || '等待执行')}</div>
                </div>

                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">流程阶段</div>
                    <div class="space-y-2">
                        ${pipeline.map(step => `
                            <div class="flex items-start justify-between gap-3 border border-gray-200 px-3 py-2">
                                <div class="font-semibold">${escapeHtml(step.label || step.key || '步骤')}</div>
                                <span class="px-2 py-0.5 ${getTaskStepClass(step.status)} text-[10px] font-bold uppercase">${escapeHtml(labelTaskStep(step.status))}</span>
                            </div>
                        `).join('') || '<div class="text-gray-400">暂无流程信息</div>'}
                    </div>
                </div>

                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">推理子任务</div>
                    <div class="space-y-2">
                        ${inferenceTasks.map(item => `
                            <div class="border border-gray-200 px-3 py-2">
                                <div class="flex items-start justify-between gap-3">
                                    <div>
                                        <div class="font-semibold">${escapeHtml(item.type || 'UNKNOWN')}</div>
                                        <div class="text-[10px] text-gray-500 mt-1">${escapeHtml(item.label || item.prompt || '未命名任务')}</div>
                                    </div>
                                    <span class="px-2 py-0.5 ${getTaskStepClass(item.status)} text-[10px] font-bold uppercase">${escapeHtml(labelTaskStep(item.status))}</span>
                                </div>
                                ${item.error ? `<div class="text-[10px] text-red-600 mt-2 break-all">${escapeHtml(item.error)}</div>` : ''}
                            </div>
                        `).join('') || '<div class="text-gray-400">暂无子任务信息</div>'}
                    </div>
                </div>

                ${task.failure_reason ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">失败原因</div>
                    <div class="border border-red-200 bg-red-50 p-3 leading-6 text-red-700">${escapeHtml(task.failure_reason)}</div>
                </div>` : ''}

                ${task.last_error_details ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">错误详情</div>
                    <pre class="whitespace-pre-wrap bg-gray-50 border border-gray-200 p-3 rounded-sm text-[10px]">${escapeHtml(task.last_error_details)}</pre>
                </div>` : ''}

                ${task.inference_result ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">推理结果</div>
                    <pre class="whitespace-pre-wrap bg-gray-50 border border-gray-200 p-3 rounded-sm text-[10px]">${escapeHtml(stringifyData(task.inference_result))}</pre>
                </div>` : ''}

                <div class="border-t border-gray-100 pt-4 flex flex-wrap gap-2">
                    ${task.can_pause ? `<button onclick="window.pauseTaskProgress('${task.uuid}')" class="px-3 py-2 border border-amber-300 text-amber-700 hover:border-amber-500 hover:bg-amber-50 transition-colors font-mono text-[10px] font-bold uppercase">暂停任务</button>` : ''}
                    ${task.can_resume ? `<button onclick="window.resumeTaskProgress('${task.uuid}')" class="px-3 py-2 border border-green-300 text-green-700 hover:border-green-500 hover:bg-green-50 transition-colors font-mono text-[10px] font-bold uppercase">${task.task_status === 'pause_requested' ? '取消暂停' : '继续任务'}</button>` : ''}
                    <button onclick="window.jumpToEventDetail('${task.uuid}')" class="px-3 py-2 border border-gray-300 hover:border-black hover:bg-gray-100 transition-colors font-mono text-[10px] font-bold uppercase">查看事件</button>
                </div>
            </div>
        `;

        showModal(`任务进度 ${uuid.slice(0, 8)}`, content);
    } catch (error) {
        console.error('Task detail load failed:', error);
        showToast('加载任务详情失败', 'error');
    } finally {
        showLoading(false);
    }
}

async function pauseTaskProgress(uuid) {
    showLoading(true);
    try {
        const response = await authFetch(`${TASKS_API}/${uuid}/pause`, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(err.detail || response.statusText);
        }
        const result = await response.json();
        showToast(result.message || '任务已暂停', 'success');
        document.getElementById('detail-modal')?.remove();
        await loadTaskProgress(_tasksPage);
    } catch (error) {
        showToast('暂停任务失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function resumeTaskProgress(uuid) {
    showLoading(true);
    try {
        const response = await authFetch(`${TASKS_API}/${uuid}/resume`, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(err.detail || response.statusText);
        }
        const result = await response.json();
        showToast(result.message || '任务已继续', 'success');
        document.getElementById('detail-modal')?.remove();
        await loadTaskProgress(_tasksPage);
    } catch (error) {
        showToast('继续任务失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function jumpToTaskProgress(uuid) {
    const keywordInput = document.getElementById('task-filter-keyword');
    if (keywordInput) keywordInput.value = uuid;
    switchView('tasks');
}

async function jumpToEventDetail(uuid) {
    document.getElementById('detail-modal')?.remove();
    await showEventDetail(uuid);
}

// ==================== Products ====================
async function loadProducts(page = 1) {
    _productsPage = page;
    showLoading(true);

    try {
        const summaryGenerated = document.getElementById('prod-filter-summary')?.value || '';
        const category = document.getElementById('prod-filter-category')?.value || '';
        const country = document.getElementById('prod-filter-country')?.value || '';

        let url = `${PRODUCTS_API}?page=${page}&limit=30`;
        if (summaryGenerated) url += `&summary_generated=${summaryGenerated}`;
        if (category) url += `&category=${encodeURIComponent(category.trim().toUpperCase())}`;
        if (country) url += `&country=${encodeURIComponent(country)}`;

        const response = await authFetch(url);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);

        const data = await response.json();
        const products = data.data || [];

        renderProductsSummary(products, data.total ?? 0);
        const countHint = document.getElementById('products-count-hint');
        if (countHint) {
            countHint.textContent = `共 ${data.total ?? 0} 条，当前第 ${data.page ?? page} 页`;
        }

        const tbody = document.getElementById('products-tbody');
        tbody.innerHTML = products.map(product => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-4 px-6 text-gray-500 font-mono text-[10px]">${product.uuid.substring(0, 8)}...</td>
                <td class="py-4 px-6 font-bold text-black max-w-sm truncate">${escapeHtml(product.event_title || '暂无')}</td>
                <td class="py-4 px-6 text-gray-600">${escapeHtml(product.event_category || '暂无')}</td>
                <td class="py-4 px-6 text-gray-600">${escapeHtml(product.event_country || '暂无')}</td>
                <td class="py-4 px-6"><span class="px-2 py-1 ${product.summary_generated ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'} text-[10px] font-bold uppercase">${product.summary_generated ? '已生成' : '未生成'}</span></td>
                <td class="py-4 px-6 text-gray-600">${formatQualityScore(product.inference_result)}</td>
                <td class="py-4 px-6 text-gray-600 text-xs">${formatDate(product.created_at)}</td>
                <td class="py-4 px-6 text-right">
                    <button onclick="window.showProductDetail('${product.uuid}')" class="px-3 py-1 border border-gray-300 hover:border-black hover:bg-black hover:text-white transition-colors font-mono text-[10px] font-bold uppercase">详情</button>
                </td>
            </tr>
        `).join('') || '<tr><td colspan="8" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">暂无成品</td></tr>';

        renderPagination('products-pagination', data.page, data.pages, loadProducts);

    } catch (error) {
        console.error('Products load failed:', error);
        showToast('加载成品列表失败', 'error');
    } finally {
        showLoading(false);
    }
}

function renderProductsSummary(products, total) {
    const el = document.getElementById('products-summary-row');
    if (!el) return;
    const generatedCount = products.filter(item => item.summary_generated).length;
    const pendingCount = products.length - generatedCount;
    const categories = new Set(products.map(item => item.event_category).filter(Boolean)).size;
    const countries = new Set(products.map(item => item.event_country).filter(Boolean)).size;
    el.innerHTML = [
        ['当前筛选总数', total],
        ['本页已生成摘要', generatedCount],
        ['本页待补摘要', pendingCount],
        ['本页覆盖国家/类别', `${countries}/${categories}`],
    ].map(([label, value]) => `
        <div class="tech-card p-4">
            <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-2">${label}</div>
            <div class="text-2xl font-mono font-light tracking-tighter">${value}</div>
        </div>
    `).join('');
}

async function showProductDetail(uuid) {
    showLoading(true);
    try {
        const response = await authFetch(`${PRODUCTS_API}/${uuid}`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);
        const product = await response.json();
        const content = `
            <div class="space-y-4 font-mono text-xs">
                <div class="grid grid-cols-2 gap-3">
                    <div><span class="text-gray-500 uppercase">事件标题</span><div class="font-bold mt-1">${escapeHtml(product.event_title || '暂无')}</div></div>
                    <div><span class="text-gray-500 uppercase">UUID</span><div class="font-bold mt-1 break-all">${escapeHtml(product.uuid)}</div></div>
                    <div><span class="text-gray-500 uppercase">类别</span><div class="font-bold mt-1">${escapeHtml(product.event_category || '暂无')}</div></div>
                    <div><span class="text-gray-500 uppercase">国家</span><div class="font-bold mt-1">${escapeHtml(product.event_country || '暂无')}</div></div>
                    <div><span class="text-gray-500 uppercase">摘要状态</span><div class="font-bold mt-1">${product.summary_generated ? '已生成' : '未生成'}</div></div>
                    <div><span class="text-gray-500 uppercase">推理质量分</span><div class="font-bold mt-1">${product.inference_quality_score ?? '暂无'}</div></div>
                    <div><span class="text-gray-500 uppercase">灾前影像日期</span><div class="font-bold mt-1">${formatDateTime(product.pre_image_date)}</div></div>
                    <div><span class="text-gray-500 uppercase">灾后影像日期</span><div class="font-bold mt-1">${formatDateTime(product.post_image_date)}</div></div>
                </div>
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">AI 摘要</div>
                    <div class="leading-6 whitespace-pre-wrap">${escapeHtml(product.summary || '暂无摘要')}</div>
                </div>
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">推理结果</div>
                    <pre class="whitespace-pre-wrap bg-gray-50 border border-gray-200 p-3 rounded-sm">${escapeHtml(stringifyData(product.inference_result || '暂无推理结果'))}</pre>
                </div>
                ${product.event_details ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">事件快照</div>
                    <pre class="whitespace-pre-wrap bg-gray-50 border border-gray-200 p-3 rounded-sm">${escapeHtml(stringifyData(product.event_details))}</pre>
                </div>` : ''}
            </div>
        `;
        showModal(`成品详情 ${uuid.slice(0, 8)}`, content);
    } catch (error) {
        showToast('加载成品详情失败', 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== Reports ====================
async function loadReports(page = 1) {
    _reportsPage = page;
    showLoading(true);

    try {
        const response = await authFetch(`${REPORTS_API}?page=${page}&limit=30`);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);

        const data = await response.json();
        const reports = data.data || [];

        renderReportsSummary(reports, data.total ?? 0);

        const tbody = document.getElementById('reports-tbody');
        tbody.innerHTML = reports.map(report => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-4 px-6 font-mono font-bold">${report.report_date}</td>
                <td class="py-4 px-6 font-semibold text-black max-w-xs truncate">${escapeHtml(report.report_title || '未命名日报')}</td>
                <td class="py-4 px-6 text-gray-600">${report.event_count || 0}</td>
                <td class="py-4 px-6 text-gray-600 text-xs">${formatDateTime(report.generated_at)}</td>
                <td class="py-4 px-6"><span class="px-2 py-1 ${report.published ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'} text-[10px] font-bold uppercase">${report.published ? '已发布' : '草稿'}</span></td>
                <td class="py-4 px-6 text-right">
                    <button onclick="window.viewReport('${report.report_date}')" class="px-3 py-1 border border-gray-300 hover:border-black hover:bg-black hover:text-white transition-colors font-mono text-[10px] font-bold uppercase">
                        查看
                    </button>
                    ${report.published ? '' : `
                        <button onclick="window.publishReport('${report.report_date}')" class="px-3 py-1 border border-gray-300 hover:border-black hover:bg-black hover:text-white transition-colors font-mono text-[10px] font-bold uppercase ml-1">
                            发布
                        </button>
                    `}
                </td>
            </tr>
        `).join('') || '<tr><td colspan="6" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">暂无日报</td></tr>';

        renderPagination('reports-pagination', data.page, data.pages, loadReports);

    } catch (error) {
        console.error('Reports load failed:', error);
        showToast('加载日报列表失败', 'error');
    } finally {
        showLoading(false);
    }
}

async function generateReport() {
    showLoading(true);

    try {
        const input = document.getElementById('report-generate-date');
        const reportDate = input?.value || formatDateInput(new Date(Date.now() - 86400000));

        const response = await authFetch(`${REPORTS_API}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: reportDate })
        });

        if (response.ok) {
            showToast('日报生成任务已启动', 'success');
            setTimeout(loadReports, 2000);
        } else {
            showToast('生成日报失败', 'error');
        }
    } catch (error) {
        showToast('连接失败，请稍后重试', 'error');
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
        const content = `
            <div class="space-y-4 font-mono text-xs">
                <div class="grid grid-cols-2 gap-3">
                    <div><span class="text-gray-500 uppercase">日期</span><div class="font-bold mt-1">${data.report_date}</div></div>
                    <div><span class="text-gray-500 uppercase">状态</span><div class="font-bold mt-1">${data.published ? '已发布' : '草稿'}</div></div>
                    <div><span class="text-gray-500 uppercase">标题</span><div class="font-bold mt-1">${escapeHtml(data.report_title || '未命名日报')}</div></div>
                    <div><span class="text-gray-500 uppercase">事件数量</span><div class="font-bold mt-1">${data.event_count || 0}</div></div>
                    <div><span class="text-gray-500 uppercase">生成时间</span><div class="font-bold mt-1">${formatDateTime(data.generated_at)}</div></div>
                    <div><span class="text-gray-500 uppercase">发布时间</span><div class="font-bold mt-1">${formatDateTime(data.published_at)}</div></div>
                </div>
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">日报正文</div>
                    <pre class="font-mono text-xs whitespace-pre-wrap bg-gray-50 border border-gray-200 p-3 rounded-sm">${escapeHtml(data.report_content || '暂无内容')}</pre>
                </div>
                ${(data.category_stats || data.severity_stats || data.country_stats) ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">统计信息</div>
                    <pre class="font-mono text-xs whitespace-pre-wrap bg-gray-50 border border-gray-200 p-3 rounded-sm">${escapeHtml(stringifyData({
                        类别统计: data.category_stats,
                        严重程度统计: data.severity_stats,
                        国家统计: data.country_stats,
                    }))}</pre>
                </div>` : ''}
            </div>
        `;
        showModal(`日报 ${date}`, content);
    } catch (error) {
        showToast('加载日报详情失败', 'error');
    } finally {
        showLoading(false);
    }
}

function renderReportsSummary(reports, total) {
    const el = document.getElementById('reports-summary-row');
    if (!el) return;
    const published = reports.filter(item => item.published).length;
    const draft = reports.length - published;
    const totalEvents = reports.reduce((sum, item) => sum + (item.event_count || 0), 0);
    el.innerHTML = [
        ['当前筛选总数', total],
        ['本页已发布', published],
        ['本页草稿', draft],
        ['本页覆盖事件', totalEvents],
    ].map(([label, value]) => `
        <div class="tech-card p-4">
            <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-2">${label}</div>
            <div class="text-2xl font-mono font-light tracking-tighter">${value}</div>
        </div>
    `).join('');
}

async function publishReport(date) {
    if (!window.confirm(`确认发布 ${date} 的日报吗？`)) return;
    showLoading(true);
    try {
        const response = await authFetch(`${REPORTS_API}/${date}/publish`, { method: 'PUT' });
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(err.detail || response.statusText);
        }
        const result = await response.json();
        showToast(result.message || '日报已发布', 'success');
        await loadReports(_reportsPage);
    } catch (error) {
        showToast('发布日报失败: ' + error.message, 'error');
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
                <td class="py-4 px-6 font-mono text-[10px] text-gray-500">${escapeHtml(token.token || '暂无')}</td>
                <td class="py-4 px-6 font-mono font-bold">${escapeHtml(token.name)}</td>
                <td class="py-4 px-6 text-gray-600 max-w-xs truncate" title="${escapeHtml(token.description || '')}">${escapeHtml(token.description || '暂无')}</td>
                <td class="py-4 px-6"><span class="px-2 py-1 ${token.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'} text-[10px] font-bold uppercase">${token.is_active ? '启用中' : '已禁用'}</span></td>
                <td class="py-4 px-6 text-gray-600">${token.usage_count ?? 0}</td>
                <td class="py-4 px-6 text-gray-600 text-xs">${formatDateTime(token.last_used)}</td>
                <td class="py-4 px-6 text-gray-600 text-xs">${formatDate(token.created_at)}</td>
                <td class="py-4 px-6 text-right">
                    ${token.is_active ? `
                        <button onclick="window.disableTokenFromButton(this)" data-token-name="${escapeHtml(token.name)}" data-token-created-at="${token.created_at}" class="px-3 py-1 border border-red-200 text-red-600 hover:border-red-500 hover:bg-red-50 transition-colors font-mono text-[10px] font-bold uppercase">禁用</button>
                    ` : '<span class="text-gray-400 text-[10px]">无操作</span>'}
                </td>
            </tr>
        `).join('') || '<tr><td colspan="8" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">暂无令牌</td></tr>';

    } catch (error) {
        console.error('Tokens load failed:', error);
        showToast('加载令牌列表失败', 'error');
    } finally {
        showLoading(false);
    }
}

async function createToken() {
    const name = document.getElementById('token-name')?.value.trim();
    const description = document.getElementById('token-description')?.value.trim() || '';
    const scopesRaw = document.getElementById('token-scopes')?.value.trim() || 'integration.read,integration.write';
    const scopes = scopesRaw.split(',').map(item => item.trim()).filter(Boolean);

    if (!name) {
        showToast('请先填写令牌名称', 'info');
        return;
    }

    showLoading(true);
    try {
        const response = await authFetch(`${ADMIN_API}/tokens`, {
            method: 'POST',
            body: JSON.stringify({ name, description, scopes })
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(err.detail || response.statusText);
        }
        const result = await response.json();
        showModal('新令牌已创建', `
            <div class="space-y-4 font-mono text-xs">
                <div>令牌名称：<span class="font-bold">${escapeHtml(result.name)}</span></div>
                <div>创建时间：<span class="font-bold">${formatDateTime(result.created_at)}</span></div>
                <div class="border border-red-200 bg-red-50 p-3 leading-6">完整令牌仅显示这一次，请立即保存到你的集成脚本或外部测试工具配置中。</div>
                <pre class="whitespace-pre-wrap break-all bg-gray-50 border border-gray-200 p-3 rounded-sm">${escapeHtml(result.token)}</pre>
            </div>
        `);
        document.getElementById('token-name').value = '';
        document.getElementById('token-description').value = '';
        await loadTokens();
        showToast('令牌创建成功', 'success');
    } catch (error) {
        showToast('创建令牌失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function disableToken(name, createdAt) {
    if (!window.confirm(`确认禁用令牌 "${name}" 吗？`)) return;
    showLoading(true);
    try {
        const response = await authFetch(`${ADMIN_API}/tokens/${encodeURIComponent(name)}?created_at=${encodeURIComponent(createdAt)}`, { method: 'DELETE' });
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(err.detail || response.statusText);
        }
        const result = await response.json();
        showToast(result.message || '令牌已禁用', 'success');
        await loadTokens();
    } catch (error) {
        showToast('禁用令牌失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function disableTokenFromButton(button) {
    const { tokenName, tokenCreatedAt } = button.dataset;
    return disableToken(tokenName || '', Number(tokenCreatedAt));
}

// ==================== Manual Jobs ====================
async function triggerJob(job) {
    const jobMap = {
        'fetch': 'fetch_rsoe_data',
        'details': 'fetch_event_details',
        'pool': 'process_pool',
        'unlock': 'process_inference_queue',
        'recheck': 'recheck_imagery',
    };

    const jobId = jobMap[job];
    if (!jobId) return;

    showLoading(true);
    try {
        const response = await authFetch(`${ADMIN_API}/jobs/${jobId}/trigger`, { method: 'POST' });
        if (response.ok) {
            showToast(`${JOB_LABELS[jobId] || jobId} 已触发`, 'success');
        } else {
            showToast('触发任务失败', 'error');
        }
    } catch (error) {
        showToast('连接失败，请稍后重试', 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== 分页渲染 ====================
function renderPagination(containerId, current, total, loadFn) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (total <= 1) { el.innerHTML = ''; return; }

    const pages = [];
    for (let i = Math.max(1, current - 2); i <= Math.min(total, current + 2); i++) pages.push(i);

    el.innerHTML = `
        <span class="font-mono text-[10px] text-gray-500">第 ${current} / ${total} 页</span>
        <div class="flex gap-1">
            ${current > 1 ? `<button onclick="window._pgCall('${loadFn.name}',${current-1})" class="px-3 py-1 border border-gray-200 font-mono text-[10px] hover:border-black">‹</button>` : ''}
            ${pages.map(p => `<button onclick="window._pgCall('${loadFn.name}',${p})" class="px-3 py-1 border font-mono text-[10px] ${p===current ? 'border-black bg-black text-white' : 'border-gray-200 hover:border-black'}">${p}</button>`).join('')}
            ${current < total ? `<button onclick="window._pgCall('${loadFn.name}',${current+1})" class="px-3 py-1 border border-gray-200 font-mono text-[10px] hover:border-black">›</button>` : ''}
        </div>
    `;
}

// 分页辅助：通过函数名反查
window._pgCall = function(name, page) {
    const map = {
        loadEvents, loadRawPool, loadTrack, loadTaskProgress, loadProducts, loadReports,
        _wfLoadEvents,
    };
    const fn = map[name] || window[name];
    if (typeof fn === 'function') fn(page);
};

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
        <div class="font-mono text-xs font-bold tracking-wider uppercase mb-1">${TOAST_TYPE_LABELS[type] || TOAST_TYPE_LABELS.info}</div>
        <div class="font-mono text-xs text-gray-700">${escapeHtml(message)}</div>
    `;

    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function showModal(title, content) {
    // 移除旧模态框
    document.getElementById('detail-modal')?.remove();

    const modal = document.createElement('div');
    modal.id = 'detail-modal';
    modal.className = 'fixed inset-0 flex items-center justify-center z-50 bg-black/40 backdrop-blur-sm';
    modal.innerHTML = `
        <div class="bg-white border border-gray-200 shadow-[8px_8px_0_#d4d4d4] w-full max-w-4xl mx-3 md:mx-4 max-h-[92vh] md:max-h-[86vh] flex flex-col">
            <div class="sticky top-0 bg-white flex justify-between items-center px-4 md:px-6 py-4 border-b border-gray-200">
                <span class="font-mono text-sm font-bold tracking-widest uppercase truncate pr-4">${escapeHtml(title)}</span>
                <button onclick="document.getElementById('detail-modal').remove()" class="font-mono text-xs font-bold px-3 py-2 border border-gray-300 hover:border-black uppercase shrink-0">关闭</button>
            </div>
            <div class="overflow-y-auto p-4 md:p-6">${content}</div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
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

function syncCategoryOptions(selectId, byCategory) {
    const select = document.getElementById(selectId);
    if (!select) return;
    const current = select.value;
    const options = Object.entries(byCategory || {})
        .sort((a, b) => b[1] - a[1])
        .map(([key, count]) => `<option value="${escapeHtml(key)}">${escapeHtml(key)} (${count})</option>`)
        .join('');
    select.innerHTML = `<option value="">全部</option>${options}`;
    if ([...select.options].some(option => option.value === current)) {
        select.value = current;
    }
}

function labelStatus(status) {
    return STATUS_LABELS[status] || (status || '暂无');
}

function labelTaskStatus(status) {
    return TASK_STATUS_LABELS[status] || (status || '暂无');
}

function labelTaskStage(stage) {
    return TASK_STAGE_LABELS[stage] || (stage || '等待执行');
}

function labelTaskStep(status) {
    const map = {
        pending: '待执行',
        running: '进行中',
        completed: '已完成',
        failed: '失败',
        skipped: '已跳过'
    };
    return map[String(status || '').toLowerCase()] || (status || '未知');
}

function labelSeverity(severity) {
    if (!severity) return '暂无';
    return SEVERITY_LABELS[String(severity).toLowerCase()] || severity;
}

function getTaskStatusClass(status) {
    const map = {
        pending: 'bg-gray-100 text-gray-700',
        running: 'bg-blue-100 text-blue-700',
        completed: 'bg-green-100 text-green-700',
        failed: 'bg-red-100 text-red-700'
    };
    return map[String(status || '').toLowerCase()] || 'bg-gray-100 text-gray-700';
}

function getTaskStepClass(status) {
    const map = {
        pending: 'bg-gray-100 text-gray-600 border border-gray-200',
        running: 'bg-blue-100 text-blue-700 border border-blue-200',
        completed: 'bg-green-100 text-green-700 border border-green-200',
        failed: 'bg-red-100 text-red-700 border border-red-200',
        skipped: 'bg-gray-100 text-gray-500 border border-gray-200'
    };
    return map[String(status || '').toLowerCase()] || 'bg-gray-100 text-gray-600 border border-gray-200';
}

function formatDate(timestamp) {
    if (!timestamp) return '暂无';
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return '暂无';
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatDateTime(timestamp) {
    if (!timestamp) return '暂无';
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return '暂无';
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function formatDateInput(date) {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) return '';
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function stringifyData(data) {
    if (typeof data === 'string') return data;
    try {
        return JSON.stringify(data, null, 2);
    } catch {
        return String(data);
    }
}

function formatQualityScore(inferenceResult) {
    if (!inferenceResult || typeof inferenceResult !== 'object') return '暂无';
    const scores = Object.values(inferenceResult)
        .map(item => item?.quality_score)
        .filter(value => typeof value === 'number');
    if (scores.length === 0) return '暂无';
    const avg = scores.reduce((sum, value) => sum + value, 0) / scores.length;
    return avg.toFixed(2);
}

function escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// ==================== Settings ====================

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
        showToast('加载配置失败: ' + e.message, 'error');
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
            el.value = String(val);
        } else if (el.type === 'password') {
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

    const updates = collectSettingsUpdates(section);

    if (Object.keys(updates).length === 0) {
        showToast('没有需要保存的改动', 'info');
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
        showToast(result.message || '配置已保存', 'success');
        await loadSettings();
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function saveAllSettings() {
    const section = document.getElementById('view-settings');
    if (!section) return;
    const updates = collectSettingsUpdates(section);
    if (Object.keys(updates).length === 0) {
        showToast('没有需要保存的改动', 'info');
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
        showToast(result.message || '配置已保存', 'success');
        await loadSettings();
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    } finally {
        showLoading(false);
    }
}

function collectSettingsUpdates(container) {
    const updates = {};
    container.querySelectorAll('[data-key]').forEach(el => {
        const key = el.dataset.key;
        const currentValue = _settingsCache[key];
        let value = el.value;

        if (el.type === 'password') {
            if (!value.trim()) return;
            updates[key] = value;
            return;
        }

        if (el.tagName === 'SELECT') {
            if (String(currentValue) !== value) updates[key] = value;
            return;
        }

        if (value === '' && currentValue !== undefined) return;
        if (String(currentValue ?? '') !== value) updates[key] = value;
    });
    return updates;
}

// ==================== Workflow ====================

let _workflowStep = 1;
let _workflowEvent = null;
let _workflowImageType = null;
let _workflowTaskUuid = null;
let _workflowPollTimer = null;
let _workflowLabDate = null;

const WORKFLOW_STEP_LABELS = ['选择事件', '选择影像', '触发推理', '查看结果'];

function initWorkflow() {
    _workflowStep = 1;
    _workflowEvent = null;
    _workflowImageType = null;
    _workflowTaskUuid = null;
    _workflowLabDate = null;
    _clearWorkflowPoll();
    goToStep(1);
}

function _clearWorkflowPoll() {
    if (_workflowPollTimer) { clearInterval(_workflowPollTimer); _workflowPollTimer = null; }
}

function goToStep(step) {
    _clearWorkflowPoll();
    _workflowStep = step;
    _renderStepIndicator();
    switch (step) {
        case 1: renderStep1(); break;
        case 2: renderStep2(); break;
        case 3: renderStep3(); break;
        case 4: renderStep4(); break;
    }
}

function _renderStepIndicator() {
    const el = document.getElementById('workflow-steps-indicator');
    if (!el) return;
    el.innerHTML = WORKFLOW_STEP_LABELS.map((label, i) => {
        const n = i + 1;
        const active = n === _workflowStep;
        const done = n < _workflowStep;
        const numClass = active
            ? 'w-7 h-7 bg-black text-white font-mono text-xs font-bold flex items-center justify-center shrink-0'
            : done
                ? 'w-7 h-7 bg-gray-400 text-white font-mono text-xs font-bold flex items-center justify-center shrink-0'
                : 'w-7 h-7 border border-gray-300 text-gray-400 font-mono text-xs font-bold flex items-center justify-center shrink-0';
        const textClass = active ? 'font-mono text-xs font-bold' : 'font-mono text-xs text-gray-400';
        const connector = n < 4 ? '<div class="flex-1 h-px bg-gray-200 mx-2 min-w-[12px]"></div>' : '';
        return `<div class="flex items-center ${n < 4 ? 'flex-1 min-w-0' : ''}">
            <div class="flex items-center gap-2 shrink-0">
                <div class="${numClass}">${done ? '✓' : n}</div>
                <span class="${textClass} hidden sm:inline">${label}</span>
            </div>
            ${connector}
        </div>`;
    }).join('');
}

// ── Step 1: 选择事件 ──────────────────────────────────

async function renderStep1() {
    const el = document.getElementById('workflow-step-content');
    if (!el) return;
    el.innerHTML = `
        <div class="tech-card p-6 space-y-4">
            <div class="flex flex-wrap gap-3 items-end">
                <div>
                    <div class="font-mono text-[10px] font-bold tracking-widest uppercase text-gray-500 mb-1">状态</div>
                    <select id="wf-filter-status" class="px-3 py-2 border border-gray-200 font-mono text-xs bg-white focus:outline-none focus:border-black">
                        <option value="">全部</option>
                        <option value="checked">已质检</option>
                        <option value="pool">事件池</option>
                        <option value="pending">待处理</option>
                    </select>
                </div>
                <div>
                    <div class="font-mono text-[10px] font-bold tracking-widest uppercase text-gray-500 mb-1">严重程度</div>
                    <select id="wf-filter-severity" class="px-3 py-2 border border-gray-200 font-mono text-xs bg-white focus:outline-none focus:border-black">
                        <option value="">全部</option>
                        <option value="extreme">极高</option>
                        <option value="high">高</option>
                        <option value="medium">中</option>
                        <option value="low">低</option>
                    </select>
                </div>
                <div>
                    <div class="font-mono text-[10px] font-bold tracking-widest uppercase text-gray-500 mb-1">国家</div>
                    <input id="wf-filter-country" type="text" placeholder="国家名称" class="px-3 py-2 border border-gray-200 font-mono text-xs focus:outline-none focus:border-black w-32">
                </div>
                <button onclick="window._wfLoadEvents(1)" class="px-4 py-2 border border-gray-200 hover:border-black font-mono text-xs font-bold tracking-widest uppercase transition-colors">搜索</button>
            </div>
            <div class="overflow-x-auto admin-table-wrap">
                <table class="w-full">
                    <thead>
                        <tr class="border-b border-gray-100 bg-gray-50">
                            <th class="py-3 px-4 text-left font-mono text-[10px] font-bold tracking-widest uppercase text-gray-500">标题</th>
                            <th class="py-3 px-4 text-left font-mono text-[10px] font-bold tracking-widest uppercase text-gray-500">国家</th>
                            <th class="py-3 px-4 text-left font-mono text-[10px] font-bold tracking-widest uppercase text-gray-500">严重程度</th>
                            <th class="py-3 px-4 text-left font-mono text-[10px] font-bold tracking-widest uppercase text-gray-500">状态</th>
                            <th class="py-3 px-4 text-left font-mono text-[10px] font-bold tracking-widest uppercase text-gray-500">影像</th>
                            <th class="py-3 px-4 text-right font-mono text-[10px] font-bold tracking-widest uppercase text-gray-500">操作</th>
                        </tr>
                    </thead>
                    <tbody id="wf-events-tbody" class="font-mono text-xs"></tbody>
                </table>
            </div>
            <div id="wf-events-pagination"></div>
        </div>`;
    lucide.createIcons();
    await _wfLoadEvents(1);
}

async function _wfLoadEvents(page = 1) {
    const status = document.getElementById('wf-filter-status')?.value || '';
    const severity = document.getElementById('wf-filter-severity')?.value || '';
    const country = document.getElementById('wf-filter-country')?.value || '';
    let url = `${EVENTS_API}?page=${page}&limit=20`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (severity) url += `&severity=${encodeURIComponent(severity)}`;
    if (country) url += `&country=${encodeURIComponent(country)}`;
    try {
        const resp = await authFetch(url);
        if (!resp.ok) throw new Error(`HTTP_${resp.status}`);
        const data = await resp.json();
        const events = data.data || [];
        document.getElementById('wf-events-tbody').innerHTML = events.map(ev => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-3 px-4 font-semibold max-w-xs truncate" title="${escapeHtml(ev.title)}">${escapeHtml(ev.title)}</td>
                <td class="py-3 px-4 text-gray-600 uppercase">${escapeHtml(ev.country || '暂无')}</td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 ${getSeverityClass(ev.severity)} text-[10px] font-bold uppercase">${labelSeverity(ev.severity)}</span></td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 bg-gray-100 text-gray-700 text-[10px] font-bold uppercase">${labelStatus(ev.status)}</span></td>
                <td class="py-3 px-4 text-[10px]">${ev.pre_image_downloaded ? '<span class="text-green-600 font-bold">前✓</span>' : '<span class="text-gray-400">前—</span>'} ${ev.post_image_downloaded ? '<span class="text-green-600 font-bold">后✓</span>' : '<span class="text-gray-400">后—</span>'}</td>
                <td class="py-3 px-4 text-right">
                    <button onclick="window._wfSelectEvent('${ev.uuid}')" class="px-3 py-1 bg-black text-white font-mono text-[10px] font-bold uppercase hover:bg-gray-800">选择</button>
                </td>
            </tr>`).join('') || '<tr><td colspan="6" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">暂无事件</td></tr>';
        renderPagination('wf-events-pagination', data.page, data.pages, _wfLoadEvents);
        // cache events for selection
        window._wfEventsCache = {};
        events.forEach(ev => { window._wfEventsCache[ev.uuid] = ev; });
    } catch (e) {
        showToast('加载事件失败: ' + e.message, 'error');
    }
}

async function _wfSelectEvent(uuid) {
    // try cache first, else fetch
    let ev = window._wfEventsCache?.[uuid];
    if (!ev) {
        try {
            const resp = await authFetch(`${EVENTS_API}/${uuid}`);
            if (resp.ok) ev = await resp.json();
        } catch (_) {}
    }
    if (!ev) { showToast('无法加载事件信息', 'error'); return; }
    _workflowEvent = ev;
    goToStep(2);
}

// ── Step 2: 选择影像 ──────────────────────────────────

function renderStep2() {
    const ev = _workflowEvent;
    const el = document.getElementById('workflow-step-content');
    if (!el) return;

    const imgCard = (type, label, downloaded) => {
        if (!downloaded) return `
            <div class="tech-card p-6 flex flex-col items-center justify-center gap-3 opacity-40 cursor-not-allowed">
                <i data-lucide="image-off" class="w-8 h-8 text-gray-400"></i>
                <div class="font-mono text-xs text-gray-500 uppercase">${label} — 未下载</div>
            </div>`;
        const imgUrl = `/api/public/image/${encodeURIComponent(ev.uuid)}/${type}`;
        const enhUrl = `/api/public/image/${encodeURIComponent(ev.uuid)}/${type}/enhanced`;
        return `
            <div class="tech-card p-4 space-y-3">
                <div class="font-mono text-xs font-bold uppercase tracking-widest">${label}</div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <div class="font-mono text-[10px] text-gray-500 mb-1">原始</div>
                        <img src="${imgUrl}" class="w-full border border-gray-200 bg-gray-50 object-contain" style="max-height:200px"
                             onerror="this.parentElement.innerHTML='<div class=\\'text-red-500 text-[10px] p-2\\'>加载失败</div>'">
                    </div>
                    <div>
                        <div class="font-mono text-[10px] text-gray-500 mb-1">增强</div>
                        <img src="${enhUrl}" class="w-full border border-gray-200 bg-gray-50 object-contain" style="max-height:200px"
                             onerror="this.parentElement.innerHTML='<div class=\\'text-red-500 text-[10px] p-2\\'>加载失败</div>'">
                    </div>
                </div>
                <button onclick="window._wfConfirmImage('${type}')" class="w-full py-2 bg-black text-white font-mono text-[10px] font-bold uppercase hover:bg-gray-800 transition-colors">
                    使用此影像 →
                </button>
            </div>`;
    };

    el.innerHTML = `
        <div class="space-y-4">
            <div class="tech-card p-4 font-mono text-xs flex flex-wrap items-center gap-3">
                <span class="text-gray-500">已选事件:</span>
                <span class="font-bold">${escapeHtml(ev.title)}</span>
                <button onclick="window.goToStep(1)" class="ml-auto px-3 py-1 border border-gray-300 hover:border-black text-[10px] uppercase transition-colors">重新选择</button>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                ${imgCard('pre', '灾前影像', ev.pre_image_downloaded)}
                ${imgCard('post', '灾后影像', ev.post_image_downloaded)}
            </div>
        </div>`;
    lucide.createIcons();
}

function _wfConfirmImage(type) {
    _workflowImageType = type;
    goToStep(3);
}

function _getWorkflowLabDate() {
    if (_workflowLabDate) return _workflowLabDate;
    const topbarDate = document.getElementById('topbar-date')?.textContent?.trim();
    if (topbarDate && /^\d{4}-\d{2}-\d{2}$/.test(topbarDate)) {
        _workflowLabDate = topbarDate;
        return _workflowLabDate;
    }
    const now = new Date();
    _workflowLabDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    return _workflowLabDate;
}

function renderWorkflowLabPanel() {
    if (!_workflowEvent) return '';
    const reportDate = _getWorkflowLabDate();
    return `
        <div class="tech-card p-5 space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <div class="font-mono text-xs font-bold tracking-widest uppercase">Workflow Lab</div>
                    <div class="font-mono text-[10px] text-gray-500 mt-1">单独测试 AI 质检、指定影像推理、单事件摘要、日报生成</div>
                </div>
                <button onclick="window.workflowLabAction('snapshot')" class="px-3 py-2 border border-gray-300 hover:border-black font-mono text-[10px] font-bold uppercase transition-colors">刷新快照</button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
                <button onclick="window.workflowLabAction('quality')" class="px-3 py-3 border border-gray-300 hover:border-black font-mono text-[10px] font-bold uppercase text-left transition-colors">
                    <div>AI 质检</div>
                    <div class="text-gray-500 font-normal mt-1">运行 pre/post 质检并写回事件</div>
                </button>
                <button onclick="window.workflowLabAction('inference')" class="px-3 py-3 border border-gray-300 hover:border-black font-mono text-[10px] font-bold uppercase text-left transition-colors">
                    <div>指定影像推理</div>
                    <div class="text-gray-500 font-normal mt-1">按当前选择影像重排队并立即消费</div>
                </button>
                <button onclick="window.workflowLabAction('summary')" class="px-3 py-3 border border-gray-300 hover:border-black font-mono text-[10px] font-bold uppercase text-left transition-colors">
                    <div>单事件摘要</div>
                    <div class="text-gray-500 font-normal mt-1">调用 AI 生成当前成品摘要</div>
                </button>
                <div class="border border-gray-300 p-3 space-y-2">
                    <div class="font-mono text-[10px] font-bold uppercase">日报日期</div>
                    <input id="wf-lab-report-date" type="date" value="${reportDate}" class="w-full border border-gray-200 px-2 py-2 font-mono text-[10px]">
                </div>
                <button onclick="window.workflowLabAction('report')" class="px-3 py-3 bg-black text-white font-mono text-[10px] font-bold uppercase text-left hover:bg-gray-800 transition-colors">
                    <div>生成日报</div>
                    <div class="text-gray-300 font-normal mt-1">用指定日期跑完整日报生成</div>
                </button>
            </div>
            <div id="wf-lab-summary" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3"></div>
            <pre id="wf-lab-output" class="bg-gray-50 border border-gray-200 p-4 font-mono text-[10px] overflow-x-auto whitespace-pre-wrap min-h-[160px]">点击上方按钮开始测试...</pre>
        </div>`;
}

function renderWorkflowLabCards(data, isError = false) {
    const el = document.getElementById('wf-lab-summary');
    if (!el) return;
    if (isError || !data || typeof data !== 'object') {
        el.innerHTML = '';
        return;
    }

    const snapshot = data?.event ? data : data?.snapshot || null;
    const cards = [];

    if (snapshot?.latest_model) {
        const latestModel = snapshot.latest_model;
        cards.push(`
            <div class="border ${latestModel.configured ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'} p-3 space-y-1">
                <div class="font-mono text-[10px] font-bold uppercase">Latest Model</div>
                <div class="font-mono text-[10px] text-gray-700">配置: <span class="font-bold">${latestModel.configured ? '已配置' : '未配置'}</span></div>
                <div class="font-mono text-[10px] text-gray-600 break-all">Endpoint: ${escapeHtml(latestModel.endpoint || '未设置')}</div>
                <div class="font-mono text-[10px] text-gray-500">Poll: ${latestModel.poll_interval_seconds || 0}s × ${latestModel.max_polls || 0}</div>
            </div>
        `);
    }

    if (snapshot?.event) {
        const event = snapshot.event;
        cards.push(`
            <div class="border border-gray-200 bg-white p-3 space-y-1">
                <div class="font-mono text-[10px] font-bold uppercase">事件快照</div>
                <div class="font-mono text-[10px] text-gray-700">状态: <span class="font-bold">${escapeHtml(labelStatus(event.status || 'unknown'))}</span></div>
                <div class="font-mono text-[10px] text-gray-600">影像: pre ${event.has_pre_image ? '✓' : '×'} / post ${event.has_post_image ? '✓' : '×'}</div>
                <div class="font-mono text-[10px] text-gray-600">质检: ${event.quality_checked ? (event.quality_pass ? '通过' : '未通过') : '未执行'}${event.quality_score != null ? ` · ${event.quality_score}` : ''}</div>
            </div>
        `);
    }

    if (snapshot?.task) {
        const task = snapshot.task;
        cards.push(`
            <div class="border border-gray-200 bg-white p-3 space-y-1">
                <div class="font-mono text-[10px] font-bold uppercase">推理任务</div>
                <div class="font-mono text-[10px] text-gray-700">状态: <span class="font-bold">${escapeHtml(labelTaskStatus(task.task_status || 'pending'))}</span></div>
                <div class="font-mono text-[10px] text-gray-600">阶段: ${escapeHtml(labelTaskStage(task.progress_stage || 'queued'))}</div>
                <div class="font-mono text-[10px] text-gray-600">进度: ${task.progress_percent || 0}% · ${task.completed_task_count || 0}/${task.task_count || 0}</div>
                <div class="font-mono text-[10px] text-gray-500">影像: ${escapeHtml(task.task_data?.selected_image_type || task.task_data?.image_kind || '未指定')}</div>
                ${task.failure_reason ? `<div class="font-mono text-[10px] text-red-600">原因: ${escapeHtml(task.failure_reason)}</div>` : ''}
            </div>
        `);
    }

    if (snapshot?.product) {
        const product = snapshot.product;
        cards.push(`
            <div class="border border-gray-200 bg-white p-3 space-y-1">
                <div class="font-mono text-[10px] font-bold uppercase">成品</div>
                <div class="font-mono text-[10px] text-gray-700">存在: <span class="font-bold">${product.exists ? '是' : '否'}</span></div>
                <div class="font-mono text-[10px] text-gray-600">摘要: ${product.summary_generated ? '已生成' : '未生成'}</div>
                <div class="font-mono text-[10px] text-gray-500 leading-5">${escapeHtml(product.summary_preview || '暂无摘要预览')}</div>
            </div>
        `);
    }

    if (data?.report) {
        cards.push(`
            <div class="border border-gray-200 bg-white p-3 space-y-1">
                <div class="font-mono text-[10px] font-bold uppercase">日报结果</div>
                <div class="font-mono text-[10px] text-gray-700">日期: <span class="font-bold">${escapeHtml(data.report.date || '未知')}</span></div>
                <div class="font-mono text-[10px] text-gray-600">事件数: ${data.report.event_count ?? 0}</div>
                <div class="font-mono text-[10px] text-gray-600">发布: ${data.report.published ? '已发布' : '未发布'}</div>
                <div class="font-mono text-[10px] text-gray-500">${escapeHtml(data.report.title || '无标题')}</div>
            </div>
        `);
    }

    el.innerHTML = cards.join('');
}

function setWorkflowLabOutput(data, isError = false) {
    const el = document.getElementById('wf-lab-output');
    if (!el) return;
    renderWorkflowLabCards(data, isError);
    el.textContent = typeof data === 'string' ? data : stringifyData(data);
    el.className = `bg-gray-50 border p-4 font-mono text-[10px] overflow-x-auto whitespace-pre-wrap min-h-[160px] ${isError ? 'border-red-200 text-red-600' : 'border-gray-200 text-gray-700'}`;
}

async function workflowLabAction(action) {
    if (!_workflowEvent) return;
    const uuid = _workflowEvent.uuid;
    const reportDateInput = document.getElementById('wf-lab-report-date');
    if (reportDateInput?.value) _workflowLabDate = reportDateInput.value;
    setWorkflowLabOutput('测试执行中，请稍候...');

    try {
        let resp;
        if (action === 'snapshot') {
            resp = await authFetch(`${ADMIN_API}/workflow-lab/events/${uuid}`);
        } else if (action === 'quality') {
            resp = await authFetch(`${ADMIN_API}/workflow-lab/events/${uuid}/quality`, {
                method: 'POST',
                body: JSON.stringify({ persist: true }),
            });
        } else if (action === 'inference') {
            resp = await authFetch(`${ADMIN_API}/workflow-lab/events/${uuid}/inference`, {
                method: 'POST',
                body: JSON.stringify({ image_type: _workflowImageType || null, reset_task: true }),
            });
        } else if (action === 'summary') {
            resp = await authFetch(`${ADMIN_API}/workflow-lab/events/${uuid}/summary`, {
                method: 'POST',
                body: JSON.stringify({ persist: true }),
            });
        } else if (action === 'report') {
            resp = await authFetch(`${ADMIN_API}/workflow-lab/reports/generate`, {
                method: 'POST',
                body: JSON.stringify({ date: _workflowLabDate || _getWorkflowLabDate() }),
            });
        } else {
            throw new Error(`UNKNOWN_ACTION:${action}`);
        }

        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.detail || resp.statusText);

        setWorkflowLabOutput(data);
        showToast('测试执行成功', 'success');

        if (action === 'inference') {
            _workflowTaskUuid = uuid;
            document.getElementById('wf-progress-area')?.classList.remove('hidden');
            _startWorkflowPoll();
        }
    } catch (e) {
        setWorkflowLabOutput(`测试失败: ${e.message}`, true);
        showToast(`测试失败: ${e.message}`, 'error');
    }
}

// ── Step 3: 触发推理 ──────────────────────────────────

function renderStep3() {
    const ev = _workflowEvent;
    const el = document.getElementById('workflow-step-content');
    if (!el) return;
    el.innerHTML = `
        <div class="tech-card p-6 space-y-6">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono text-xs">
                <div><div class="text-gray-500 uppercase mb-1">事件</div><div class="font-bold truncate" title="${escapeHtml(ev.title)}">${escapeHtml(ev.title)}</div></div>
                <div><div class="text-gray-500 uppercase mb-1">国家</div><div class="font-bold uppercase">${escapeHtml(ev.country || '暂无')}</div></div>
                <div><div class="text-gray-500 uppercase mb-1">严重程度</div><div class="font-bold">${labelSeverity(ev.severity)}</div></div>
                <div><div class="text-gray-500 uppercase mb-1">选用影像</div><div class="font-bold">${_workflowImageType === 'pre' ? '灾前' : '灾后'}</div></div>
            </div>
            <div id="wf-inference-status" class="font-mono text-xs text-gray-500">点击下方按钮开始推理</div>
            <div class="flex gap-3">
                <button onclick="window.goToStep(2)" class="px-4 py-2 border border-gray-300 hover:border-black font-mono text-xs font-bold uppercase transition-colors">返回</button>
                <button id="wf-trigger-btn" onclick="window._wfTriggerInference()" class="px-6 py-2 bg-black text-white font-mono text-xs font-bold uppercase hover:bg-gray-800 shadow-[3px_3px_0_#d4d4d4] transition-all">
                    触发推理
                </button>
            </div>
            <div id="wf-progress-area" class="hidden space-y-2">
                <div class="h-2 border border-gray-200 bg-white overflow-hidden">
                    <div id="wf-progress-bar" class="h-full bg-black transition-all duration-500" style="width:0%"></div>
                </div>
                <div id="wf-progress-msg" class="font-mono text-[10px] text-gray-500"></div>
            </div>
            ${renderWorkflowLabPanel()}
        </div>`;
}

async function _wfTriggerInference() {
    const ev = _workflowEvent;
    const btn = document.getElementById('wf-trigger-btn');
    if (btn) { btn.disabled = true; btn.textContent = '提交中...'; }
    try {
        const resp = await authFetch(`${EVENTS_API}/${ev.uuid}/process`, {
            method: 'POST',
            body: JSON.stringify({ image_type: _workflowImageType || null }),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || resp.statusText);
        }
        _workflowTaskUuid = ev.uuid;
        const statusEl = document.getElementById('wf-inference-status');
        if (statusEl) statusEl.textContent = '推理任务已提交，正在轮询进度...';
        document.getElementById('wf-progress-area')?.classList.remove('hidden');
        _startWorkflowPoll();
    } catch (e) {
        showToast('触发推理失败: ' + e.message, 'error');
        if (btn) { btn.disabled = false; btn.textContent = '触发推理'; }
    }
}

function _startWorkflowPoll() {
    _clearWorkflowPoll();
    _wfPollOnce();
    _workflowPollTimer = setInterval(_wfPollOnce, 3000);
}

async function _wfPollOnce() {
    if (!_workflowTaskUuid) return;
    try {
        const resp = await authFetch(`${TASKS_API}/${_workflowTaskUuid}`);
        if (!resp.ok) return;
        const task = await resp.json();
        const pct = task.progress_percent || 0;
        const bar = document.getElementById('wf-progress-bar');
        const msg = document.getElementById('wf-progress-msg');
        const statusEl = document.getElementById('wf-inference-status');
        if (bar) bar.style.width = `${pct}%`;
        if (msg) msg.textContent = task.progress_message || '';
        if (statusEl) statusEl.textContent = `状态: ${TASK_STATUS_LABELS[task.task_status] || task.task_status} — ${TASK_STAGE_LABELS[task.progress_stage] || task.progress_stage || ''}`;
        if (task.task_status === 'completed') {
            _clearWorkflowPoll();
            showToast('推理完成', 'success');
            goToStep(4);
        } else if (task.task_status === 'failed') {
            _clearWorkflowPoll();
            showToast('推理失败: ' + (task.failure_reason || '未知原因'), 'error');
        }
    } catch (_) {}
}

// ── Step 4: 查看结果 ──────────────────────────────────

async function renderStep4() {
    const el = document.getElementById('workflow-step-content');
    if (!el) return;
    el.innerHTML = `<div class="tech-card p-6 font-mono text-xs text-gray-500">加载结果中...</div>`;
    try {
        const resp = await authFetch(`${TASKS_API}/${_workflowTaskUuid}`);
        if (!resp.ok) throw new Error(`HTTP_${resp.status}`);
        const task = await resp.json();

        // try to load product
        let product = null;
        try {
            const pr = await authFetch(`${PRODUCTS_API}/${_workflowTaskUuid}`);
            if (pr.ok) product = await pr.json();
        } catch (_) {}

        el.innerHTML = `
            <div class="tech-card p-6 space-y-6">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="font-mono text-sm font-bold tracking-widest">推理结果</div>
                    <div class="flex gap-3">
                        <button onclick="window.goToStep(1)" class="px-4 py-2 border border-gray-300 hover:border-black font-mono text-xs font-bold uppercase transition-colors">新工作流</button>
                        <button onclick="window.generateReport()" class="px-4 py-2 bg-black text-white font-mono text-xs font-bold uppercase hover:bg-gray-800">生成日报</button>
                    </div>
                </div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono text-xs">
                    <div><div class="text-gray-500 uppercase mb-1">事件</div><div class="font-bold truncate">${escapeHtml(_workflowEvent?.title || '—')}</div></div>
                    <div><div class="text-gray-500 uppercase mb-1">任务状态</div><div class="font-bold text-green-600">${TASK_STATUS_LABELS[task.task_status] || task.task_status}</div></div>
                    <div><div class="text-gray-500 uppercase mb-1">完成时间</div><div class="font-bold">${formatDateTime(task.completed_at)}</div></div>
                    <div><div class="text-gray-500 uppercase mb-1">进度</div><div class="font-bold">${task.progress_percent || 0}%</div></div>
                </div>
                ${product?.summary ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-mono text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3">AI 摘要</div>
                    <div class="font-mono text-xs leading-6 whitespace-pre-wrap">${escapeHtml(product.summary)}</div>
                </div>` : ''}
                ${product?.inference_result ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-mono text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3">推理详情</div>
                    <pre class="bg-gray-50 border border-gray-200 p-4 font-mono text-[10px] overflow-x-auto whitespace-pre-wrap">${escapeHtml(stringifyData(product.inference_result))}</pre>
                </div>` : task.step_details ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-mono text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3">任务详情</div>
                    <pre class="bg-gray-50 border border-gray-200 p-4 font-mono text-[10px] overflow-x-auto whitespace-pre-wrap">${escapeHtml(stringifyData(task.step_details))}</pre>
                </div>` : ''}
                ${renderWorkflowLabPanel()}
            </div>`;
    } catch (e) {
        el.innerHTML = `<div class="tech-card p-6 font-mono text-xs text-red-500">加载结果失败: ${escapeHtml(e.message)}</div>`;
    }
}

// ── GEE 重新初始化 ────────────────────────────────────

async function reinitializeGee() {
    const resp = await authFetch(`${ADMIN_API}/gee/reinitialize`, { method: 'POST' });
    if (resp.ok) showToast('GEE 重新初始化已在后台启动', 'success');
    else showToast('操作失败', 'error');
}

async function exportEventsCsv() {
    const resp = await authFetch(`${ADMIN_API}/export/events`);
    if (!resp.ok) { showToast('导出失败', 'error'); return; }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'events.csv'; a.click();
    URL.revokeObjectURL(url);
}

async function exportGeeTasksCsv() {
    const resp = await authFetch(`${ADMIN_API}/export/gee-tasks`);
    if (!resp.ok) { showToast('导出失败', 'error'); return; }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'gee_tasks.csv'; a.click();
    URL.revokeObjectURL(url);
}

// ==================== 全局导出 ====================
window.processEvent = processEvent;
window.showPoolEventDetail = showPoolEventDetail;
window.showEventDetail = showEventDetail;
window.showTaskProgressDetail = showTaskProgressDetail;
window.pauseTaskProgress = pauseTaskProgress;
window.resumeTaskProgress = resumeTaskProgress;
window.jumpToTaskProgress = jumpToTaskProgress;
window.jumpToEventDetail = jumpToEventDetail;
window.showProductDetail = showProductDetail;
window.viewReport = viewReport;
window.publishReport = publishReport;
window.generateReport = generateReport;
window.loadEvents = loadEvents;
window.loadTaskProgress = loadTaskProgress;
window.exportEventsCsv = exportEventsCsv;
window.exportGeeTasksCsv = exportGeeTasksCsv;
window.reinitializeGee = reinitializeGee;
window.initWorkflow = initWorkflow;
window.goToStep = goToStep;
window._wfLoadEvents = _wfLoadEvents;
window._wfSelectEvent = _wfSelectEvent;
window._wfConfirmImage = _wfConfirmImage;
window._wfTriggerInference = _wfTriggerInference;
window.workflowLabAction = workflowLabAction;
window.loadPool = loadPool;
window.loadRawPool = loadRawPool;
window.loadTrack = loadTrack;
window.loadPoolStats = loadPoolStats;
window.switchPoolTab = switchPoolTab;
window.loadProducts = loadProducts;
window.loadReports = loadReports;
window.loadTokens = loadTokens;
window.createToken = createToken;
window.disableToken = disableToken;
window.disableTokenFromButton = disableTokenFromButton;
window.triggerJob = triggerJob;
window.loadSettings = loadSettings;
window.saveAllSettings = saveAllSettings;
window.toggleSection = toggleSection;
window.saveSettingsGroup = saveSettingsGroup;
window.switchView = switchView;
