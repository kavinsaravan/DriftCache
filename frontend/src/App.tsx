import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import './App.css'

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto py-6 px-4">
            <h1 className="text-3xl font-bold text-gray-900">
              DriftCache
            </h1>
            <p className="text-gray-600">Adaptive Semantic Caching Platform</p>
          </div>
        </header>

        <main className="max-w-7xl mx-auto py-6 px-4">
          <Routes>
            <Route path="/" element={<HomePage />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

function HomePage() {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-2xl font-semibold mb-4">Welcome to DriftCache</h2>
      <p className="text-gray-700">
        Semantic caching and autonomous optimization for LLM systems.
      </p>
    </div>
  )
}

export default App
