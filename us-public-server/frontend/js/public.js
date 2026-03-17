/**
 * DISASTER_MONITOR — Public Frontend
 * Tabs: 事件池 | AI报告 | AI分析
 */

'use strict';

const API_BASE   = '';
const POOL_API   = `${API_BASE}/api/pool`;
const PUBLIC_API = `${API_BASE}/api/public`;

// ── Global state ────────────────────────────────────────────────────────────

const poolState = {
    filters: { category: '', country: '', severity: '' },
    pagination: { currentPage: 1, pageSize: 20, totalPages: 1 },
};

const reportsState = {
    page: 1, pages: 1,
    loading: false,
};

const analysisState = {
    page: 1, pages: 1, limit: 12,
    loading: false,
};

// ── ECharts 实例 ─────────────────────────────────────────────────────────────

let chartSeverity   = null;
let chartCategory   = null;
let chartReportCat  = null;
let chartReportSev  = null;
let chartReportCou  = null;

// ── 严重程度颜色映射 ─────────────────────────────────────────────────────────

const SEV_COLOR = {
    extreme: '#dc2626',
    high:    '#f97316',
    medium:  '#eab308',
    low:     '#9ca3af',
};

const SEV_COLOR_CARD = {
    extreme: 'bg-red-600 text-white',
    high:    'bg-orange-500 text-white',
    medium:  'bg-yellow-500 text-black',
    low:     'bg-gray-400 text-white',
};

const SEV_STYLE = {
    extreme: 'border-red-500 bg-red-50 text-red-600',
    high:    'border-orange-400 bg-orange-50 text-orange-600',
    medium:  'border-yellow-400 bg-yellow-50 text-yellow-700',
    low:     'border-gray-300 bg-gray-50 text-gray-500',
};

// ECharts 公共字体
const MONO = 'JetBrains Mono, monospace';

// ── Bootstrap ────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();

    // marked.js 配置 - 支持 GFM 表格、自动换行
    if (window.marked) {
        marked.setOptions({ gfm: true, breaks: true });
    }

    initPoolListeners();
    switchTab('pool');  // 默认 Tab

    // 每 30 秒刷新活跃/总量指标
    setInterval(() => {
        if (document.getElementById('view-pool').classList.contains('hidden')) return;
        refreshPoolStats();
    }, 30_000);

    // 窗口 resize 时重绘图表
    window.addEventListener('resize', () => {
        chartSeverity?.resize();
        chartCategory?.resize();
        chartReportCat?.resize();
        chartReportSev?.resize();
        chartReportCou?.resize();
    });
});

// ── Tab switching ────────────────────────────────────────────────────────────

window.switchTab = function switchTab(tab) {
    ['pool', 'reports', 'analysis'].forEach(t => {
        document.getElementById(`view-${t}`).classList.toggle('hidden', t !== tab);
        const btn = document.getElementById(`tab-${t}`);
        if (t === tab) {
            btn.classList.add('active');
            btn.classList.remove('text-gray-500');
        } else {
            btn.classList.remove('active');
            btn.classList.add('text-gray-500');
        }
    });

    if (tab === 'pool')     { loadPoolStats(); loadPoolEvents(); }
    if (tab === 'reports')  { loadReports(); }
    if (tab === 'analysis') { loadProducts(); }
};

// ══════════════════════════════════════════════════════════════════════════════
// TAB 1: 事件池
// ══════════════════════════════════════════════════════════════════════════════

function initPoolListeners() {
    document.getElementById('filter-category').addEventListener('change', handlePoolFilter);
    document.getElementById('filter-country').addEventListener('input', debounce(handlePoolFilter, 500));
    document.getElementById('filter-severity').addEventListener('change', handlePoolFilter);
    document.getElementById('btn-prev').addEventListener('click', () => changePoolPage(-1));
    document.getElementById('btn-next').addEventListener('click', () => changePoolPage(1));
}

