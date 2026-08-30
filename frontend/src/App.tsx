import { QueryClientProvider } from '@tanstack/react-query'
import { Route, BrowserRouter as Router, Routes } from 'react-router-dom'

import { ErrorBoundary } from '@/components/ErrorBoundary'
import { queryClient } from '@/lib/queryClient'
import { CompletePage } from '@/pages/CompletePage'
import { DashboardPage } from '@/pages/DashboardPage'
import { ErrorPage } from '@/pages/ErrorPage'
import { NewSessionPage } from '@/pages/NewSessionPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ReadbackPage } from '@/pages/ReadbackPage'
import { WorkspacePage } from '@/pages/WorkspacePage'

/** Mục N — định tuyến màn hình. Đã lược bỏ /login, /audit, /stats, /admin/users (xem Checklist.MD). */
export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Router>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/sessions/new" element={<NewSessionPage />} />
            <Route path="/sessions/:sessionId" element={<WorkspacePage />} />
            <Route path="/sessions/:sessionId/readback" element={<ReadbackPage />} />
            <Route path="/sessions/:sessionId/complete" element={<CompletePage />} />
            <Route path="/error" element={<ErrorPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Router>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
