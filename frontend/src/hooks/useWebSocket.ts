import { useState, useEffect, useRef, useCallback } from 'react'
import { wsApi } from '../api/client'

export interface ProgressData {
  job_id: number
  total_pages: number
  stage1: {
    pending: number
    processing: number
    completed: number
    failed: number
  }
  stage2: {
    pending: number
    processing: number
    completed: number
    failed: number
  }
  stage3: {
    completed: number
  }
  overall_progress: number
  throughput: number
  eta_seconds: number | null
  avg_latency: {
    render: number
    ocr: number
    ai: number
  }
  error_rate: number
  resolution_groups: string[]
}

export interface SystemStats {
  stage1_queue_size: number
  stage2_queue_size: number
  stage3_queue_size: number
  active_workers: number
  active_ai_requests: number
  pages_per_minute: number
  ai_requests_per_minute: number
}

export interface WebSocketMessage {
  type: 'progress' | 'system_stats' | 'job_complete'
  job_id?: number
  data: ProgressData | SystemStats
}

interface UseWebSocketOptions {
  jobId?: number
  onProgress?: (data: ProgressData) => void
  onSystemStats?: (data: SystemStats) => void
  onJobComplete?: (jobId: number, data: ProgressData) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Event) => void
  reconnect?: boolean
  reconnectInterval?: number
}

interface WebSocketState {
  isConnected: boolean
  isConnecting: boolean
  lastMessage: WebSocketMessage | null
  connectionCount: number
}

export function useWebSocket(options: UseWebSocketOptions = {}): WebSocketState {
  const {
    jobId,
    onProgress,
    onSystemStats,
    onJobComplete,
    onConnect,
    onDisconnect,
    onError,
    reconnect = true,
    reconnectInterval = 5000,
  } = options

  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isConnecting: false,
    lastMessage: null,
    connectionCount: 0,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectCountRef = useRef<number>(0)

  const getWebSocketUrl = useCallback((): string => {
    if (jobId) {
      return wsApi.getJobWsUrl(jobId)
    }
    return wsApi.getGeneralWsUrl()
  }, [jobId])

  const connect = useCallback(() => {
    // Clear any existing timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setState((prev) => ({
      ...prev,
      isConnecting: true,
    }))

    const url = getWebSocketUrl()
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setState((prev) => ({
        ...prev,
        isConnected: true,
        isConnecting: false,
        connectionCount: prev.connectionCount + 1,
      }))
      reconnectCountRef.current = 0
      onConnect?.()
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        setState((prev) => ({
          ...prev,
          lastMessage: message,
        }))

        switch (message.type) {
          case 'progress':
            onProgress?.(message.data as ProgressData)
            break
          case 'system_stats':
            onSystemStats?.(message.data as SystemStats)
            break
          case 'job_complete':
            onJobComplete?.(message.job_id!, message.data as ProgressData)
            break
        }
      } catch (err) {
        console.error('Error parsing WebSocket message:', err)
      }
    }

    ws.onclose = () => {
      setState((prev) => ({
        ...prev,
        isConnected: false,
        isConnecting: false,
      }))
      onDisconnect?.()

      // Reconnect if enabled
      if (reconnect && reconnectCountRef.current < 10) {
        const delay = reconnectInterval * Math.pow(1.5, reconnectCountRef.current)
        reconnectCountRef.current += 1
        reconnectTimeoutRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = (error) => {
      onError?.(error)
    }
  }, [
    getWebSocketUrl,
    onConnect,
    onDisconnect,
    onError,
    onProgress,
    onSystemStats,
    onJobComplete,
    reconnect,
    reconnectInterval,
  ])

  const disconnect = useCallback(() => {
    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    // Close connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setState((prev) => ({
      ...prev,
      isConnected: false,
      isConnecting: false,
    }))
    reconnectCountRef.current = 0
  }, [])

  const send = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  // Connect on mount
  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  // Reconnect when jobId changes
  useEffect(() => {
    disconnect()
    connect()
  }, [jobId, connect, disconnect])

  return {
    ...state,
    send,
    disconnect,
  }
}

export interface JobStatus {
  id: number
  filename: string
  original_filename: string
  total_pages: number
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  processed_pages: number
  failed_pages: number
  output_zip_path: string | null
  error_message: string | null
  progress?: ProgressData
}

// Custom hook for job status with WebSocket
export function useJobStatus(
  jobId: number,
  options: Omit<UseWebSocketOptions, 'jobId'> = {}
): WebSocketState & { jobStatus?: JobStatus; isLoading: boolean } {
  const [jobStatus, setJobStatus] = useState<JobStatus | undefined>()
  const [isLoading, setIsLoading] = useState<boolean>(true)

  const wsState = useWebSocket({
    ...options,
    jobId,
    onProgress: (data: ProgressData) => {
      setJobStatus((prev) =>
        prev
          ? {
              ...prev,
              progress: data,
              processed_pages: data.stage2.completed + data.stage3.completed,
              failed_pages:
                data.stage1.failed + data.stage2.failed + data.stage3.failed,
            }
          : undefined
      )
      options.onProgress?.(data)
    },
    onJobComplete: (id, data) => {
      setJobStatus((prev) =>
        prev
          ? {
              ...prev,
              status: 'completed',
              progress: data,
              completed_at: new Date().toISOString(),
            }
          : undefined
      )
      options.onJobComplete?.(id, data)
    },
  })

  // Fetch initial job status
  useEffect(() => {
    const fetchJobStatus = async () => {
      try {
        setIsLoading(true)
        const response = await fetch(`${wsApi.getJobWsUrl(0).replace('ws://', 'http://')}/api/jobs/${jobId}/status`)
        const data = await response.json()
        setJobStatus(data)
      } catch (err) {
        console.error('Error fetching job status:', err)
      } finally {
        setIsLoading(false)
      }
    }

    fetchJobStatus()
  }, [jobId])

  return {
    ...wsState,
    jobStatus,
    isLoading,
  }
}
