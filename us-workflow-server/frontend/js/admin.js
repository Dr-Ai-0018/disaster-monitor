const API_BASE = '';
const AUTH_API = `${API_BASE}/api/auth`;
const WORKFLOW_API = `${API_BASE}/api/workflow`;

const POOL_LABELS = {
    event_pool: '事件池',
    imagery_pool: '影像池',
    image_review_pool: '影像审核池',
    inference_pool: '推理池',
    summary_report_pool: '摘要日报池',
};

const POOL_DESCRIPTIONS = {
    event_pool: '自动维护事件、经纬度和详情补抓，等待影像落地。',
    imagery_pool: '自动维护 GEE 影像下载，不在这里做人审。',
    image_review_pool: 'Grok / 人工确认影像可不可用于后续推理。',
    inference_pool: '只保留通过影像审核的事件，手动触发推理。',
    summary_report_pool: '手动生成摘要、审核摘要、推入日报候选并生成日报。',
};

let AUTH_TOKEN = localStorage.getItem('workflow_token') || '';
let OVERVIEW = null;
let CURRENT_POOL = 'event_pool';
let CURRENT_ITEMS = [];
let SELECTED_UUIDS = new Set();
let ACTIVE_UUID = '';
let CURRENT_REPORTS = [];
let LAST_BATCH_RESULT = null;

async function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (AUTH_TOKEN) headers.Authorization = `Bearer ${AUTH_TOKEN}`;
    if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const resp = await fetch(url, { ...options, headers });
    if (resp.status === 401) {
        localStorage.removeItem('workflow_token');
        AUTH_TOKEN = '';
        renderAuthShell();
    }
    return resp;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function formatDateTime(ts) {
    if (!ts) return '-';
    return new Date(ts).toLocaleString('zh-CN');
}

function badge(text, tone = 'neutral') {
    const classes = {
        neutral: 'bg-neutral-100 text-neutral-700',
        green: 'bg-green-100 text-green-700',
        amber: 'bg-amber-100 text-amber-700',
        red: 'bg-red-100 text-red-700',
        black: 'bg-black text-white',
    };
    return `<span class="inline-flex px-2 py-1 text-[11px] font-bold ${classes[tone] || classes.neutral}">${escapeHtml(text)}</span>`;
}

function poolMode(poolKey) {
    const card = OVERVIEW?.cards?.find((item) => item.key === poolKey);
    return card?.auto_mode || '手动';
}

