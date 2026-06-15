import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        {/* Route stubs for future sub-pages */}
        <Route path="/admin" element={<AdminPlaceholder />} />
        <Route path="/changelog" element={<ChangelogPlaceholder />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  )
}

function AdminPlaceholder() {
  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-primary-dark text-white pt-[72px]">
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-4">Web 管理后台</h1>
        <p className="text-white/60">功能开发中...</p>
      </div>
    </div>
  )
}

function ChangelogPlaceholder() {
  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-white text-primary-dark pt-[72px]">
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-4">更新日志</h1>
        <p className="text-primary-medium">功能开发中...</p>
      </div>
    </div>
  )
}

function NotFound() {
  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-primary-dark text-white pt-[72px]">
      <div className="text-center">
        <h1 className="text-5xl font-bold mb-4">404</h1>
        <p className="text-white/60">页面未找到</p>
      </div>
    </div>
  )
}
