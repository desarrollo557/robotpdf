import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'
import toast from 'react-hot-toast'

// Configuration
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export const API_BASE_URL = API_BASE
export const WS_BASE_URL = WS_BASE

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config: AxiosRequestConfig) => {
    // Add auth token if available
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  (error: AxiosError) => {
    if (error.response) {
      const { status, data } = error.response
      
      // Handle specific error codes
      switch (status) {
        case 400:
          toast.error(data?.detail || 'Solicitud inválida')
          break
        case 401:
          toast.error('No autorizado')
          break
        case 403:
          toast.error('Prohibido')
          break
        case 404:
          toast.error('Recurso no encontrado')
          break
        case 413:
          toast.error(data?.detail || 'Archivo demasiado grande')
          break
        case 500:
          toast.error('Error interno del servidor')
          break
        default:
          toast.error('Ocurrió un error')
      }
    } else if (error.request) {
      // Network error
      toast.error('Error de conexión')
    }
    
    return Promise.reject(error)
  }
)

// Job API
export const jobApi = {
  // Create a new job by uploading a PDF
  uploadPDF: (file: File, onUploadProgress?: (progress: number) => void) => {
    const formData = new FormData()
    formData.append('file', file)
    
    return api.post('/api/jobs/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onUploadProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
          onUploadProgress(percentCompleted)
        }
      },
    })
  },

  // Get all jobs
  getJobs: (params?: { status?: string; limit?: number; offset?: number }) => {
    return api.get('/api/jobs', { params })
  },

  // Get job status
  getJobStatus: (jobId: number) => {
    return api.get(`/api/jobs/${jobId}/status`)
  },

  // Get job pages
  getJobPages: (jobId: number) => {
    return api.get(`/api/jobs/${jobId}/pages`)
  },

  // Get job resolutions
  getJobResolutions: (jobId: number) => {
    return api.get(`/api/jobs/${jobId}/resolutions`)
  },

  // Delete a job
  deleteJob: (jobId: number) => {
    return api.delete(`/api/jobs/${jobId}`)
  },

  // Get job statistics
  getJobStatistics: (jobId: number) => {
    return api.get(`/api/download/${jobId}/statistics`)
  },
}

// Download API
export const downloadApi = {
  // Download ZIP for a job
  downloadJobZip: (jobId: number) => {
    return api.get(`/api/download/${jobId}/zip`, {
      responseType: 'blob',
    })
  },

  // Download a single resolution PDF
  downloadResolutionPDF: (jobId: number, resolutionId: number) => {
    return api.get(`/api/download/${jobId}/resolution/${resolutionId}`, {
      responseType: 'blob',
    })
  },

  // Download resolution PDF by code
  downloadResolutionPDFByCode: (jobId: number, resolutionCode: string) => {
    return api.get(`/api/download/${jobId}/resolution/by-code/${encodeURIComponent(resolutionCode)}`, {
      responseType: 'blob',
    })
  },

  // Download page image
  downloadPageImage: (jobId: number, pageNumber: number) => {
    return api.get(`/api/download/${jobId}/page/${pageNumber}`, {
      responseType: 'blob',
    })
  },

  // Get OCR text for a page
  getPageOcrText: (jobId: number, pageNumber: number) => {
    return api.get(`/api/download/${jobId}/ocr-text/${pageNumber}`)
  },
}

// Health check
export const healthApi = {
  check: () => {
    return api.get('/health')
  },
}

// WebSocket API
export const wsApi = {
  // Get WebSocket URL for a job
  getJobWsUrl: (jobId: number) => {
    return `${WS_BASE_URL}/ws/${jobId}`
  },

  // Get general WebSocket URL
  getGeneralWsUrl: () => {
    return `${WS_BASE_URL}/ws`
  },
}

// Export the configured axios instance
export default api
