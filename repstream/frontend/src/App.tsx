import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import MyInsights from './pages/MyInsights'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"               element={<Navigate to="/insights" replace />} />
        <Route path="/insights/*"     element={<MyInsights />} />
        {/* redirect old action-center deep links */}
        <Route path="/action-center/*" element={<Navigate to="/insights" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
