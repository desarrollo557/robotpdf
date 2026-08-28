import React, { useState, useEffect, useCallback } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  BarElement,
  ArcElement,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { X } from 'lucide-react'
import { useWebSocket, ProgressData, SystemStats } from '../hooks/useWebSocket'
import { wsApi } from '../api/client'

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  BarElement,
  ArcElement
)

interface StatsPanelProps {
  jobId: number | null
  onClose: () => void
}

interface ChartData {
  labels: string[]
  datasets: {
    label: string
    data: number[]
    borderColor: string
    backgroundColor: string
    fill: boolean
    tension: number
  }[]
}

function StatsPanel({ jobId, onClose }: StatsPanelProps) {
  const [progressData, setProgressData] = useState<ProgressData | null>(null)
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null)
  const [throughputHistory, setThroughputHistory] = useState<number[]>([])
  const [latencyHistory, setLatencyHistory] = useState<{
    render: number[]
    ocr: number[]
    ai: number[]
  }>({ render: [], ocr: [], ai: [] })
  const [alertVisible, setAlertVisible] = useState(false)

  // Use WebSocket for real-time updates
  const { isConnected, lastMessage } = useWebSocket({
    jobId: jobId || undefined,
    onProgress: (data) => {
      setProgressData(data)
      
      // Update throughput history (keep last 10 values)
      if (data.throughput > 0) {
        setThroughputHistory((prev) => [
          ...prev.slice(-9),
          data.throughput
        ])
      }
      
      // Update latency history
      setLatencyHistory((prev) => ({
        render: [...prev.render.slice(-9), data.avg_latency.render],
        ocr: [...prev.ocr.slice(-9), data.avg_latency.ocr],
        ai: [...prev.ai.slice(-9), data.avg_latency.ai],
      }))
      
      // Check for high error rate
      if (data.error_rate > 10) {
        setAlertVisible(true)
      }
    },
    onSystemStats: (data) => {
      setSystemStats(data as SystemStats)
    },
    onJobComplete: () => {
      // Job completed, we could auto-close or show a notification
    },
    reconnect: true,
    reconnectInterval: 2000,
  })

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])

  // Format numbers
  const formatNumber = useCallback((value: number) => {
    return new Intl.NumberFormat('es-ES').format(value)
  }, [])

  const formatDecimal = useCallback((value: number, decimals: number = 2) => {
    return value.toFixed(decimals)
  }, [])

  const formatTime = useCallback((seconds: number) => {
    if (seconds < 1) return `${(seconds * 1000).toFixed(0)} ms`
    if (seconds < 60) return `${seconds.toFixed(2)} s`
    if (seconds < 3600) return `${(seconds / 60).toFixed(2)} min`
    return `${(seconds / 3600).toFixed(2)} h`
  }, [])

  const getStatusColor = useCallback((status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800'
      case 'processing': return 'bg-blue-100 text-blue-800'
      case 'failed': return 'bg-red-100 text-red-800'
      case 'pending': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }, [])

  // Calculate ETA
  const calculateETA = useCallback((data: ProgressData) => {
    if (!data.eta_seconds || data.eta_seconds <= 0) return 'Calculando...'
    return formatTime(data.eta_seconds)
  }, [formatTime])

  // Chart data for throughput
  const throughputChartData: ChartData = {
    labels: throughputHistory.map((_, i) => `-${10 - i}s`),
    datasets: [
      {
        label: 'Páginas/minuto',
        data: throughputHistory,
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.4,
      },
    ],
  }

  // Chart data for latency
  const latencyChartData: ChartData = {
    labels: latencyHistory.render.map((_, i) => `-${10 - i}s`),
    datasets: [
      {
        label: 'Renderizado',
        data: latencyHistory.render,
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        fill: true,
        tension: 0.4,
      },
      {
        label: 'OCR',
        data: latencyHistory.ocr,
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        fill: true,
        tension: 0.4,
      },
      {
        label: 'AI',
        data: latencyHistory.ai,
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: true,
        tension: 0.4,
      },
    ],
  }

  if (!jobId) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div
          className="modal"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">
                Estadísticas en Tiempo Real
              </h2>
              <button
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <X className="h-5 w-5 text-gray-600" />
              </button>
            </div>
            <p className="text-gray-500 text-center py-8">
              Selecciona un trabajo para ver las estadísticas en tiempo real
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal w-full max-w-4xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              Estadísticas en Tiempo Real
            </h2>
            <p className="text-sm text-gray-500">
              Trabajo #{jobId} | Actualizado cada 2 segundos
            </p>
          </div>
          <div className="flex items-center gap-4">
            <span
              className={`badge ${isConnected ? 'badge-success' : 'badge-error'}`}
            >
              {isConnected ? 'Conectado' : 'Desconectado'}
            </span>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X className="h-5 w-5 text-gray-600" />
            </button>
          </div>
        </div>

        {/* Alert Banner */}
        {alertVisible && (
          <div className="p-4 bg-red-50 border-l-4 border-red-500">
            <div className="flex items-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-red-500 mr-3"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1zm-4 4a1 1 0 100-2 1 1 0 000 2z"
                  clipRule="evenodd"
                />
              </svg>
              <p className="text-red-700">
                <strong>Alerta:</strong> La tasa de error es superior al 10%. 
                Revisa el procesamiento.
              </p>
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="stat-card">
            <div className="stat-value">
              {formatNumber(progressData?.total_pages || 0)}
            </div>
            <div className="stat-label">Páginas Totales</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">
              {formatNumber(
                (progressData?.stage2.completed || 0) + 
                (progressData?.stage3.completed || 0)
              )}
            </div>
            <div className="stat-label">Procesadas</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">
              {formatNumber(
                (progressData?.stage1.failed || 0) + 
                (progressData?.stage2.failed || 0) + 
                (progressData?.stage3.failed || 0)
              )}
            </div>
            <div className="stat-label">Pendientes/Error</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">
              {formatDecimal(progressData?.overall_progress || 0)}%
            </div>
            <div className="stat-label">% Avance</div>
          </div>
        </div>

        {/* ETA and Throughput */}
        <div className="px-6 pb-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-700">Throughput</h3>
              <span className="badge badge-info">
                {formatDecimal(progressData?.throughput || 0)} páginas/min
              </span>
            </div>
            <div className="h-40">
              <Line
                data={throughputChartData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      display: false,
                    },
                    tooltip: {
                      callbacks: {
                        label: (context) => {
                          return `Páginas/min: ${formatDecimal(context.parsed.y)}`
                        },
                      },
                    },
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      ticks: {
                        callback: (value) => formatNumber(value as number),
                      },
                    },
                  },
                }}
              />
            </div>
          </div>
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-700">Tiempo Estimado Restante</h3>
              <span className="badge badge-info">
                {progressData ? calculateETA(progressData) : 'Calculando...'}
              </span>
            </div>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Páginas restantes:</span>
                <span className="font-medium">
                  {formatNumber(
                    (progressData?.total_pages || 0) - 
                    ((progressData?.stage2?.completed || 0) + 
                     (progressData?.stage3?.completed || 0))
                  )}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Resoluciones detectadas:</span>
                <span className="font-medium">
                  {formatNumber(progressData?.resolution_groups?.length || 0)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Tasa de error:</span>
                <span className={`font-medium ${
                  (progressData?.error_rate || 0) > 10 ? 'text-red-600' : 'text-gray-900'
                }`}>
                  {formatDecimal(progressData?.error_rate || 0)}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Latency Chart */}
        <div className="px-6 pb-6">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-700">
                Latencia Promedio por Etapa (segundos)
              </h3>
            </div>
            <div className="h-48">
              <Line
                data={latencyChartData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      position: 'top' as const,
                      align: 'end' as const,
                    },
                    tooltip: {
                      callbacks: {
                        label: (context) => {
                          return `${context.dataset.label}: ${formatDecimal(context.parsed.y, 3)}s`
                        },
                      },
                    },
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      ticks: {
                        callback: (value) => formatDecimal(value as number, 2),
                      },
                    },
                  },
                }}
              />
            </div>
          </div>
        </div>

        {/* Stage Queue Sizes */}
        {systemStats && (
          <div className="px-6 pb-6">
            <div className="card">
              <h3 className="font-semibold text-gray-700 mb-4">
                Tamaños de Cola
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    {systemStats.stage1_queue_size}
                  </div>
                  <div className="text-sm text-gray-500">
                    Cola de Renderizado + OCR
                  </div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    {systemStats.stage2_queue_size}
                  </div>
                  <div className="text-sm text-gray-500">
                    Cola de Clasificación AI
                  </div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    {systemStats.stage3_queue_size}
                  </div>
                  <div className="text-sm text-gray-500">
                    Cola de Ensamblado PDF
                  </div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    {systemStats.active_ai_requests}
                  </div>
                  <div className="text-sm text-gray-500">
                    Solicitudes AI activas
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* System Stats Summary */}
        <div className="px-6 pb-6">
          <div className="card">
            <h3 className="font-semibold text-gray-700 mb-4">
              Resumen del Sistema
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-5 w-5 text-blue-600"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.414-1.414L11 9.586V6z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
                <div>
                  <div className="font-medium text-gray-900">
                    {formatDecimal(systemStats?.pages_per_minute || progressData?.throughput || 0)}
                  </div>
                  <div className="text-sm text-gray-500">Páginas/minuto</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-5 w-5 text-green-600"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
                <div>
                  <div className="font-medium text-gray-900">
                    {formatDecimal(progressData?.avg_latency.ai || 0)}s
                  </div>
                  <div className="text-sm text-gray-500">Latencia AI Promedio</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-5 w-5 text-purple-600"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path d="M2 5a2 2 0 012-2h7a2 2 0 012 2v4a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
                    <path d="M15 7v2a2 2 0 01-2 2h-2v-2h2a2 2 0 012-2z" />
                  </svg>
                </div>
                <div>
                  <div className="font-medium text-gray-900">
                    {formatNumber(progressData?.resolution_groups?.length || 0)}
                  </div>
                  <div className="text-sm text-gray-500">Resoluciones Detectadas</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default StatsPanel
