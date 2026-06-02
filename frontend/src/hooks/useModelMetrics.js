import { useState, useEffect } from 'react'

/**
 * Fetches audio classifier evaluation metrics from the API.
 *
 * When `token` is provided, calls the authenticated endpoint.
 * When `token` is falsy (public demo mode), calls the unauthenticated
 * /public endpoint so the presentation slides work without a login session.
 *
 * @param {string|null} token - JWT bearer token, or null for public access
 */
export function useModelMetrics(token) {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)

    const url = token ? '/api/model/metrics' : '/api/model/metrics/public'
    const headers = token ? { Authorization: `Bearer ${token}` } : {}

    fetch(url, { headers })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data) => {
        setMetrics(data)
        setLoading(false)
      })
      .catch((e) => {
        setError(e)
        setLoading(false)
      })
  }, [token])

  return { metrics, loading, error }
}
