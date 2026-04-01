import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Input } from '../components/ui/input'
import { reportApi } from '../lib/api'
import type { DailyReport } from '../types'
import { formatDate } from '../lib/utils'
import { FileText, Calendar, Send, Eye, Plus } from 'lucide-react'

export function Reports() {
  const navigate = useNavigate()
  const [reports, setReports] = useState<DailyReport[]>([])
  const [loading, setLoading] = useState(true)
  const [generateDate, setGenerateDate] = useState(new Date().toISOString().split('T')[0])
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    loadReports()
  }, [])

  const loadReports = async () => {
    try {
      const data = await reportApi.getReports(20)
      setReports(data.data)
    } catch (error) {
      console.error('Failed to load reports:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateReport = async () => {
    if (!generateDate) {
      alert('请选择日期')
      return
    }

    try {
      setGenerating(true)
      const result = await reportApi.generateReport(generateDate)
      alert(`日报生成成功: ${result.report_title || generateDate}`)
      await loadReports()
    } catch (error: any) {
      alert(`生成失败: ${error.response?.data?.detail || error.message}`)
    } finally {
      setGenerating(false)
    }
  }

  const handlePublishReport = async (reportDate: string) => {
    if (!confirm(`确定要发布 ${reportDate} 的日报吗？`)) return

    try {
      await reportApi.publishReport(reportDate)
      alert('日报发布成功')
      await loadReports()
    } catch (error: any) {
      alert(`发布失败: ${error.response?.data?.detail || error.message}`)
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">日报管理</h1>
          <p className="text-muted-foreground mt-2">
            生成、预览和发布每日灾害分析报告
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              生成新日报
            </CardTitle>
            <CardDescription>
              从日报候选池生成指定日期的日报草稿
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4 items-end">
              <div className="flex-1 max-w-xs">
                <label className="text-sm font-medium mb-2 block">选择日期</label>
                <Input
                  type="date"
                  value={generateDate}
                  onChange={(e) => setGenerateDate(e.target.value)}
                />
              </div>
              <Button onClick={handleGenerateReport} disabled={generating}>
                <FileText className="h-4 w-4 mr-2" />
                {generating ? '生成中...' : '生成日报'}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <h2 className="text-xl font-semibold">历史日报</h2>
          
          {loading ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                加载中...
              </CardContent>
            </Card>
          ) : reports.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                暂无日报
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {reports.map((report) => (
                <Card key={report.report_date} className="hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <span className="font-semibold">{report.report_date}</span>
                      </div>
                      <Badge variant={report.published ? 'default' : 'secondary'}>
                        {report.published ? '已发布' : '草稿'}
                      </Badge>
                    </div>
                    <CardTitle className="text-base mt-2">
                      {report.report_title || '无标题'}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">事件数量</span>
                      <span className="font-semibold">{report.event_count}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">生成时间</span>
                      <span className="text-xs">{formatDate(report.generated_at)}</span>
                    </div>
                    {report.published && report.published_at && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">发布时间</span>
                        <span className="text-xs">{formatDate(report.published_at)}</span>
                      </div>
                    )}
                    <div className="flex gap-2 pt-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => navigate(`/report/${report.report_date}`)}
                        className="flex-1"
                      >
                        <Eye className="h-4 w-4 mr-1" />
                        查看
                      </Button>
                      {!report.published && (
                        <Button
                          size="sm"
                          onClick={() => handlePublishReport(report.report_date)}
                          className="flex-1"
                        >
                          <Send className="h-4 w-4 mr-1" />
                          发布
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
