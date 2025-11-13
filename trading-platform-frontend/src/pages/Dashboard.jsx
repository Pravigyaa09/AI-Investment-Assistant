import { useState, useEffect } from 'react';
import { DollarSign, TrendingUp, Briefcase, Activity, RefreshCw } from 'lucide-react';
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
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async (refreshPrices = false) => {
    try {
      if (refreshPrices) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      const data = await api.getPortfolio(refreshPrices);
      setPortfolio(data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  if (loading) return <LoadingSpinner size="lg" />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-400">Dashboard</h1>
        <button
          onClick={() => loadDashboardData(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-dark-card border border-dark-border rounded-lg hover:bg-dark-hover disabled:opacity-50 text-gray-400"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh Prices'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-dark-card rounded-xl border border-dark-border p-6">
          <div className="flex items-center justify-between mb-4">
            <DollarSign className="w-8 h-8 text-blue-500" />
            <span className={`text-sm font-medium ${portfolio?.total_pnl_percent >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {formatPercent(portfolio?.total_pnl_percent)}
            </span>
          </div>
          <h3 className="text-sm font-medium text-gray-500">Total Value</h3>
          <p className="text-2xl font-bold text-white mt-1">
            {formatCurrency(portfolio?.total_value)}
          </p>
        </div>

        <div className="bg-dark-card rounded-xl border border-dark-border p-6">
          <TrendingUp className="w-8 h-8 text-green-500 mb-4" />
          <h3 className="text-sm font-medium text-gray-500">Total P&L</h3>
          <p className={`text-2xl font-bold mt-1 ${portfolio?.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {formatCurrency(portfolio?.total_pnl)}
          </p>
        </div>

        <div className="bg-dark-card rounded-xl border border-dark-border p-6">
          <Briefcase className="w-8 h-8 text-purple-500 mb-4" />
          <h3 className="text-sm font-medium text-gray-500">Positions</h3>
          <p className="text-2xl font-bold text-white mt-1">
            {portfolio?.holdings_count || 0}
          </p>
        </div>

        <div className="bg-dark-card rounded-xl border border-dark-border p-6">
          <Activity className="w-8 h-8 text-yellow-500 mb-4" />
          <h3 className="text-sm font-medium text-gray-500">Cash Balance</h3>
          <p className="text-2xl font-bold text-white mt-1">
            {formatCurrency(portfolio?.cash_balance)}
          </p>
        </div>
      </div>

      {portfolio?.holdings?.length > 0 && (
        <div className="bg-dark-card rounded-xl border border-dark-border overflow-hidden">
          <div className="px-6 py-4 border-b border-dark-border">
            <h2 className="text-lg font-semibold text-gray-400">Holdings</h2>
          </div>
          <table className="w-full">
            <thead className="bg-dark-hover">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Quantity</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Value</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border">
              {portfolio.holdings.map((holding) => (
                <tr key={holding.ticker} className="hover:bg-dark-hover">
                  <td className="px-6 py-4 font-medium text-gray-400">{holding.ticker}</td>
                  <td className="px-6 py-4 text-right text-gray-400">{holding.quantity}</td>
                  <td className="px-6 py-4 text-right text-white">{formatCurrency(holding.current_value)}</td>
                  <td className={`px-6 py-4 text-right font-medium ${holding.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
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