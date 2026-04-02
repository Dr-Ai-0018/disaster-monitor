import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../lib/api'
import { Shield, AlertCircle, Loader2 } from 'lucide-react'

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
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || '用户名或密码不正确')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      <div className="hidden lg:flex lg:w-2/5 bg-slate-900 flex-col justify-between p-12">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded bg-blue-600 flex items-center justify-center">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <span className="text-white font-semibold text-base">灾害监测后台</span>
        </div>

        <div className="space-y-6">
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-widest text-slate-500">处理流程</div>
            <div className="space-y-3 pt-2">
              {[
                { step: '01', label: '事件接入', desc: '自动采集全球灾害事件数据' },
                { step: '02', label: '影像审核', desc: '遥感影像质量人工复核' },
                { step: '03', label: '影像分析', desc: '触发分析，生成处置成果' },
                { step: '04', label: '摘要复核', desc: '内容审核，确认后纳入日报' },
                { step: '05', label: '日报发布', desc: '生成并发布每日报告' },
              ].map(item => (
                <div key={item.step} className="flex items-start gap-3">
                  <span className="text-xs font-mono text-blue-500 w-5 flex-shrink-0 mt-0.5">{item.step}</span>
                  <div>
                    <div className="text-sm font-medium text-slate-200">{item.label}</div>
                    <div className="text-xs text-slate-500">{item.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="text-xs text-slate-600">内部运营系统 · 仅限授权人员访问</div>
      </div>

      <div className="flex-1 flex items-center justify-center bg-slate-50 px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <div className="h-8 w-8 rounded bg-blue-700 flex items-center justify-center">
              <Shield className="h-4 w-4 text-white" />
            </div>
            <span className="text-slate-900 font-semibold">灾害监测后台</span>
          </div>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-slate-900">登录</h1>
            <p className="text-sm text-slate-500 mt-1">请使用分配的账户凭据登录</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-1.5">
                用户名
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                disabled={loading}
                required
                className="w-full h-10 px-3 text-sm border border-slate-300 rounded-md bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent disabled:bg-slate-100 disabled:cursor-not-allowed transition"
                placeholder="输入用户名"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1.5">
                密码
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                disabled={loading}
                required
                className="w-full h-10 px-3 text-sm border border-slate-300 rounded-md bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent disabled:bg-slate-100 disabled:cursor-not-allowed transition"
                placeholder="输入密码"
              />
            </div>

            {error && (
              <div className="flex items-start gap-2.5 rounded-md bg-red-50 border border-red-200 px-3 py-3">
                <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0 mt-0.5" />
                <span className="text-sm text-red-700">{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-10 bg-blue-700 hover:bg-blue-800 disabled:bg-blue-400 text-white text-sm font-semibold rounded-md transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  登录中
                </>
              ) : '登录'}
            </button>
          </form>

          <p className="mt-8 text-center text-xs text-slate-400">
            如需帮助，请联系管理员
          </p>
        </div>
      </div>
    </div>
  )
}