function renderAuthShell() {
    const root = document.getElementById('auth-shell');
    if (!root) return;
    if (AUTH_TOKEN) {
        root.innerHTML = `
            <div class="border border-black bg-white p-4">
                <div class="text-[11px] uppercase tracking-[0.35em] text-neutral-500">Auth</div>
                <div class="mt-2 text-lg font-black">已登录</div>
                <div class="mt-2 text-sm text-neutral-600 leading-6">当前会话已持有 workflow token，可以直接操作五池后台。</div>
                <button id="logout-btn" class="mt-4 px-4 py-2 border border-black bg-white">退出登录</button>
            </div>
        `;
        document.getElementById('logout-btn')?.addEventListener('click', () => {
            AUTH_TOKEN = '';
            localStorage.removeItem('workflow_token');
            renderAuthShell();
        });
        return;
    }
    root.innerHTML = `
        <form id="login-form" class="border border-black bg-white p-4 space-y-3">
            <div class="text-[11px] uppercase tracking-[0.35em] text-neutral-500">Workflow Login</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input id="login-username" class="border border-black px-3 py-2" placeholder="用户名" autocomplete="username">
                <input id="login-password" type="password" class="border border-black px-3 py-2" placeholder="密码" autocomplete="current-password">
            </div>
            <button class="px-4 py-2 bg-black text-white">登录后台</button>
        </form>
    `;
    document.getElementById('login-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const username = document.getElementById('login-username')?.value?.trim();
        const password = document.getElementById('login-password')?.value || '';
        if (!username || !password) {
            alert('请输入用户名和密码');
            return;
        }
        const resp = await fetch(`${AUTH_API}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
            alert(data.detail || '登录失败');
            return;
        }
        AUTH_TOKEN = data.access_token;
        localStorage.setItem('workflow_token', AUTH_TOKEN);
        renderAuthShell();
        await bootstrapAfterLogin();
    });
}

async function ensureLogin() {
    if (!AUTH_TOKEN) {
        renderAuthShell();
        return false;
    }
    return true;
}

async function loadOverview() {
    const resp = await apiFetch(`${WORKFLOW_API}/overview`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '加载概览失败');
    OVERVIEW = data;
    document.getElementById('runtime-meta').innerHTML = `
        <div class="bg-white border border-black p-4">
            <div class="text-[11px] uppercase tracking-[0.25em] text-neutral-500">遗留调度器</div>
            <div class="mt-3 text-2xl font-black">${data.legacy_scheduler_enabled ? '仍可运行' : '建议冻结'}</div>
            <div class="mt-2 text-xs text-neutral-500">建议旧项目设为 ENABLE_SCHEDULER=false，避免双跑。</div>
        </div>
        <div class="bg-white border border-black p-4">
            <div class="text-[11px] uppercase tracking-[0.25em] text-neutral-500">旧项目路径</div>
            <div class="mt-3 text-xs break-all leading-6">${escapeHtml(data.legacy_root)}</div>
        </div>
        <div class="bg-white border border-black p-4">
            <div class="text-[11px] uppercase tracking-[0.25em] text-neutral-500">数据库</div>
            <div class="mt-3 text-xs break-all leading-6">${escapeHtml(data.database_path)}</div>
        </div>
        <div class="bg-white border border-black p-4">
            <div class="text-[11px] uppercase tracking-[0.25em] text-neutral-500">遗留 Python</div>
            <div class="mt-3 text-xs break-all leading-6">${escapeHtml(data.legacy_python)}</div>
        </div>
    `;
    document.getElementById('overview-cards').innerHTML = data.cards.map((card) => `
        <button data-pool-card="${card.key}" class="pool-card text-left bg-white border border-neutral-300 p-4 transition-all ${CURRENT_POOL === card.key ? 'active' : ''}">
            <div class="flex items-start justify-between gap-3">
                <div>
                    <div class="text-[11px] uppercase tracking-[0.25em] text-neutral-500">${escapeHtml(card.label)}</div>
                    <div class="mt-3 text-4xl font-black">${card.total}</div>
                </div>
                ${badge(card.auto_mode === '自动' ? '自动' : '人工', card.auto_mode === '自动' ? 'green' : 'amber')}
            </div>
            <div class="mt-4 text-sm text-neutral-600 leading-6">${escapeHtml(card.description)}</div>
        </button>
    `).join('');
}

function syncPoolHeader(total = CURRENT_ITEMS.length) {
    document.getElementById('pool-select').value = CURRENT_POOL;
    document.getElementById('pool-headline').textContent = POOL_LABELS[CURRENT_POOL];
    document.getElementById('pool-description').textContent = POOL_DESCRIPTIONS[CURRENT_POOL] || '';
    document.getElementById('pool-total').textContent = String(total);
    document.getElementById('pool-mode').textContent = poolMode(CURRENT_POOL);
    document.getElementById('selected-total').textContent = String(SELECTED_UUIDS.size);
}

async function loadItems() {
    const resp = await apiFetch(`${WORKFLOW_API}/items?pool=${encodeURIComponent(CURRENT_POOL)}&limit=200`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '加载任务列表失败');
    CURRENT_ITEMS = data.data || [];
    const activeSet = new Set(CURRENT_ITEMS.map((item) => item.uuid));
    SELECTED_UUIDS = new Set([...SELECTED_UUIDS].filter((uuid) => activeSet.has(uuid)));
    syncPoolHeader(data.total || CURRENT_ITEMS.length);
    renderItemsTable();
}

function renderItemsTable() {
    const tbody = document.getElementById('items-tbody');
    tbody.innerHTML = CURRENT_ITEMS.map((item) => `
        <tr class="border-b border-neutral-200 cursor-pointer ${ACTIVE_UUID === item.uuid ? 'row-active' : ''}" data-row-uuid="${item.uuid}">
            <td class="px-4 py-4" onclick="event.stopPropagation()">
                <input type="checkbox" data-select-uuid="${item.uuid}" ${SELECTED_UUIDS.has(item.uuid) ? 'checked' : ''}>
            </td>
            <td class="px-4 py-4">
                <div class="font-black">${escapeHtml(item.title || item.uuid)}</div>
                <div class="mt-1 text-xs text-neutral-500">${escapeHtml(item.uuid)}</div>
            </td>
            <td class="px-4 py-4">${escapeHtml(item.country || '-')}</td>
            <td class="px-4 py-4">${escapeHtml(item.severity || '-')}</td>
            <td class="px-4 py-4">${badge(item.pool_status, 'black')}</td>
            <td class="px-4 py-4">${escapeHtml(item.imagery)}</td>
            <td class="px-4 py-4">${escapeHtml(item.quality)}</td>
            <td class="px-4 py-4">${escapeHtml(item.inference)}</td>
            <td class="px-4 py-4">${escapeHtml(item.summary)}</td>
            <td class="px-4 py-4">${escapeHtml(item.report_candidate)}</td>
            <td class="px-4 py-4 text-xs text-neutral-500">${formatDateTime(item.updated_at)}</td>
        </tr>
    `).join('') || `<tr><td colspan="11" class="px-4 py-10 text-center text-neutral-500">该池暂无数据</td></tr>`;
    document.getElementById('master-checkbox').checked = CURRENT_ITEMS.length > 0 && CURRENT_ITEMS.every((item) => SELECTED_UUIDS.has(item.uuid));
}

async function loadDetail(uuid) {
    ACTIVE_UUID = uuid;
    renderItemsTable();
    const resp = await apiFetch(`${WORKFLOW_API}/items/${uuid}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '加载详情失败');
    document.getElementById('detail-empty').classList.add('hidden');
    const panel = document.getElementById('detail-panel');
    panel.classList.remove('hidden');
    panel.innerHTML = `
        <div class="space-y-2">
            <div class="text-xl font-black leading-tight">${escapeHtml(data.title || data.uuid)}</div>
            <div class="text-xs text-neutral-500 break-all">${escapeHtml(data.uuid)}</div>
        </div>
        <div class="grid grid-cols-2 gap-3 text-sm">
            <div class="border border-neutral-300 p-3 bg-white"><div class="text-xs text-neutral-500">池子</div><div class="mt-2 font-black">${escapeHtml(POOL_LABELS[data.pool] || data.pool)}</div></div>
            <div class="border border-neutral-300 p-3 bg-white"><div class="text-xs text-neutral-500">阶段</div><div class="mt-2 font-black">${escapeHtml(data.pool_status)}</div></div>
            <div class="border border-neutral-300 p-3 bg-white"><div class="text-xs text-neutral-500">国家</div><div class="mt-2 font-black">${escapeHtml(data.country || '-')}</div></div>
            <div class="border border-neutral-300 p-3 bg-white"><div class="text-xs text-neutral-500">严重度</div><div class="mt-2 font-black">${escapeHtml(data.severity || '-')}</div></div>
            <div class="border border-neutral-300 p-3 bg-white"><div class="text-xs text-neutral-500">坐标</div><div class="mt-2 font-black">${escapeHtml(`${data.latitude ?? '-'}, ${data.longitude ?? '-'}`)}</div></div>
            <div class="border border-neutral-300 p-3 bg-white"><div class="text-xs text-neutral-500">影像选择</div><div class="mt-2 font-black">${escapeHtml(data.selected_image_type || '-')}</div></div>
        </div>
        <div class="space-y-2">
            <div class="text-xs uppercase tracking-[0.25em] text-neutral-500">事件与任务</div>
            <div class="border border-neutral-300 bg-white p-3 text-sm leading-7">
                <div>事件状态: <span class="font-black">${escapeHtml(data.event_status || '-')}</span></div>
                <div>详情抓取: <span class="font-black">${escapeHtml(data.detail_fetch_status || '-')}</span></div>
                <div>推理状态: <span class="font-black">${escapeHtml(data.task_status || '-')}</span></div>
                <div>推理进度: <span class="font-black">${escapeHtml(data.task_progress_stage || '-')}</span></div>
                <div>推理说明: <span class="font-black">${escapeHtml(data.task_progress_message || '-')}</span></div>
                <div>错误信息: <span class="font-black">${escapeHtml(data.task_failure_reason || '-')}</span></div>
            </div>
        </div>
        <div class="space-y-2">
            <div class="text-xs uppercase tracking-[0.25em] text-neutral-500">影像路径</div>
            <div class="border border-neutral-300 bg-white p-3 text-xs leading-6 break-all">
                <div>灾前: ${escapeHtml(data.pre_image_path || '-')}</div>
                <div class="mt-2">灾后: ${escapeHtml(data.post_image_path || '-')}</div>
            </div>
        </div>
        <div class="space-y-2">
            <div class="text-xs uppercase tracking-[0.25em] text-neutral-500">摘要与日报</div>
            <div class="border border-neutral-300 bg-white p-3 text-sm leading-7">
                <div>摘要审核: <span class="font-black">${escapeHtml(data.summary_review_status || '-')}</span></div>
                <div>打回原因: <span class="font-black">${escapeHtml(data.summary_review_reason || '-')}</span></div>
                <div>日报日期: <span class="font-black">${escapeHtml(data.report_date || '-')}</span></div>
                <div>日报状态: <span class="font-black">${data.report_ready ? '已可进入日报流' : '尚未就绪'}</span></div>
            </div>
            <div class="border border-neutral-300 bg-white p-3 text-sm leading-7 whitespace-pre-wrap">${escapeHtml(data.summary_text || '暂无摘要')}</div>
        </div>
        <div class="grid grid-cols-2 gap-3">
            <button data-single-action="reset" data-uuid="${escapeHtml(data.uuid)}" class="px-4 py-3 border border-red-400 text-red-700 bg-white">重置推理/摘要</button>
            <button data-single-action="reset-stage" data-uuid="${escapeHtml(data.uuid)}" class="px-4 py-3 border border-black bg-white">回退指定阶段</button>
            <button data-single-action="trigger-inference" data-uuid="${escapeHtml(data.uuid)}" class="px-4 py-3 bg-black text-white">再次触发推理</button>
            <button data-single-action="generate-summary" data-uuid="${escapeHtml(data.uuid)}" class="px-4 py-3 border border-black bg-white">生成摘要</button>
            <button data-single-action="reject-summary" data-uuid="${escapeHtml(data.uuid)}" class="px-4 py-3 border border-black bg-white">摘要打回</button>
            <button data-single-action="approve-summary" data-uuid="${escapeHtml(data.uuid)}" class="px-4 py-3 border border-black bg-white">摘要准入日报</button>
        </div>
    `;
}

async function postJson(url, body) {
    const resp = await apiFetch(url, { method: 'POST', body: JSON.stringify(body || {}) });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || '请求失败');
    return data;
}

