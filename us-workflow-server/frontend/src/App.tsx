import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Login } from './pages/Login'
import { Overview } from './pages/Overview'
import { Dashboard } from './pages/Dashboard'
import { Pools } from './pages/Pools'
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
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<PrivateRoute><Overview /></PrivateRoute>} />
        <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/pools" element={<PrivateRoute><Pools /></PrivateRoute>} />
        <Route path="/reports" element={<PrivateRoute><Reports /></PrivateRoute>} />
        <Route path="/item/:uuid" element={<PrivateRoute><ItemDetail /></PrivateRoute>} />
        <Route path="/report/:reportDate" element={<PrivateRoute><ReportDetail /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
