import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${BASE_URL}/api`,
  timeout: 30000,
})

// --- Upload ---
export const uploadFile = (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress
      ? (e) => onProgress(Math.round((e.loaded * 100) / e.total))
      : undefined,
  })
}

// --- Jobs ---
export const listJobs = (limit = 50, offset = 0) =>
  api.get('/jobs', { params: { limit, offset } })

export const getJob = (meetingId) =>
  api.get(`/jobs/${meetingId}`)

export const getQueueStatus = () =>
  api.get('/jobs/queue/status')

// --- Transcripts ---
export const getTranscript = (meetingId) =>
  api.get(`/transcripts/${meetingId}`)

export const updateSegment = (segmentId, text) =>
  api.patch(`/transcripts/segments/${segmentId}`, { text })

export const restoreSegment = (segmentId) =>
  api.patch(`/transcripts/segments/${segmentId}/restore`)

export const exportTranscriptTxt = (meetingId) => {
  const url = `${BASE_URL}/api/transcripts/${meetingId}/export/txt`
  window.open(url, '_blank')
}

export const exportTranscriptJson = (meetingId) => {
  const url = `${BASE_URL}/api/transcripts/${meetingId}/export/json`
  window.open(url, '_blank')
}

// --- Search ---
export const searchTranscripts = (query, limit = 100) =>
  api.get('/search', { params: { q: query, limit } })

// --- Live session ---
export const saveLiveSession = (title, participants, blocks) =>
  axios.post(`${BASE_URL}/ws/live/save`, {
    title: title || null,
    participants,
    segments: blocks.map((b) => ({
      speaker: b.speaker,
      start: b.start,
      end: b.end,
      text: b.text,
    })),
  })

// --- Speaker profiles ---
export const listSpeakers = () =>
  api.get('/speakers')

export const enrollSpeaker = (name, audioBlob) => {
  const formData = new FormData()
  formData.append('name', name)
  formData.append('audio', audioBlob, 'enrollment.webm')
  return api.post('/speakers/enroll', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

export const deleteSpeaker = (profileId) =>
  api.delete(`/speakers/${profileId}`)

export default api
