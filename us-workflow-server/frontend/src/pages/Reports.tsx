import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { reportApi } from '../lib/api'
import { useToast } from '../components/Toast'
import { useConfirm } from '../components/ConfirmDialog'
import type { DailyReport } from '../types'
import { formatDate } from '../lib/utils'
import { FileText, Send, Eye, RefreshCw, Loader2, AlertCircle, FilePlus } from 'lucide-react'

export function Reports() {
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  const [reports, setReports] = useState<DailyReport[]>([])
  const [loading, setLoading] = useState(true)
  const [generateDate, setGenerateDate] = useState(new Date().toISOString().split('T')[0])
  const [generating, setGenerating] = useState(false)
  const [publishingDate, setPublishingDate] = useState<string | null>(null)

  useEffect(() => { loadReports() }, [])

  const loadReports = async () => {
    setLoading(true)
    try {
      const data = await reportApi.getReports(30)
      setReports(data.data)
    } catch {
      toast.error('加载失败', '无法获取日报列表')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerate = async () => {
    if (!generateDate) { toast.warning('请选择日期'); return }
    setGenerating(true)
    try {
      const result = await reportApi.generateReport(generateDate)
      toast.success('日报草稿已生成', result.report_title || generateDate)
      await loadReports()
    } catch (err: any) {
      toast.error('生成失败', err.response?.data?.detail || err.message)
    } finally {
      setGenerating(false)
    }
  }

  const handlePublish = async (reportDate: string) => {
    const ok = await confirm({
      title: `发布 ${reportDate} 日报`,
      message: '发布后日报将正式可见，确认发布？',
      confirmText: '确认发布',
    })
    if (!ok) return
    setPublishingDate(reportDate)
    try {
      await reportApi.publishReport(reportDate)
      toast.success('日报已发布', reportDate)
      await loadReports()
    } catch (err: any) {
      toast.error('发布失败', err.response?.data?.detail || err.message)
    } finally {
      setPublishingDate(null)
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-900">日报</h1>
          <button
            onClick={loadReports}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 border border-slate-200 rounded-md px-3 py-1.5 bg-white hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <FilePlus className="h-4 w-4 text-slate-500" />
            <h2 className="text-sm font-semibold text-slate-700">生成日报草稿</h2>
          </div>
          <div className="flex items-end gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">报告日期</label>
              <input
                type="date"
                value={generateDate}
                onChange={e => setGenerateDate(e.target.value)}
                className="h-9 px-3 text-sm border border-slate-300 rounded-md bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
              />
            </div>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 h-9 px-4 bg-blue-700 hover:bg-blue-800 disabled:opacity-50 text-white text-sm font-medium rounded-md transition-colors"
            >
              {generating
                ? <><Loader2 className="h-4 w-4 animate-spin" />生成中</>
                : <><FileText className="h-4 w-4" />生成草稿</>}
            </button>
          </div>
          <p className="text-xs text-slate-400 mt-2">将根据已加入当日日报的事件摘要自动生成草稿</p>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 bg-slate-50">
            <h2 className="text-sm font-semibold text-slate-700">日报列表</h2>
          </div>

          {loading ? (
            <div className="divide-y divide-slate-100">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="px-5 py-4 animate-pulse flex items-center gap-4">
                  <div className="h-4 w-24 bg-slate-100 rounded" />
                  <div className="h-4 flex-1 bg-slate-100 rounded" />
                  <div className="h-4 w-16 bg-slate-100 rounded" />
                  <div className="h-4 w-20 bg-slate-100 rounded" />
                </div>
              ))}
            </div>
          ) : reports.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2 text-slate-400">
              <AlertCircle className="h-6 w-6" />
              <p className="text-sm">暂无日报</p>
            </div>
          ) : (() => {
            const todayStr = new Date().toISOString().split('T')[0]
            return (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  <th className="px-5 py-3 text-left">日期</th>
                  <th className="px-4 py-3 text-left">标题</th>
                  <th className="px-4 py-3 text-left w-16">事件数</th>
                  <th className="px-4 py-3 text-left w-24">状态</th>
                  <th className="px-4 py-3 text-left hidden lg:table-cell">生成时间</th>
                  <th className="px-4 py-3 text-left hidden xl:table-cell">发布时间</th>
                  <th className="px-4 py-3 text-right w-28"></th>
                </tr>
              </thead>
              <tbody>
                {reports.map(report => {
                  const isToday = report.report_date === todayStr
                  return (
                  <tr
                    key={report.report_date}
                    className={`border-b border-slate-100 transition-colors ${isToday ? 'bg-blue-50/40 hover:bg-blue-50' : 'hover:bg-slate-50'}`}
                  >
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-semibold text-slate-800">{report.report_date}</span>
                        {isToday && <span className="text-xs font-medium bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">今日</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 max-w-xs">
                      <span className="text-slate-700 truncate block" title={report.report_title ?? ''}>
                        {report.report_title || <span className="text-slate-400">无标题</span>}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 tabular-nums text-slate-700 font-medium">
                      {report.event_count}
                    </td>
                    <td className="px-4 py-3.5">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                        report.published
                          ? 'bg-green-50 text-green-700'
                          : 'bg-amber-50 text-amber-700'
                      }`}>
                        {report.published ? '已发布' : '草稿'}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-xs text-slate-400 hidden lg:table-cell whitespace-nowrap">
                      {formatDate(report.generated_at)}
                    </td>
                    <td className="px-4 py-3.5 text-xs text-slate-400 hidden xl:table-cell whitespace-nowrap">
                      {report.published && report.published_at ? formatDate(report.published_at) : '—'}
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => navigate(`/report/${report.report_date}`)}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-slate-600 border border-slate-300 rounded-md hover:bg-slate-50 transition-colors"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          查看
                        </button>
                        {!report.published && (
                          <button
                            onClick={() => handlePublish(report.report_date)}
                            disabled={publishingDate === report.report_date}
                            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-blue-700 hover:bg-blue-800 rounded-md transition-colors disabled:opacity-50"
                          >
                            {publishingDate === report.report_date
                              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <Send className="h-3.5 w-3.5" />}
                            发布
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )})}
              </tbody>
            </table>
          )
          })()}

          {!loading && reports.length > 0 && (
            <div className="px-5 py-2.5 border-t border-slate-100 text-xs text-slate-400">
              共 {reports.length} 份
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
