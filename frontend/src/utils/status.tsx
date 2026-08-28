import React from 'react'

export function getStatusBadge(status: string): React.ReactNode {
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
    case 'cancelled':
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
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clipRule="evenodd"
            />
          </svg>
          Cancelado
        </span>
      )
    default:
      return <span className="badge-info">{status}</span>
  }
}

export function getPageStatusBadge(status: string): React.ReactNode {
  switch (status) {
    case 'completed':
      return <span className="badge-success">Completado</span>
    case 'failed':
      return <span className="badge-error">Error</span>
    case 'processing':
    case 'rendering':
    case 'ocr_processing':
    case 'ai_classifying':
      return <span className="badge-info">Procesando</span>
    case 'pending':
      return <span className="badge-warning">Pendiente</span>
    default:
      return <span className="badge-error">{status}</span>
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'text-green-600'
    case 'processing':
      return 'text-blue-600'
    case 'failed':
      return 'text-red-600'
    case 'pending':
      return 'text-yellow-600'
    case 'cancelled':
      return 'text-gray-600'
    default:
      return 'text-gray-600'
  }
}
