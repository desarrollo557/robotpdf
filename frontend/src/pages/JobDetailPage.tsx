import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import axios from 'axios'
import ResolutionList from '../components/ResolutionList'
import PageList from '../components/PageList'
import ProgressBar from '../components/ProgressBar'
import { API_BASE_URL } from '../api/client'

interface JobDetailPageProps {
  toggleStats: (jobId?: number) => void
}

interface Job {
  id: number
  filename: string
  original_filename: string
  total_pages: number
  status: string
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  processed_pages: number
  failed_pages: number
  output_zip_path: string | null
  error_message: string | null
  progress: any
}

function JobDetailPage({ toggleStats }: JobDetailPageProps) {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'resolutions' | 'pages'>('resolutions')

  const { data: job, isLoading, error, refetch } = useQuery({
    queryKey: ['job', jobId],
    queryFn: async () => {
      const response = await axios.get(`${API_BASE_URL}/api/jobs/${jobId}/status`)
      return response.data as Job
    },
    refetchInterval: 2000,
  })

  useEffect(() => {
    if (error) {
      toast.error('Error al cargar el trabajo')
    }
  }, [error])

  const handleDownloadZip = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/download/${jobId}/zip`, {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${job?.original_filename || 'resoluciones'}.zip`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success('Descarga iniciada')
    } catch (err) {
      toast.error('No se pudo descargar el ZIP')
    }
  }

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto card">
          <div className="flex items-center justify-center h-64">
            <div className="loading-spinner" />
            <span className="ml-4 text-gray-600">Cargando...</span>
          </div>
        </div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto card text-center py-12">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">
            Trabajo no encontrado
          </h2>
          <a href="/jobs" className="btn btn-primary">
            Volver a trabajos
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-4">
                <button
                  onClick={() => navigate('/jobs')}
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-6 w-6 text-gray-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 19l-7-7 7-7"
                    />
                  </svg>
                </button>
                <h1 className="text-3xl font-bold text-gray-900">
                  {job.original_filename}
                </h1>
              </div>
              <p className="text-gray-600 mt-2">
                Trabajo #{job.id} | {job.total_pages} páginas
              </p>
            </div>
            <div className="flex items-center gap-4">
              {job.status === 'completed' && (
                <button
                  onClick={handleDownloadZip}
                  className="btn btn-success"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-5 w-5 mr-2"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Descargar Todo (ZIP)
                </button>
              )}
              <button
                onClick={() => toggleStats(job.id)}
                className="btn btn-outline"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-5 w-5 mr-2"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
                    clipRule="evenodd"
                  />
                  <path d="M2 10h2v5H2v-5zm2-4h2v2H4V6zm6-4h2v2h-2V2zm2 4h2v2h-2V6zm2 4h2v2h-2v-2z" />
                </svg>
                Estadísticas en Tiempo Real
              </button>
            </div>
          </div>
        </header>

        {/* Status */}
        <div className="card mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="stat-card">
              <div className="stat-value">
                {getStatusBadge(job.status)}
              </div>
              <div className="stat-label">Estado</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">
                {job.processed_pages} / {job.total_pages}
              </div>
              <div className="stat-label">Páginas Procesadas</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-red-600">
                {job.failed_pages}
              </div>
              <div className="stat-label">Páginas con Error</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">
                {job.progress?.overall_progress?.toFixed(1) || 0}%
              </div>
              <div className="stat-label">Progreso</div>
            </div>
          </div>

          {/* Progress Bar */}
          {job.status === 'processing' && (
            <div className="mt-6">
              <ProgressBar
                value={job.progress?.overall_progress || 0}
                className="h-4"
              />
              <div className="flex items-center justify-between mt-2 text-sm text-gray-500">
                <span>Procesando...</span>
                {job.progress?.eta_seconds && (
                  <span>
                    Tiempo estimado: {formatETA(job.progress.eta_seconds)}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="card">
          <div className="border-b border-gray-200 mb-6">
            <nav className="-mb-px flex space-x-8" aria-label="Tabs">
              <button
                onClick={() => setActiveTab('resolutions')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'resolutions'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Resoluciones Detectadas ({job.progress?.resolution_groups?.length || 0})
              </button>
              <button
                onClick={() => setActiveTab('pages')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'pages'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Páginas ({job.total_pages})
              </button>
            </nav>
          </div>

          {/* Tab Content */}
          <div className="min-h-[400px]">
            {activeTab === 'resolutions' ? (
              <ResolutionList jobId={job.id} />
            ) : (
              <PageList jobId={job.id} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'completed':
      return (
        <span className="badge-success">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4 mr-1"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
          Completado
        </span>
      )
    case 'processing':
      return (
        <span className="badge-info">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4 mr-1 animate-spin"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
              clipRule="evenodd"
            />
          </svg>
          Procesando
        </span>
      )
    case 'failed':
      return (
        <span className="badge-error">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4 mr-1"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1zm-4 4a1 1 0 100-2 1 1 0 000 2z"
              clipRule="evenodd"
            />
          </svg>
          Error
        </span>
      )
    case 'pending':
      return (
        <span className="badge-warning">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4 mr-1"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
              clipRule="evenodd"
            />
          </svg>
          Pendiente
        </span>
      )
    default:
      return <span className="badge-info">{status}</span>
  }
}

function formatETA(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)} segundos`
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)} minutos`
  }
  return `${Math.round(seconds / 3600)} horas`
}

export default JobDetailPage
