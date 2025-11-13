import React, { useState, useEffect, useCallback } from 'react';
import { Loader2, Star, StarOff, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { formatCurrency } from '../utils/formatters';
import api from '../services/api';
import Alert from '../components/common/Alert';
import { useWatchlist } from '../hooks/useWatchlist';
import { useErrorHandler } from '../hooks/useErrorHandler';
import { LoadingOverlay } from '../components/common/LoadingStates';
import { ErrorMessage } from '../components/common/ErrorHandler';

const Trading = () => {
  const [ticker, setTicker] = useState('');
  const [side, setSide] = useState('BUY');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [message, setMessage] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [tradeLoading, setTradeLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Use custom hooks
  const { error, loading, handleAsync, clearError } = useErrorHandler();
  const { addToWatchlist, removeFromWatchlist, isInWatchlist } = useWatchlist();
  const [isWatched, setIsWatched] = useState(false);

  useEffect(() => {
    loadPortfolio();
  }, []);

  useEffect(() => {
    if (ticker) {
      setIsWatched(isInWatchlist(ticker));
    }
  }, [ticker, isInWatchlist]);

  const loadPortfolio = async () => {
    await handleAsync(async () => {
      const data = await api.getPortfolio();
      setPortfolio(data);
    });
  };

  const fetchPrice = useCallback(async (silent = false) => {
    if (!ticker) {
      setMessage({ type: 'error', text: 'Please enter a ticker symbol' });
      return;
    }

    if (!silent) setPriceLoading(true);
    clearError();

    try {
      const data = await api.getPrice(ticker);
      console.log('Price data:', data);
      setPrice(data.price?.toString() || '');
      setMarketData(data);
      setIsWatched(isInWatchlist(ticker));
      setLastUpdated(new Date());
      if (!silent) setMessage(null);
    } catch (error) {
      if (!silent) {
        setMessage({
          type: 'error',
          text: `Failed to fetch price for ${ticker}. Please check the ticker symbol.`
        });
      }
      setPrice('');
      setMarketData(null);
      setAutoRefresh(false);
    } finally {
      if (!silent) setPriceLoading(false);
    }
  }, [ticker, clearError, isInWatchlist]);

  // Auto-refresh price every 10 seconds when enabled
  useEffect(() => {
    let intervalId;
    if (autoRefresh && ticker && marketData) {
      intervalId = setInterval(() => {
        fetchPrice(true); // Silent refresh
      }, 10000); // 10 seconds
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [autoRefresh, ticker, marketData, fetchPrice]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validation
    if (!ticker || !quantity || !price) {
      setMessage({ type: 'error', text: 'Please fill in all fields' });
      return;
    }

    if (parseFloat(quantity) <= 0) {
      setMessage({ type: 'error', text: 'Quantity must be greater than 0' });
      return;
    }

    if (parseFloat(price) <= 0) {
      setMessage({ type: 'error', text: 'Price must be greater than 0' });
      return;
    }

    // Check if user has enough cash for BUY
    if (side === 'BUY') {
      const totalCost = parseFloat(quantity) * parseFloat(price);
      if (portfolio?.cash_balance < totalCost) {
        setMessage({ 
          type: 'error', 
          text: `Insufficient funds. You need ${formatCurrency(totalCost)} but have ${formatCurrency(portfolio?.cash_balance)}` 
        });
        return;
      }
    }

    setTradeLoading(true);
    setMessage(null);

    try {
      const response = await api.executeTrade({
        ticker: ticker.toUpperCase(),
        side,
        quantity: parseFloat(quantity),
        price: parseFloat(price),
      });

      setMessage({
        type: 'success',
        text: response.message || `${side} order executed successfully for ${ticker}`,
      });

      // Reset form
      setTicker('');
      setQuantity('');
      setPrice('');
      setMarketData(null);
      setIsWatched(false);
      setAutoRefresh(false);
      setLastUpdated(null);

      // Reload portfolio
      await loadPortfolio();
    } catch (error) {
      setMessage({
        type: 'error',
        text: error.message || 'Failed to execute trade. Please try again.',
      });
    } finally {
      setTradeLoading(false);
    }
  };

  const toggleWatchlist = () => {
    if (!ticker) return;
    
    if (isWatched) {
      removeFromWatchlist(ticker);
      setIsWatched(false);
      setMessage({ type: 'info', text: `${ticker} removed from watchlist` });
    } else {
      addToWatchlist(ticker);
      setIsWatched(true);
      setMessage({ type: 'success', text: `${ticker} added to watchlist` });
    }
  };

  const totalValue = parseFloat(quantity || 0) * parseFloat(price || 0);
  const commission = totalValue * 0.001; // 0.1% commission

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-400">Trading</h1>
        <button
          onClick={loadPortfolio}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-dark-card border border-dark-border rounded-lg hover:bg-dark-hover disabled:opacity-50 text-gray-400"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <ErrorMessage 
          error={error} 
          onClose={clearError}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="bg-dark-card rounded-xl border border-dark-border p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-semibold text-gray-400">Execute Trade</h2>
              {ticker && (
                <button
                  onClick={toggleWatchlist}
                  className="p-2 hover:bg-dark-hover rounded-lg transition-colors"
                  title={isWatched ? 'Remove from watchlist' : 'Add to watchlist'}
                >
                  {isWatched ? (
                    <Star className="w-5 h-5 text-yellow-500 fill-current" />
                  ) : (
                    <StarOff className="w-5 h-5 text-gray-400" />
                  )}
                </button>
              )}
            </div>

            {message && (
              <div className="mb-4">
                <Alert
                  type={message.type}
                  message={message.text}
                  onClose={() => setMessage(null)}
                />
              </div>
            )}

            <LoadingOverlay show={tradeLoading}>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Ticker Symbol
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={ticker}
                      onChange={(e) => setTicker(e.target.value.toUpperCase())}
                      className="flex-1 px-4 py-2 bg-black border border-dark-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white placeholder-gray-600"
                      placeholder="AAPL"
                      maxLength={5}
                      required
                    />
                    <button
                      type="button"
                      onClick={fetchPrice}
                      disabled={priceLoading || !ticker}
                      className="px-4 py-2 bg-dark-hover text-gray-400 rounded-lg hover:bg-dark-border disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                      {priceLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        'Get Price'
                      )}
                    </button>
                  </div>
                </div>

                {marketData && (
                  <div className="p-3 bg-dark-hover border border-dark-border rounded-lg space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500">Current Market Price</span>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-semibold text-white">
                          {formatCurrency(marketData.price)}
                        </span>
                        {marketData.change && (
                          <span className={`text-sm flex items-center ${marketData.change >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                            {marketData.change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            {Math.abs(marketData.change).toFixed(2)}%
                          </span>
                        )}
                      </div>
                    </div>
                    {lastUpdated && (
                      <div className="text-xs text-gray-500">
                        Last updated: {lastUpdated.toLocaleTimeString()}
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <label className="flex items-center text-xs text-gray-500">
                        <input
                          type="checkbox"
                          checked={autoRefresh}
                          onChange={(e) => setAutoRefresh(e.target.checked)}
                          className="mr-2 rounded"
                        />
                        Auto-refresh (10s)
                      </label>
                      {autoRefresh && (
                        <span className="text-xs text-green-500 flex items-center">
                          <span className="w-1.5 h-1.5 bg-green-500 rounded-full mr-1 animate-pulse"></span>
                          Live
                        </span>
                      )}
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Side</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setSide('BUY')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        side === 'BUY'
                          ? 'bg-green-500 text-white'
                          : 'bg-dark-hover text-gray-400 hover:bg-dark-border'
                      }`}
                    >
                      Buy
                    </button>
                    <button
                      type="button"
                      onClick={() => setSide('SELL')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        side === 'SELL'
                          ? 'bg-red-500 text-white'
                          : 'bg-dark-hover text-gray-400 hover:bg-dark-border'
                      }`}
                    >
                      Sell
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Quantity</label>
                    <input
                      type="number"
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      className="w-full px-4 py-2 bg-black border border-dark-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white placeholder-gray-600"
                      placeholder="100"
                      min="1"
                      step="1"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Price per Share</label>
                    <input
                      type="number"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                      className="w-full px-4 py-2 bg-black border border-dark-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white placeholder-gray-600"
                      placeholder="150.00"
                      min="0.01"
                      step="0.01"
                      required
                    />
                  </div>
                </div>

                {quantity && price && (
                  <div className="p-4 bg-dark-hover border border-dark-border rounded-lg space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Total Value</span>
                      <span className="font-semibold text-white">
                        {formatCurrency(totalValue)}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Commission (0.1%)</span>
                      <span className="text-gray-500">
                        {formatCurrency(commission)}
                      </span>
                    </div>
                    <div className="pt-2 border-t border-dark-border flex justify-between">
                      <span className="text-gray-400 font-medium">Total Cost</span>
                      <span className="font-bold text-lg text-white">
                        {formatCurrency(side === 'BUY' ? totalValue + commission : totalValue - commission)}
                      </span>
                    </div>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={tradeLoading || !ticker || !quantity || !price}
                  className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-colors ${
                    side === 'BUY' 
                      ? 'bg-green-500 hover:bg-green-600 disabled:bg-green-300' 
                      : 'bg-red-500 hover:bg-red-600 disabled:bg-red-300'
                  } disabled:cursor-not-allowed`}
                >
                  {tradeLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin mx-auto" />
                  ) : (
                    `${side} ${ticker || 'Stock'}`
                  )}
                </button>
              </form>
            </LoadingOverlay>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-dark-card rounded-xl border border-dark-border p-6">
            <h3 className="text-lg font-semibold text-gray-400 mb-4">Account Summary</h3>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-500">Available Cash</p>
                <p className="text-2xl font-bold text-white">
                  {portfolio ? formatCurrency(portfolio.cash_balance) : '-'}
                </p>
              </div>
              <div className="pt-3 border-t border-dark-border">
                <p className="text-sm text-gray-500">Portfolio Value</p>
                <p className="text-xl font-semibold text-white">
                  {portfolio ? formatCurrency(portfolio.total_value) : '-'}
                </p>
              </div>
              <div className="pt-3 border-t border-dark-border">
                <p className="text-sm text-gray-500">Total P&L</p>
                <p className={`text-xl font-semibold ${
                  portfolio?.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'
                }`}>
                  {portfolio ? formatCurrency(portfolio.total_pnl || 0) : '-'}
                </p>
              </div>
            </div>
          </div>

          {/* Quick Tips */}
          <div className="bg-dark-hover border border-dark-border rounded-xl p-4">
            <h4 className="font-medium text-gray-400 mb-2">Trading Tips</h4>
            <ul className="text-sm text-gray-500 space-y-1">
              <li>• Click the star to add stocks to your watchlist</li>
              <li>• Check market price before placing orders</li>
              <li>• Commission is 0.1% per trade</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Trading;