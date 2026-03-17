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

let AUTH_TOKEN = localStorage.getItem('admin_token') || '';

// 分页状态
let _eventsPage = 1;
let _rawPoolPage = 1;
let _trackPage = 1;

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
        case 'pool': loadPool(); break;
        case 'events': loadEvents(1); break;
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
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">Total Events</span>
                    <i data-lucide="database" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${data.database?.events_count || 0}</div>
            </div>
            <div class="tech-card p-5">
                <div class="flex justify-between items-start mb-4">
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">Pending Tasks</span>
                    <i data-lucide="clock" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${data.database?.tasks_pending || 0}</div>
            </div>
            <div class="tech-card p-5">
                <div class="flex justify-between items-start mb-4">
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">Tracking</span>
                    <i data-lucide="satellite-dish" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${trackingCount}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">post-imagery pending</div>
            </div>
            <div class="tech-card p-5">
                <div class="flex justify-between items-start mb-4">
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">Products</span>
                    <i data-lucide="package" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${data.database?.products_count || 0}</div>
            </div>
            <div class="tech-card p-5">
                <div class="flex justify-between items-start mb-4">
                    <span class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold">DB Size</span>
                    <i data-lucide="hard-drive" class="w-4 h-4 text-black opacity-80"></i>
                </div>
                <div class="text-3xl font-mono font-light tracking-tighter">${data.database?.size_mb || 0}<span class="text-sm text-gray-400">MB</span></div>
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
                <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-3">Raw Pool Total</div>
                <div class="text-3xl font-mono font-light tracking-tighter">${ps.total_events ?? '—'}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">active: ${ps.active_events ?? '—'}</div>
            </div>
            <div class="tech-card p-5">
                <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-3">Processing</div>
                <div class="text-3xl font-mono font-light tracking-tighter">${(evByStatus.pending||0) + (evByStatus.pool||0)}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">pending+pool</div>
            </div>
            <div class="tech-card p-5">
                <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-3">Imagery Tracking</div>
                <div class="text-3xl font-mono font-light tracking-tighter">${imgStatus.post_pending ?? '—'}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">post-imagery open</div>
            </div>
            <div class="tech-card p-5">
                <div class="font-mono text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-3">Both Ready</div>
                <div class="text-3xl font-mono font-light tracking-tighter">${imgStatus.both_ready ?? '—'}</div>
                <div class="font-mono text-[10px] text-gray-400 mt-1">pre+post downloaded</div>
            </div>
        `;
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
                <td class="py-3 px-4 text-gray-600">${escapeHtml(ev.category_name || ev.category || 'N/A')}</td>
                <td class="py-3 px-4 text-gray-600 uppercase">${escapeHtml(ev.country || 'N/A')}</td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 ${getSeverityClass(ev.severity)} text-[10px] font-bold uppercase">${ev.severity || 'N/A'}</span></td>
                <td class="py-3 px-4 text-gray-500">${formatDate(ev.last_seen)}</td>
                <td class="py-3 px-4 text-gray-600">${ev.fetch_count}</td>
            </tr>
        `).join('') || '<tr><td colspan="7" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">NO_DATA</td></tr>';

        renderPagination('raw-pool-pagination', data.page, data.pages, loadRawPool);
    } catch(e) {
        console.error('Raw pool failed:', e);
        showToast('Failed to load raw pool', 'error');
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
                <td class="py-3 px-4 text-gray-600 uppercase">${escapeHtml(ev.country || 'N/A')}</td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 bg-gray-100 text-gray-700 text-[10px] font-bold uppercase">${ev.status}</span></td>
                <td class="py-3 px-4">${formatImageryStatus(ev)}</td>
                <td class="py-3 px-4 text-gray-500">${ev.imagery_check_count ?? 0}</td>
                <td class="py-3 px-4 text-right">
                    <button onclick="window.processEvent('${ev.uuid}')" class="px-2 py-1 border border-gray-300 hover:border-black hover:bg-black hover:text-white transition-colors font-mono text-[10px] font-bold uppercase">PROCESS</button>
                </td>
            </tr>
        `).join('') || '<tr><td colspan="6" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">NO_DATA</td></tr>';

        renderPagination('track-pagination', data.page, data.pages, loadTrack);
    } catch(e) {
        console.error('Track load failed:', e);
        showToast('Failed to load processing track', 'error');
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
        const response = await authFetch(url);
        if (!response.ok) throw new Error(`HTTP_${response.status}`);

        const data = await response.json();
        const events = data.data || [];

        const tbody = document.getElementById('events-tbody');
        tbody.innerHTML = events.map(event => `
            <tr class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-3 px-4 font-semibold max-w-xs truncate" title="${escapeHtml(event.title)}">${escapeHtml(event.title)}</td>
                <td class="py-3 px-4 text-gray-600 uppercase">${escapeHtml(event.country || 'N/A')}</td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 bg-gray-100 text-gray-700 text-[10px] font-bold uppercase">${event.status}</span></td>
                <td class="py-3 px-4"><span class="px-2 py-0.5 ${getSeverityClass(event.severity)} text-[10px] font-bold uppercase">${event.severity || 'N/A'}</span></td>
                <td class="py-3 px-4">${formatImageryStatus(event)}</td>
                <td class="py-3 px-4 text-gray-500">${event.imagery_check_count ?? 0}</td>
                <td class="py-3 px-4 text-right">
                    <button onclick="window.showEventDetail('${event.uuid}')" class="px-2 py-1 border border-gray-200 hover:border-black font-mono text-[10px] font-bold uppercase mr-1">DETAIL</button>
                    <button onclick="window.processEvent('${event.uuid}')" class="px-2 py-1 border border-gray-300 hover:border-black hover:bg-black hover:text-white transition-colors font-mono text-[10px] font-bold uppercase">PROCESS</button>
                </td>
            </tr>
        `).join('') || '<tr><td colspan="7" class="py-12 text-center text-gray-400 font-mono text-xs uppercase">NO_EVENTS</td></tr>';

        renderPagination('events-pagination', data.page, data.pages, loadEvents);
        lucide.createIcons();
    } catch (error) {
        console.error('Events load failed:', error);
        showToast('Failed to load events', 'error');
    } finally {
        showLoading(false);
    }
}

async function showEventDetail(uuid) {
    showLoading(true);
    try {
        const resp = await authFetch(`${EVENTS_API}/${uuid}`);
        if (!resp.ok) throw new Error(`HTTP_${resp.status}`);
        const ev = await resp.json();

        const preStatus = ev.pre_image_downloaded
            ? `<span class="text-green-600 font-bold">✓ Downloaded</span> (${ev.pre_image_source || 'N/A'}, ${ev.pre_window_days}d window)`
            : ev.pre_imagery_exhausted
                ? `<span class="text-red-600 font-bold">✗ Exhausted</span> (max window reached)`
                : `<span class="text-yellow-600 font-bold">⏳ Searching</span> (${ev.pre_window_days}d window)`;

        const postStatus = ev.post_image_downloaded
            ? `<span class="text-green-600 font-bold">✓ Downloaded</span> (${ev.post_image_source || 'N/A'}, ${ev.post_window_days}d window)`
            : ev.post_imagery_open === false
                ? `<span class="text-red-600 font-bold">✗ Stopped</span> (max window reached)`
                : `<span class="text-yellow-600 font-bold">⏳ Tracking</span> (${ev.post_window_days}d window, checked ${ev.imagery_check_count ?? 0}x${ev.post_imagery_last_check ? ', last: ' + formatDate(ev.post_imagery_last_check) : ''})`;

        const content = `
            <div class="space-y-4 font-mono text-xs">
                <div class="grid grid-cols-2 gap-3">
                    <div><span class="text-gray-500 uppercase">Status</span><div class="font-bold mt-1">${ev.status}</div></div>
                    <div><span class="text-gray-500 uppercase">Severity</span><div class="font-bold mt-1 ${getSeverityClass(ev.severity)} px-2 py-0.5 inline-block uppercase text-[10px]">${ev.severity || 'N/A'}</div></div>
                    <div><span class="text-gray-500 uppercase">Country</span><div class="font-bold mt-1 uppercase">${ev.country || 'N/A'}</div></div>
                    <div><span class="text-gray-500 uppercase">Category</span><div class="font-bold mt-1">${ev.category_name || ev.category || 'N/A'}</div></div>
                    <div><span class="text-gray-500 uppercase">Coordinates</span><div class="font-bold mt-1">${ev.longitude?.toFixed(4) ?? '—'}, ${ev.latitude?.toFixed(4) ?? '—'}</div></div>
                    <div><span class="text-gray-500 uppercase">Event Date</span><div class="font-bold mt-1">${formatDate(ev.event_date)}</div></div>
                </div>
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">Imagery Tracking</div>
                    <div class="space-y-2">
                        <div class="flex gap-3 items-start"><span class="text-gray-500 w-14 shrink-0">Pre:</span><span>${preStatus}</span></div>
                        <div class="flex gap-3 items-start"><span class="text-gray-500 w-14 shrink-0">Post:</span><span>${postStatus}</span></div>
                    </div>
                </div>
                ${ev.quality_checked ? `
                <div class="border-t border-gray-100 pt-4">
                    <div class="font-bold uppercase tracking-widest text-gray-600 mb-3">Quality Assessment</div>
                    <div>Score: <span class="font-bold">${ev.quality_score ?? 'N/A'}</span> — <span class="font-bold ${ev.quality_pass ? 'text-green-600' : 'text-red-600'}">${ev.quality_pass ? 'PASS' : 'FAIL'}</span></div>
                </div>` : ''}
            </div>
        `;
        showModal(ev.title, content);
    } catch(e) {
        showToast('Failed to load event detail', 'error');
    } finally {
        showLoading(false);
    }
}

function formatImageryStatus(event) {
    const preOk = event.pre_image_downloaded;
    const postOk = event.post_image_downloaded;
    const postOpen = event.post_imagery_open !== false;
    const preExhausted = event.pre_imagery_exhausted;
    const preWin = event.pre_window_days ?? 7;
    const postWin = event.post_window_days ?? 7;

    const preBadge = preOk
        ? `<span class="px-1.5 py-0.5 bg-green-100 text-green-700 text-[9px] font-bold">pre✓</span>`
        : preExhausted
            ? `<span class="px-1.5 py-0.5 bg-red-100 text-red-700 text-[9px] font-bold">pre✗</span>`
            : `<span class="px-1.5 py-0.5 bg-yellow-100 text-yellow-700 text-[9px] font-bold">pre⏳${preWin}d</span>`;

    const postBadge = postOk
        ? `<span class="px-1.5 py-0.5 bg-green-100 text-green-700 text-[9px] font-bold">post✓</span>`
        : !postOpen
            ? `<span class="px-1.5 py-0.5 bg-red-100 text-red-700 text-[9px] font-bold">post✗</span>`
            : `<span class="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[9px] font-bold">post⏳${postWin}d</span>`;

    return `<div class="flex gap-1">${preBadge}${postBadge}</div>`;
}

async function processEvent(uuid) {
    showLoading(true);
    try {
        const response = await authFetch(`${EVENTS_API}/${uuid}/process`, { method: 'POST' });
        if (response.ok) {
            showToast('Event processing initiated', 'success');
            setTimeout(() => loadEvents(_eventsPage), 2000);
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
        'unlock': 'release_timeout_locks',
        'recheck': 'recheck_imagery',
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

// ==================== 分页渲染 ====================
function renderPagination(containerId, current, total, loadFn) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (total <= 1) { el.innerHTML = ''; return; }

    const pages = [];
    for (let i = Math.max(1, current - 2); i <= Math.min(total, current + 2); i++) pages.push(i);

    el.innerHTML = `
        <span class="font-mono text-[10px] text-gray-500">Page ${current} / ${total}</span>
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
        loadEvents, loadRawPool, loadTrack,
    };
    if (map[name]) map[name](page);
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
        <div class="font-mono text-xs font-bold tracking-wider uppercase mb-1">${type.toUpperCase()}</div>
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
        <div class="bg-white border border-gray-200 shadow-[8px_8px_0_#d4d4d4] w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col">
            <div class="flex justify-between items-center px-6 py-4 border-b border-gray-200">
                <span class="font-mono text-sm font-bold tracking-widest uppercase truncate pr-4">${escapeHtml(title)}</span>
                <button onclick="document.getElementById('detail-modal').remove()" class="font-mono text-xs font-bold px-3 py-1 border border-gray-300 hover:border-black uppercase">CLOSE</button>
            </div>
            <div class="overflow-y-auto p-6">${content}</div>
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

function formatDate(timestamp) {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toISOString().split('T')[0];
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

    const updates = {};
    section.querySelectorAll('[data-key]').forEach(el => {
        const key = el.dataset.key;
        let value = el.value;

        if (el.type === 'password') {
            if (!value.trim()) return;
        }
        if (el.tagName === 'SELECT') {
            updates[key] = value;
            return;
        }
        if (value === '' && _settingsCache[key] !== undefined) return;
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
        await loadSettings();
    } catch (e) {
        showToast('Save failed: ' + e.message, 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== 全局导出 ====================
window.processEvent = processEvent;
window.showEventDetail = showEventDetail;
window.viewReport = viewReport;
window.generateReport = generateReport;
window.loadEvents = loadEvents;
window.loadPool = loadPool;
window.loadRawPool = loadRawPool;
window.loadTrack = loadTrack;
window.loadPoolStats = loadPoolStats;
window.switchPoolTab = switchPoolTab;
window.loadProducts = loadProducts;
window.loadReports = loadReports;
window.loadTokens = loadTokens;
window.triggerJob = triggerJob;
window.loadSettings = loadSettings;
window.toggleSection = toggleSection;
window.saveSettingsGroup = saveSettingsGroup;
window.switchView = switchView;