function renderBatchResult(data) {
    LAST_BATCH_RESULT = data;
    const panel = document.getElementById('batch-result-panel');
    if (!panel || !data?.results) return;
    panel.classList.remove('hidden');
    document.getElementById('batch-result-title').textContent = data.message || '批量结果';
    document.getElementById('batch-result-summary').textContent = `共 ${data.total} 条，成功 ${data.succeeded} 条，失败 ${data.failed} 条`;
    document.getElementById('batch-result-list').innerHTML = data.results.map((item) => `
        <div class="border border-neutral-300 p-3 bg-white">
            <div class="flex items-start justify-between gap-3">
                <div class="font-black text-sm break-all">${escapeHtml(item.uuid)}</div>
                ${badge(item.ok ? '成功' : '失败', item.ok ? 'green' : 'red')}
            </div>
            <div class="mt-2 text-xs text-neutral-500 leading-6">${escapeHtml(item.message || '')}</div>
        </div>
    `).join('');
}

function promptForImageType() {
    const input = prompt('影像类型: pre 或 post', 'post');
    if (!input) return undefined;
    const normalized = input.trim().toLowerCase();
    return normalized === 'pre' ? 'pre' : 'post';
}

function promptForStageReset() {
    const input = prompt('回退阶段: image_review / inference / summary', 'inference');
    if (!input) return undefined;
    const normalized = input.trim().toLowerCase();
    if (['image_review', 'inference', 'summary'].includes(normalized)) return normalized;
    alert('只支持 image_review、inference、summary');
    return undefined;
}