async function loadPoolStats() {
    try {
        const res = await fetch(`${POOL_API}/stats`);
        if (!res.ok) throw new Error(`HTTP_${res.status}`);
        const data = await res.json();

        document.getElementById('metric-active').textContent = data.active_events ?? 0;
        document.getElementById('metric-total').textContent  = data.total_events ?? 0;
        document.getElementById('stat-categories').textContent = Object.keys(data.by_category || {}).length;
        document.getElementById('stat-countries').textContent  = Object.keys(data.by_country   || {}).length;

        populatePoolCategoryFilter(data);
        hidePoolError();

        // 渲染 ECharts 图表
        renderSeverityChart(data.by_severity || {});
        renderCategoryChart(data.by_category || {});

    } catch (err) {
        console.error('Pool stats failed:', err);
        showPoolError('无法加载事件池统计数据，请检查 API 是否可用。');
    }
}

async function refreshPoolStats() {
    try {
        const res = await fetch(`${POOL_API}/stats`);
        if (!res.ok) return;
        const data = await res.json();
        document.getElementById('metric-active').textContent = data.active_events ?? 0;
        document.getElementById('metric-total').textContent  = data.total_events ?? 0;
        // 静默刷新图表
        if (data.by_severity) renderSeverityChart(data.by_severity);
        if (data.by_category) renderCategoryChart(data.by_category);
    } catch (_) {}
}

function populatePoolCategoryFilter(stats) {
    const sel = document.getElementById('filter-category');
    sel.innerHTML = '<option value="">全部类型</option>';
    Object.keys(stats.by_category || {}).forEach(cat => {
        if (cat && cat !== 'null') {
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat.toUpperCase();
            sel.appendChild(opt);
        }
    });
}

async function loadPoolEvents() {
    showLoading(true, '正在同步事件池');
    try {
        const params = new URLSearchParams({
            page:        poolState.pagination.currentPage,
            limit:       poolState.pagination.pageSize,
            active_only: 'true',
        });
        if (poolState.filters.category) params.append('category', poolState.filters.category);
        if (poolState.filters.country)  params.append('country',  poolState.filters.country);
        if (poolState.filters.severity) params.append('severity', poolState.filters.severity);

        const res = await fetch(`${POOL_API}?${params}`);
        if (!res.ok) throw new Error(`HTTP_${res.status}`);
        const data = await res.json();

        poolState.pagination.totalPages = data.pages || 1;
        renderPoolEvents(data.data || []);
        updatePoolPagination();
        hidePoolError();
    } catch (err) {
        console.error('Pool events failed:', err);
        renderPoolEmpty();
        showPoolError('无法加载事件列表，请检查 API 可用性。');
    } finally {
        showLoading(false);
    }
}

function renderPoolEvents(events) {
    const tbody   = document.getElementById('event-tbody');
    const countEl = document.getElementById('event-count');
    countEl.textContent = `${events.length} 个事件`;

    if (!events.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="py-12 text-center text-gray-400 font-mono text-xs uppercase tracking-widest">暂无事件</td></tr>';
        return;
    }

    tbody.innerHTML = events.map(ev => {
        const sev   = (ev.severity || 'unknown').toLowerCase();
        const cls   = SEV_COLOR_CARD[sev] || 'bg-gray-300 text-gray-700';
        return `
        <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
            <td class="py-4 px-5 font-mono text-[11px] text-gray-500 font-semibold">${ev.event_id}-${ev.sub_id}</td>
            <td class="py-4 px-5 font-bold text-black text-sm">
                <div class="max-w-sm overflow-hidden text-ellipsis whitespace-nowrap">${escapeHtml(ev.title)}</div>
            </td>
            <td class="py-4 px-5 font-mono text-[11px] text-gray-600 uppercase tracking-wider">
                ${escapeHtml(ev.country || ev.continent || 'N/A')}
            </td>
            <td class="py-4 px-5 font-mono text-[11px] text-gray-600 uppercase">
                ${escapeHtml(ev.category_name || ev.category || 'N/A')}
            </td>
            <td class="py-4 px-5 text-right">
                <span class="inline-block px-2.5 py-0.5 ${cls} font-mono font-bold text-[10px] tracking-widest uppercase">${sev.toUpperCase()}</span>
            </td>
        </tr>`;
    }).join('');
}

