import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { workflowApi } from '../lib/api'
import { useToast } from '../components/Toast'
import { useConfirm } from '../components/ConfirmDialog'
import type { WorkflowItemDetail } from '../types'
import { formatDate } from '../lib/utils'
import { cn } from '../lib/utils'
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  CheckCircle,
  ExternalLink,
  FileText,
  Image as ImageIcon,
  Loader2,
  MapPin,
  RefreshCw,
  RotateCcw,
  Tag,
  XCircle,
  Zap,
} from 'lucide-react'

type ReviewImageType = 'pre' | 'post'
type ImageVariant = 'original' | 'enhanced'

const SEVERITY_LABEL: Record<string, string> = { red: '极高风险', orange: '高风险', green: '一般', low: 'low', mid: 'mid', high: 'high' }
const SEVERITY_CLASS: Record<string, string> = {
  red: 'bg-red-50 text-red-700 border border-red-200',
  orange: 'bg-amber-50 text-amber-700 border border-amber-200',
  green: 'bg-green-50 text-green-700 border border-green-200',
  low: 'bg-slate-100 text-slate-700 border border-slate-200',
  mid: 'bg-amber-50 text-amber-700 border border-amber-200',
  high: 'bg-red-50 text-red-700 border border-red-200',
}
const STATUS_CLASS: Record<string, string> = {
  '待影像': 'bg-slate-100 text-slate-600',
  '待重新准备影像': 'bg-slate-100 text-slate-600',
  '待质检归档': 'bg-blue-50 text-blue-700',
  '待影像审核': 'bg-amber-50 text-amber-700',
  '影像已打回': 'bg-red-50 text-red-700',
  '待触发推理': 'bg-amber-50 text-amber-700',
  '待执行推理': 'bg-blue-50 text-blue-700',
  '推理中': 'bg-blue-50 text-blue-700',
  '推理需处理': 'bg-red-50 text-red-700',
  '待落成品': 'bg-blue-50 text-blue-700',
  '待生成摘要': 'bg-amber-50 text-amber-700',
  '待摘要审核': 'bg-amber-50 text-amber-700',
  '摘要已打回': 'bg-red-50 text-red-700',
  '待推入日报': 'bg-amber-50 text-amber-700',
  '可生成日报': 'bg-green-50 text-green-700',
  '日报草稿已生成': 'bg-green-50 text-green-700',
  '日报已发布': 'bg-green-100 text-green-800',
  '已通过': 'bg-green-50 text-green-700',
  '已打回': 'bg-red-50 text-red-700',
  '待审核': 'bg-slate-100 text-slate-600',
  '待人工审核': 'bg-amber-50 text-amber-700',
}
const STATUS_DISPLAY: Record<string, string> = {
  '待重新准备影像': '待准备影像',
  '待触发推理': '待触发分析',
  '待执行推理': '分析排队中',
  '推理中': '分析进行中',
  '推理需处理': '分析异常',
  '待落成品': '成果生成中',
  '待推入日报': '待加入日报',
  '待质检归档': '质检中',
}
const DETAIL_FETCH_LABEL: Record<string, string> = { pending: '待补抓', success: '已补抓', failed: '补抓失败', not_found: '源站无详情' }
const DETAIL_FETCH_CLASS: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-700 border border-amber-200',
  success: 'bg-green-50 text-green-700 border border-green-200',
  failed: 'bg-red-50 text-red-700 border border-red-200',
  not_found: 'bg-slate-100 text-slate-600 border border-slate-200',
}
const POOL_LABEL: Record<string, string> = {
  event_pool: '事件接入',
  imagery_pool: '影像准备',
  image_review_pool: '影像审核',
  inference_pool: '待分析',
  summary_report_pool: '待确认摘要',
}

