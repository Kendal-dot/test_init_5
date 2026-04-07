import { useState, useEffect, useCallback } from 'react'
import { listSpeakers, deleteSpeaker } from '../services/api'

export function useSpeakers() {
  const [speakers, setSpeakers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchSpeakers = useCallback(async () => {
    try {
      const res = await listSpeakers()
      setSpeakers(res.data.items)
      setError(null)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSpeakers()
  }, [fetchSpeakers])

  const removeSpeaker = useCallback(async (id) => {
    try {
      await deleteSpeaker(id)
      setSpeakers((prev) => prev.filter((s) => s.id !== id))
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    }
  }, [])

  return { speakers, loading, error, refetch: fetchSpeakers, removeSpeaker }
}
