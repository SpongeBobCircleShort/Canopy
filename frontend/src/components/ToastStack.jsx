import { useEffect, useState } from 'react'

export default function ToastStack({ toasts = [] }) {
  const [dismissedIds, setDismissedIds] = useState([])

  useEffect(() => {
    setDismissedIds((currentIds) => currentIds.filter((id) => toasts.some((toast) => toast.id === id)))
  }, [toasts])

  const visibleToasts = toasts.filter((toast) => toast.message && !dismissedIds.includes(toast.id))
  if (!visibleToasts.length) return null

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {visibleToasts.map((toast) => (
        <section className={`toast ${toast.type || 'info'}`} key={toast.id}>
          <p>{toast.message}</p>
          <button
            type="button"
            aria-label={`Dismiss ${toast.type || 'notification'} notification`}
            onClick={() => setDismissedIds((currentIds) => [...currentIds, toast.id])}
          >
            x
          </button>
        </section>
      ))}
    </div>
  )
}
