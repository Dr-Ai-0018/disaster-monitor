import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { workflowApi } from '../lib/api'
import { useToast } from '../components/Toast'
import { useConfirm } from '../components/ConfirmDialog'
import type { WorkflowItem, WorkflowOverview, BatchActionResponse } from '../types'
import { formatDate } from '../lib/utils'
import {
  RefreshCw, Eye, CheckCircle, XCircle, Zap, FileText,
  AlertCircle, Loader2, X,
} from 'lucide-react'
import { cn } from '../lib/utils'

const STAGES = [
  { key: 'event_pool',          label: '全部事件',  short: '事件' },
  { key: 'imagery_pool',        label: '影像准备',  short: '影像' },
  { key: 'image_review_pool',   label: '待审核',    short: '审核' },
  { key: 'inference_pool',      label: '待分析',    short: '分析' },
  { key: 'summary_report_pool', label: '待确认摘要', short: '摘要' },
]

const STAGE_EMPTY: Record<string, string> = {
  event_pool:          '暂无新进事件',
  imagery_pool:        '暂无正在准备影像的事件',
  image_review_pool:   '暂无待审核影像',
  inference_pool:      '暂无待触发分析的事件',
  summary_report_pool: '暂无待确认摘要的事件',
}

const SEVERITY_LABEL: Record<string, string> = {
  red: '极高', orange: '高', green: '低',
}
const SEVERITY_CLASS: Record<string, string> = {
  red:    'bg-red-50 text-red-700 border-red-200',
  orange: 'bg-amber-50 text-amber-700 border-amber-200',
  green:  'bg-green-50 text-green-700 border-green-200',
}

const STATUS_CLASS: Record<string, string> = {
  '待影像':        'bg-slate-100 text-slate-600',
  '待质检归档':    'bg-blue-50 text-blue-700',
  '待影像审核':    'bg-amber-50 text-amber-700',
  '影像已打回':    'bg-red-50 text-red-700',
  '待触发推理':    'bg-amber-50 text-amber-700',
  '待执行推理':    'bg-blue-50 text-blue-700',
  '推理中':        'bg-blue-50 text-blue-700',
  '推理需处理':    'bg-red-50 text-red-700',
  '待落成品':      'bg-blue-50 text-blue-700',
  '待生成摘要':    'bg-amber-50 text-amber-700',
  '待摘要审核':    'bg-amber-50 text-amber-700',
  '摘要已打回':    'bg-red-50 text-red-700',
  '待推入日报':    'bg-amber-50 text-amber-700',
  '可生成日报':    'bg-green-50 text-green-700',
  '日报草稿已生成':'bg-green-50 text-green-700',
  '日报已发布':    'bg-green-100 text-green-800',
}

const STATUS_DISPLAY: Record<string, string> = {
  '待触发推理': '待触发分析',
  '待执行推理': '分析排队中',
  '推理中':     '分析进行中',
  '推理需处理': '分析异常',
  '待落成品':   '成果生成中',
  '待推入日报': '待加入日报',
  '待质检归档': '质检中',
}

function StatusChip({ label }: { label: string }) {
  const cls = STATUS_CLASS[label] ?? 'bg-slate-100 text-slate-600'
  const display = STATUS_DISPLAY[label] ?? label
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {display}
    </span>
  )
}

