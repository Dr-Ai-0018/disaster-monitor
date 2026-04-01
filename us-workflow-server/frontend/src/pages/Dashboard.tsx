import { useEffect, useState } from 'react'
import { Layout } from '../components/Layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { workflowApi } from '../lib/api'
import type { WorkflowOverview } from '../types'
import { Activity, CheckCircle2, Clock, AlertTriangle } from 'lucide-react'

export function Dashboard() {
  const [overview, setOverview] = useState<WorkflowOverview | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadOverview()
  }, [])

  const loadOverview = async () => {
    try {
      const data = await workflowApi.getOverview()
      setOverview(data)
    } catch (error) {
      console.error('Failed to load overview:', error)
    } finally {
      setLoading(false)
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

  if (!overview) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <div className="text-destructive">加载失败</div>
        </div>
      </Layout>
    )
  }

  const totalItems = overview.cards.reduce((sum, card) => sum + card.total, 0)
  const autoCards = overview.cards.filter(c => c.auto_mode === '自动')
  const manualCards = overview.cards.filter(c => c.auto_mode === '手动')

  return (
    <Layout>
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">仪表盘</h1>
          <p className="text-muted-foreground mt-2">
            五池工作流系统总览与监控
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                总事件数
              </CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalItems}</div>
              <p className="text-xs text-muted-foreground">
                跨五个工作流池
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                自动化池
              </CardTitle>
              <CheckCircle2 className="h-4 w-4 text-green-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{autoCards.length}</div>
              <p className="text-xs text-muted-foreground">
                {overview.automation_scope}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                人工审核池
              </CardTitle>
              <Clock className="h-4 w-4 text-orange-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{manualCards.length}</div>
              <p className="text-xs text-muted-foreground">
                {overview.review_scope}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                服务状态
              </CardTitle>
              <AlertTriangle className="h-4 w-4 text-blue-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold capitalize">{overview.service_status}</div>
              <p className="text-xs text-muted-foreground">
                工作流服务器
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {overview.cards.map((card) => (
            <Card key={card.key} className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{card.label}</CardTitle>
                  <div className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    card.auto_mode === '自动' 
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' 
                      : 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
                  }`}>
                    {card.auto_mode}
                  </div>
                </div>
                <CardDescription className="text-sm">
                  {card.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-bold">{card.total}</span>
                  <span className="text-sm text-muted-foreground">事件</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </Layout>
  )
}