function renderPoolEmpty() {
    document.getElementById('event-tbody').innerHTML =
        '<tr><td colspan="5" class="py-12 text-center text-gray-400 font-mono text-xs uppercase tracking-widest">暂无事件</td></tr>';
}

function updatePoolPagination() {
    const { currentPage, totalPages } = poolState.pagination;
    document.getElementById('pagination-info').textContent = `第 ${currentPage} / ${totalPages} 页`;
    document.getElementById('btn-prev').disabled = currentPage === 1;
    document.getElementById('btn-next').disabled = currentPage >= totalPages;
}

function changePoolPage(delta) {
    const next = poolState.pagination.currentPage + delta;
    if (next >= 1 && next <= poolState.pagination.totalPages) {
        poolState.pagination.currentPage = next;
        loadPoolEvents();
    }
}

function handlePoolFilter() {
    poolState.filters.category = document.getElementById('filter-category').value;
    poolState.filters.country  = document.getElementById('filter-country').value;
    poolState.filters.severity = document.getElementById('filter-severity').value;
    poolState.pagination.currentPage = 1;
    loadPoolEvents();
}

function showPoolError(msg) {
    document.getElementById('error-text').textContent = msg;
    document.getElementById('error-notice').classList.remove('hidden');
}
function hidePoolError() {
    document.getElementById('error-notice').classList.add('hidden');
}

// ══════════════════════════════════════════════════════════════════════════════
// ECharts — 事件池侧栏图表
// ══════════════════════════════════════════════════════════════════════════════

function renderSeverityChart(bySeverity) {
    const el = document.getElementById('chart-severity');
    if (!el || !window.echarts) return;

    if (!chartSeverity) chartSeverity = echarts.init(el);

    const entries = Object.entries(bySeverity).filter(([, v]) => v > 0);
    if (!entries.length) { chartSeverity.clear(); return; }

    const data = entries.map(([k, v]) => ({
        value: v,
        name:  k.toUpperCase(),
        itemStyle: { color: SEV_COLOR[k.toLowerCase()] || '#cbd5e1' },
    }));

    chartSeverity.setOption({
        animation: true,
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c} 个 ({d}%)',
            textStyle: { fontFamily: MONO, fontSize: 11 },
        },
        legend: {
            bottom: 0,
            textStyle: { fontFamily: MONO, fontSize: 9, color: '#6b7280' },
            itemWidth: 10, itemHeight: 10, itemGap: 8,
        },
        series: [{
            type: 'pie',
            radius: ['38%', '66%'],
            center: ['50%', '44%'],
            data,
            label: { show: false },
            emphasis: {
                label: { show: true, fontSize: 11, fontFamily: MONO, fontWeight: '700' },
                itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.15)' },
            },
        }],
    });
}

function renderCategoryChart(byCategory) {
    const el = document.getElementById('chart-category');
    if (!el || !window.echarts) return;

    if (!chartCategory) chartCategory = echarts.init(el);

    const entries = Object.entries(byCategory)
        .filter(([k]) => k && k !== 'null')
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6);

    if (!entries.length) { chartCategory.clear(); return; }

    chartCategory.setOption({
        animation: true,
        tooltip: { trigger: 'axis', textStyle: { fontFamily: MONO, fontSize: 11 } },
        grid: { left: 4, right: 28, top: 4, bottom: 4, containLabel: true },
        xAxis: {
            type: 'value',
            axisLabel: { fontFamily: MONO, fontSize: 8, color: '#9ca3af' },
            splitLine: { lineStyle: { color: '#f1f5f9' } },
            axisLine: { show: false }, axisTick: { show: false },
        },
        yAxis: {
            type: 'category',
            data: entries.map(([k]) => k.length > 14 ? k.slice(0, 14) + '…' : k),
            axisLabel: { fontFamily: MONO, fontSize: 8, color: '#6b7280' },
            axisTick: { show: false }, axisLine: { show: false },
            inverse: true,
        },
        series: [{
            type: 'bar',
            data: entries.map(([, v]) => v),
            itemStyle: { color: '#111' },
            barMaxWidth: 12,
            label: {
                show: true, position: 'right',
                fontFamily: MONO, fontSize: 8, color: '#9ca3af',
                formatter: '{c}',
            },
        }],
    });
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 2: AI报告
// ══════════════════════════════════════════════════════════════════════════════

