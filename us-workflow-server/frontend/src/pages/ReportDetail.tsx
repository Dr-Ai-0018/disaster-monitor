import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { reportApi } from '../lib/api'
import type { DailyReport } from '../types'
import { formatDate } from '../lib/utils'
import { ArrowLeft, Send, Calendar, FileText } from 'lucide-react'

export function ReportDetail() {
  const { reportDate } = useParams<{ reportDate: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<DailyReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (reportDate) loadReport()
  }, [reportDate])

  const loadReport = async () => {
    if (!reportDate) return
    try {
      const data = await reportApi.getReportDetail(reportDate)
      setReport(data)
    } catch (error) {
      console.error('Failed to load report:', error)
    } finally {
      setLoading(false)
    }
  }

  const handlePublish = async () => {
    if (!reportDate || !confirm(`确定要发布 ${reportDate} 的日报吗？`)) return

    try {
      await reportApi.publishReport(reportDate)
      alert('日报发布成功')
      await loadReport()
    } catch (error: any) {
      alert(`发布失败: ${error.response?.data?.detail || error.message}`)
    }
  }

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">加载中...</div>
        </div>
      </Layout>
    )
  }

  if (!report) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <div className="text-destructive">日报不存在</div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              返回
            </Button>
          </div>
          {!report.published && (
            <Button onClick={handlePublish}>
              <Send className="h-4 w-4 mr-2" />
              发布日报
            </Button>
          )}
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-muted-foreground" />
                  <span className="text-lg font-semibold">{report.report_date}</span>
                </div>
                <CardTitle className="text-2xl">{report.report_title || '无标题'}</CardTitle>
              </div>
              <Badge variant={report.published ? 'default' : 'secondary'} className="text-sm">
                {report.published ? '已发布' : '草稿'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground mb-1">事件数量</p>
                <p className="text-2xl font-bold">{report.event_count}</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground mb-1">生成时间</p>
                <p className="text-sm font-medium">{formatDate(report.generated_at)}</p>
              </div>
              {report.published && report.published_at && (
                <div className="p-4 bg-muted rounded-lg">
                  <p className="text-sm text-muted-foreground mb-1">发布时间</p>
                  <p className="text-sm font-medium">{formatDate(report.published_at)}</p>
                </div>
              )}
            </div>

            {report.report_content && (
              <div>
                <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  报告内容
                </h3>
                <div className="p-6 bg-muted rounded-lg">
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                    {report.report_content}
                  </pre>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {report.category_stats && (
                <div>
                  <h4 className="font-semibold mb-2">类别统计</h4>
                  <div className="p-4 bg-muted rounded-lg text-sm">
                    <pre className="whitespace-pre-wrap">{report.category_stats}</pre>
                  </div>
                </div>
              )}
              {report.severity_stats && (
                <div>
                  <h4 className="font-semibold mb-2">严重程度统计</h4>
                  <div className="p-4 bg-muted rounded-lg text-sm">
                    <pre className="whitespace-pre-wrap">{report.severity_stats}</pre>
                  </div>
                </div>
              )}
              {report.country_stats && (
                <div>
                  <h4 className="font-semibold mb-2">国家统计</h4>
                  <div className="p-4 bg-muted rounded-lg text-sm">
                    <pre className="whitespace-pre-wrap">{report.country_stats}</pre>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  )
}
