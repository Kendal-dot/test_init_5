import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import UploadPage from './pages/UploadPage'
import JobsPage from './pages/JobsPage'
import JobDetailPage from './pages/JobDetailPage'
import TranscriptPage from './pages/TranscriptPage'
import SearchPage from './pages/SearchPage'
import LivePage from './pages/LivePage'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Navbar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/jobs/:meetingId" element={<JobDetailPage />} />
            <Route path="/transcript/:meetingId" element={<TranscriptPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/live" element={<LivePage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