function prettyJson(value: unknown) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try { return JSON.stringify(value, null, 2) } catch { return String(value) }
}
function extractDetailSummary(item: WorkflowItemDetail): Array<{ label: string; value: string }> {
  const raw = item.details_json
  const summary: Array<{ label: string; value: string }> = []
  const push = (label: string, value: unknown) => {
    if (value == null) return
    const text = String(value).trim()
    if (!text || text === '-') return
    summary.push({ label, value: text })
  }

  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    const root = raw as Record<string, unknown>
    const feature = Array.isArray(root.features) ? root.features[0] as Record<string, unknown> | undefined : undefined
    const props = feature && typeof feature.properties === 'object' && feature.properties ? feature.properties as Record<string, unknown> : {}
    const eventTime = props.eventDate ?? root.eventDate ?? item.event_date
    const lastUpdate = props.lastUpdate ?? root.lastUpdate ?? item.last_update
    push('标题', props.title ?? root.title ?? item.title)
    push('类别', props.categoryName ?? props.category ?? root.categoryName ?? root.category ?? item.category)
    push('严重度', props.severity ?? root.severity ?? item.severity)
    push('事件时间', eventTime != null ? formatMaybeDate(Number(eventTime)) : null)
    push('最后更新', lastUpdate != null ? formatMaybeDate(Number(lastUpdate)) : null)
    push('影响区域', props.location ?? props.address ?? root.location ?? root.affectedRegion ?? item.address)
    push('来源', root.source ?? props.source)
    push('来源链接', root.sourceUrl ?? root.source_url ?? item.source_url)
    push('补充信息', root.description ?? props.description)
  }

  if (summary.length === 0) {
    push('标题', item.title)
    push('类别', item.category)
    push('严重度', item.severity)
    push('地区', item.country)
    push('地址', item.address)
  }

  return summary
}
function formatMaybeDate(value: number | null | undefined) {
  return value ? formatDate(value) : '暂无'
}
function imageKey(imageType: ReviewImageType, variant: ImageVariant) {
  return `${imageType}-${variant}`
}

function InfoRow({ label, children, mono = false }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex gap-3 py-2.5 border-b border-slate-100 last:border-0">
      <span className="text-xs text-slate-400 w-24 flex-shrink-0 pt-0.5">{label}</span>
      <span className={cn('text-sm text-slate-800 flex-1 min-w-0', mono && 'font-mono text-xs text-slate-500 break-all')}>{children}</span>
    </div>
  )
}

function StatusChip({ label }: { label: string }) {
  const cls = STATUS_CLASS[label] ?? 'bg-slate-100 text-slate-600'
  const display = STATUS_DISPLAY[label] ?? label
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{display}</span>
}

function SectionCard({ title, actions, children }: { title: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
        {actions}
      </div>
      <div className="px-5 py-1">{children}</div>
    </div>
  )
}

function ActionBtn({
  icon: Icon, label, variant = 'default', loading = false, disabled = false, fullWidth = false, onClick,
}: {
  icon: React.ElementType
  label: string
  variant?: 'primary' | 'success' | 'danger' | 'default'
  loading?: boolean
  disabled?: boolean
  fullWidth?: boolean
  onClick: () => void
}) {
  const cls: Record<string, string> = {
    primary: 'bg-blue-700 hover:bg-blue-800 text-white border-transparent',
    success: 'bg-green-700 hover:bg-green-800 text-white border-transparent',
    danger: 'bg-red-600 hover:bg-red-700 text-white border-transparent',
    default: 'bg-white hover:bg-slate-50 text-slate-700 border-slate-300',
  }
  return (
    <button
      disabled={loading || disabled}
      onClick={onClick}
      className={cn('flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium border transition-colors disabled:opacity-50', fullWidth && 'w-full justify-center', cls[variant])}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
      {label}
    </button>
  )
}

