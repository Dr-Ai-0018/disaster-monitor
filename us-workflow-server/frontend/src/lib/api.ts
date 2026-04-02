import axios from 'axios'
import type { 
  WorkflowOverview, 
  WorkflowItemListResult,
  WorkflowItemDetail,
  ReportCandidate,
  DailyReport,
  LoginResponse,
  BatchActionResponse
} from '../types'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const { data } = await api.post<LoginResponse>('/auth/login', { username, password })
    return data
  },
  refresh: async (): Promise<LoginResponse> => {
    const { data } = await api.post<LoginResponse>('/auth/refresh')
    return data
  },
}

export const workflowApi = {
  getOverview: async (): Promise<WorkflowOverview> => {
    const { data } = await api.get<WorkflowOverview>('/workflow/overview')
    return data
  },
  
  getItems: async (
    pool: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<WorkflowItemListResult> => {
    const { data } = await api.get('/workflow/items', {
      params: { pool, page, page_size: pageSize },
    })
    return data
  },

  getItemSelection: async (pool: string): Promise<{ total: number; uuids: string[] }> => {
    const { data } = await api.get('/workflow/items/selection', { params: { pool } })
    return data
  },
  
  getItemDetail: async (uuid: string): Promise<WorkflowItemDetail> => {
    const { data } = await api.get<WorkflowItemDetail>(`/workflow/items/${uuid}`)
    return data
  },
  
  resetInference: async (uuid: string): Promise<{ message: string; affected: number }> => {
    const { data } = await api.post(`/workflow/items/${uuid}/reset-inference`)
    return data
  },
  
  batchResetInference: async (uuids: string[]): Promise<BatchActionResponse> => {
    const { data } = await api.post('/workflow/items/batch-reset-inference', { uuids })
    return data
  },
  
  resetStage: async (uuid: string, stage: string): Promise<{ message: string; affected: number }> => {
    const { data } = await api.post(`/workflow/items/${uuid}/reset-stage`, { stage })
    return data
  },
  
  batchResetStage: async (uuids: string[], stage: string): Promise<BatchActionResponse> => {
    const { data } = await api.post('/workflow/items/batch-reset-stage', { uuids, stage })
    return data
  },

  rollbackPrevious: async (uuid: string): Promise<{ message: string; affected: number }> => {
    const { data } = await api.post(`/workflow/items/${uuid}/rollback-previous`)
    return data
  },

  batchRollbackPrevious: async (uuids: string[]): Promise<BatchActionResponse> => {
    const { data } = await api.post('/workflow/items/batch-rollback-previous', { uuids })
    return data
  },
  
  reviewImage: async (
    uuid: string, 
    approved: boolean, 
    image_type?: string, 
    reason?: string
  ): Promise<{ message: string; affected: number }> => {
    const { data } = await api.post(`/workflow/items/${uuid}/image-review`, {
      approved,
      image_type,
      reason,
    })
    return data
  },
  
  batchReviewImage: async (
    uuids: string[], 
    approved: boolean, 
    image_type?: string, 
    reason?: string
  ): Promise<BatchActionResponse> => {
    const { data } = await api.post('/workflow/items/batch-image-review', {
      uuids,
      approved,
      image_type,
      reason,
    })
    return data
  },
  
  triggerInference: async (uuid: string, selected_image_type?: string): Promise<{ message: string; affected: number }> => {
    const { data } = await api.post(`/workflow/items/${uuid}/trigger-inference`, { selected_image_type })
    return data
  },
  
  batchTriggerInference: async (uuids: string[], selected_image_type?: string): Promise<BatchActionResponse> => {
    const { data } = await api.post('/workflow/items/batch-trigger-inference', { uuids, selected_image_type })
    return data
  },
  
  generateSummary: async (uuid: string, persist: boolean = true): Promise<{ message: string; affected: number }> => {
    const { data } = await api.post(`/workflow/items/${uuid}/generate-summary`, { persist })
    return data
  },
  
  batchGenerateSummary: async (uuids: string[], persist: boolean = true): Promise<BatchActionResponse> => {
    const { data } = await api.post('/workflow/items/batch-generate-summary', { uuids, persist })
    return data
  },
  
  approveSummary: async (
    uuid: string, 
    approved: boolean, 
    reason?: string, 
    report_date?: string
  ): Promise<{ message: string; affected: number }> => {
    const { data } = await api.post(`/workflow/items/${uuid}/summary-approval`, {
      approved,
      reason,
      report_date,
    })
    return data
  },
  
  batchApproveSummary: async (
    uuids: string[], 
    approved: boolean, 
    reason?: string, 
    report_date?: string
  ): Promise<BatchActionResponse> => {
    const { data } = await api.post('/workflow/items/batch-summary-approval', {
      uuids,
      approved,
      reason,
      report_date,
    })
    return data
  },
  
  removeReportCandidate: async (uuid: string): Promise<{ message: string; affected: number }> => {
    const { data } = await api.post(`/workflow/items/${uuid}/remove-report-candidate`)
    return data
  },
}

export const reportApi = {
  getCandidates: async (report_date: string): Promise<{ total: number; data: ReportCandidate[] }> => {
    const { data } = await api.get('/workflow/report-candidates', { params: { report_date } })
    return data
  },
  
  getReports: async (limit: number = 20): Promise<{ total: number; data: DailyReport[] }> => {
    const { data } = await api.get('/workflow/reports', { params: { limit } })
    return data
  },
  
  getReportDetail: async (report_date: string): Promise<DailyReport> => {
    const { data } = await api.get<DailyReport>(`/workflow/reports/${report_date}`)
    return data
  },
  
  generateReport: async (report_date: string): Promise<{
    message: string
    report_date: string
    report_title?: string
    event_count: number
    published: boolean
  }> => {
    const { data } = await api.post('/workflow/reports/generate', { report_date })
    return data
  },
  
  publishReport: async (report_date: string): Promise<{ message: string; affected: number }> => {
    const { data } = await api.post(`/workflow/reports/${report_date}/publish`)
    return data
  },
}

export default api
