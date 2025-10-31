import React, { useState } from 'react';
import { Star, RefreshCw, TrendingUp, TrendingDown, Trash2, Plus } from 'lucide-react';
import { useWatchlist } from '../../hooks/useWatchlist';
import { formatCurrency, formatPercent } from '../../utils/formatters';
import LoadingSpinner from '../common/LoadingSpinner';

const WatchlistCard = () => {
  const {
    watchlist,
    watchlistData,
    loading,
    error,
    addToWatchlist,
    removeFromWatchlist,
    refreshWatchlist
  } = useWatchlist();

  const [newTicker, setNewTicker] = useState('');
  const [addError, setAddError] = useState('');

  const handleAdd = (e) => {
    e.preventDefault();
    setAddError('');
    
    if (!newTicker) {
      setAddError('Please enter a ticker symbol');
      return;
    }

    if (newTicker.length > 5) {
      setAddError('Invalid ticker symbol');
      return;
    }

    const added = addToWatchlist(newTicker);
    if (added) {
      setNewTicker('');
    } else {
      setAddError('Already in watchlist');
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Star className="w-5 h-5 text-yellow-500" />
          Watchlist
        </h2>
        <button
          onClick={refreshWatchlist}
          disabled={loading}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Add new ticker */}
      <form onSubmit={handleAdd} className="mb-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            placeholder="Add ticker..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            maxLength={5}
          />
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add
          </button>
        </div>
        {addError && (
          <p className="text-red-500 text-sm mt-1">{addError}</p>
        )}
      </form>

      {/* Watchlist items */}
      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg mb-3">
          {error}
        </div>
      )}

      {loading && watchlist.length === 0 ? (
        <LoadingSpinner />
      ) : watchlist.length === 0 ? (
        <p className="text-gray-500 text-center py-8">
          No items in watchlist. Add some stocks to track!
        </p>
      ) : (
        <div className="space-y-2">
          {watchlistData.map((item, index) => (
            <WatchlistItem
              key={watchlist[index]}
              ticker={watchlist[index]}
              data={item}
              onRemove={removeFromWatchlist}
              loading={loading}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const WatchlistItem = ({ ticker, data, onRemove, loading }) => {
  const priceChange = data?.change || 0;
  const isPositive = priceChange >= 0;

  return (
    <div className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors">
      <div className="flex items-center gap-3">
        <div>
          <p className="font-semibold text-gray-900">{ticker}</p>
          {loading ? (
            <div className="h-4 w-16 bg-gray-200 animate-pulse rounded" />
          ) : data?.error ? (
            <p className="text-sm text-red-500">Failed to load</p>
          ) : (
            <p className="text-lg font-medium">
              {formatCurrency(data?.price || 0)}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {!loading && !data?.error && (
          <div className={`flex items-center gap-1 ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
            {isPositive ? (
              <TrendingUp className="w-4 h-4" />
            ) : (
              <TrendingDown className="w-4 h-4" />
            )}
            <span className="font-medium">
              {formatPercent(data?.change_percent || 0)}
            </span>
          </div>
        )}
        <button
          onClick={() => onRemove(ticker)}
          className="p-1 hover:bg-red-50 rounded text-red-500 hover:text-red-600 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default WatchlistCard;