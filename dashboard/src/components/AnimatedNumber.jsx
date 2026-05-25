import { useEffect, useRef, useState } from 'react'

export default function AnimatedNumber({ value, duration = 800, className = '' }) {
  const [display, setDisplay] = useState(0)
  const startRef = useRef(null)
  const rafRef = useRef(null)

  useEffect(() => {
    const target = Number(value)
    if (isNaN(target)) return

    const start = performance.now()
    const from = display

    const tick = (now) => {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      // ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(Math.round(from + (target - from) * eased))
      if (progress < 1) rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [value])

  return <span className={className}>{display}</span>
}
