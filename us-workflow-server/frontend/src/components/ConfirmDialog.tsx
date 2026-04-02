import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { cn } from '../lib/utils'

interface ConfirmOptions {
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

interface ConfirmState extends ConfirmOptions {
  open: boolean
  resolve: ((v: boolean) => void) | null
}

interface ConfirmContextValue {
  confirm: (opts: ConfirmOptions) => Promise<boolean>
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null)

export function ConfirmDialogProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ConfirmState>({
    open: false,
    title: '',
    message: '',
    resolve: null,
  })
  const resolveRef = useRef<((v: boolean) => void) | null>(null)

  const confirm = useCallback((opts: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      resolveRef.current = resolve
      setState({ ...opts, open: true, resolve })
    })
  }, [])

  const handleClose = (result: boolean) => {
    setState(s => ({ ...s, open: false }))
    if (resolveRef.current) {
      resolveRef.current(result)
      resolveRef.current = null
    }
  }

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {state.open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 fade-in"
          style={{ background: 'rgba(15, 23, 42, 0.5)' }}
          onClick={() => handleClose(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl w-full max-w-md slide-up"
            onClick={e => e.stopPropagation()}
          >
            <div className="p-6">
              {state.danger && (
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="h-5 w-5 text-red-600" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-slate-900">{state.title}</h3>
                  </div>
                </div>
              )}
              {!state.danger && (
                <h3 className="text-base font-semibold text-slate-900 mb-3">{state.title}</h3>
              )}
              <p className="text-sm text-slate-600 leading-relaxed">{state.message}</p>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 pb-6">
              <button
                onClick={() => handleClose(false)}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 transition-colors"
              >
                {state.cancelText || '取消'}
              </button>
              <button
                onClick={() => handleClose(true)}
                className={cn(
                  'px-4 py-2 text-sm font-medium text-white rounded-md transition-colors',
                  state.danger
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-blue-700 hover:bg-blue-800'
                )}
              >
                {state.confirmText || '确认'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm(): (opts: ConfirmOptions) => Promise<boolean> {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm must be used within ConfirmDialogProvider')
  return ctx.confirm
}
