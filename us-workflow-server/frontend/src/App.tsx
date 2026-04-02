import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import { ConfirmDialogProvider } from './components/ConfirmDialog'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { Tasks } from './pages/Tasks'
import { Reports } from './pages/Reports'
import { ItemDetail } from './pages/ItemDetail'
import { ReportDetail } from './pages/ReportDetail'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('token')
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <ConfirmDialogProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<PrivateRoute><Navigate to="/dashboard" replace /></PrivateRoute>} />
            <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
            <Route path="/tasks" element={<PrivateRoute><Tasks /></PrivateRoute>} />
            <Route path="/pools" element={<PrivateRoute><Navigate to="/tasks" replace /></PrivateRoute>} />
            <Route path="/reports" element={<PrivateRoute><Reports /></PrivateRoute>} />
            <Route path="/item/:uuid" element={<PrivateRoute><ItemDetail /></PrivateRoute>} />
            <Route path="/report/:reportDate" element={<PrivateRoute><ReportDetail /></PrivateRoute>} />
          </Routes>
        </ConfirmDialogProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}

export default App
