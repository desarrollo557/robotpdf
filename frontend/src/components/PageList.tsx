import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { jobApi, downloadApi } from '../api/client'
import toast from 'react-hot-toast'
import { getPageStatusBadge } from '../utils/status'

interface Page {
  id: number
  page_number: number
  status: string
  resolution_code: string | null
  ocr_confidence: number | null
  ocr_engine: string | null
  error_message: string | null
  error_type: string | null
  retry_count: number
}

interface PageListProps {
  jobId: number
}

function PageList({ jobId }: PageListProps) {
  const [expandedPage, setExpandedPage] = useState<number | null>(null)

  const { data: pages, isLoading, error, refetch } = useQuery({
    queryKey: ['job-pages', jobId],
    queryFn: async () => {
      const response = await jobApi.getJobPages(jobId)
      return response.data as Page[]
    },
    refetchInterval: 5000,
  })

  const handleDownloadImage = async (page: Page) => {
    try {
      const response = await downloadApi.downloadPageImage(jobId, page.page_number)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `page_${page.page_number}.png`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success('Descarga de imagen iniciada')
    } catch (err) {
      toast.error('No se pudo descargar la imagen')
    }
  }

  const handleViewOcrText = async (page: Page) => {
    try {
      const response = await downloadApi.getPageOcrText(jobId, page.page_number)
      const data = response.data
      setExpandedPage(page.id)
      toast.success('Texto OCR cargado')
    } catch (err) {
      toast.error('No se pudo cargar el texto OCR')
    }
  }

  const formatConfidence = (confidence: number | null) => {
    if (!confidence) return '—'
    return `${(confidence * 100).toFixed(1)}%`
  }

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <div className="loading-spinner mx-auto" />
        <p className="text-gray-500 mt-4">Cargando páginas...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8 text-red-500">
        <p>Error al cargar las páginas</p>
        <button onClick={() => refetch()} className="btn btn-outline mt-4">
          Reintentar
        </button>
      </div>
    )
  }

  if (!pages || pages.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No se encontraron páginas</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="table-container">
        <table className="table">
          <thead className="table-header">
            <tr>
              <th className="table-th">#</th>
              <th className="table-th">Código de Resolución</th>
              <th className="table-th">Motor OCR</th>
              <th className="table-th">Confianza</th>
              <th className="table-th">Estado</th>
              <th className="table-th">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {pages.map((page) => (
              <React.Fragment key={page.id}>
                <tr className="table-tr">
                  <td className="table-td font-medium">{page.page_number}</td>
                  <td className="table-td">
                    {page.resolution_code ? (
                      <code className="bg-blue-50 px-2 py-1 rounded text-xs">
                        {page.resolution_code}
                      </code>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="table-td text-sm">{page.ocr_engine || '—'}</td>
                  <td className="table-td">
                    {formatConfidence(page.ocr_confidence)}
                  </td>
                  <td className="table-td">{getPageStatusBadge(page.status)}</td>
                  <td className="table-td">
                    <div className="flex items-center gap-2">
                      {page.ocr_text && (
                        <button
                          onClick={() => setExpandedPage(
                            expandedPage === page.id ? null : page.id
                          )}
                          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                          title="Ver texto OCR"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-5 w-5 text-gray-600"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                          >
                            <path
                              fillRule="evenodd"
                              d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </button>
                      )}
                      <button
                        onClick={() => handleDownloadImage(page)}
                        className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                        title="Descargar imagen"
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="h-5 w-5 text-gray-600"
                          viewBox="0 0 20 20"
                          fill="currentColor"
                        >
                          <path
                            fillRule="evenodd"
                            d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
                
                {/* Expanded OCR Text */}
                {expandedPage === page.id && page.ocr_text && (
                  <tr className="bg-gray-50">
                    <td colSpan={6} className="p-4">
                      <div className="bg-white rounded-lg p-4 shadow">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-medium text-gray-900">
                            Texto OCR - Página {page.page_number}
                          </h4>
                          <button
                            onClick={() => setExpandedPage(null)}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              className="h-5 w-5"
                              viewBox="0 0 20 20"
                              fill="currentColor"
                            >
                              <path
                                fillRule="evenodd"
                                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                                clipRule="evenodd"
                              />
                            </svg>
                          </button>
                        </div>
                        <pre className="text-xs text-gray-700 whitespace-pre-wrap max-h-64 overflow-y-auto">
                          {page.ocr_text}
                        </pre>
                        {page.error_message && (
                          <div className="mt-4 p-3 bg-red-50 rounded-lg">
                            <p className="text-sm font-medium text-red-600">Error:</p>
                            <p className="text-sm text-red-600">{page.error_message}</p>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
        <p className="text-sm text-gray-500">
          {pages.length} páginas totales
        </p>
        <p className="text-sm text-gray-500">
          Motor OCR: {pages[0]?.ocr_engine || '—'}
        </p>
      </div>
    </div>
  )
}

export default PageList