function JsonBlock({ value }: { value: unknown }) {
  const text = prettyJson(value)
  if (!text) return <div className="py-4 text-sm text-slate-400">暂无数据</div>
  return <pre className="bg-slate-950 text-slate-100 rounded-lg p-4 text-xs leading-6 overflow-x-auto whitespace-pre-wrap break-words my-4">{text}</pre>
}

function ImagePreviewCard({
  title, imageType, variant, onVariantChange, url, loading, error, imagePath, imageDate, imageSource,
}: {
  title: string
  imageType: ReviewImageType
  variant: ImageVariant
  onVariantChange: (next: ImageVariant) => void
  url?: string
  loading?: boolean
  error?: string
  imagePath?: string | null
  imageDate?: number | null
  imageSource?: string | null
}) {
  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden bg-white">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-800">{title}</h4>
          <p className="text-xs text-slate-500 mt-1">{imagePath ? '可直接预览原图与增强图' : '当前没有可用影像文件'}</p>
        </div>
        <div className="inline-flex rounded-md border border-slate-200 bg-white p-1">
          {(['original', 'enhanced'] as ImageVariant[]).map((item) => (
            <button key={item} onClick={() => onVariantChange(item)} className={cn('px-3 py-1.5 text-xs font-medium rounded', item === variant ? 'bg-blue-700 text-white' : 'text-slate-600 hover:bg-slate-100')}>
              {item === 'original' ? '原图' : '增强图'}
            </button>
          ))}
        </div>
      </div>
      <div className="p-4">
        <div className="aspect-[4/3] rounded-lg border border-slate-200 bg-slate-50 overflow-hidden flex items-center justify-center">
          {!imagePath && <div className="text-sm text-slate-400">暂无影像</div>}
          {imagePath && loading && <Loader2 className="h-6 w-6 text-slate-400 animate-spin" />}
          {imagePath && !loading && error && <div className="px-4 text-center text-sm text-red-500">{error}</div>}
          {imagePath && !loading && !error && url && <img src={url} alt={`${title}-${imageType}-${variant}`} className="h-full w-full object-contain bg-slate-950/95" />}
        </div>
        <div className="mt-4 space-y-2 text-xs text-slate-500">
          <div className="flex justify-between gap-4"><span>时间</span><span className="text-right text-slate-700">{formatMaybeDate(imageDate)}</span></div>
          <div className="flex justify-between gap-4"><span>来源</span><span className="text-right text-slate-700 break-all">{imageSource || '暂无'}</span></div>
          <div className="flex justify-between gap-4"><span>路径</span><span className="text-right text-slate-700 break-all">{imagePath || '暂无'}</span></div>
        </div>
      </div>
    </div>
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
  const [selectedReviewImageType, setSelectedReviewImageType] = useState<ReviewImageType>('post')
  const [imageVariant, setImageVariant] = useState<Record<ReviewImageType, ImageVariant>>({ pre: 'enhanced', post: 'enhanced' })
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({})
  const [imageLoading, setImageLoading] = useState<Record<string, boolean>>({})
  const [imageErrors, setImageErrors] = useState<Record<string, string>>({})
  const objectUrlRegistry = useRef<string[]>([])

  const loadItem = async () => {
    if (!uuid) return
    setLoading(true)
    try {
      setItem(await workflowApi.getItemDetail(uuid))
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

  useEffect(() => { if (uuid) void loadItem() }, [uuid])

  useEffect(() => {
    if (!item) return
    if (item.selected_image_type === 'pre' || item.selected_image_type === 'post') setSelectedReviewImageType(item.selected_image_type)
    else if (item.post_image_path) setSelectedReviewImageType('post')
    else if (item.pre_image_path) setSelectedReviewImageType('pre')
  }, [item])

  useEffect(() => {
    objectUrlRegistry.current.forEach((url) => URL.revokeObjectURL(url))
    objectUrlRegistry.current = []
    setImageUrls({})
    setImageLoading({})
    setImageErrors({})
    if (!item) return
    let cancelled = false

    const loadVariant = async (imageType: ReviewImageType, variant: ImageVariant) => {
      const imagePath = imageType === 'pre' ? item.pre_image_path : item.post_image_path
      if (!imagePath) return
      const key = imageKey(imageType, variant)
      setImageLoading((prev) => ({ ...prev, [key]: true }))
      try {
        const blob = await workflowApi.getImageBlob(item.uuid, imageType, variant === 'enhanced')
        if (cancelled) return
        const url = URL.createObjectURL(blob)
        objectUrlRegistry.current.push(url)
        setImageUrls((prev) => ({ ...prev, [key]: url }))
      } catch (err: any) {
        let message = err.message || '影像加载失败'
        const payload = err.response?.data
        if (payload instanceof Blob) {
          try {
            const text = await payload.text()
            const parsed = JSON.parse(text)
            message = parsed.detail || text || message
          } catch {
            message = err.message || message
          }
        }
        if (!cancelled) setImageErrors((prev) => ({ ...prev, [key]: message }))
      } finally {
        if (!cancelled) setImageLoading((prev) => ({ ...prev, [key]: false }))
      }
    }

    ;(['pre', 'post'] as ReviewImageType[]).forEach((imageType) => {
      void loadVariant(imageType, 'original')
      void loadVariant(imageType, 'enhanced')
    })

    return () => {
      cancelled = true
      objectUrlRegistry.current.forEach((url) => URL.revokeObjectURL(url))
      objectUrlRegistry.current = []
    }
  }, [item?.uuid, item?.pre_image_path, item?.post_image_path])

  const handleRefreshDetail = () => run('refresh_detail', async () => {
    await workflowApi.refreshDetail(uuid!)
    toast.success('事件详情已重新补抓')
  })
  const handleApproveImage = () => run('approve_image', async () => {
    await workflowApi.reviewImage(uuid!, true, selectedReviewImageType)
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
  const handleTriggerInference = () => run('trigger_inference', async () => {
    await workflowApi.triggerInference(uuid!, selectedReviewImageType)
    toast.success('分析已触发')
  })
  const handleResetInference = async () => {
    const ok = await confirm({ title: '重置分析与摘要', message: '将清空当前事件的分析成果和摘要内容，操作不可撤销，确认继续？', confirmText: '确认重置', danger: true })
    if (!ok) return
    void run('reset_inference', async () => {
      await workflowApi.resetInference(uuid!)
      toast.success('分析与摘要已重置')
    })
  }
  const handleRollbackPrevious = async () => {
    const ok = await confirm({ title: '打回上一池', message: '将清空当前阶段及下游相关状态，并把事件打回上一池。确认继续？', confirmText: '确认打回', danger: true })
    if (!ok) return
    void run('rollback_previous', async () => {
      await workflowApi.rollbackPrevious(uuid!)
      toast.success('事件已打回上一池')
    })
  }
  const handleGenerateSummary = () => run('generate_summary', async () => {
    await workflowApi.generateSummary(uuid!)
    toast.success('摘要生成完成')
  })
  const handleApproveSummary = () => run('approve_summary', async () => {
    await workflowApi.approveSummary(uuid!, true, undefined, new Date().toISOString().split('T')[0])
    toast.success('摘要已通过，已加入日报')
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

  const detailFetchMeta = useMemo(() => {
    const status = item?.detail_fetch_status || 'pending'
    return { label: DETAIL_FETCH_LABEL[status] ?? status, className: DETAIL_FETCH_CLASS[status] ?? 'bg-slate-100 text-slate-600 border border-slate-200' }
  }, [item?.detail_fetch_status])

  if (loading) {
    return <Layout><div className="h-40 rounded-lg border border-slate-200 bg-white animate-pulse" /></Layout>
  }
  if (!item) {
    return <Layout><div className="flex flex-col items-center justify-center py-24 gap-3"><AlertCircle className="h-8 w-8 text-slate-300" /><p className="text-slate-500">事件不存在</p><button onClick={() => navigate(-1)} className="text-sm text-blue-700 hover:underline">返回</button></div></Layout>
  }

  const isImageReview = item.pool === 'image_review_pool'
  const isInference = item.pool === 'inference_pool'
  const isSummary = item.pool === 'summary_report_pool'
  const canRollbackPrevious = item.pool !== 'event_pool'
  const poolStatusDisplay = STATUS_DISPLAY[item.pool_status] ?? item.pool_status
  const detailSummary = extractDetailSummary(item)

  return (
    <Layout>
      <div className="space-y-5">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors">
            <ArrowLeft className="h-4 w-4" />返回
          </button>
          <span className="text-slate-300">/</span>
          <span className="text-sm text-slate-500">事件处理</span>
          <span className="text-slate-300">/</span>
          <span className="text-sm text-slate-700 font-medium truncate max-w-xs">{item.title || item.uuid.slice(0, 12)}</span>
        </div>

        <div className="flex items-start gap-3 flex-wrap">
          <h1 className="text-xl font-bold text-slate-900 flex-1 min-w-0 leading-snug">{item.title || <span className="text-slate-400">无标题事件</span>}</h1>
          <div className="flex items-center gap-2 flex-shrink-0">
            {item.severity && <span className={`px-2.5 py-1 rounded text-xs font-semibold ${SEVERITY_CLASS[item.severity] ?? 'bg-slate-100 text-slate-600'}`}>{SEVERITY_LABEL[item.severity] ?? item.severity}</span>}
            <span className={`px-2.5 py-1 rounded text-xs font-semibold ${STATUS_CLASS[item.pool_status] ?? 'bg-slate-100 text-slate-600'}`}>{poolStatusDisplay}</span>
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-5">
            <SectionCard title="基本信息">
              <InfoRow label="事件 ID" mono>{item.uuid}</InfoRow>
              {item.category && <InfoRow label="类别">{item.category}</InfoRow>}
              {item.country && <InfoRow label="地区"><span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-slate-400" />{item.country}</span></InfoRow>}
              {item.address && <InfoRow label="地址">{item.address}</InfoRow>}
              {(item.latitude != null && item.longitude != null) && <InfoRow label="坐标">{item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}</InfoRow>}
              {item.event_date && <InfoRow label="事件时间"><span className="flex items-center gap-1"><Calendar className="h-3.5 w-3.5 text-slate-400" />{formatDate(item.event_date)}</span></InfoRow>}
              {item.last_update && <InfoRow label="源站更新">{formatDate(item.last_update)}</InfoRow>}
              {item.source_url && <InfoRow label="原始来源"><a href={item.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-blue-700 hover:underline break-all">打开源站详情<ExternalLink className="h-3.5 w-3.5" /></a></InfoRow>}
            </SectionCard>

            <SectionCard title="处理进度">
              <InfoRow label="当前阶段"><span className="font-medium text-slate-700">{POOL_LABEL[item.pool] ?? item.pool}</span></InfoRow>
              <InfoRow label="状态"><StatusChip label={item.pool_status} /></InfoRow>
              <InfoRow label="影像"><span className={item.imagery === '已就绪' ? 'text-green-600 font-medium' : 'text-slate-500'}>{item.imagery}</span></InfoRow>
              <InfoRow label="质检"><StatusChip label={item.quality} /></InfoRow>
              {item.inference && item.inference !== '待创建' && <InfoRow label="分析任务"><span className={item.inference === 'done' || item.inference === 'completed' ? 'text-green-700' : item.inference === 'failed' ? 'text-red-600' : 'text-blue-600'}>{item.inference}</span></InfoRow>}
              <InfoRow label="摘要"><StatusChip label={item.summary} /></InfoRow>
              {item.report_candidate && <InfoRow label="日报候选">{item.report_candidate}</InfoRow>}
              {item.last_operator && <InfoRow label="操作人">{item.last_operator}</InfoRow>}
              <InfoRow label="更新时间">{formatMaybeDate(item.updated_at)}</InfoRow>
            </SectionCard>

            <SectionCard title="详情补抓" actions={<ActionBtn icon={RefreshCw} label="重新补抓" variant="default" loading={acting === 'refresh_detail'} onClick={handleRefreshDetail} />}>
              <InfoRow label="抓取状态"><span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${detailFetchMeta.className}`}>{detailFetchMeta.label}</span></InfoRow>
              <InfoRow label="尝试次数">{item.detail_fetch_attempts ?? 0}</InfoRow>
              <InfoRow label="最近尝试">{formatMaybeDate(item.detail_fetch_last_attempt)}</InfoRow>
              <InfoRow label="完成时间">{formatMaybeDate(item.detail_fetch_completed_at)}</InfoRow>
              <InfoRow label="HTTP 状态">{item.detail_fetch_http_status ?? '暂无'}</InfoRow>
              {item.detail_fetch_error && <InfoRow label="错误信息"><span className="text-red-600">{item.detail_fetch_error}</span></InfoRow>}
            </SectionCard>

            <SectionCard title="已抓取详情摘要">
              {detailSummary.length > 0 ? (
                <div className="grid gap-x-6 gap-y-3 py-4 md:grid-cols-2">
                  {detailSummary.map((entry) => (
                    <div key={`${entry.label}-${entry.value}`} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="text-xs text-slate-400">{entry.label}</div>
                      <div className="mt-1 text-sm text-slate-800 break-words">{entry.value}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-4 text-sm text-slate-400">当前还没有抓到可展示的详情内容</div>
              )}
            </SectionCard>

            <SectionCard title="影像预览">
              <div className="grid gap-4 py-4 xl:grid-cols-2">
                <ImagePreviewCard title="灾前影像" imageType="pre" variant={imageVariant.pre} onVariantChange={(next) => setImageVariant((prev) => ({ ...prev, pre: next }))} url={imageUrls[imageKey('pre', imageVariant.pre)]} loading={imageLoading[imageKey('pre', imageVariant.pre)]} error={imageErrors[imageKey('pre', imageVariant.pre)]} imagePath={item.pre_image_path} imageDate={item.pre_image_date} imageSource={item.pre_image_source} />
                <ImagePreviewCard title="灾后影像" imageType="post" variant={imageVariant.post} onVariantChange={(next) => setImageVariant((prev) => ({ ...prev, post: next }))} url={imageUrls[imageKey('post', imageVariant.post)]} loading={imageLoading[imageKey('post', imageVariant.post)]} error={imageErrors[imageKey('post', imageVariant.post)]} imagePath={item.post_image_path} imageDate={item.post_image_date} imageSource={item.post_image_source} />
              </div>
            </SectionCard>

            <SectionCard title="事件原始详情"><JsonBlock value={item.details_json} /></SectionCard>

            {(item.quality_score != null || item.quality_assessment != null) && (
              <SectionCard title="质检结果">
                {item.quality_score != null && <InfoRow label="质量分">{item.quality_score.toFixed(3)}</InfoRow>}
                <JsonBlock value={item.quality_assessment} />
              </SectionCard>
            )}

            {item.task_status && (
              <SectionCard title="分析任务详情">
                <InfoRow label="任务状态"><span className={cn('font-medium', item.task_status === 'done' || item.task_status === 'completed' ? 'text-green-700' : item.task_status === 'failed' ? 'text-red-600' : item.task_status === 'running' ? 'text-blue-600' : 'text-slate-600')}>{item.task_status}</span></InfoRow>
                {item.task_progress_stage && <InfoRow label="进度阶段">{item.task_progress_stage}</InfoRow>}
                {item.task_progress_message && <InfoRow label="进度信息">{item.task_progress_message}</InfoRow>}
                {item.task_failure_reason && <InfoRow label="失败原因"><span className="text-red-600">{item.task_failure_reason}</span></InfoRow>}
              </SectionCard>
            )}

            {item.summary_text && (
              <SectionCard title="摘要内容">
                <div className="py-4">
                  {item.summary_review_status && <div className="flex items-center gap-2 mb-3 flex-wrap"><Tag className="h-3.5 w-3.5 text-slate-400" /><span className="text-xs text-slate-500">审核状态：</span><StatusChip label={item.summary_review_status === 'approved' ? '已通过' : item.summary_review_status === 'rejected' ? '已打回' : '待审核'} />{item.summary_review_reason && <span className="text-xs text-red-500">({item.summary_review_reason})</span>}</div>}
                  <div className="bg-slate-50 rounded-md border border-slate-200 p-4 text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">{item.summary_text}</div>
                </div>
              </SectionCard>
            )}
          </div>

          <div className="space-y-4">
            {isImageReview && (
              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50 flex items-center gap-2"><ImageIcon className="h-4 w-4 text-slate-500" /><h3 className="text-sm font-semibold text-slate-700">影像审核</h3></div>
                <div className="p-5">
                  <p className="text-xs text-slate-500 mb-4">先看原图和增强图，再选择当前通过的是灾前还是灾后影像。</p>
                  <div className="grid grid-cols-2 gap-2 mb-4">
                    {(['pre', 'post'] as ReviewImageType[]).map((imageType) => {
                      const available = imageType === 'pre' ? !!item.pre_image_path : !!item.post_image_path
                      return <button key={imageType} disabled={!available} onClick={() => setSelectedReviewImageType(imageType)} className={cn('px-3 py-2 rounded-md border text-sm font-medium transition-colors', selectedReviewImageType === imageType ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50', !available && 'opacity-40 cursor-not-allowed')}>{imageType === 'pre' ? '灾前影像' : '灾后影像'}</button>
                    })}
                  </div>
                  <ActionBtn icon={CheckCircle} label={`影像通过并记录为${selectedReviewImageType === 'pre' ? '灾前' : '灾后'}`} variant="success" loading={acting === 'approve_image'} onClick={handleApproveImage} fullWidth />
                  <div className="mt-4 pt-4 border-t border-slate-100"><button disabled={acting === 'reject_image'} onClick={() => setShowRejectModal('image')} className="flex items-center gap-2 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50 transition-colors"><XCircle className="h-4 w-4" />退回影像</button></div>
                </div>
              </div>
            )}

            {isInference && (
              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50 flex items-center gap-2"><Zap className="h-4 w-4 text-slate-500" /><h3 className="text-sm font-semibold text-slate-700">影像分析</h3></div>
                <div className="p-5">
                  <p className="text-xs text-slate-500 mb-4">触发影像分析任务，使用当前选中的影像类型推进到成果生成。</p>
                  <div className="grid grid-cols-2 gap-2 mb-4">
                    {(['pre', 'post'] as ReviewImageType[]).map((imageType) => {
                      const available = imageType === 'pre' ? !!item.pre_image_path : !!item.post_image_path
                      return <button key={imageType} disabled={!available} onClick={() => setSelectedReviewImageType(imageType)} className={cn('px-3 py-2 rounded-md border text-sm font-medium transition-colors', selectedReviewImageType === imageType ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50', !available && 'opacity-40 cursor-not-allowed')}>{imageType === 'pre' ? '灾前影像' : '灾后影像'}</button>
                    })}
                  </div>
                  <ActionBtn icon={Zap} label="开始分析" variant="primary" loading={acting === 'trigger_inference'} onClick={handleTriggerInference} fullWidth />
                  <div className="mt-4 pt-4 border-t border-slate-100"><p className="text-xs text-slate-400 mb-2.5">重置操作</p><button disabled={acting === 'reset_inference'} onClick={handleResetInference} className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50 transition-colors"><RotateCcw className="h-4 w-4" />重置分析与摘要</button></div>
                </div>
              </div>
            )}

            {isSummary && (
              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50 flex items-center gap-2"><FileText className="h-4 w-4 text-slate-500" /><h3 className="text-sm font-semibold text-slate-700">摘要复核</h3></div>
                <div className="p-5">
                  {item.summary_text ? (
                    <>
                      <p className="text-xs text-slate-500 mb-4">审核摘要内容，通过后加入日报。</p>
                      <ActionBtn icon={CheckCircle} label="通过并加入日报" variant="success" loading={acting === 'approve_summary'} onClick={handleApproveSummary} fullWidth />
                      <div className="mt-3"><ActionBtn icon={FileText} label="重新生成" variant="default" loading={acting === 'generate_summary'} onClick={handleGenerateSummary} fullWidth /></div>
                      <div className="mt-4 pt-4 border-t border-slate-100 space-y-2.5">
                        <button disabled={acting === 'reject_summary'} onClick={() => setShowRejectModal('summary')} className="flex items-center gap-2 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50 transition-colors"><XCircle className="h-4 w-4" />退回摘要</button>
                        <button disabled={acting === 'reset_inference'} onClick={handleResetInference} className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50 transition-colors"><RotateCcw className="h-4 w-4" />重置分析与摘要</button>
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="text-xs text-slate-500 mb-4">当前尚无摘要，请先生成。</p>
                      <ActionBtn icon={FileText} label="生成摘要" variant="primary" loading={acting === 'generate_summary'} onClick={handleGenerateSummary} fullWidth />
                      <div className="mt-4 pt-4 border-t border-slate-100"><button disabled={acting === 'reset_inference'} onClick={handleResetInference} className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50 transition-colors"><RotateCcw className="h-4 w-4" />重置分析与摘要</button></div>
                    </>
                  )}
                </div>
              </div>
            )}

            {!isImageReview && !isInference && !isSummary && (
              <div className="bg-white rounded-lg border border-slate-200 p-5 text-center">
                {canRollbackPrevious ? <div className="space-y-3"><p className="text-xs text-slate-400">当前阶段暂无直接处理动作</p><ActionBtn icon={RotateCcw} label="打回上一池" variant="danger" loading={acting === 'rollback_previous'} onClick={handleRollbackPrevious} fullWidth /></div> : <p className="text-xs text-slate-400">当前阶段无需人工操作</p>}
              </div>
            )}

            {(isImageReview || isInference || isSummary) && <div className="bg-white rounded-lg border border-slate-200 p-5"><p className="text-xs text-slate-400 mb-3">池子回退</p><ActionBtn icon={RotateCcw} label="打回上一池" variant="danger" loading={acting === 'rollback_previous'} onClick={handleRollbackPrevious} fullWidth /></div>}
          </div>
        </div>
      </div>

      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 fade-in" style={{ background: 'rgba(15,23,42,0.5)' }} onClick={() => { setShowRejectModal(null); setRejectReason('') }}>
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md slide-up" onClick={(e) => e.stopPropagation()}>
            <div className="p-6">
              <h3 className="text-sm font-semibold text-slate-900 mb-1">{showRejectModal === 'image' ? '打回影像' : '打回摘要'}</h3>
              <p className="text-xs text-slate-500 mb-4">请填写打回原因</p>
              <textarea className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm text-slate-800 resize-none focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent" rows={3} placeholder="输入原因…" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} autoFocus />
            </div>
            <div className="flex items-center justify-end gap-3 px-6 pb-6">
              <button onClick={() => { setShowRejectModal(null); setRejectReason('') }} className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 transition-colors">取消</button>
              <button disabled={!rejectReason.trim()} onClick={showRejectModal === 'image' ? handleRejectImage : handleRejectSummary} className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md transition-colors disabled:opacity-50">确认打回</button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
