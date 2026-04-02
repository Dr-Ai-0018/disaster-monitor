import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { reportApi } from '../lib/api'
import { useToast } from '../components/Toast'
import { useConfirm } from '../components/ConfirmDialog'
import type { DailyReport } from '../types'
import { formatDate } from '../lib/utils'
import { ArrowLeft, Send, AlertCircle, Loader2, CheckCircle2, Clock } from 'lucide-react'

function parseStats(raw: string | undefined): Array<{ name: string; value: number }> {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (typeof parsed === 'object' && !Array.isArray(parsed)) {
      return Object.entries(parsed).map(([name, value]) => ({
        name,
        value: typeof value === 'number' ? value : Number(value) || 0,
      }))
    }
  } catch {
    const lines = raw.split('\n').filter(Boolean)
    const result: Array<{ name: string; value: number }> = []
    for (const line of lines) {
      const m = line.match(/^(.+?)[\s:：]+(\d+)/)
      if (m) result.push({ name: m[1].trim(), value: parseInt(m[2]) })
    }
    return result
  }
  return []
}

const BAR_COLORS = ['#3B82F6', '#6366F1', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#14B8A6']

function StatsBlock({ title, raw }: { title: string; raw: string | undefined }) {
  if (!raw) return null
  const data = parseStats(raw)
  if (!data.length) return (
    <div>
      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">{title}</h4>
      <p className="text-xs text-slate-400 italic">暂无数据</p>
    </div>
  )
  return (
    <div>
      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">{title}</h4>
      <div className="space-y-2">
        {data.map((item, i) => {
          const max = Math.max(...data.map(d => d.value))
          return (
            <div key={item.name} className="flex items-center gap-2">
              <span className="text-xs text-slate-600 w-28 truncate flex-shrink-0" title={item.name}>{item.name}</span>
              <div className="flex-1 h-4 bg-slate-100 rounded overflow-hidden">
                <div
                  className="h-full rounded transition-all"
                  style={{
                    width: `${max > 0 ? (item.value / max) * 100 : 0}%`,
                    backgroundColor: BAR_COLORS[i % BAR_COLORS.length],
                  }}
                />
              </div>
              <span className="text-xs font-semibold text-slate-700 tabular-nums w-6 text-right">{item.value}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function ReportDetail() {
  const { reportDate } = useParams<{ reportDate: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  const [report, setReport] = useState<DailyReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [publishing, setPublishing] = useState(false)

  useEffect(() => {
    if (reportDate) loadReport()
  }, [reportDate])

  const loadReport = async () => {
    if (!reportDate) return
    setLoading(true)
    try {
      const data = await reportApi.getReportDetail(reportDate)
      setReport(data)
    } catch (err: any) {
      toast.error('加载失败', err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  const handlePublish = async () => {
    if (!reportDate) return
    const ok = await confirm({
      title: `发布 ${reportDate} 日报`,
      message: '发布后日报状态将更新为已发布，确认继续？',
      confirmText: '确认发布',
    })
    if (!ok) return
    setPublishing(true)
    try {
      await reportApi.publishReport(reportDate)
      toast.success('日报已发布', reportDate)
      await loadReport()
    } catch (err: any) {
      toast.error('发布失败', err.response?.data?.detail || err.message)
    } finally {
      setPublishing(false)
    }
  }

  if (loading) {
    return (
      <Layout>
        <div className="space-y-5 animate-pulse">
          <div className="h-5 w-20 bg-slate-200 rounded" />
          <div className="h-28 bg-white rounded-lg border border-slate-200" />
          <div className="h-96 bg-white rounded-lg border border-slate-200" />
        </div>
      </Layout>
    )
  }

  if (!report) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <AlertCircle className="h-8 w-8 text-slate-300" />
          <p className="text-slate-500">日报不存在</p>
          <button onClick={() => navigate(-1)} className="text-sm text-blue-700 hover:underline">返回</button>
        </div>
      </Layout>
    )
  }

  const hasStats = report.category_stats || report.severity_stats || report.country_stats

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
          <span className="text-sm text-slate-500">日报</span>
          <span className="text-slate-300">/</span>
          <span className="text-sm font-medium text-slate-700 font-mono">{report.report_date}</span>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono text-slate-400">{report.report_date}</span>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${
                  report.published ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'
                }`}>
                  {report.published
                    ? <><CheckCircle2 className="h-3 w-3" />已发布</>
                    : <><Clock className="h-3 w-3" />草稿</>}
                </span>
              </div>
              <h1 className="text-xl font-bold text-slate-900 leading-snug">
                {report.report_title || <span className="text-slate-400">无标题</span>}
              </h1>
            </div>
            {!report.published && (
              <button
                onClick={handlePublish}
                disabled={publishing}
                className="flex items-center gap-2 px-4 py-2 bg-blue-700 hover:bg-blue-800 disabled:opacity-50 text-white text-sm font-medium rounded-md transition-colors flex-shrink-0"
              >
                {publishing
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : <Send className="h-4 w-4" />}
                发布日报
              </button>
            )}
          </div>

          <div className="flex items-center gap-5 mt-4 pt-4 border-t border-slate-100">
            <div>
              <div className="text-2xl font-bold text-slate-900 tabular-nums">{report.event_count}</div>
              <div className="text-xs text-slate-400">覆盖事件</div>
            </div>
            <div className="h-8 w-px bg-slate-200" />
            <div>
              <div className="text-sm text-slate-700">{formatDate(report.generated_at)}</div>
              <div className="text-xs text-slate-400">生成时间</div>
            </div>
            {report.published && report.published_at && (
              <>
                <div className="h-8 w-px bg-slate-200" />
                <div>
                  <div className="text-sm text-slate-700">{formatDate(report.published_at)}</div>
                  <div className="text-xs text-slate-400">发布时间</div>
                </div>
              </>
            )}
          </div>
        </div>

        {hasStats && (
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">数据概览</h2>
            </div>
            <div className="px-5 py-5">
              <div className="grid gap-8 md:grid-cols-3">
                <StatsBlock title="类别分布" raw={report.category_stats} />
                <StatsBlock title="严重程度" raw={report.severity_stats} />
                <StatsBlock title="国家 / 地区" raw={report.country_stats} />
              </div>
            </div>
          </div>
        )}

        {report.report_content && (
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">报告正文</h2>
              <span className="text-xs text-slate-400">{report.report_date}</span>
            </div>
            <div className="px-8 py-7 max-w-3xl">
              <div className="text-slate-800 leading-[1.85] text-[0.9375rem] whitespace-pre-wrap font-[system-ui,sans-serif]">
                {report.report_content}
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
