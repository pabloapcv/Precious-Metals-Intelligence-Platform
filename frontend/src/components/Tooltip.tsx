import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

interface TooltipProps {
  label: string
  children: React.ReactNode
}

export function Tooltip({ label, children }: TooltipProps) {
  const [open, setOpen] = useState(false)
  const [box, setBox] = useState({ top: 0, left: 0, below: false })
  const wrap = useRef<HTMLSpanElement>(null)
  const tip = useRef<HTMLSpanElement>(null)
  const closeTimer = useRef<number | null>(null)
  const tipId = useId()

  const clearClose = () => {
    if (closeTimer.current != null) {
      window.clearTimeout(closeTimer.current)
      closeTimer.current = null
    }
  }

  const place = () => {
    const rect = wrap.current?.getBoundingClientRect()
    if (!rect) return
    const below = rect.top < 140
    const left = Math.min(Math.max(rect.left + rect.width / 2, 160), window.innerWidth - 160)
    setBox({
      top: below ? rect.bottom + 10 : rect.top - 10,
      left,
      below,
    })
  }

  const show = () => {
    clearClose()
    place()
    setOpen(true)
  }

  const hideSoon = () => {
    clearClose()
    closeTimer.current = window.setTimeout(() => setOpen(false), 120)
  }

  useEffect(() => () => clearClose(), [])

  useEffect(() => {
    if (!open) return
    const onScroll = () => place()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <span
      ref={wrap}
      className="tooltip-wrap"
      onMouseEnter={show}
      onMouseLeave={hideSoon}
      onFocus={show}
      onBlur={hideSoon}
    >
      {children}
      <button
        type="button"
        className="tooltip-trigger"
        aria-label={label}
        aria-describedby={open ? tipId : undefined}
        onClick={(event) => {
          event.preventDefault()
          event.stopPropagation()
          if (open) setOpen(false)
          else show()
        }}
      >
        ?
      </button>
      {open && createPortal(
        <span
          ref={tip}
          id={tipId}
          role="tooltip"
          className={`tooltip-content tooltip-portal ${box.below ? 'below' : 'above'}`}
          style={{ top: box.top, left: box.left }}
          onMouseEnter={show}
          onMouseLeave={hideSoon}
        >
          {label}
        </span>,
        document.body,
      )}
    </span>
  )
}
