import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table'
import { workflowApi } from '../lib/api'
import type { WorkflowItem, WorkflowOverview } from '../types'
import { formatDate } from '../lib/utils'
import { RefreshCw, Eye, CheckCircle, XCircle, Zap, FileText } from 'lucide-react'

export function Pools() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const currentPool = searchParams.get('pool') || 'event_pool'
  
  const [overview, setOverview] = useState<WorkflowOverview | null>(null)
  const [items, setItems] = useState<WorkflowItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadData()
  }, [currentPool])

  const loadData = async () => {
    setLoading(true)
    try {
      const [overviewData, itemsData] = await Promise.all([
        workflowApi.getOverview(),
        workflowApi.getItems(currentPool, 50)
      ])
      setOverview(overviewData)
      setItems(itemsData.data)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handlePoolChange = (pool: string) => {
    setSearchParams({ pool })
    setSelectedItems(new Set())
  }

  const handleSelectItem = (uuid: string) => {
    const newSelected = new Set(selectedItems)
    if (newSelected.has(uuid)) {
      newSelected.delete(uuid)
    } else {
      newSelected.add(uuid)
    }
    setSelectedItems(newSelected)
  }

  const handleSelectAll = () => {
    if (selectedItems.size === items.length) {
      setSelectedItems(new Set())
    } else {
      setSelectedItems(new Set(items.map(item => item.uuid)))
    }
  }

  const handleBatchAction = async (action: string) => {
    if (selectedItems.size === 0) {
      alert('请先选择项目')
      return
    }

    const uuids = Array.from(selectedItems)
    
    try {
      setLoading(true)
      
      switch (action) {
        case 'approve_image':
          await workflowApi.batchReviewImage(uuids, true, 'post')
          alert(`批量通过影像审核成功: ${uuids.length} 项`)
          break
        case 'reject_image':
          await workflowApi.batchReviewImage(uuids, false, undefined, '不符合要求')
          alert(`批量打回影像成功: ${uuids.length} 项`)
          break
        case 'trigger_inference':
          await workflowApi.batchTriggerInference(uuids)
          alert(`批量触发推理成功: ${uuids.length} 项`)
          break
        case 'generate_summary':
          await workflowApi.batchGenerateSummary(uuids)
          alert(`批量生成摘要成功: ${uuids.length} 项`)
          break
        case 'approve_summary':
          const today = new Date().toISOString().split('T')[0]
          await workflowApi.batchApproveSummary(uuids, true, undefined, today)
          alert(`批量通过摘要并准入日报成功: ${uuids.length} 项`)
          break
      }
      
      await loadData()
      setSelectedItems(new Set())
    } catch (error: any) {
      alert(`操作失败: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const currentCard = overview?.cards.find(c => c.key === currentPool)

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">工作流池管理</h1>
            <p className="text-muted-foreground mt-2">
              五池协同工作流 - {currentCard?.label || ''}
            </p>
          </div>
          <Button onClick={loadData} variant="outline" disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>

        <div className="flex gap-2 flex-wrap">
          {overview?.cards.map((card) => (
            <Button
              key={card.key}
              variant={currentPool === card.key ? 'default' : 'outline'}
              onClick={() => handlePoolChange(card.key)}
              className="flex items-center gap-2"
            >
              {card.label}
              <Badge variant="secondary" className="ml-1">
                {card.total}
              </Badge>
            </Button>
          ))}
        </div>

        {currentCard && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{currentCard.label}</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    {currentCard.description}
                  </p>
                </div>
                <Badge variant={currentCard.auto_mode === '自动' ? 'default' : 'secondary'}>
                  {currentCard.auto_mode}模式
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              {selectedItems.size > 0 && (
                <div className="mb-4 p-4 bg-muted rounded-lg flex items-center justify-between">
                  <span className="text-sm font-medium">
                    已选择 {selectedItems.size} 项
                  </span>
                  <div className="flex gap-2">
                    {currentPool === 'image_review_pool' && (
                      <>
                        <Button size="sm" variant="default" onClick={() => handleBatchAction('approve_image')}>
                          <CheckCircle className="h-4 w-4 mr-1" />
                          批量通过
                        </Button>
                        <Button size="sm" variant="destructive" onClick={() => handleBatchAction('reject_image')}>
                          <XCircle className="h-4 w-4 mr-1" />
                          批量打回
                        </Button>
                      </>
                    )}
                    {currentPool === 'inference_pool' && (
                      <Button size="sm" onClick={() => handleBatchAction('trigger_inference')}>
                        <Zap className="h-4 w-4 mr-1" />
                        批量触发推理
                      </Button>
                    )}
                    {currentPool === 'summary_report_pool' && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => handleBatchAction('generate_summary')}>
                          <FileText className="h-4 w-4 mr-1" />
                          批量生成摘要
                        </Button>
                        <Button size="sm" onClick={() => handleBatchAction('approve_summary')}>
                          <CheckCircle className="h-4 w-4 mr-1" />
                          批量准入日报
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              )}

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <input
                        type="checkbox"
                        checked={items.length > 0 && selectedItems.size === items.length}
                        onChange={handleSelectAll}
                        className="rounded border-gray-300"
                      />
                    </TableHead>
                    <TableHead>标题</TableHead>
                    <TableHead>国家</TableHead>
                    <TableHead>严重程度</TableHead>
                    <TableHead>池状态</TableHead>
                    <TableHead>影像</TableHead>
                    <TableHead>质检</TableHead>
                    <TableHead>推理</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={10} className="text-center py-8 text-muted-foreground">
                        {loading ? '加载中...' : '暂无数据'}
                      </TableCell>
                    </TableRow>
                  ) : (
                    items.map((item) => (
                      <TableRow key={item.uuid} className={selectedItems.has(item.uuid) ? 'bg-muted/50' : ''}>
                        <TableCell>
                          <input
                            type="checkbox"
                            checked={selectedItems.has(item.uuid)}
                            onChange={() => handleSelectItem(item.uuid)}
                            className="rounded border-gray-300"
                          />
                        </TableCell>
                        <TableCell className="font-medium max-w-xs truncate">
                          {item.title || '-'}
                        </TableCell>
                        <TableCell>{item.country || '-'}</TableCell>
                        <TableCell>
                          <Badge variant={
                            item.severity === 'red' ? 'destructive' : 
                            item.severity === 'orange' ? 'default' : 'secondary'
                          }>
                            {item.severity || '-'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className="text-xs">{item.pool_status}</span>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{item.imagery}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{item.quality}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{item.inference}</Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(item.updated_at)}
                        </TableCell>
                        <TableCell>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => navigate(`/item/${item.uuid}`)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  )
}
