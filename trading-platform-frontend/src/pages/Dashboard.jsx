import { useState, useEffect } from 'react';
import { DollarSign, TrendingUp, Briefcase, Activity } from 'lucide-react';
import { formatCurrency, formatPercent } from '../utils/formatters';
import api from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';
import WatchlistCard from '../components/watchlist/WatchlistCard';
import { LoadingOverlay, SkeletonCard, TableSkeleton } from '../components/common/LoadingStates';
import { ErrorMessage } from '../components/common/ErrorHandler';
import { useErrorHandler } from '../hooks/useErrorHandler';

const Dashboard = () => {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const data = await api.getPortfolio();
      setPortfolio(data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner size="lg" />;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <DollarSign className="w-8 h-8 text-blue-600" />
            <span className={`text-sm font-medium ${portfolio?.total_pnl_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatPercent(portfolio?.total_pnl_percent)}
            </span>
          </div>
          <h3 className="text-sm font-medium text-gray-600">Total Value</h3>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {formatCurrency(portfolio?.total_value)}
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6">
          <TrendingUp className="w-8 h-8 text-green-600 mb-4" />
          <h3 className="text-sm font-medium text-gray-600">Total P&L</h3>
          <p className={`text-2xl font-bold mt-1 ${portfolio?.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatCurrency(portfolio?.total_pnl)}
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6">
          <Briefcase className="w-8 h-8 text-purple-600 mb-4" />
          <h3 className="text-sm font-medium text-gray-600">Positions</h3>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {portfolio?.holdings_count || 0}
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6">
          <Activity className="w-8 h-8 text-yellow-600 mb-4" />
          <h3 className="text-sm font-medium text-gray-600">Cash Balance</h3>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {formatCurrency(portfolio?.cash_balance)}
          </p>
        </div>
      </div>

      {portfolio?.holdings?.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Holdings</h2>
          </div>
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Quantity</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Value</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {portfolio.holdings.map((holding) => (
                <tr key={holding.ticker}>
                  <td className="px-6 py-4 font-medium">{holding.ticker}</td>
                  <td className="px-6 py-4 text-right">{holding.quantity}</td>
                  <td className="px-6 py-4 text-right">{formatCurrency(holding.current_value)}</td>
                  <td className={`px-6 py-4 text-right font-medium ${holding.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {formatPercent(holding.pnl_percent)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default Dashboard;