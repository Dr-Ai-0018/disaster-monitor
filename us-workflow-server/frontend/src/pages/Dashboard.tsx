import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { workflowApi, reportApi } from '../lib/api'
import type { WorkflowOverview, DailyReport } from '../types'
import {
  AlertCircle, Image, Zap, FileCheck, FileText,
  RefreshCw, ArrowRight, CheckCircle2, Clock, Eye, ChevronRight,
} from 'lucide-react'

const MANUAL_STAGES = [
  {
    key: 'image_review_pool',
    label: '待影像审核',
    desc: '影像质量人工复核',
    cta: '前往审核',
    Icon: Image,
    activeColor: 'text-amber-600',
    activeBg: 'bg-amber-50',
    activeBorder: 'border-amber-300',
  },
  {
    key: 'inference_pool',
    label: '待触发分析',
    desc: '影像已通过，待手动触发',
    cta: '开始处理',
    Icon: Zap,
    activeColor: 'text-violet-600',
    activeBg: 'bg-violet-50',
    activeBorder: 'border-violet-300',
  },
  {
    key: 'summary_report_pool',
    label: '待确认摘要',
    desc: '摘要已生成，等待人工确认',
    cta: '查看摘要',
    Icon: FileCheck,
    activeColor: 'text-blue-600',
    activeBg: 'bg-blue-50',
    activeBorder: 'border-blue-300',
  },
]

const AUTO_STAGES = [
  { key: 'event_pool',   label: '新进事件',   desc: '等待进入影像准备', Icon: Eye },
  { key: 'imagery_pool', label: '影像准备中', desc: '影像下载与质检进行中', Icon: Image },
]

