import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { workflowApi } from '../lib/api'
import { useToast } from '../components/Toast'
import { useConfirm } from '../components/ConfirmDialog'
import type { WorkflowItemDetail } from '../types'
import { formatDate } from '../lib/utils'
import { cn } from '../lib/utils'
import {
  ArrowLeft, CheckCircle, XCircle, Zap, FileText, RotateCcw,
  AlertCircle, Loader2, MapPin, Calendar, Tag, User, Image,
} from 'lucide-react'

const SEVERITY_LABEL: Record<string, string> = { red: '极高风险', orange: '高风险', green: '一般' }
const SEVERITY_CLASS: Record<string, string> = {
  red:    'bg-red-50 text-red-700 border border-red-200',
  orange: 'bg-amber-50 text-amber-700 border border-amber-200',
  green:  'bg-green-50 text-green-700 border border-green-200',
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
  '日报草稿已生成': 'bg-green-50 text-green-700',
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

function InfoRow({ label, children, mono = false }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex gap-3 py-2.5 border-b border-slate-100 last:border-0">
      <span className="text-xs text-slate-400 w-20 flex-shrink-0 pt-0.5">{label}</span>
      <span className={cn('text-sm text-slate-800 flex-1 min-w-0', mono && 'font-mono text-xs text-slate-500 break-all')}>
        {children}
      </span>
    </div>
  )
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

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50">
        <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      </div>
      <div className="px-5 py-1">{children}</div>
    </div>
  )
}

function ActionBtn({
  icon: Icon,
  label,
  variant = 'default',
  loading = false,
  disabled = false,
  fullWidth = false,
  onClick,
}: {
  icon: React.ElementType
  label: string
  variant?: 'primary' | 'success' | 'danger' | 'default' | 'ghost'
  loading?: boolean
  disabled?: boolean
  fullWidth?: boolean
  onClick: () => void
}) {
  const cls: Record<string, string> = {
    primary: 'bg-blue-700 hover:bg-blue-800 text-white border-transparent',
    success: 'bg-green-700 hover:bg-green-800 text-white border-transparent',
    danger:  'bg-red-600 hover:bg-red-700 text-white border-transparent',
    default: 'bg-white hover:bg-slate-50 text-slate-700 border-slate-300',
    ghost:   'bg-transparent hover:bg-slate-100 text-slate-600 border-transparent',
  }
  return (
    <button
      disabled={loading || disabled}
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium border transition-colors disabled:opacity-50',
        fullWidth && 'w-full justify-center',
        cls[variant]
      )}
    >
      {loading
        ? <Loader2 className="h-4 w-4 animate-spin" />
        : <Icon className="h-4 w-4" />}
      {label}
    </button>
  )
}

