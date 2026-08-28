import React from 'react'
import PDFUploader from '../components/PDFUploader'
import JobList from '../components/JobList'

interface HomePageProps {
  toggleStats: (jobId?: number) => void
}

function HomePage({ toggleStats }: HomePageProps) {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <header className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Bot de Segmentación de PDFs por Resolución
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Sube un documento PDF y el sistema lo procesará para identificar y
            separar automáticamente las resoluciones contenidas en él.
          </p>
        </header>

        <div className="space-y-8">
          {/* Upload Section */}
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Subir Nuevo PDF</h2>
              <p className="text-sm text-gray-500 mt-1">
                Sube un archivo PDF para comenzar el procesamiento
              </p>
            </div>
            <PDFUploader />
          </section>

          {/* Recent Jobs */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-semibold text-gray-900">
                Trabajos Recientes
              </h2>
              <a
                href="/jobs"
                className="btn btn-outline text-sm"
              >
                Ver todos
              </a>
            </div>
            <JobList limit={5} toggleStats={toggleStats} />
          </section>
        </div>
      </div>
    </div>
  )
}

export default HomePage
