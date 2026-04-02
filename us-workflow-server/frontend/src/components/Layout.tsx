import { useState, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, ClipboardList, FileText, LogOut, Shield, Menu, X } from 'lucide-react'
import { cn } from '../lib/utils'

interface LayoutProps {
  children: ReactNode
}

const navItems = [
  { path: '/dashboard', label: '今日概览', icon: LayoutDashboard },
  { path: '/tasks',     label: '事件处理', icon: ClipboardList },
  { path: '/reports',   label: '日报',     icon: FileText },
]

export function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const isActive = (path: string) =>
    path === '/dashboard'
      ? location.pathname === '/' || location.pathname === '/dashboard'
      : location.pathname.startsWith(path)

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      <div className="px-5 py-5 border-b border-white/10">
        <Link to="/dashboard" className="flex items-center gap-3 group" onClick={() => setMobileOpen(false)}>
          <div className="h-8 w-8 rounded bg-blue-600 flex items-center justify-center flex-shrink-0">
            <Shield className="h-4 w-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white leading-tight">灾害监测后台</div>
            <div className="text-xs text-slate-400 leading-tight">监控 · 审核 · 日报</div>
          </div>
        </Link>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map(item => {
          const Icon = item.icon
          const active = isActive(item.path)
          return (
            <Link
              key={item.path}
              to={item.path}
              onClick={() => setMobileOpen(false)}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
                active
                  ? 'bg-blue-700 text-white'
                  : 'text-slate-300 hover:bg-white/10 hover:text-white'
              )}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="px-3 pb-4 border-t border-white/10 pt-3">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-slate-400 hover:bg-white/10 hover:text-white transition-colors w-full text-left"
        >
          <LogOut className="h-4 w-4 flex-shrink-0" />
          退出登录
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden lg:flex flex-col w-56 flex-shrink-0 bg-slate-900 fixed inset-y-0 left-0 z-30">
        <SidebarContent />
      </aside>

      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="fixed inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="relative flex flex-col w-56 bg-slate-900 z-50">
            <button
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
              onClick={() => setMobileOpen(false)}
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent />
          </aside>
        </div>
      )}

      <div className="lg:pl-56 flex-1 flex flex-col min-w-0">
        <header className="lg:hidden sticky top-0 z-20 bg-slate-900 px-4 h-14 flex items-center gap-3">
          <button onClick={() => setMobileOpen(true)} className="text-slate-300 hover:text-white">
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-blue-400" />
            <span className="text-sm font-semibold text-white">灾害监测后台</span>
          </div>
        </header>

        <main className="flex-1 px-6 py-6 lg:px-8 lg:py-7 min-w-0">
          {children}
        </main>
      </div>
    </div>
  )
}
