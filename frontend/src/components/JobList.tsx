import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { jobApi } from '../api/client'
import ProgressBar from './ProgressBar'
import { getStatusBadge } from '../utils/status'

interface Job {
  id: number
  filename: string
  original_filename: string
  total_pages: number
  status: string
  created_at: string | null
  completed_at: string | null
  processed_pages: number
  failed_pages: number
}

interface JobListProps {
  limit?: number
  filter?: string
  toggleStats: (jobId?: number) => void
}

function JobList({ limit, filter, toggleStats }: JobListProps) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading: queryLoading, refetch } = useQuery({
    queryKey: ['jobs', filter, limit],
    queryFn: async () => {
      const params: any = {}
      if (filter && filter !== 'all') params.status_filter = filter
      if (limit) params.limit = limit
      
      const response = await jobApi.getJobs(params)
      return response.data as Job[]
    },
    refetchInterval: 5000,
  })

  useEffect(() => {
    if (data) {
      setJobs(data)
    }
    setIsLoading(queryLoading)
  }, [data, queryLoading])

  useEffect(() => {
    refetch()
  }, [filter, limit, refetch])

  if (isLoading && jobs.length === 0) {
    return (
      <div className="card text-center py-12">
        <div className="loading-spinner mx-auto" />
        <p className="text-gray-500 mt-4">Cargando trabajos...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card text-center py-12 text-red-500">
        <p>Error: {error}</p>
        <button onClick={() => refetch()} className="btn btn-outline mt-4">
          Reintentar
        </button>
      </div>
    )
  }

  if (jobs.length === 0) {
    return (
      <div className="card text-center py-12">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-16 w-16 mx-auto text-gray-300 mb-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <p className="text-gray-500">No hay trabajos disponibles</p>
        <p className="text-sm text-gray-400 mt-2">
          Sube un PDF para comenzar
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {jobs.map((job) => (
        <JobCard
          key={job.id}
          job={job}
          onViewStats={() => toggleStats(job.id)}
        />
      ))}
    </div>
  )
}

interface JobCardProps {
  job: Job
  onViewStats: () => void
}

function JobCard({ job, onViewStats }: JobCardProps) {
  const getProgress = () => {
    const processed = job.processed_pages + job.failed_pages
    return (processed / job.total_pages) * 100
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '—'
    return new Date(dateString).toLocaleString('es-ES', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="card hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-4">
            <Link to={`/jobs/${job.id}`} className="hover:text-blue-600">
              <h3 className="text-lg font-semibold text-gray-900">
                {job.original_filename}
              </h3>
            </Link>
            <span className="text-sm text-gray-500">
              Trabajo #{job.id}
            </span>
          </div>
          
          <div className="mt-2 flex items-center gap-4 text-sm text-gray-500">
            <span>{job.total_pages} páginas</span>
            <span>
              Creado: {formatDate(job.created_at)}
              {job.completed_at && ` | Finalizado: ${formatDate(job.completed_at)}`}
            </span>
          </div>

          {/* Progress and Stats */}
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {getStatusBadge(job.status)}
                <span className="text-sm text-gray-600">
                  {job.processed_pages} procesadas, {job.failed_pages} con error
                </span>
              </div>
            </div>
            
            {job.status === 'processing' && (
              <ProgressBar value={getProgress()} className="h-2" />
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to={`/jobs/${job.id}`}
            className="btn btn-outline text-sm"
          >
            Ver detalles
          </Link>
          {job.status === 'processing' && (
            <button
              onClick={onViewStats}
              className="btn btn-primary text-sm"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4 mr-1"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
                  clipRule="evenodd"
                />
              </svg>
              Estadísticas
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default JobList
