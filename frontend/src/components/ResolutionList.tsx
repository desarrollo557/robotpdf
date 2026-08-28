import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { jobApi, downloadApi } from '../api/client'
import toast from 'react-hot-toast'

interface Resolution {
  id: number
  resolution_code: string
  start_page: number
  end_page: number
  page_count: number
  output_pdf_path: string | null
  file_size: number | null
  status: string
}

interface ResolutionListProps {
  jobId: number
}

function ResolutionList({ jobId }: ResolutionListProps) {
  const { data: resolutions, isLoading, error, refetch } = useQuery({
    queryKey: ['job-resolutions', jobId],
    queryFn: async () => {
      const response = await jobApi.getJobResolutions(jobId)
      return response.data as Resolution[]
    },
    refetchInterval: 5000,
  })

  const handleDownload = async (resolution: Resolution) => {
    try {
      const response = await downloadApi.downloadResolutionPDFByCode(
        jobId,
        resolution.resolution_code
      )
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const safeName = resolution.resolution_code
        .replace(/[<>:"/\\|?*]/g, '_')
        .substring(0, 50)
      link.setAttribute('download', `${safeName}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success('Descarga iniciada')
    } catch (err) {
      toast.error('No se pudo descargar el PDF')
    }
  }

  const formatFileSize = (bytes: number | null) => {
    if (!bytes) return '—'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <div className="loading-spinner mx-auto" />
        <p className="text-gray-500 mt-4">Cargando resoluciones...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8 text-red-500">
        <p>Error al cargar las resoluciones</p>
        <button onClick={() => refetch()} className="btn btn-outline mt-4">
          Reintentar
        </button>
      </div>
    )
  }

  if (!resolutions || resolutions.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No se han detectado resoluciones aún</p>
        <p className="text-sm mt-2">
          El procesamiento está en curso...
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="table-container">
        <table className="table">
          <thead className="table-header">
            <tr>
              <th className="table-th">Código de Resolución</th>
              <th className="table-th">Páginas</th>
              <th className="table-th">Rango</th>
              <th className="table-th">Tamaño</th>
              <th className="table-th">Estado</th>
              <th className="table-th">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {resolutions.map((resolution) => (
              <tr key={resolution.id} className="table-tr">
                <td className="table-td">
                  <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                    {resolution.resolution_code || 'Sin código'}
                  </code>
                </td>
                <td className="table-td">
                  {resolution.page_count}
                </td>
                <td className="table-td">
                  {resolution.start_page} - {resolution.end_page}
                </td>
                <td className="table-td">
                  {formatFileSize(resolution.file_size)}
                </td>
                <td className="table-td">
                  {resolution.status === 'completed' ? (
                    <span className="badge-success">Listo</span>
                  ) : (
                    <span className="badge-warning">Procesando</span>
                  )}
                </td>
                <td className="table-td">
                  {resolution.status === 'completed' && (
                    <button
                      onClick={() => handleDownload(resolution)}
                      className="btn btn-outline text-xs"
                      disabled={!resolution.output_pdf_path}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-4 w-4 mr-1"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                      >
                        <path
                          fillRule="evenodd"
                          d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"
                          clipRule="evenodd"
                        />
                      </svg>
                      Descargar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
        <p className="text-sm text-gray-500">
          {resolutions.length} resoluciones detectadas
        </p>
        <p className="text-sm text-gray-500">
          Total: {resolutions.reduce((sum, r) => sum + r.page_count, 0)} páginas
        </p>
      </div>
    </div>
  )
}

export default ResolutionList