function requireSelection() {
    if (!SELECTED_UUIDS.size) {
        alert('请先勾选至少一条事件');
        return null;
    }
    return [...SELECTED_UUIDS];
}

async function refreshAll(keepDetail = true) {
    await loadOverview();
    await loadItems();
    if (keepDetail && ACTIVE_UUID && CURRENT_ITEMS.some((item) => item.uuid === ACTIVE_UUID)) {
        await loadDetail(ACTIVE_UUID);
    } else if (ACTIVE_UUID) {
        ACTIVE_UUID = '';
        document.getElementById('detail-panel').classList.add('hidden');
        document.getElementById('detail-empty').classList.remove('hidden');
    }
}

async function runBatchAction(action) {
    const uuids = requireSelection();
    if (!uuids) return;
    let result = null;
    if (action === 'reset-selected') {
        result = await postJson(`${WORKFLOW_API}/items/batch-reset-inference`, { uuids });
    } else if (action === 'reset-image-review') {
        result = await postJson(`${WORKFLOW_API}/items/batch-reset-stage`, { uuids, stage: 'image_review' });
    } else if (action === 'reset-summary') {
        result = await postJson(`${WORKFLOW_API}/items/batch-reset-stage`, { uuids, stage: 'summary' });
    } else if (action === 'approve-image') {
        const imageType = promptForImageType();
        result = await postJson(`${WORKFLOW_API}/items/batch-image-review`, { uuids, approved: true, image_type: imageType });
    } else if (action === 'reject-image') {
        const reason = prompt('打回原因', '') || '';
        result = await postJson(`${WORKFLOW_API}/items/batch-image-review`, { uuids, approved: false, reason });
    } else if (action === 'trigger-inference') {
        const imageType = promptForImageType();
        result = await postJson(`${WORKFLOW_API}/items/batch-trigger-inference`, { uuids, selected_image_type: imageType });
    } else if (action === 'generate-summary') {
        result = await postJson(`${WORKFLOW_API}/items/batch-generate-summary`, { uuids, persist: true });
    } else if (action === 'reject-summary') {
        const reason = prompt('摘要打回原因', '') || '';
        result = await postJson(`${WORKFLOW_API}/items/batch-summary-approval`, { uuids, approved: false, reason });
    } else if (action === 'approve-summary') {
        const reportDate = document.getElementById('report-date-input')?.value || prompt('日报日期 YYYY-MM-DD', '') || '';
        result = await postJson(`${WORKFLOW_API}/items/batch-summary-approval`, { uuids, approved: true, report_date: reportDate || undefined });
    }
    if (result?.results) renderBatchResult(result);
    SELECTED_UUIDS.clear();
    await refreshAll();
}