async function loadReports() {
    if (reportsState.loading) return;
    reportsState.loading = true;
    showLoading(true, '正在加载报告');
    try {
        const res = await fetch(`${PUBLIC_API}/reports?page=${reportsState.page}&limit=20`);
        if (!res.ok) throw new Error(`HTTP_${res.status}`);
        const data = await res.json();
        reportsState.pages = data.pages || 1;
        renderReportList(data.data || []);
    } catch (err) {
        console.error('Reports load failed:', err);
    } finally {
        reportsState.loading = false;
        showLoading(false);
    }
}

function renderReportList(reports) {
    const list   = document.getElementById('report-list');
    const noData = document.getElementById('report-no-data');

    if (!reports.length) {
        list.innerHTML = '';
        noData.classList.remove('hidden');
        return;
    }
    noData.classList.add('hidden');

    list.innerHTML = reports.map(r => {
        const dateStr  = r.report_date || '--';
        const title    = escapeHtml(r.report_title || '灾害日报 ' + dateStr);
        const evCount  = r.event_count ?? 0;
        const pubAt    = r.published_at ? fmtDatetime(r.published_at) : '--';
        return `
        <div class="tech-card p-5 cursor-pointer fade-in-up" onclick="loadReportDetail('${dateStr}')">
            <div class="font-mono text-[10px] text-gray-400 uppercase tracking-widest mb-1">${dateStr}</div>
            <div class="font-semibold text-sm leading-snug mb-3 line-clamp-2">${title}</div>
            <div class="flex items-center justify-between font-mono text-[10px] text-gray-500">
                <span>${evCount} 个事件</span>
                <span class="text-gray-300">${pubAt}</span>
            </div>
        </div>`;
    }).join('');
}

async function loadReportDetail(date) {
    showLoading(true, '正在加载报告');
    try {
        const res = await fetch(`${PUBLIC_API}/reports/${date}`);
        if (!res.ok) throw new Error(`HTTP_${res.status}`);
        const r = await res.json();
        renderReportDetail(r);
    } catch (err) {
        console.error('Report detail failed:', err);
    } finally {
        showLoading(false);
    }
}

function renderReportDetail(r) {
    document.getElementById('report-detail-empty').classList.add('hidden');
    document.getElementById('report-detail-content').classList.remove('hidden');

    document.getElementById('rd-date').textContent        = r.report_date || '--';
    document.getElementById('rd-title').textContent       = r.report_title || '灾害日报';
    document.getElementById('rd-event-count').textContent = r.event_count ?? '--';

    const genSecs = r.generation_time_seconds;
    document.getElementById('rd-gen-time').textContent = genSecs
        ? `生成耗时 ${genSecs.toFixed(1)}s` : '--';

    // ECharts 统计图表
    const statsEl = document.getElementById('rd-stats');
    if (r.category_stats || r.severity_stats || r.country_stats) {
        statsEl.classList.remove('hidden');
        // 在 DOM 可见后再初始化/更新图表
        requestAnimationFrame(() => {
            renderReportBarChart('chart-report-cat', chartReportCat,
                (c) => { chartReportCat = c; }, r.category_stats, '#111');
            renderReportBarChart('chart-report-sev', chartReportSev,
                (c) => { chartReportSev = c; }, r.severity_stats, null, true);
            renderReportBarChart('chart-report-cou', chartReportCou,
                (c) => { chartReportCou = c; }, r.country_stats, '#475569');
        });
    } else {
        statsEl.classList.add('hidden');
    }

    // 报告正文 — 优先用 marked.js，回退到内置解析
    const bodyEl = document.getElementById('rd-body');
    if (window.marked) {
        bodyEl.innerHTML = marked.parse(r.report_content || '');
    } else {
        bodyEl.innerHTML = markdownToHtmlFallback(r.report_content || '');
    }
}

