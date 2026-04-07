import { useState, useEffect, useCallback, useRef } from 'react'
import { listJobs, getJob } from '../services/api'

export function useJobs(pollInterval = 5000) {
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  const fetchJobs = useCallback(async () => {
    try {
      const res = await listJobs()
      setJobs(res.data.items)
      setTotal(res.data.total)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
    intervalRef.current = setInterval(fetchJobs, pollInterval)
    return () => clearInterval(intervalRef.current)
  }, [fetchJobs, pollInterval])

  return { jobs, total, loading, error, refetch: fetchJobs }
}

export function useJob(meetingId, pollInterval = 3000) {
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  const fetchJob = useCallback(async () => {
    if (!meetingId) return
    try {
      const res = await getJob(meetingId)
      setJob(res.data)
      setError(null)
      // Sluta polla när jobbet är klart eller misslyckat
      if (res.data.status === 'completed' || res.data.status === 'failed') {
        clearInterval(intervalRef.current)
      }
    } catch (err) {
      setError(err.message)
      clearInterval(intervalRef.current)
    } finally {
      setLoading(false)
    }
  }, [meetingId])

  useEffect(() => {
    fetchJob()
    intervalRef.current = setInterval(fetchJob, pollInterval)
    return () => clearInterval(intervalRef.current)
  }, [fetchJob, pollInterval])

  return { job, loading, error, refetch: fetchJob }
}
