import React, { useState, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';
import { formatCurrency, formatPercent, formatDate } from '../utils/formatters';
import api from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

const Portfolio = () => {
  const [portfolio, setPortfolio] = useState(null);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadPortfolioData();
  }, []);

  const loadPortfolioData = async (refreshPrices = false) => {
    try {
      if (refreshPrices) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      const [portfolioData, tradesData] = await Promise.all([
        api.getPortfolio(refreshPrices),
        api.getTrades()
      ]);
      setPortfolio(portfolioData);
      setTrades(tradesData || []);
    } catch (error) {
      console.error('Error loading portfolio:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const closePosition = async (ticker) => {
    if (!window.confirm(`Close position for ${ticker}?`)) return;
    
    try {
      await api.closePosition(ticker);
      loadPortfolioData();
    } catch (error) {
      console.error('Error closing position:', error);
    }
  };

  if (loading) return <LoadingSpinner size="lg" />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-400">Portfolio Overview</h1>
        <button
          onClick={() => loadPortfolioData(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-dark-card border border-dark-border rounded-lg hover:bg-dark-hover disabled:opacity-50 text-gray-400"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh Prices'}
        </button>
      </div>

      {/* Portfolio Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-dark-card rounded-xl border border-dark-border p-6">
          <h3 className="text-sm font-medium text-gray-500">Total Value</h3>
          <p className="text-2xl font-bold text-white mt-1">
            {formatCurrency(portfolio?.total_value)}
          </p>
        </div>
        <div className="bg-dark-card rounded-xl border border-dark-border p-6">
          <h3 className="text-sm font-medium text-gray-500">Total P&L</h3>
          <p className={`text-2xl font-bold mt-1 ${portfolio?.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {formatCurrency(portfolio?.total_pnl)}
          </p>
        </div>
        <div className="bg-dark-card rounded-xl border border-dark-border p-6">
          <h3 className="text-sm font-medium text-gray-500">Cash Balance</h3>
          <p className="text-2xl font-bold text-white mt-1">
            {formatCurrency(portfolio?.cash_balance)}
          </p>
        </div>
      </div>

      {/* Holdings */}
      {portfolio?.holdings?.length > 0 && (
        <div className="bg-dark-card rounded-xl border border-dark-border p-6">
          <h2 className="text-lg font-semibold text-gray-400 mb-4">Holdings</h2>
          <div className="space-y-3">
            {portfolio.holdings.map((holding) => (
              <div key={holding.ticker} className="border border-dark-border rounded-lg p-4 hover:bg-dark-hover">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-gray-400">{holding.ticker}</h3>
                    <p className="text-sm text-gray-500">{holding.quantity} shares @ {formatCurrency(holding.avg_cost)}</p>
                  </div>
                  <div className="text-right">
                    <p className={`font-semibold ${holding.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {formatPercent(holding.pnl_percent)}
                    </p>
                    <p className="text-sm text-white">{formatCurrency(holding.current_value)}</p>
                    <button
                      onClick={() => closePosition(holding.ticker)}
                      className="mt-2 text-red-500 hover:text-red-400 text-sm font-medium"
                    >
                      Close Position
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trade History */}
      {trades.length > 0 && (
        <div className="bg-dark-card rounded-xl border border-dark-border p-6">
          <h2 className="text-lg font-semibold text-gray-400 mb-4">Recent Trades</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-dark-hover">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Ticker</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Side</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Quantity</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Price</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-border">
                {trades.slice(0, 10).map((trade, idx) => (
                  <tr key={idx} className="hover:bg-dark-hover">
                    <td className="px-4 py-2 text-sm text-gray-400">{formatDate(trade.executed_at)}</td>
                    <td className="px-4 py-2 font-medium text-gray-400">{trade.ticker}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                        trade.side === 'BUY' ? 'bg-green-900 text-green-400' : 'bg-red-900 text-red-400'
                      }`}>
                        {trade.side}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right text-sm text-gray-400">{trade.quantity}</td>
                    <td className="px-4 py-2 text-right text-sm text-white">{formatCurrency(trade.price)}</td>
                    <td className="px-4 py-2 text-right font-medium text-white">{formatCurrency(trade.total_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default Portfolio;