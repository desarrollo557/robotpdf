import React, { useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import JobsPage from './pages/JobsPage'
import JobDetailPage from './pages/JobDetailPage'
import StatsPanel from './components/StatsPanel'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  const [statsVisible, setStatsVisible] = useState(false)
  const [currentJobId, setCurrentJobId] = useState<number | null>(null)

  const toggleStats = (jobId?: number) => {
    setCurrentJobId(jobId || null)
    setStatsVisible(!statsVisible)
  }

  const closeStats = () => {
    setStatsVisible(false)
    setCurrentJobId(null)
  }

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-50">
        <Routes>
          <Route path="/" element={<Layout toggleStats={toggleStats} />}>
            <Route index element={<HomePage toggleStats={toggleStats} />} />
            <Route path="jobs" element={<JobsPage toggleStats={toggleStats} />} />
            <Route
              path="jobs/:jobId"
              element={<JobDetailPage toggleStats={toggleStats} />}
            />
          </Route>
        </Routes>

        {/* Stats Panel Modal */}
        {statsVisible && (
          <StatsPanel
            jobId={currentJobId}
            onClose={closeStats}
          />
        )}
      </div>
    </QueryClientProvider>
  )
}

export default App