function BatchResultModal({
  result,
  title,
  onClose,
}: {
  result: BatchActionResponse
  title: string
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 fade-in"
      style={{ background: 'rgba(15,23,42,0.5)' }}
      onClick={onClose}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[70vh] flex flex-col slide-up"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              共 {result.total} 条 · 成功 {result.succeeded} · 失败 {result.failed}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-5 py-3 space-y-1.5">
          {result.results.map(r => (
            <div key={r.uuid} className={`flex items-start gap-2.5 text-xs py-1.5 border-b border-slate-100 last:border-0`}>
              {r.ok
                ? <CheckCircle className="h-3.5 w-3.5 text-green-600 flex-shrink-0 mt-0.5" />
                : <AlertCircle className="h-3.5 w-3.5 text-red-500 flex-shrink-0 mt-0.5" />}
              <span className="font-mono text-slate-400 flex-shrink-0 w-16 truncate">{r.uuid.slice(0, 8)}</span>
              <span className={r.ok ? 'text-slate-600' : 'text-red-600'}>{r.message}</span>
            </div>
          ))}
        </div>
        <div className="px-5 py-3 border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm font-medium text-white bg-blue-700 hover:bg-blue-800 rounded-md transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}

export function Tasks() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  const currentPool = searchParams.get('pool') || 'event_pool'
  const [overview, setOverview] = useState<WorkflowOverview | null>(null)
  const [items, setItems] = useState<WorkflowItem[]>([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchResult, setBatchResult] = useState<{ result: BatchActionResponse; title: string } | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, it] = await Promise.all([
        workflowApi.getOverview(),
        workflowApi.getItems(currentPool, 100),
      ])
      setOverview(ov)
      setItems(it.data)
    } catch {
      toast.error('加载失败', '请检查网络连接后重试')
    } finally {
      setLoading(false)
    }
  }, [currentPool])

  useEffect(() => {
    setSelected(new Set())
    loadData()
  }, [loadData])

  const switchPool = (key: string) => {
    setSearchParams({ pool: key })
    setSelected(new Set())
  }

  const toggleItem = (uuid: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(uuid) ? next.delete(uuid) : next.add(uuid)
      return next
    })
  }

  const toggleAll = () => {
    setSelected(prev => prev.size === items.length ? new Set() : new Set(items.map(i => i.uuid)))
  }

  const runBatch = async (action: string) => {
    const uuids = Array.from(selected)
    if (!uuids.length) return

    const actionLabels: Record<string, string> = {
      approve_image: '批量通过影像审核',
      reject_image: '批量打回影像',
      trigger_inference: '批量触发分析',
      generate_summary: '批量生成摘要',
      approve_summary: '批量通过摘要并加入日报',
      reset_inference: '批量重置分析/摘要',
    }

    const dangerous = ['reject_image', 'reset_inference']
    if (dangerous.includes(action)) {
      const ok = await confirm({
        title: actionLabels[action],
        message: `将对已选 ${uuids.length} 条事件执行此操作，操作不可撤销。确认继续？`,
        confirmText: '确认执行',
        danger: true,
      })
      if (!ok) return
    }

    setActing(true)
    try {
      let result: BatchActionResponse
      const today = new Date().toISOString().split('T')[0]

      switch (action) {
        case 'approve_image':
          result = await workflowApi.batchReviewImage(uuids, true, 'post')
          break
        case 'reject_image':
          result = await workflowApi.batchReviewImage(uuids, false, undefined, '不符合审核要求')
          break
        case 'trigger_inference':
          result = await workflowApi.batchTriggerInference(uuids)
          break
        case 'generate_summary':
          result = await workflowApi.batchGenerateSummary(uuids)
          break
        case 'approve_summary':
          result = await workflowApi.batchApproveSummary(uuids, true, undefined, today)
          break
        case 'reset_inference':
          result = await workflowApi.batchResetInference(uuids)
          break
        default:
          return
      }

      setBatchResult({ result, title: actionLabels[action] ?? '批量操作' })
      setSelected(new Set())
      await loadData()
    } catch (err: any) {
      toast.error('操作失败', err.response?.data?.detail || err.message)
    } finally {
      setActing(false)
    }
  }

  const getCount = (key: string) =>
    overview?.cards.find(c => c.key === key)?.total ?? 0

  const allChecked = items.length > 0 && selected.size === items.length
  const someChecked = selected.size > 0 && selected.size < items.length

  return (
    <Layout>
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-900">事件处理</h1>
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 border border-slate-200 rounded-md px-3 py-1.5 bg-white hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>

        <div className="border-b border-slate-200">
          <nav className="-mb-px flex gap-0 overflow-x-auto">
            {STAGES.map(stage => {
              const count = getCount(stage.key)
              const active = currentPool === stage.key
              return (
                <button
                  key={stage.key}
                  onClick={() => switchPool(stage.key)}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors',
                    active
                      ? 'border-slate-900 text-slate-900'
                      : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                  )}
                >
                  <span className="hidden sm:inline">{stage.label}</span>
                  <span className="sm:hidden">{stage.short}</span>
                  <span className={cn(
                    'text-xs tabular-nums rounded-full px-1.5 py-0.5 leading-none font-semibold min-w-[1.25rem] text-center',
                    active
                      ? 'bg-slate-900 text-white'
                      : count > 0 ? 'bg-slate-200 text-slate-700' : 'bg-slate-100 text-slate-400'
                  )}>
                    {count}
                  </span>
                </button>
              )
            })}
          </nav>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          {selected.size > 0 && (
            <div className="flex items-center justify-between px-4 py-2.5 bg-slate-800 border-b border-slate-700">
              <span className="text-sm font-semibold text-white">
                已选择 {selected.size} 项
              </span>
              <div className="flex items-center gap-2 flex-wrap">
                {currentPool === 'image_review_pool' && (
                  <>
                    <ActionBtn
                      icon={CheckCircle}
                      label="通过审核"
                      variant="success"
                      loading={acting}
                      onClick={() => runBatch('approve_image')}
                    />
                    <ActionBtn
                      icon={XCircle}
                      label="打回"
                      variant="danger"
                      loading={acting}
                      onClick={() => runBatch('reject_image')}
                    />
                  </>
                )}
                {currentPool === 'inference_pool' && (
                  <>
                    <ActionBtn
                      icon={Zap}
                      label="触发分析"
                      variant="primary"
                      loading={acting}
                      onClick={() => runBatch('trigger_inference')}
                    />
                    <ActionBtn
                      icon={RefreshCw}
                      label="重置分析"
                      variant="danger"
                      loading={acting}
                      onClick={() => runBatch('reset_inference')}
                    />
                  </>
                )}
                {currentPool === 'summary_report_pool' && (
                  <>
                    <ActionBtn
                      icon={FileText}
                      label="生成摘要"
                      variant="default"
                      loading={acting}
                      onClick={() => runBatch('generate_summary')}
                    />
                    <ActionBtn
                      icon={CheckCircle}
                      label="加入日报"
                      variant="success"
                      loading={acting}
                      onClick={() => runBatch('approve_summary')}
                    />
                  </>
                )}
              </div>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  <th className="pl-4 pr-2 py-3 text-left w-10">
                    <input
                      type="checkbox"
                      checked={allChecked}
                      ref={el => { if (el) el.indeterminate = someChecked }}
                      onChange={toggleAll}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                  </th>
                  <th className="px-3 py-3 text-left">事件</th>
                  <th className="px-3 py-3 text-left">地区</th>
                  <th className="px-3 py-3 text-left">严重程度</th>
                  <th className="px-3 py-3 text-left">当前状态</th>
                  <th className="px-3 py-3 text-left hidden lg:table-cell">影像</th>
                  <th className="px-3 py-3 text-left hidden xl:table-cell">更新时间</th>
                  <th className="px-3 py-3 text-left w-12"></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  [...Array(5)].map((_, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="pl-4 pr-2 py-3"><div className="h-4 w-4 bg-slate-100 rounded animate-pulse" /></td>
                      <td className="px-3 py-3"><div className="h-4 bg-slate-100 rounded animate-pulse w-48" /></td>
                      <td className="px-3 py-3"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>
                      <td className="px-3 py-3"><div className="h-4 bg-slate-100 rounded animate-pulse w-16" /></td>
                      <td className="px-3 py-3"><div className="h-4 bg-slate-100 rounded animate-pulse w-24" /></td>
                      <td className="px-3 py-3 hidden lg:table-cell"><div className="h-4 bg-slate-100 rounded animate-pulse w-16" /></td>
                      <td className="px-3 py-3 hidden xl:table-cell"><div className="h-4 bg-slate-100 rounded animate-pulse w-28" /></td>
                      <td className="px-3 py-3" />
                    </tr>
                  ))
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={8}>
                      <div className="flex flex-col items-center justify-center py-16 gap-2">
                        <AlertCircle className="h-6 w-6 text-slate-200" />
                        <p className="text-sm text-slate-400">{STAGE_EMPTY[currentPool] ?? '暂无数据'}</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  items.map(item => (
                    <tr
                      key={item.uuid}
                      className={cn(
                        'border-b border-slate-100 hover:bg-slate-50 transition-colors',
                        selected.has(item.uuid) && 'bg-blue-50 hover:bg-blue-50'
                      )}
                    >
                      <td className="pl-4 pr-2 py-3">
                        <input
                          type="checkbox"
                          checked={selected.has(item.uuid)}
                          onChange={() => toggleItem(item.uuid)}
                          className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                        />
                      </td>
                      <td className="px-3 py-3 max-w-xs">
                        <div className="font-medium text-slate-900 truncate" title={item.title ?? ''}>
                          {item.title || <span className="text-slate-400">无标题</span>}
                        </div>
                        <div className="text-xs text-slate-400 font-mono truncate mt-0.5">{item.uuid.slice(0, 12)}…</div>
                      </td>
                      <td className="px-3 py-3 text-slate-600 whitespace-nowrap">
                        {item.country || <span className="text-slate-300">—</span>}
                      </td>
                      <td className="px-3 py-3">
                        {item.severity ? (
                          <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium ${SEVERITY_CLASS[item.severity] ?? 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                            {SEVERITY_LABEL[item.severity] ?? item.severity}
                          </span>
                        ) : <span className="text-slate-300">—</span>}
                      </td>
                      <td className="px-3 py-3">
                        <StatusChip label={item.pool_status} />
                      </td>
                      <td className="px-3 py-3 hidden lg:table-cell">
                        <span className={`text-xs ${item.imagery === '已就绪' ? 'text-green-600' : 'text-slate-400'}`}>
                          {item.imagery}
                        </span>
                      </td>
                      <td className="px-3 py-3 hidden xl:table-cell text-xs text-slate-400 whitespace-nowrap">
                        {formatDate(item.updated_at)}
                      </td>
                      <td className="px-3 py-3">
                        <button
                          onClick={() => navigate(`/item/${item.uuid}`)}
                          className="p-1.5 rounded-md text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                          title="查看详情"
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {!loading && items.length > 0 && (
            <div className="px-4 py-2.5 border-t border-slate-100 text-xs text-slate-400">
              共 {items.length} 条
            </div>
          )}
        </div>
      </div>

      {batchResult && (
        <BatchResultModal
          result={batchResult.result}
          title={batchResult.title}
          onClose={() => setBatchResult(null)}
        />
      )}
    </Layout>
  )
}

function ActionBtn({
  icon: Icon,
  label,
  variant,
  loading,
  onClick,
}: {
  icon: React.ElementType
  label: string
  variant: 'primary' | 'success' | 'danger' | 'default'
  loading: boolean
  onClick: () => void
}) {
  const cls: Record<string, string> = {
    primary: 'bg-blue-600 hover:bg-blue-500 text-white',
    success: 'bg-green-600 hover:bg-green-500 text-white',
    danger:  'bg-red-500 hover:bg-red-400 text-white',
    default: 'bg-slate-700 hover:bg-slate-600 text-white border border-slate-600',
  }
  return (
    <button
      disabled={loading}
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors disabled:opacity-50',
        cls[variant]
      )}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
      {label}
    </button>
  )
}
