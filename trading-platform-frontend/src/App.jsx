import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import ErrorBoundary from './components/common/ErrorBoundary';
import Layout from './components/layout/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import VerifyEmail from './pages/VerifyEmail';
import Dashboard from './pages/Dashboard';
import Trading from './pages/Trading';
import Portfolio from './pages/Portfolio';
import Analysis from './pages/Analysis';
import News from './pages/News';
import StockAnalysis from './pages/StockAnalysis';

function App() {
  return (
    <ErrorBoundary>
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="trading" element={<Trading />} />
            <Route path="portfolio" element={<Portfolio />} />
            <Route path="analysis" element={<Analysis />} />
            <Route path="stock-analysis" element={<StockAnalysis />} />
            <Route path="news" element={<News />} />
          </Route>
        </Routes>
      </Router>
    </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;