async function runSingleAction(action, uuid) {
    if (action === 'reset') {
        await postJson(`${WORKFLOW_API}/items/${uuid}/reset-inference`);
    } else if (action === 'reset-stage') {
        const stage = promptForStageReset();
        if (!stage) return;
        await postJson(`${WORKFLOW_API}/items/${uuid}/reset-stage`, { stage });
    } else if (action === 'trigger-inference') {
        const imageType = promptForImageType();
        await postJson(`${WORKFLOW_API}/items/${uuid}/trigger-inference`, { selected_image_type: imageType });
    } else if (action === 'generate-summary') {
        await postJson(`${WORKFLOW_API}/items/${uuid}/generate-summary`, { persist: true });
    } else if (action === 'reject-summary') {
        const reason = prompt('摘要打回原因', '') || '';
        await postJson(`${WORKFLOW_API}/items/${uuid}/summary-approval`, { approved: false, reason });
    } else if (action === 'approve-summary') {
        const reportDate = document.getElementById('report-date-input')?.value || prompt('日报日期 YYYY-MM-DD', '') || '';
        await postJson(`${WORKFLOW_API}/items/${uuid}/summary-approval`, { approved: true, report_date: reportDate || undefined });
    }
    await refreshAll();
}

async function loadCandidates() {
    const reportDate = document.getElementById('report-date-input')?.value;
    if (!reportDate) {
        alert('先选择日报日期');
        return;
    }
    const resp = await apiFetch(`${WORKFLOW_API}/report-candidates?report_date=${encodeURIComponent(reportDate)}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '候选列表加载失败');
    document.getElementById('candidate-summary').textContent = `日期 ${reportDate} 当前有 ${data.total} 条候选事件`;
    document.getElementById('candidate-list').innerHTML = data.data.map((item) => `
        <div class="border border-neutral-300 bg-white p-3">
            <div class="flex items-start justify-between gap-3">
                <button data-candidate-uuid="${item.uuid}" class="flex-1 text-left hover:bg-neutral-50">
                    <div class="font-black">${escapeHtml(item.title || item.uuid)}</div>
                    <div class="mt-1 text-xs text-neutral-500">${escapeHtml(item.country || '-')} / ${escapeHtml(item.severity || '-')}</div>
                </button>
                <button data-remove-candidate="${item.uuid}" class="px-3 py-2 border border-black bg-white text-xs">移出</button>
            </div>
        </div>
    `).join('') || '<div class="text-sm text-neutral-500">该日期暂无候选事件</div>';
}

async function loadReports() {
    const resp = await apiFetch(`${WORKFLOW_API}/reports?limit=12`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '日报列表加载失败');
    CURRENT_REPORTS = data.data || [];
    document.getElementById('report-list').innerHTML = CURRENT_REPORTS.map((item) => `
        <div class="border border-neutral-300 bg-white p-3">
            <div class="flex items-start justify-between gap-3">
                <div>
                    <div class="font-black">${escapeHtml(item.report_date)}</div>
                    <div class="mt-1 text-xs text-neutral-500">${escapeHtml(item.report_title || '未命名日报')}</div>
                    <div class="mt-2 text-xs text-neutral-500">${item.event_count} 条事件 / ${formatDateTime(item.generated_at)}</div>
                </div>
                <div class="space-y-2 text-right">
                    <div>${badge(item.published ? '已发布' : '草稿', item.published ? 'green' : 'amber')}</div>
                    <button data-view-report="${item.report_date}" class="px-3 py-2 border border-black bg-white text-xs">详情</button>
                    ${item.published ? '' : `<button data-publish-report="${item.report_date}" class="px-3 py-2 border border-black bg-white text-xs">发布</button>`}
                </div>
            </div>
        </div>
    `).join('') || '<div class="text-sm text-neutral-500">暂无日报草稿或已发布日报</div>';
}

async function viewReport(reportDate) {
    const resp = await apiFetch(`${WORKFLOW_API}/reports/${encodeURIComponent(reportDate)}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '日报详情加载失败');
    document.getElementById('report-detail-panel').classList.remove('hidden');
    document.getElementById('report-detail-title').textContent = data.report_title || data.report_date;
    document.getElementById('report-detail-meta').textContent = `${data.report_date} / ${data.event_count} 条事件 / ${data.published ? '已发布' : '草稿'}`;
    document.getElementById('report-detail-content').textContent = data.report_content || '暂无内容';
}

