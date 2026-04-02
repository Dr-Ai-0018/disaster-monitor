import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Card } from '../components/ui/card'
import { authApi } from '../lib/api'
import { Globe, Lock, User, AlertCircle, ArrowRight, Shield, Activity, Database } from 'lucide-react'

export function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await authApi.login(username, password)
      localStorage.setItem('token', response.access_token)
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || '登录失败，请检查用户名和密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 p-12 flex-col justify-between relative overflow-hidden">
        {/* Animated Background Pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 -left-4 w-72 h-72 bg-white rounded-full mix-blend-multiply filter blur-xl animate-blob"></div>
          <div className="absolute top-0 -right-4 w-72 h-72 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl animate-blob animation-delay-2000"></div>
          <div className="absolute -bottom-8 left-20 w-72 h-72 bg-indigo-300 rounded-full mix-blend-multiply filter blur-xl animate-blob animation-delay-4000"></div>
        </div>

        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-8">
            <div className="h-12 w-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Globe className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">灾害监测平台</h1>
              <p className="text-blue-100 text-sm">Disaster Monitor</p>
            </div>
          </div>
        </div>

        <div className="relative z-10 space-y-6">
          <h2 className="text-4xl font-bold text-white leading-tight">
            智能灾害监测<br />工作流管理系统
          </h2>
          <p className="text-blue-100 text-lg leading-relaxed">
            集成 RSOE 实时监测、GEE 影像分析、AI 质检推理、Gemini 智能摘要的全流程灾害应急响应平台
          </p>
          
          <div className="grid grid-cols-2 gap-4 pt-8">
            <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
              <Activity className="h-6 w-6 text-white mb-2" />
              <div className="text-white font-semibold">实时监测</div>
              <div className="text-blue-100 text-sm">24/7 全球灾害追踪</div>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
              <Database className="h-6 w-6 text-white mb-2" />
              <div className="text-white font-semibold">五池工作流</div>
              <div className="text-blue-100 text-sm">自动化处理流程</div>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
              <Shield className="h-6 w-6 text-white mb-2" />
              <div className="text-white font-semibold">AI 推理</div>
              <div className="text-blue-100 text-sm">智能分析与预测</div>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
              <Globe className="h-6 w-6 text-white mb-2" />
              <div className="text-white font-semibold">全球覆盖</div>
              <div className="text-blue-100 text-sm">多源数据融合</div>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-blue-100 text-sm">
          © 2024 Disaster Monitor. Enterprise Edition.
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="h-12 w-12 rounded-xl bg-blue-600 flex items-center justify-center">
              <Globe className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">灾害监测平台</h1>
              <p className="text-slate-600 text-sm">Disaster Monitor</p>
            </div>
          </div>

          <Card className="border-slate-200 shadow-xl">
            <div className="p-8">
              <div className="mb-8">
                <h2 className="text-3xl font-bold text-slate-900 mb-2">欢迎回来</h2>
                <p className="text-slate-600">登录您的账户以访问工作流管理系统</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <label htmlFor="username" className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    <User className="h-4 w-4" />
                    用户名
                  </label>
                  <Input
                    id="username"
                    type="text"
                    placeholder="请输入用户名"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={loading}
                    required
                    className="h-12 text-base"
                  />
                </div>

                <div className="space-y-2">
                  <label htmlFor="password" className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    <Lock className="h-4 w-4" />
                    密码
                  </label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="请输入密码"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                    required
                    className="h-12 text-base"
                  />
                </div>

                {error && (
                  <div className="flex items-start gap-3 rounded-lg bg-red-50 border border-red-200 p-4">
                    <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <div className="text-sm text-red-800">{error}</div>
                  </div>
                )}

                <Button
                  type="submit"
                  className="w-full h-12 text-base font-semibold bg-blue-600 hover:bg-blue-700"
                  disabled={loading}
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      登录中...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      登录
                      <ArrowRight className="h-5 w-5" />
                    </span>
                  )}
                </Button>
              </form>

              <div className="mt-8 pt-6 border-t border-slate-200">
                <div className="text-center text-sm text-slate-600">
                  需要帮助？请联系系统管理员
                </div>
              </div>
            </div>
          </Card>

          <div className="mt-8 text-center text-sm text-slate-500">
            <p>使用本系统即表示您同意我们的服务条款和隐私政策</p>
          </div>
        </div>
      </div>
    </div>
  )
}
