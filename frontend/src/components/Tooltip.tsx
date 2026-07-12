import { useState } from 'react'

interface TooltipProps {
  label: string
  children: React.ReactNode
}

export function Tooltip({ label, children }: TooltipProps) {
  const [open, setOpen] = useState(false)

  return (
    <span
      className="tooltip-wrap"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      <button
        type="button"
        className="tooltip-trigger"
        aria-label={label}
        aria-describedby={open ? 'tooltip-content' : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        ?
      </button>
      {open && (
        <span id="tooltip-content" role="tooltip" className="tooltip-content">
          {label}
        </span>
      )}
    </span>
  )
}
