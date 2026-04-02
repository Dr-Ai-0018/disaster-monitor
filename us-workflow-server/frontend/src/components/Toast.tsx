import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { X, CheckCircle2, AlertCircle, AlertTriangle, Info } from 'lucide-react'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface ToastItem {
  id: string
  type: ToastType
  title: string
  message?: string
  exiting?: boolean
}

interface ToastContextValue {
  success: (title: string, message?: string) => void
  error: (title: string, message?: string) => void
  warning: (title: string, message?: string) => void
  info: (title: string, message?: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const ICONS: Record<ToastType, React.ElementType> = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const STYLES: Record<ToastType, string> = {
  success: 'border-l-4 border-green-500 bg-white',
  error:   'border-l-4 border-red-500 bg-white',
  warning: 'border-l-4 border-amber-500 bg-white',
  info:    'border-l-4 border-blue-500 bg-white',
}

const ICON_COLORS: Record<ToastType, string> = {
  success: 'text-green-600',
  error:   'text-red-600',
  warning: 'text-amber-600',
  info:    'text-blue-600',
}

function ToastItem({ toast, onDismiss }: { toast: ToastItem; onDismiss: (id: string) => void }) {
  const Icon = ICONS[toast.type]
  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-md shadow-lg w-80 max-w-sm ${STYLES[toast.type]} ${toast.exiting ? 'toast-exit' : 'toast-enter'}`}
    >
      <Icon className={`h-5 w-5 mt-0.5 flex-shrink-0 ${ICON_COLORS[toast.type]}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900 leading-snug">{toast.title}</p>
        {toast.message && (
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">{toast.message}</p>
        )}
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="flex-shrink-0 text-slate-400 hover:text-slate-600 transition-colors"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t))
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 200)
    const t = timers.current.get(id)
    if (t) { clearTimeout(t); timers.current.delete(id) }
  }, [])

  const push = useCallback((type: ToastType, title: string, message?: string) => {
    const id = Math.random().toString(36).slice(2, 9)
    setToasts(prev => [...prev, { id, type, title, message }])
    const timer = setTimeout(() => dismiss(id), 5000)
    timers.current.set(id, timer)
  }, [dismiss])

  const value: ToastContextValue = {
    success: (t, m) => push('success', t, m),
    error:   (t, m) => push('error',   t, m),
    warning: (t, m) => push('warning', t, m),
    info:    (t, m) => push('info',    t, m),
  }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map(toast => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastItem toast={toast} onDismiss={dismiss} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
