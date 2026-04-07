import { useState, useEffect, useCallback } from 'react'
import { getTranscript, updateSegment, restoreSegment } from '../services/api'

export function useTranscript(meetingId) {
  const [transcript, setTranscript] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const fetchTranscript = useCallback(async () => {
    if (!meetingId) return
    setLoading(true)
    try {
      const res = await getTranscript(meetingId)
      setTranscript(res.data)
      setError(null)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [meetingId])

  useEffect(() => {
    fetchTranscript()
  }, [fetchTranscript])

  const saveSegment = useCallback(async (segmentId, newText) => {
    setSaving(true)
    try {
      const res = await updateSegment(segmentId, newText)
      setTranscript((prev) => ({
        ...prev,
        segments: prev.segments.map((s) =>
          s.id === segmentId ? res.data : s
        ),
      }))
    } finally {
      setSaving(false)
    }
  }, [])

  const restoreSegmentText = useCallback(async (segmentId) => {
    setSaving(true)
    try {
      const res = await restoreSegment(segmentId)
      setTranscript((prev) => ({
        ...prev,
        segments: prev.segments.map((s) =>
          s.id === segmentId ? res.data : s
        ),
      }))
    } finally {
      setSaving(false)
    }
  }, [])

  return {
    transcript,
    loading,
    error,
    saving,
    saveSegment,
    restoreSegmentText,
    refetch: fetchTranscript,
  }
}