export function ItemDetail() {
  const { uuid } = useParams<{ uuid: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  const [item, setItem] = useState<WorkflowItemDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectModal, setShowRejectModal] = useState<'image' | 'summary' | null>(null)

  useEffect(() => {
    if (uuid) loadItem()
  }, [uuid])

  const loadItem = async () => {
    if (!uuid) return
    setLoading(true)
    try {
      const data = await workflowApi.getItemDetail(uuid)
      setItem(data)
    } catch (err: any) {
      toast.error('加载失败', err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setActing(key)
    try {
      await fn()
      await loadItem()
    } catch (err: any) {
      toast.error('操作失败', err.response?.data?.detail || err.message)
    } finally {
      setActing(null)
    }
  }

  const handleApproveImage = () =>
    run('approve_image', async () => {
      await workflowApi.reviewImage(uuid!, true, 'post')
      toast.success('影像审核通过')
    })

  const handleRejectImage = async () => {
    if (!rejectReason.trim()) return
    setShowRejectModal(null)
    await run('reject_image', async () => {
      await workflowApi.reviewImage(uuid!, false, undefined, rejectReason.trim())
      toast.success('影像已打回')
      setRejectReason('')
    })
  }

  const handleTriggerInference = () =>
    run('trigger_inference', async () => {
      await workflowApi.triggerInference(uuid!)
      toast.success('分析已触发')
    })

  const handleResetInference = async () => {
    const ok = await confirm({
      title: '重置分析与摘要',
      message: '将清空当前事件的分析成果和摘要内容，操作不可撤销，确认继续？',
      confirmText: '确认重置',
      danger: true,
    })
    if (!ok) return
    run('reset_inference', async () => {
      await workflowApi.resetInference(uuid!)
      toast.success('分析与摘要已重置')
    })
  }

  const handleGenerateSummary = () =>
    run('generate_summary', async () => {
      await workflowApi.generateSummary(uuid!)
      toast.success('摘要生成完成')
    })

  const handleApproveSummary = () =>
    run('approve_summary', async () => {
      const today = new Date().toISOString().split('T')[0]
      await workflowApi.approveSummary(uuid!, true, undefined, today)
      toast.success('摘要已通过，已准入日报')
    })

  const handleRejectSummary = async () => {
    if (!rejectReason.trim()) return
    setShowRejectModal(null)
    await run('reject_summary', async () => {
      await workflowApi.approveSummary(uuid!, false, rejectReason.trim())
      toast.success('摘要已打回')
      setRejectReason('')
    })
  }

  if (loading) {
    return (
      <Layout>
        <div className="flex flex-col gap-5 animate-pulse">
          <div className="h-5 w-24 bg-slate-200 rounded" />
          <div className="grid gap-5 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-5">
              <div className="h-48 bg-white rounded-lg border border-slate-200" />
              <div className="h-32 bg-white rounded-lg border border-slate-200" />
            </div>
            <div className="h-64 bg-white rounded-lg border border-slate-200" />
          </div>
        </div>
      </Layout>
    )
  }

  if (!item) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <AlertCircle className="h-8 w-8 text-slate-300" />
          <p className="text-slate-500">事件不存在</p>
          <button onClick={() => navigate(-1)} className="text-sm text-blue-700 hover:underline">返回</button>
        </div>
      </Layout>
    )
  }

  const isImageReview = item.pool === 'image_review_pool'
  const isInference  = item.pool === 'inference_pool'
  const isSummary    = item.pool === 'summary_report_pool'

  const POOL_LABEL: Record<string, string> = {
    event_pool:          '事件接入',
    imagery_pool:        '影像准备',
    image_review_pool:   '影像审核',
    inference_pool:      '待分析',
    summary_report_pool: '待确认摘要',
  }

  return (
    <Layout>
      <div className="space-y-5">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            返回
          </button>
          <span className="text-slate-300">/</span>
          <span className="text-sm text-slate-500">事件处理</span>
          <span className="text-slate-300">/</span>
          <span className="text-sm text-slate-700 font-medium truncate max-w-xs">{item.title || item.uuid.slice(0, 12)}</span>
        </div>

        <div className="flex items-start gap-3 flex-wrap">
          <h1 className="text-xl font-bold text-slate-900 flex-1 min-w-0 leading-snug">
            {item.title || <span className="text-slate-400">无标题事件</span>}
          </h1>
          <div className="flex items-center gap-2 flex-shrink-0">
            {item.severity && (
              <span className={`px-2.5 py-1 rounded text-xs font-semibold ${SEVERITY_CLASS[item.severity] ?? 'bg-slate-100 text-slate-600'}`}>
                {SEVERITY_LABEL[item.severity] ?? item.severity}
              </span>
            )}
            <span className={`px-2.5 py-1 rounded text-xs font-semibold ${STATUS_CLASS[item.pool_status] ?? 'bg-slate-100 text-slate-600'}`}>
              {item.pool_status}
            </span>
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-5">
            <SectionCard title="基本信息">
              <InfoRow label="事件 ID" mono>{item.uuid}</InfoRow>
              {item.category && <InfoRow label="类别">{item.category}</InfoRow>}
              {item.country  && <InfoRow label="地区"><span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-slate-400" />{item.country}</span></InfoRow>}
              {item.address  && <InfoRow label="地址">{item.address}</InfoRow>}
              {(item.latitude != null && item.longitude != null) && (
                <InfoRow label="坐标">
                  {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                </InfoRow>
              )}
              {item.event_date && (
                <InfoRow label="事件时间">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5 text-slate-400" />
                    {formatDate(item.event_date)}
                  </span>
                </InfoRow>
              )}
            </SectionCard>

            <SectionCard title="处理进度">
              <InfoRow label="当前阶段">
                <span className="font-medium text-slate-700">{POOL_LABEL[item.pool] ?? item.pool}</span>
              </InfoRow>
              <InfoRow label="状态"><StatusChip label={item.pool_status} /></InfoRow>
              <InfoRow label="影像">
                <span className={item.imagery === '已就绪' ? 'text-green-600 font-medium' : 'text-slate-500'}>
                  {item.imagery}
                </span>
              </InfoRow>
              <InfoRow label="质检">
                <StatusChip label={item.quality} />
              </InfoRow>
              {item.inference && item.inference !== '待创建' && (
                <InfoRow label="分析任务">
                  <span className={item.inference === 'done' || item.inference === 'completed' ? 'text-green-700' : item.inference === 'failed' ? 'text-red-600' : 'text-blue-600'}>
                    {item.inference}
                  </span>
                </InfoRow>
              )}
              <InfoRow label="摘要"><StatusChip label={item.summary} /></InfoRow>
              {item.report_candidate && (
                <InfoRow label="日报候选">
                  <span className={item.report_candidate.includes('已入候选') ? 'text-green-700 font-medium' : 'text-slate-500'}>
                    {item.report_candidate}
                  </span>
                </InfoRow>
              )}
              {item.last_operator && <InfoRow label="操作人"><span className="flex items-center gap-1"><User className="h-3.5 w-3.5 text-slate-400" />{item.last_operator}</span></InfoRow>}
              <InfoRow label="更新时间">{formatDate(item.updated_at)}</InfoRow>
            </SectionCard>

            {item.task_status && (
              <SectionCard title="分析任务详情">
                <InfoRow label="任务状态">
                  <span className={cn(
                    'font-medium',
                    item.task_status === 'done' || item.task_status === 'completed' ? 'text-green-700' :
                    item.task_status === 'failed' ? 'text-red-600' :
                    item.task_status === 'running' ? 'text-blue-600' : 'text-slate-600'
                  )}>{item.task_status}</span>
                </InfoRow>
                {item.task_progress_stage && <InfoRow label="进度阶段">{item.task_progress_stage}</InfoRow>}
                {item.task_progress_message && <InfoRow label="进度信息">{item.task_progress_message}</InfoRow>}
                {item.task_failure_reason && (
                  <InfoRow label="失败原因">
                    <span className="text-red-600">{item.task_failure_reason}</span>
                  </InfoRow>
                )}
              </SectionCard>
            )}

            {item.summary_text && (
              <SectionCard title="摘要内容">
                <div className="py-3">
                  {item.summary_review_status && (
                    <div className="flex items-center gap-2 mb-3">
                      <Tag className="h-3.5 w-3.5 text-slate-400" />
                      <span className="text-xs text-slate-500">审核状态：</span>
                      <StatusChip label={
                        item.summary_review_status === 'approved' ? '已通过' :
                        item.summary_review_status === 'rejected' ? '已打回' : '待审核'
                      } />
                      {item.summary_review_reason && (
                        <span className="text-xs text-red-500 ml-2">({item.summary_review_reason})</span>
                      )}
                    </div>
                  )}
                  <div className="bg-slate-50 rounded-md border border-slate-200 p-4 text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
                    {item.summary_text}
                  </div>
                </div>
              </SectionCard>
            )}
          </div>

          <div className="space-y-4">
            {isImageReview && (
              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
                  <Image className="h-4 w-4 text-slate-500" />
                  <h3 className="text-sm font-semibold text-slate-700">影像审核</h3>
                </div>
                <div className="p-5">
                  <p className="text-xs text-slate-500 mb-4">审核影像质量，确认是否可进入分析阶段。</p>
                  <ActionBtn
                    icon={CheckCircle}
                    label="影像通过"
                    variant="success"
                    loading={acting === 'approve_image'}
                    onClick={handleApproveImage}
                    fullWidth
                  />
                  <div className="mt-4 pt-4 border-t border-slate-100">
                    <button
                      disabled={acting === 'reject_image'}
                      onClick={() => setShowRejectModal('image')}
                      className="flex items-center gap-2 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50 transition-colors"
                    >
                      <XCircle className="h-4 w-4" />
                      退回影像
                    </button>
                  </div>
                </div>
              </div>
            )}

            {isInference && (
              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
                  <Zap className="h-4 w-4 text-slate-500" />
                  <h3 className="text-sm font-semibold text-slate-700">影像分析</h3>
                </div>
                <div className="p-5">
                  <p className="text-xs text-slate-500 mb-4">触发影像分析任务，生成处置成果。</p>
                  <ActionBtn
                    icon={Zap}
                    label="开始分析"
                    variant="primary"
                    loading={acting === 'trigger_inference'}
                    onClick={handleTriggerInference}
                    fullWidth
                  />
                  <div className="mt-4 pt-4 border-t border-slate-100">
                    <p className="text-xs text-slate-400 mb-2.5">重置操作</p>
                    <button
                      disabled={acting === 'reset_inference'}
                      onClick={handleResetInference}
                      className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50 transition-colors"
                    >
                      <RotateCcw className="h-4 w-4" />
                      重置分析与摘要
                    </button>
                  </div>
                </div>
              </div>
            )}

            {isSummary && (
              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
                  <FileText className="h-4 w-4 text-slate-500" />
                  <h3 className="text-sm font-semibold text-slate-700">摘要复核</h3>
                </div>
                <div className="p-5">
                  {item.summary_text ? (
                    <>
                      <p className="text-xs text-slate-500 mb-4">审核摘要内容，通过后加入日报。</p>
                      <ActionBtn
                        icon={CheckCircle}
                        label="通过并加入日报"
                        variant="success"
                        loading={acting === 'approve_summary'}
                        onClick={handleApproveSummary}
                        fullWidth
                      />
                      <div className="mt-3">
                        <ActionBtn
                          icon={FileText}
                          label="重新生成"
                          variant="default"
                          loading={acting === 'generate_summary'}
                          onClick={handleGenerateSummary}
                          fullWidth
                        />
                      </div>
                      <div className="mt-4 pt-4 border-t border-slate-100 space-y-2.5">
                        <button
                          disabled={acting === 'reject_summary'}
                          onClick={() => setShowRejectModal('summary')}
                          className="flex items-center gap-2 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50 transition-colors"
                        >
                          <XCircle className="h-4 w-4" />
                          退回摘要
                        </button>
                        <button
                          disabled={acting === 'reset_inference'}
                          onClick={handleResetInference}
                          className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50 transition-colors"
                        >
                          <RotateCcw className="h-4 w-4" />
                          重置分析与摘要
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="text-xs text-slate-500 mb-4">当前尚无摘要，请先生成。</p>
                      <ActionBtn
                        icon={FileText}
                        label="生成摘要"
                        variant="primary"
                        loading={acting === 'generate_summary'}
                        onClick={handleGenerateSummary}
                        fullWidth
                      />
                      <div className="mt-4 pt-4 border-t border-slate-100">
                        <button
                          disabled={acting === 'reset_inference'}
                          onClick={handleResetInference}
                          className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50 transition-colors"
                        >
                          <RotateCcw className="h-4 w-4" />
                          重置分析与摘要
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            {!isImageReview && !isInference && !isSummary && (
              <div className="bg-white rounded-lg border border-slate-200 p-5 text-center">
                <p className="text-xs text-slate-400">当前阶段无需人工操作</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {showRejectModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 fade-in"
          style={{ background: 'rgba(15,23,42,0.5)' }}
          onClick={() => { setShowRejectModal(null); setRejectReason('') }}
        >
          <div
            className="bg-white rounded-lg shadow-xl w-full max-w-md slide-up"
            onClick={e => e.stopPropagation()}
          >
            <div className="p-6">
              <h3 className="text-sm font-semibold text-slate-900 mb-1">
                {showRejectModal === 'image' ? '打回影像' : '打回摘要'}
              </h3>
              <p className="text-xs text-slate-500 mb-4">请填写打回原因</p>
              <textarea
                className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm text-slate-800 resize-none focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                rows={3}
                placeholder="输入原因…"
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                autoFocus
              />
            </div>
            <div className="flex items-center justify-end gap-3 px-6 pb-6">
              <button
                onClick={() => { setShowRejectModal(null); setRejectReason('') }}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 transition-colors"
              >
                取消
              </button>
              <button
                disabled={!rejectReason.trim()}
                onClick={showRejectModal === 'image' ? handleRejectImage : handleRejectSummary}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md transition-colors disabled:opacity-50"
              >
                确认打回
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
