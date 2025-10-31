import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import './styles/index.css'

function TestApp() {
  const [apiStatus, setApiStatus] = useState('Not tested')
  const [loading, setLoading] = useState(false)

  const testBackend = async () => {
    setLoading(true)
    try {
      const response = await fetch('http://localhost:8000/api/health')
      if (response.ok) {
        setApiStatus('✅ Backend Connected!')
      } else {
        setApiStatus('❌ Backend responded but with error')
      }
    } catch (error) {
      setApiStatus('❌ Backend not reachable - Make sure it\'s running on port 8000')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Frontend Test Dashboard</h1>
        
        <div className="space-y-4">
          {/* React Test */}
          <div className="bg-white p-4 rounded-lg shadow">
            <h2 className="font-semibold">React Status</h2>
            <p className="text-green-600">✅ Working - This page is rendered by React</p>
          </div>

          {/* Tailwind Test */}
          <div className="bg-blue-50 p-4 rounded-lg shadow border-2 border-blue-200">
            <h2 className="font-semibold text-blue-900">Tailwind CSS Status</h2>
            <p className="text-blue-600">✅ Working - Styles are applied</p>
          </div>

          {/* API Test */}
          <div className="bg-white p-4 rounded-lg shadow">
            <h2 className="font-semibold mb-2">Backend API Status</h2>
            <p className="mb-3">{apiStatus}</p>
            <button
              onClick={testBackend}
              disabled={loading}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
            >
              {loading ? 'Testing...' : 'Test Backend Connection'}
            </button>
          </div>

          {/* Environment Test */}
          <div className="bg-white p-4 rounded-lg shadow">
            <h2 className="font-semibold">Environment Variables</h2>
            <p className="text-sm text-gray-600">
              API URL: {import.meta.env.VITE_API_BASE_URL || 'Not set'}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <TestApp />
  </React.StrictMode>,
)