/**
 * 渲染报告统计横向条形图
 * @param {string}   elId       - DOM 元素 ID
 * @param {object}   instance   - 当前 ECharts 实例（可为 null）
 * @param {function} setInst    - 保存实例的回调 fn(instance)
 * @param {object}   statsObj   - { key: count, ... }
 * @param {string}   color      - 固定颜色（null = 按严重程度映射）
 * @param {boolean}  isSeverity - 是否按 severity 颜色映射
 */
function renderReportBarChart(elId, instance, setInst, statsObj, color, isSeverity = false) {
    const el = document.getElementById(elId);
    if (!el || !window.echarts) return;

    if (!instance) {
        instance = echarts.init(el);
        setInst(instance);
    }

    const entries = Object.entries(statsObj || {})
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

    if (!entries.length) { instance.clear(); return; }

    instance.setOption({
        animation: true,
        tooltip: { trigger: 'axis', textStyle: { fontFamily: MONO, fontSize: 10 } },
        grid: { left: 4, right: 28, top: 4, bottom: 4, containLabel: true },
        xAxis: {
            type: 'value',
            axisLabel: { fontFamily: MONO, fontSize: 8, color: '#9ca3af' },
            splitLine: { lineStyle: { color: '#f1f5f9' } },
            axisLine: { show: false }, axisTick: { show: false },
        },
        yAxis: {
            type: 'category',
            data: entries.map(([k]) => k.length > 12 ? k.slice(0, 12) + '…' : k),
            axisLabel: { fontFamily: MONO, fontSize: 8, color: '#6b7280' },
            axisTick: { show: false }, axisLine: { show: false },
            inverse: true,
        },
        series: [{
            type: 'bar',
            data: entries.map(([k, v]) => ({
                value: v,
                itemStyle: {
                    color: isSeverity
                        ? (SEV_COLOR[k.toLowerCase()] || '#cbd5e1')
                        : (color || '#111'),
                },
            })),
            barMaxWidth: 14,
            label: {
                show: true, position: 'right',
                fontFamily: MONO, fontSize: 8, color: '#9ca3af',
            },
        }],
    });
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 3: AI分析
// ══════════════════════════════════════════════════════════════════════════════

async function loadProducts() {
    if (analysisState.loading) return;
    analysisState.loading = true;
    showLoading(true, '正在加载分析成品');
    try {
        const res = await fetch(`${PUBLIC_API}/products?page=${analysisState.page}&limit=${analysisState.limit}`);
        if (!res.ok) throw new Error(`HTTP_${res.status}`);
        const data = await res.json();
        analysisState.pages = data.pages || 1;
        renderProductList(data.data || []);
        updateProdPagination();
    } catch (err) {
        console.error('Products load failed:', err);
    } finally {
        analysisState.loading = false;
        showLoading(false);
    }
}

function renderProductList(products) {
    const list   = document.getElementById('product-list');
    const noData = document.getElementById('product-no-data');

    if (!products.length) {
        list.innerHTML = '';
        noData.classList.remove('hidden');
        return;
    }
    noData.classList.add('hidden');

    const SEV_BORDER = {
        extreme: 'border-red-500 text-red-600',
        high:    'border-orange-400 text-orange-500',
        medium:  'border-yellow-400 text-yellow-600',
        low:     'border-gray-300 text-gray-500',
    };

    list.innerHTML = products.map(p => {
        const sev     = (p.severity || '').toLowerCase();
        const sevCls  = SEV_BORDER[sev] || 'border-gray-200 text-gray-400';
        const hasImg  = p.has_pre_image || p.has_post_image;
        const cat     = p.event_category || 'N/A';
        const country = p.event_country  || '';
        const evDate  = p.event_date ? fmtDate(p.event_date) : '--';

        return `
        <div class="tech-card p-4 cursor-pointer fade-in-up" onclick="loadProductDetail('${p.uuid}')">
            <div class="flex items-start justify-between mb-2">
                <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="font-mono text-[9px] font-bold tracking-widest uppercase px-1.5 py-0.5 border ${sevCls}">${sev.toUpperCase() || 'N/A'}</span>
                    <span class="font-mono text-[9px] font-bold tracking-widest uppercase px-1.5 py-0.5 border border-gray-200 text-gray-500">${escapeHtml(cat)}</span>
                </div>
                ${hasImg ? '<span class="font-mono text-[9px] text-green-600 font-bold">▸ 含影像</span>' : ''}
            </div>
            <div class="font-semibold text-sm leading-snug mb-2 line-clamp-2">${escapeHtml(p.event_title || '未命名')}</div>
            <div class="flex justify-between font-mono text-[10px] text-gray-400">
                <span>${escapeHtml(country)}</span>
                <span>${evDate}</span>
            </div>
            ${p.summary_generated ? '<div class="mt-2 font-mono text-[9px] text-blue-500 font-bold">✦ AI摘要</div>' : ''}
        </div>`;
    }).join('');
}

function updateProdPagination() {
    const { page, pages } = analysisState;
    document.getElementById('prod-page-info').textContent = `${page} / ${pages}`;

    const prevBtn = document.getElementById('prod-prev');
    const nextBtn = document.getElementById('prod-next');
    prevBtn.disabled = page === 1;
    nextBtn.disabled = page >= pages;

    prevBtn.onclick = () => { if (analysisState.page > 1) { analysisState.page--; loadProducts(); } };
    nextBtn.onclick = () => { if (analysisState.page < analysisState.pages) { analysisState.page++; loadProducts(); } };
}

async function loadProductDetail(uuid) {
    showLoading(true, '正在加载详情');
    try {
        const res = await fetch(`${PUBLIC_API}/products/${uuid}`);
        if (!res.ok) throw new Error(`HTTP_${res.status}`);
        const p = await res.json();
        renderProductDetail(p);
    } catch (err) {
        console.error('Product detail failed:', err);
    } finally {
        showLoading(false);
    }
}

function renderProductDetail(p) {
    document.getElementById('product-detail-empty').classList.add('hidden');
    document.getElementById('product-detail-content').classList.remove('hidden');

    const sev    = (p.severity || '').toLowerCase();
    const sevCls = SEV_STYLE[sev] || 'border-gray-200 bg-gray-50 text-gray-400';

    document.getElementById('pd-category-badge').textContent  = p.event_category || 'N/A';
    document.getElementById('pd-severity-badge').textContent  = sev.toUpperCase() || 'N/A';
    document.getElementById('pd-severity-badge').className    =
        `font-mono text-[9px] font-bold tracking-widest uppercase px-2 py-0.5 border ${sevCls}`;

    document.getElementById('pd-title').textContent    = p.event_title   || '未命名';
    document.getElementById('pd-location').textContent =
        [p.address, p.event_country].filter(Boolean).join(' · ') || '--';

    const srcLink = document.getElementById('pd-source-link');
    if (p.source_url) {
        srcLink.href = p.source_url;
        srcLink.style.display = '';
    } else {
        srcLink.style.display = 'none';
    }

    const parts = [];
    if (p.event_date)  parts.push(`事件时间: ${fmtDate(p.event_date)}`);
    if (p.longitude)   parts.push(`${p.latitude?.toFixed(4)}°N ${p.longitude?.toFixed(4)}°E`);
    if (p.created_at)  parts.push(`分析时间: ${fmtDatetime(p.created_at)}`);
    document.getElementById('pd-meta').textContent = parts.join('  ·  ') || '--';

    renderSatImg('pd-pre-wrap',  p.uuid, 'pre',  p.has_pre_image);
    renderSatImg('pd-post-wrap', p.uuid, 'post', p.has_post_image);
    document.getElementById('pd-pre-date').textContent  = p.pre_image_date  ? fmtDate(p.pre_image_date)  : '--';
    document.getElementById('pd-post-date').textContent = p.post_image_date ? fmtDate(p.post_image_date) : '--';

    renderInference(p.inference_result);

    const summaryCard = document.getElementById('pd-summary-card');
    const summaryText = document.getElementById('pd-summary-text');
    if (p.summary_generated && p.summary) {
        summaryCard.classList.remove('hidden');
        summaryText.textContent = p.summary;
    } else {
        summaryCard.classList.add('hidden');
    }

    renderRawData(p);
    lucide.createIcons();
}

// ── 卫星影像渲染（修复 onerror 转义 bug）─────────────────────────────────────

/**
 * 卫星图像加载失败回调 — 必须是全局函数，onerror 属性才能调用
 */
window.onSatImgError = function onSatImgError(img) {
    img.parentNode.innerHTML =
        '<div class="satellite-img-placeholder">' +
        '<span class="font-mono text-[10px] text-gray-400">加载失败</span>' +
        '</div>';
};

function renderSatImg(wrapperId, uuid, type, hasImage) {
    const wrap = document.getElementById(wrapperId);
    if (hasImage) {
        const imgUrl = `${PUBLIC_API}/image/${uuid}/${type}`;
        // 使用全局函数而非内联字符串拼接，避免引号转义问题
        const img = document.createElement('img');
        img.src     = imgUrl;
        img.alt     = type === 'pre' ? '灾前卫星影像' : '灾后卫星影像';
        img.className = 'satellite-img';
        img.loading = 'lazy';
        img.onerror = function() { window.onSatImgError(this); };
        wrap.innerHTML = '';
        wrap.appendChild(img);
    } else {
        wrap.innerHTML =
            '<div class="satellite-img-placeholder">' +
            '<span class="font-mono text-[10px] text-gray-400">无图像</span>' +
            '</div>';
    }
}

function renderInference(inferenceResult) {
    const container = document.getElementById('pd-inference');
    if (!inferenceResult || !Object.keys(inferenceResult).length) {
        container.innerHTML = '<span class="font-mono text-[10px] text-gray-300">暂无推理数据</span>';
        return;
    }

    const rows = [];
    for (const [taskName, taskObj] of Object.entries(inferenceResult)) {
        const result = taskObj?.result ?? taskObj;
        rows.push(`
        <div class="border border-gray-100 p-3">
            <div class="font-mono text-[9px] font-bold text-gray-400 uppercase tracking-widest mb-2">
                ${escapeHtml(taskName.replace(/_/g, ' '))}
            </div>
            ${renderResultKV(result)}
        </div>`);
    }
    container.innerHTML = rows.join('');
}

function renderResultKV(result) {
    if (result === null || result === undefined)
        return '<span class="font-mono text-[10px] text-gray-300">null</span>';
    if (typeof result !== 'object')
        return `<span class="font-mono text-xs font-semibold">${escapeHtml(String(result))}</span>`;

    return Object.entries(result).map(([k, v]) => {
        const label = k.replace(/_/g, ' ').toUpperCase();
        const val   = typeof v === 'object' ? JSON.stringify(v) : String(v ?? '--');
        let valClass = 'font-mono text-xs font-bold text-black';
        const vLow = val.toLowerCase();
        if (['high', 'severe', 'extreme', 'critical', 'major'].some(w => vLow.includes(w)))
            valClass = 'font-mono text-xs font-bold text-red-600';
        else if (['medium', 'moderate'].some(w => vLow.includes(w)))
            valClass = 'font-mono text-xs font-bold text-orange-500';

        return `
        <div class="flex justify-between items-start gap-3 py-1 border-b border-gray-50 last:border-0">
            <span class="font-mono text-[10px] text-gray-500 uppercase tracking-wider shrink-0">${escapeHtml(label)}</span>
            <span class="${valClass} text-right break-all">${escapeHtml(val)}</span>
        </div>`;
    }).join('');
}

function renderRawData(p) {
    const container = document.getElementById('pd-raw-data');
    const fields = [
        ['UUID',        p.uuid],
        ['事件时间',    p.event_date  ? fmtDate(p.event_date)  : null],
        ['国家/地区',   p.event_country],
        ['事件类别',    p.event_category],
        ['严重程度',    p.severity],
        ['纬度',        p.latitude  != null ? p.latitude.toFixed(5)  : null],
        ['经度',        p.longitude != null ? p.longitude.toFixed(5) : null],
        ['地址',        p.address],
        ['原始来源',    p.source_url],
        ['分析时间',    p.created_at ? fmtDatetime(p.created_at) : null],
    ].filter(([, v]) => v != null && v !== '');

    container.innerHTML = fields.map(([label, val]) => {
        const isUrl = label === '原始来源';
        const valHtml = isUrl
            ? `<a href="${escapeHtml(val)}" target="_blank" rel="noopener noreferrer"
                  class="text-blue-600 underline break-all hover:text-black transition-colors">
                  ${escapeHtml(val)}
               </a>`
            : `<span class="text-gray-800 break-all">${escapeHtml(String(val))}</span>`;
        return `
        <div class="flex gap-3 py-1.5 border-b border-gray-50 last:border-0">
            <span class="text-gray-400 uppercase tracking-widest shrink-0 w-20">${label}</span>
            ${valHtml}
        </div>`;
    }).join('');
}

// ══════════════════════════════════════════════════════════════════════════════
// Markdown 回退解析（仅在 marked.js 不可用时使用）
// ══════════════════════════════════════════════════════════════════════════════

function markdownToHtmlFallback(md) {
    if (!md) return '';
    return md
        .replace(/^---+$/gm, '<hr>')
        .replace(/^### (.+)$/gm, (_, t) => `<h3>${escapeHtml(t)}</h3>`)
        .replace(/^## (.+)$/gm,  (_, t) => `<h2>${escapeHtml(t)}</h2>`)
        .replace(/^# (.+)$/gm,   (_, t) => `<h1>${escapeHtml(t)}</h1>`)
        .replace(/\*\*(.+?)\*\*/g, (_, t) => `<strong>${escapeHtml(t)}</strong>`)
        .replace(/^[*-] (.+)$/gm, (_, t) => `<li>${escapeHtml(t)}</li>`)
        .replace(/^\d+\. (.+)$/gm, (_, t) => `<li>${escapeHtml(t)}</li>`)
        .replace(/(<li>[\s\S]*?<\/li>)\n?(?!<li>)/g, block => `<ul>${block}</ul>`)
        .replace(/\n\n+/g, '\n')
        .replace(/^(?![<])(.+)$/gm, (_, t) => `<p>${escapeHtml(t)}</p>`);
}

// ══════════════════════════════════════════════════════════════════════════════
// 共享工具函数
// ══════════════════════════════════════════════════════════════════════════════

function showLoading(show, text = '正在同步') {
    const el = document.getElementById('loading');
    if (show) {
        document.getElementById('loading-text').textContent = text;
        el.classList.remove('hidden');
    } else {
        el.classList.add('hidden');
    }
}

function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = String(text ?? '');
    return d.innerHTML;
}

/** 时间戳 → YYYY-MM-DD */
function fmtDate(ts) {
    if (!ts) return '--';
    const ms = ts > 1e10 ? ts : ts * 1000;
    return new Date(ms).toISOString().slice(0, 10);
}

/** 时间戳 → YYYY-MM-DD HH:mm */
function fmtDatetime(ts) {
    if (!ts) return '--';
    const ms = ts > 1e10 ? ts : ts * 1000;
    return new Date(ms).toISOString().slice(0, 16).replace('T', ' ');
}

function debounce(fn, wait) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), wait);
    };
}