async function generateReport() {
    const reportDate = document.getElementById('report-date-input')?.value;
    if (!reportDate) {
        alert('先选择日报日期');
        return;
    }
    const data = await postJson(`${WORKFLOW_API}/reports/generate`, { report_date: reportDate });
    alert(`日报已生成: ${data.report_title || data.report_date} / ${data.event_count} 条事件`);
    await refreshAll(false);
    await loadCandidates();
    await loadReports();
}

async function publishReport(reportDate) {
    const data = await postJson(`${WORKFLOW_API}/reports/${encodeURIComponent(reportDate)}/publish`);
    alert(data.message || `日报 ${reportDate} 已发布`);
    await refreshAll(false);
    await loadReports();
}

async function removeCandidate(uuid) {
    const data = await postJson(`${WORKFLOW_API}/items/${uuid}/remove-report-candidate`);
    alert(data.message || '已移出日报候选');
    await refreshAll(false);
    await loadCandidates();
}

async function bootstrapAfterLogin() {
    syncPoolHeader(0);
    await refreshAll(false);
    await loadCandidates();
    await loadReports();
}

document.addEventListener('click', async (event) => {
    const poolCard = event.target.closest('[data-pool-card]');
    if (poolCard) {
        CURRENT_POOL = poolCard.dataset.poolCard;
        SELECTED_UUIDS.clear();
        ACTIVE_UUID = '';
        await refreshAll(false);
        return;
    }

    const row = event.target.closest('[data-row-uuid]');
    if (row) {
        await loadDetail(row.dataset.rowUuid);
        return;
    }

    const batchBtn = event.target.closest('[data-batch-action]');
    if (batchBtn) {
        try {
            await runBatchAction(batchBtn.dataset.batchAction);
        } catch (err) {
            alert(err.message);
        }
        return;
    }

    const singleBtn = event.target.closest('[data-single-action]');
    if (singleBtn) {
        try {
            await runSingleAction(singleBtn.dataset.singleAction, singleBtn.dataset.uuid);
        } catch (err) {
            alert(err.message);
        }
        return;
    }

    const candidateBtn = event.target.closest('[data-candidate-uuid]');
    if (candidateBtn) {
        try {
            await loadDetail(candidateBtn.dataset.candidateUuid);
        } catch (err) {
            alert(err.message);
        }
        return;
    }

    const publishBtn = event.target.closest('[data-publish-report]');
    if (publishBtn) {
        try {
            await publishReport(publishBtn.dataset.publishReport);
        } catch (err) {
            alert(err.message);
        }
        return;
    }

    const viewReportBtn = event.target.closest('[data-view-report]');
    if (viewReportBtn) {
        try {
            await viewReport(viewReportBtn.dataset.viewReport);
        } catch (err) {
            alert(err.message);
        }
        return;
    }

    const removeCandidateBtn = event.target.closest('[data-remove-candidate]');
    if (removeCandidateBtn) {
        if (!confirm('确认将该事件移出日报候选？')) return;
        try {
            await removeCandidate(removeCandidateBtn.dataset.removeCandidate);
        } catch (err) {
            alert(err.message);
        }
    }
});