export function Dashboard() {
  const [overview, setOverview]         = useState<WorkflowOverview | null>(null)
  const [todayReport, setTodayReport]   = useState<DailyReport | null | undefined>(undefined)
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState(false)
  const navigate = useNavigate()

  useEffect(() => { load() }, [])

  const load = async () => {
    setLoading(true); setError(false)
    try {
      const today = new Date().toISOString().split('T')[0]
      const [ov, rp] = await Promise.all([
        workflowApi.getOverview(),
        reportApi.getReports(7).catch(() => ({ data: [] as DailyReport[] })),
      ])
      setOverview(ov)
      setTodayReport(rp.data.find((r: DailyReport) => r.report_date === today) ?? null)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  const n = (key: string) => overview?.cards.find(c => c.key === key)?.total ?? 0
  const manualTotal = MANUAL_STAGES.reduce((s, x) => s + n(x.key), 0)
  const today = new Date().toLocaleDateString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  return (
    <Layout>
      <div className="space-y-6">

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">概览</h1>
            <p className="text-sm text-slate-500 mt-0.5">{today}</p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 border border-slate-200 rounded-md px-3 py-1.5 bg-white hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            数据加载失败，请刷新重试
          </div>
        )}

        {loading && !overview && (
          <div className="space-y-4 animate-pulse">
            <div className="h-4 w-24 bg-slate-200 rounded" />
            <div className="grid gap-3 sm:grid-cols-3">
              {[0, 1, 2].map(i => (
                <div key={i} className="h-28 bg-white rounded-lg border border-slate-200" />
              ))}
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="h-32 bg-white rounded-lg border border-slate-200" />
              <div className="h-32 bg-white rounded-lg border border-slate-200" />
            </div>
          </div>
        )}

        {overview && (
          <>
            {/* ── SECTION: 需要介入 ── */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <h2 className="text-sm font-semibold text-slate-700">需要介入</h2>
                {manualTotal > 0
                  ? <span className="text-xs font-bold bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full tabular-nums">{manualTotal}</span>
                  : <span className="text-xs text-slate-400">暂无</span>
                }
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {MANUAL_STAGES.map(s => {
                  const cnt = n(s.key)
                  const has = cnt > 0
                  return (
                    <div
                      key={s.key}
                      onClick={() => navigate(`/tasks?pool=${s.key}`)}
                      className={`bg-white rounded-lg border p-4 cursor-pointer hover:shadow-sm transition-all group ${has ? s.activeBorder : 'border-slate-200'}`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className={`h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0 ${has ? s.activeBg : 'bg-slate-50'}`}>
                          <s.Icon className={`h-4 w-4 ${has ? s.activeColor : 'text-slate-300'}`} />
                        </div>
                        <span className={`text-2xl font-bold tabular-nums leading-none ${has ? s.activeColor : 'text-slate-200'}`}>
                          {cnt}
                        </span>
                      </div>
                      <div className="text-sm font-semibold text-slate-800 mb-0.5">{s.label}</div>
                      <div className="text-xs text-slate-400">{s.desc}</div>
                      {has && (
                        <div className={`mt-3 flex items-center gap-1 text-xs font-semibold ${s.activeColor} group-hover:gap-1.5 transition-all`}>
                          {s.cta} <ArrowRight className="h-3 w-3" />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* ── SECTION: 系统处理中 + 今日日报 ── */}
            <div className="grid gap-4 lg:grid-cols-2">

              <div className="bg-white rounded-lg border border-slate-200 px-5 py-4">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">系统处理中</h3>
                <div className="space-y-0.5">
                  {AUTO_STAGES.map(s => (
                    <div
                      key={s.key}
                      onClick={() => navigate(`/tasks?pool=${s.key}`)}
                      className="flex items-center justify-between px-3 py-2.5 rounded-md hover:bg-slate-50 cursor-pointer group transition-colors"
                    >
                      <div className="flex items-center gap-2.5">
                        <s.Icon className="h-3.5 w-3.5 text-slate-400" />
                        <div>
                          <div className="text-sm text-slate-700 leading-none">{s.label}</div>
                          <div className="text-xs text-slate-400 mt-0.5">{s.desc}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-bold text-slate-600 tabular-nums">{n(s.key)}</span>
                        <ChevronRight className="h-3.5 w-3.5 text-slate-300 group-hover:text-slate-500 transition-colors" />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between px-3 text-xs text-slate-400">
                  <span>系统存量合计</span>
                  <span className="font-bold text-slate-600 tabular-nums">
                    {MANUAL_STAGES.reduce((s, x) => s + n(x.key), 0) + AUTO_STAGES.reduce((s, x) => s + n(x.key), 0)}
                  </span>
                </div>
              </div>

              <div className="bg-white rounded-lg border border-slate-200 px-5 py-4">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">今日日报</h3>
                {todayReport === undefined ? (
                  <div className="flex items-center justify-center py-6 text-slate-300">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  </div>
                ) : todayReport === null ? (
                  <div className="space-y-3 py-1">
                    <p className="text-sm text-slate-500">今日暂未生成日报</p>
                    <button
                      onClick={() => navigate('/reports')}
                      className="flex items-center gap-1.5 text-xs font-medium text-blue-700 hover:text-blue-800 transition-colors"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      前往生成草稿
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2.5 py-1">
                    <div>
                      {todayReport.published
                        ? <span className="inline-flex items-center gap-1 text-xs font-semibold bg-green-50 text-green-700 border border-green-200 px-2 py-0.5 rounded"><CheckCircle2 className="h-3 w-3" />已发布</span>
                        : <span className="inline-flex items-center gap-1 text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded"><Clock className="h-3 w-3" />草稿</span>}
                    </div>
                    <p className="text-sm font-medium text-slate-800 leading-snug line-clamp-2">
                      {todayReport.report_title || '无标题'}
                    </p>
                    <p className="text-xs text-slate-400">覆盖 {todayReport.event_count} 项事件</p>
                    <button
                      onClick={() => navigate(`/report/${todayReport.report_date}`)}
                      className="flex items-center gap-1.5 text-xs font-medium text-blue-700 hover:text-blue-800 transition-colors"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      查看详情
                    </button>
                  </div>
                )}
              </div>

            </div>

            {manualTotal === 0 && (
              <div className="flex items-center gap-2.5 px-4 py-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
                <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                当前没有需要人工介入的任务
              </div>
            )}
          </>
        )}

      </div>
    </Layout>
  )
}
