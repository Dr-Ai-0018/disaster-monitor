import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { workflowApi } from '../lib/api'
import type { WorkflowItemDetail } from '../types'
import { formatDate } from '../lib/utils'
import { ArrowLeft, Image, Zap, FileText, CheckCircle, XCircle, RotateCcw } from 'lucide-react'

export function ItemDetail() {
  const { uuid } = useParams<{ uuid: string }>()
  const navigate = useNavigate()
  const [item, setItem] = useState<WorkflowItemDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (uuid) loadItem()
  }, [uuid])

  const loadItem = async () => {
    if (!uuid) return
    try {
      const data = await workflowApi.getItemDetail(uuid)
      setItem(data)
    } catch (error) {
      console.error('Failed to load item:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAction = async (action: string) => {
    if (!uuid) return
    
    try {
      switch (action) {
        case 'approve_image':
          await workflowApi.reviewImage(uuid, true, 'post')
          alert('影像审核通过')
          break
        case 'reject_image':
          const reason = prompt('请输入打回原因')
          if (!reason) return
          await workflowApi.reviewImage(uuid, false, undefined, reason)
          alert('影像已打回')
          break
        case 'trigger_inference':
          await workflowApi.triggerInference(uuid)
          alert('推理已触发')
          break
        case 'generate_summary':
          await workflowApi.generateSummary(uuid)
          alert('摘要生成成功')
          break
        case 'approve_summary':
          const today = new Date().toISOString().split('T')[0]
          await workflowApi.approveSummary(uuid, true, undefined, today)
          alert('摘要已通过并准入日报')
          break
        case 'reject_summary':
          const rejectReason = prompt('请输入打回原因')
          if (!rejectReason) return
          await workflowApi.approveSummary(uuid, false, rejectReason)
          alert('摘要已打回')
          break
        case 'reset_inference':
          if (!confirm('确定要重置推理和摘要吗？')) return
          await workflowApi.resetInference(uuid)
          alert('推理和摘要已重置')
          break
      }
      await loadItem()
    } catch (error: any) {
      alert(`操作失败: ${error.response?.data?.detail || error.message}`)
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

  if (!item) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <div className="text-destructive">事件不存在</div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回
          </Button>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>基本信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <span className="text-sm text-muted-foreground">UUID</span>
                <p className="font-mono text-sm">{item.uuid}</p>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">标题</span>
                <p className="font-medium">{item.title || '-'}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-sm text-muted-foreground">国家</span>
                  <p>{item.country || '-'}</p>
                </div>
                <div>
                  <span className="text-sm text-muted-foreground">严重程度</span>
                  <p>
                    <Badge variant={
                      item.severity === 'red' ? 'destructive' : 
                      item.severity === 'orange' ? 'default' : 'secondary'
                    }>
                      {item.severity || '-'}
                    </Badge>
                  </p>
                </div>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">类别</span>
                <p>{item.category || '-'}</p>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">地址</span>
                <p className="text-sm">{item.address || '-'}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-sm text-muted-foreground">经度</span>
                  <p className="text-sm">{item.longitude || '-'}</p>
                </div>
                <div>
                  <span className="text-sm text-muted-foreground">纬度</span>
                  <p className="text-sm">{item.latitude || '-'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>工作流状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <span className="text-sm text-muted-foreground">当前池</span>
                <p className="font-medium">{item.pool}</p>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">池状态</span>
                <p>{item.pool_status}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-sm text-muted-foreground">影像状态</span>
                  <p><Badge variant="outline">{item.imagery}</Badge></p>
                </div>
                <div>
                  <span className="text-sm text-muted-foreground">质检状态</span>
                  <p><Badge variant="outline">{item.quality}</Badge></p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-sm text-muted-foreground">推理状态</span>
                  <p><Badge variant="outline">{item.inference}</Badge></p>
                </div>
                <div>
                  <span className="text-sm text-muted-foreground">摘要状态</span>
                  <p><Badge variant="outline">{item.summary}</Badge></p>
                </div>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">最后操作人</span>
                <p>{item.last_operator || '-'}</p>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">更新时间</span>
                <p className="text-sm">{formatDate(item.updated_at)}</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {item.pool === 'image_review_pool' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Image className="h-5 w-5" />
                影像审核
              </CardTitle>
              <CardDescription>审核影像质量，决定是否进入推理流程</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Button onClick={() => handleAction('approve_image')}>
                  <CheckCircle className="h-4 w-4 mr-2" />
                  通过审核
                </Button>
                <Button variant="destructive" onClick={() => handleAction('reject_image')}>
                  <XCircle className="h-4 w-4 mr-2" />
                  打回重新处理
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {item.pool === 'inference_pool' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5" />
                推理控制
              </CardTitle>
              <CardDescription>触发 Latest Model API 推理</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {item.task_status && (
                <div className="p-4 bg-muted rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">任务状态</span>
                    <Badge>{item.task_status}</Badge>
                  </div>
                  {item.task_progress_message && (
                    <p className="text-sm text-muted-foreground">{item.task_progress_message}</p>
                  )}
                  {item.task_failure_reason && (
                    <p className="text-sm text-destructive">{item.task_failure_reason}</p>
                  )}
                </div>
              )}
              <div className="flex gap-2">
                <Button onClick={() => handleAction('trigger_inference')}>
                  <Zap className="h-4 w-4 mr-2" />
                  触发推理
                </Button>
                <Button variant="outline" onClick={() => handleAction('reset_inference')}>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  重置推理
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {item.pool === 'summary_report_pool' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                摘要与日报
              </CardTitle>
              <CardDescription>生成摘要、审核并准入日报候选</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {item.summary_text && (
                <div className="p-4 bg-muted rounded-lg">
                  <p className="text-sm whitespace-pre-wrap">{item.summary_text}</p>
                </div>
              )}
              <div className="flex gap-2 flex-wrap">
                <Button variant="outline" onClick={() => handleAction('generate_summary')}>
                  <FileText className="h-4 w-4 mr-2" />
                  生成摘要
                </Button>
                {item.summary_text && (
                  <>
                    <Button onClick={() => handleAction('approve_summary')}>
                      <CheckCircle className="h-4 w-4 mr-2" />
                      通过并准入日报
                    </Button>
                    <Button variant="destructive" onClick={() => handleAction('reject_summary')}>
                      <XCircle className="h-4 w-4 mr-2" />
                      打回摘要
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  )
}