document.addEventListener('change', async (event) => {
    const select = event.target.closest('#pool-select');
    if (select) {
        CURRENT_POOL = select.value;
        SELECTED_UUIDS.clear();
        ACTIVE_UUID = '';
        await refreshAll(false);
        return;
    }

    const checkbox = event.target.closest('[data-select-uuid]');
    if (checkbox) {
        const uuid = checkbox.dataset.selectUuid;
        if (checkbox.checked) SELECTED_UUIDS.add(uuid);
        else SELECTED_UUIDS.delete(uuid);
        syncPoolHeader();
        document.getElementById('master-checkbox').checked = CURRENT_ITEMS.length > 0 && CURRENT_ITEMS.every((item) => SELECTED_UUIDS.has(item.uuid));
        return;
    }

    if (event.target.id === 'master-checkbox') {
        if (event.target.checked) {
            CURRENT_ITEMS.forEach((item) => SELECTED_UUIDS.add(item.uuid));
        } else {
            CURRENT_ITEMS.forEach((item) => SELECTED_UUIDS.delete(item.uuid));
        }
        syncPoolHeader();
        renderItemsTable();
    }
});

document.getElementById('reload-btn')?.addEventListener('click', async () => {
    try {
        await refreshAll();
    } catch (err) {
        alert(err.message);
    }
});

document.getElementById('select-all-btn')?.addEventListener('click', () => {
    CURRENT_ITEMS.forEach((item) => SELECTED_UUIDS.add(item.uuid));
    syncPoolHeader();
    renderItemsTable();
});

document.getElementById('clear-selection-btn')?.addEventListener('click', () => {
    SELECTED_UUIDS.clear();
    syncPoolHeader();
    renderItemsTable();
});

document.getElementById('reset-all-btn')?.addEventListener('click', async () => {
    if (!confirm('确认重置所有推理/摘要阶段内容？')) return;
    try {
        await postJson(`${WORKFLOW_API}/reset-inference-all`);
        SELECTED_UUIDS.clear();
        await refreshAll(false);
    } catch (err) {
        alert(err.message);
    }
});

document.getElementById('load-candidates-btn')?.addEventListener('click', async () => {
    try {
        await loadCandidates();
        await loadReports();
    } catch (err) {
        alert(err.message);
    }
});

document.getElementById('generate-report-btn')?.addEventListener('click', async () => {
    try {
        if (!confirm('确认按当前候选池生成日报草稿？')) return;
        await generateReport();
    } catch (err) {
        alert(err.message);
    }
});

document.getElementById('batch-result-close')?.addEventListener('click', () => {
    document.getElementById('batch-result-panel')?.classList.add('hidden');
});

window.addEventListener('DOMContentLoaded', async () => {
    renderAuthShell();
    const today = new Date();
    document.getElementById('report-date-input').value = today.toISOString().slice(0, 10);
    const ok = await ensureLogin();
    if (!ok) return;
    try {
        await bootstrapAfterLogin();
    } catch (err) {
        alert(err.message);
    }
});
