const API_BASE = '';
const AUTH_API = `${API_BASE}/api/auth`;
const WORKFLOW_API = `${API_BASE}/api/workflow`;

let AUTH_TOKEN = localStorage.getItem('workflow_token') || '';

async function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (AUTH_TOKEN) headers.Authorization = `Bearer ${AUTH_TOKEN}`;
    if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    return fetch(url, { ...options, headers });
}

async function ensureLogin() {
    if (AUTH_TOKEN) return true;
    const username = prompt('Workflow 用户名');
    const password = prompt('Workflow 密码');
    if (!username || !password) return false;
    const resp = await fetch(`${AUTH_API}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    if (!resp.ok) {
        alert('登录失败');
        return false;
    }
    const data = await resp.json();
    AUTH_TOKEN = data.access_token;
    localStorage.setItem('workflow_token', AUTH_TOKEN);
    return true;
}

function badge(text, color = 'neutral') {
    const map = {
        neutral: 'bg-neutral-100 text-neutral-700',
        green: 'bg-green-100 text-green-700',
        amber: 'bg-amber-100 text-amber-700',
        red: 'bg-red-100 text-red-700',
    };
    return `<span class="px-2 py-1 text-xs font-semibold ${map[color] || map.neutral}">${text}</span>`;
}

async function loadOverview() {
    const resp = await apiFetch(`${WORKFLOW_API}/overview`);
    const data = await resp.json();
    document.getElementById('runtime-meta').innerHTML = `
        <div class="bg-white border border-neutral-200 p-4"><div class="text-xs text-neutral-500 uppercase">调度器</div><div class="text-xl font-bold">${data.scheduler_enabled ? '新项目已启用' : '已禁用'}</div></div>
        <div class="bg-white border border-neutral-200 p-4"><div class="text-xs text-neutral-500 uppercase">旧项目路径</div><div class="text-sm break-all">${data.legacy_root}</div></div>
        <div class="bg-white border border-neutral-200 p-4"><div class="text-xs text-neutral-500 uppercase">数据库</div><div class="text-sm break-all">${data.database_path}</div></div>
    `;
    document.getElementById('overview-cards').innerHTML = data.cards.map(card => `
        <div class="bg-white border border-neutral-200 p-4 space-y-2">
            <div class="text-xs uppercase text-neutral-500">${card.label}</div>
            <div class="text-3xl font-black">${card.total}</div>
            <div>${badge(card.auto_mode === '自动' ? '自动推进' : '人工把关', card.auto_mode === '自动' ? 'green' : 'amber')}</div>
            <div class="text-sm text-neutral-600">${card.description}</div>
        </div>
    `).join('');
}

function actionButtons(item) {
    return [
        `<button data-action="reset" data-uuid="${item.uuid}" class="px-2 py-1 border border-neutral-300">重置推理</button>`,
        `<button data-action="approve-image" data-uuid="${item.uuid}" class="px-2 py-1 border border-green-300 text-green-700">影像通过</button>`,
        `<button data-action="reject-image" data-uuid="${item.uuid}" class="px-2 py-1 border border-red-300 text-red-700">影像打回</button>`,
        `<button data-action="approve-summary" data-uuid="${item.uuid}" class="px-2 py-1 border border-neutral-300">摘要准入日报</button>`,
    ].join(' ');
}

async function loadItems() {
    const pool = document.getElementById('pool-select').value;
    const resp = await apiFetch(`${WORKFLOW_API}/items?pool=${encodeURIComponent(pool)}`);
    const data = await resp.json();
    document.getElementById('items-tbody').innerHTML = data.data.map(item => `
        <tr class="border-b border-neutral-100">
            <td class="py-3">${item.title || item.uuid}</td>
            <td class="py-3">${item.country || '-'}</td>
            <td class="py-3">${item.severity || '-'}</td>
            <td class="py-3">${item.imagery}</td>
            <td class="py-3">${item.quality}</td>
            <td class="py-3">${item.inference}</td>
            <td class="py-3">${item.summary}</td>
            <td class="py-3">${item.report_candidate}</td>
            <td class="py-3 space-x-1">${actionButtons(item)}</td>
        </tr>
    `).join('') || `<tr><td colspan="9" class="py-8 text-center text-neutral-500">该池暂无数据</td></tr>`;
}

async function postJson(url, body) {
    const resp = await apiFetch(url, { method: 'POST', body: JSON.stringify(body || {}) });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || '请求失败');
    return data;
}

document.addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const { action, uuid } = button.dataset;
    try {
        if (action === 'reset') {
            await postJson(`${WORKFLOW_API}/items/${uuid}/reset-inference`);
        } else if (action === 'approve-image') {
            await postJson(`${WORKFLOW_API}/items/${uuid}/image-review`, { approved: true });
        } else if (action === 'reject-image') {
            const reason = prompt('打回原因') || '';
            await postJson(`${WORKFLOW_API}/items/${uuid}/image-review`, { approved: false, reason });
        } else if (action === 'approve-summary') {
            const reportDate = prompt('日报日期 YYYY-MM-DD') || '';
            await postJson(`${WORKFLOW_API}/items/${uuid}/summary-approval`, { approved: true, report_date: reportDate || undefined });
        }
        await loadOverview();
        await loadItems();
    } catch (err) {
        alert(err.message);
    }
});

document.getElementById('reload-btn')?.addEventListener('click', async () => {
    await loadOverview();
    await loadItems();
});

document.getElementById('pool-select')?.addEventListener('change', loadItems);

document.getElementById('reset-all-btn')?.addEventListener('click', async () => {
    if (!confirm('确认重置所有推理/摘要阶段内容？')) return;
    try {
        await postJson(`${WORKFLOW_API}/reset-inference-all`);
        await loadOverview();
        await loadItems();
    } catch (err) {
        alert(err.message);
    }
});

window.addEventListener('DOMContentLoaded', async () => {
    const ok = await ensureLogin();
    if (!ok) return;
    await loadOverview();
    await loadItems();
});
