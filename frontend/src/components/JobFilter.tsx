import React from 'react'

interface JobFilterProps {
  value: string
  onChange: (value: string) => void
}

const filterOptions = [
  { id: 'all', label: 'Todos' },
  { id: 'pending', label: 'Pendientes' },
  { id: 'processing', label: 'Procesando' },
  { id: 'completed', label: 'Completados' },
  { id: 'failed', label: 'Con Error' },
]

function JobFilter({ value, onChange }: JobFilterProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {filterOptions.map((option) => (
        <button
          key={option.id}
          onClick={() => onChange(option.id)}
          className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
            value === option.id
              ? 'bg-blue-600 text-white shadow'
              : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export default JobFilter
