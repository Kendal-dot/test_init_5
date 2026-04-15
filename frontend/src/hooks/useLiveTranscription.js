/**
 * Hook för chunk-baserad live-transkribering via WebSocket.
 *
 * Segment grupperas visuellt: samma talare i följd → ett växande block.
 * Max 30 sekunder per block oavsett talare.
 */

import { useState, useRef, useCallback, useEffect } from 'react'

// Nytt block skapas om talaren byts ELLER om blocket är längre än detta
const BLOCK_MAX_SECONDS = 30

const WS_BASE = 'VITE_WS_URL' in import.meta.env
  ? import.meta.env.VITE_WS_URL
  : 'ws://localhost:8000'
const WS_URL = (WS_BASE || `ws://${window.location.host}`) + '/ws/live/transcribe'
// 3s chunks = ~4-5s latens totalt (3s inspelning + ~1s Whisper-inferens på GPU)
// Kortare än 2s ger för lite kontext för bra transkribering
const CHUNK_DURATION_MS = 3000

/**
 * Välj bästa tillgängliga MIME-type för inspelning.
 * Backend accepterar alla format – ffmpeg konverterar automatiskt.
 */
function getSupportedMimeType() {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ]
  for (const mime of candidates) {
    if (MediaRecorder.isTypeSupported(mime)) return mime
  }
  return '' // låt webbläsaren välja
}

export function useLiveTranscription(participants = []) {
  // blocks = visuella block, varje block = en talare-turn (max 30s)
  // { id, speaker, start, end, text, chunkCount }
  const [blocks, setBlocks] = useState([])
  const [status, setStatus] = useState('idle') // idle | connecting | recording | stopping | error
  const [error, setError] = useState(null)
  const [processing, setProcessing] = useState(false) // chunk skickat, väntar på svar

  const wsRef = useRef(null)
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunkIntervalRef = useRef(null)
  // Ref för status för att undvika stale closure i ws.onclose
  const statusRef = useRef('idle')

  const updateStatus = (s) => {
    statusRef.current = s
    setStatus(s)
  }

  const stopRecordingInternal = useCallback(() => {
    clearTimeout(chunkIntervalRef.current)
    clearInterval(chunkIntervalRef.current)
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop()
    }
    streamRef.current?.getTracks().forEach((t) => t.stop())
    recorderRef.current = null
    streamRef.current = null
  }, [])

  const start = useCallback(async () => {
    setError(null)
    setBlocks([])
    updateStatus('connecting')

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        // Skicka deltagarnamn till backend innan inspelning startar
        if (participants.length > 0) {
          ws.send(JSON.stringify({ type: 'init', participants }))
        }
        updateStatus('recording')
        startRecording(stream, ws)
      }

      ws.onmessage = (event) => {
        setProcessing(false)
        try {
          const data = JSON.parse(event.data)
          if (data.error) {
            console.warn('Live-transkribering fel:', data.error)
            return
          }
          // Tysta chunks (silent: true) eller tomma texter ignoreras
          if (!data.text || data.text.trim() === '') return

          setBlocks((prev) => {
            const last = prev[prev.length - 1]
            const blockDuration = last ? (data.end - last.start) : Infinity
            const sameSpeaker = last && last.speaker === data.speaker
            const blockFull = blockDuration >= BLOCK_MAX_SECONDS

            if (last && sameSpeaker && !blockFull) {
              // Lägg till text i befintligt block
              const updated = {
                ...last,
                end: data.end,
                text: last.text + ' ' + data.text.trim(),
                chunkCount: last.chunkCount + 1,
              }
              return [...prev.slice(0, -1), updated]
            } else {
              // Nytt block (ny talare eller max-tid nådd)
              return [...prev, {
                id: Date.now(),
                speaker: data.speaker,
                start: data.start,
                end: data.end,
                text: data.text.trim(),
                chunkCount: 1,
              }]
            }
          })
        } catch {
          // ignorera JSON-parse-fel
        }
      }

      ws.onerror = (e) => {
        console.error('WebSocket-fel:', e)
        setError('Anslutningsfel. Kontrollera att backend körs på port 8000.')
        updateStatus('error')
        stopRecordingInternal()
      }

      ws.onclose = () => {
        if (statusRef.current !== 'idle' && statusRef.current !== 'stopping') {
          updateStatus('idle')
        }
        stopRecordingInternal()
      }
    } catch (err) {
      setError(`Mikrofonåtkomst nekades: ${err.message}`)
      updateStatus('error')
    }
  // participants måste vara med – annars fångas den gamla tomma arrayen (stale closure)
  }, [stopRecordingInternal, participants])

  const startRecording = (stream, ws) => {
    // Starta ny MediaRecorder-instans för varje chunk.
    // Varje instans producerar ett komplett, självständigt avkodningsbart WebM-block
    // (med eget EBML-header + init-segment). requestData() fungerar INTE för detta
    // eftersom Chrome bara inkluderar init-segmentet i den allra första blobben.
    const recordNextChunk = () => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return

      const mimeType = getSupportedMimeType()
      const options = mimeType ? { mimeType } : {}
      const recorder = new MediaRecorder(stream, options)
      recorderRef.current = recorder

      recorder.ondataavailable = async (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          const buffer = await e.data.arrayBuffer()
          ws.send(buffer)
          setProcessing(true)
          // Starta omedelbart nästa chunk-inspelning
          recordNextChunk()
        }
      }

      recorder.start()
      // Stoppa efter CHUNK_DURATION_MS – triggar ondataavailable med komplett blob
      chunkIntervalRef.current = setTimeout(() => {
        if (recorder.state === 'recording') {
          recorder.stop()
        }
      }, CHUNK_DURATION_MS)
    }

    recordNextChunk()
  }

  const stop = useCallback(() => {
    updateStatus('stopping')
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('STOP')
      wsRef.current.close()
    }
    stopRecordingInternal()
    updateStatus('idle')
  }, [stopRecordingInternal])

  // Städa upp vid unmount
  useEffect(() => {
    return () => {
      clearInterval(chunkIntervalRef.current)
      wsRef.current?.close()
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  return { blocks, status, error, processing, start, stop }
}
