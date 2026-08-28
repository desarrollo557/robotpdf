import React, { useState } from 'react'
import JobList from '../components/JobList'
import JobFilter from '../components/JobFilter'

interface JobsPageProps {
  toggleStats: (jobId?: number) => void
}

function JobsPage({ toggleStats }: JobsPageProps) {
  const [filter, setFilter] = useState<string>('all')

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Todos los Trabajos
              </h1>
              <p className="text-gray-600 mt-1">
                Historia de todos los documentos procesados
              </p>
            </div>
            <a href="/" className="btn btn-primary">
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
              </svg>
              Nuevo PDF
            </a>
          </div>
        </header>

        <div className="space-y-6">
          {/* Filters */}
          <JobFilter value={filter} onChange={setFilter} />

          {/* Job List */}
          <JobList filter={filter} toggleStats={toggleStats} />
        </div>
      </div>
    </div>
  )
}

export default JobsPage
