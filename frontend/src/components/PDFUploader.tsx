import React, { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { jobApi } from '../api/client'

interface PDFUploaderProps {
  onUploadComplete?: (jobId: number) => void
}

function PDFUploader({ onUploadComplete }: PDFUploaderProps) {
  const navigate = useNavigate()
  const [isDragging, setIsDragging] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const uploadMutation = useMutation({
    mutationFn: (file: File) => jobApi.uploadPDF(file, setUploadProgress),
    onSuccess: (response) => {
      const job = response.data
      toast.success(`¡PDF subido correctamente! (${job.total_pages} páginas)`)
      onUploadComplete?.(job.id)
      navigate(`/jobs/${job.id}`)
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Error al subir el PDF'
      toast.error(message)
    },
    onSettled: () => {
      setUploadProgress(0)
      setIsUploading(false)
    },
  })

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      if (event.target.files && event.target.files[0]) {
        uploadFile(event.target.files[0])
      }
    },
    [uploadMutation]
  )

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)

      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        uploadFile(e.dataTransfer.files[0])
      }
    },
    [uploadMutation]
  )

  const uploadFile = useCallback(
    (file: File) => {
      // Validate file type
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        toast.error('Por favor, sube un archivo PDF')
        return
      }

      // Validate file size (1GB max)
      const maxSize = 1024 * 1024 * 1024
      if (file.size > maxSize) {
        toast.error('El archivo es demasiado grande. Máximo: 1GB')
        return
      }

      setIsUploading(true)
      setUploadProgress(0)
      uploadMutation.mutate(file)
    },
    [uploadMutation]
  )

  const handleClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  return (
    <div className="space-y-4">
      {/* File Input (Hidden) */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf"
        className="hidden"
        disabled={isUploading}
      />

      {/* Upload Area */}
      <div
        onClick={handleClick}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-xl transition-all duration-200 cursor-pointer ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : isUploading
            ? 'border-blue-300 bg-blue-50'
            : 'border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100'
        }`}
        style={isUploading ? { cursor: 'wait' } : {}}
      >
        <div className="p-8 text-center">
          {isUploading ? (
            <div className="space-y-4">
              <div className="loading-spinner mx-auto" />
              <p className="text-gray-700">Subiendo...</p>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div
                  className="bg-blue-600 h-2.5 rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-sm text-gray-500">{uploadProgress}%</p>
            </div>
          ) : (
            <div className="space-y-4">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-16 w-16 mx-auto text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 11v6m0 0l-3-3m3 3l3-3m-3-4a1 1 0 100-2 1 1 0 000 2z"
                />
              </svg>
              <div className="space-y-2">
                <p className="text-lg font-medium text-gray-700">
                  Arrastrar y soltar el PDF aquí
                </p>
                <p className="text-sm text-gray-500">
                  o haz clic para seleccionar un archivo
                </p>
              </div>
              <button
                type="button"
                onClick={handleClick}
                className="btn btn-primary mx-auto"
                disabled={isUploading}
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
                Seleccionar PDF
              </button>
            </div>
          )}
        </div>
      </div>

      {/* File Info */}
      <div className="text-center text-sm text-gray-500">
        <p>
          Soportado: .pdf | Tamaño máximo: 1GB (configurable en el servidor)
        </p>
      </div>
    </div>
  )
}

export default PDFUploader
