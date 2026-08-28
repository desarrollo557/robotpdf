import React from 'react'
import clsx from 'clsx'

interface ProgressBarProps {
  value: number
  max?: number
  className?: string
  showLabel?: boolean
  labelFormatter?: (value: number, max?: number) => string
}

function ProgressBar({
  value,
  max = 100,
  className = 'h-2.5',
  showLabel = false,
  labelFormatter,
}: ProgressBarProps) {
  const clampedValue = Math.min(Math.max(value, 0), max)
  const percentage = (clampedValue / max) * 100

  const defaultLabelFormatter = (value: number, max?: number) => {
    if (max) {
      return `${Math.round((value / max) * 100)}%`
    }
    return `${Math.round(value)}%`
  }

  const formatter = labelFormatter || defaultLabelFormatter

  return (
    <div className="w-full progress-bar rounded-full overflow-hidden" role="progressbar">
      <div
        className={clsx(
          'progress-fill bg-blue-600 transition-all duration-300 ease-out',
          className
        )}
        style={{ width: `${percentage}%` }}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
      />
      {showLabel && (
        <span className="absolute inset-0 flex items-center justify-center text-xs text-white font-medium">
          {formatter(value, max)}
        </span>
      )}
    </div>
  )
}

export default ProgressBar
