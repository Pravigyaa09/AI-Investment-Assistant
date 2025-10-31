import { useState, useEffect } from 'react';
import api from '../services/api';

export const useWatchlist = () => {
  const [watchlist, setWatchlist] = useState([]);
  const [watchlistData, setWatchlistData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load watchlist from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('watchlist');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setWatchlist(parsed);
      } catch (e) {
        console.error('Failed to parse watchlist:', e);
      }
    }
  }, []);

  // Fetch prices for watchlist items
  useEffect(() => {
    if (watchlist.length > 0) {
      fetchWatchlistData();
    }
  }, [watchlist]);

  const fetchWatchlistData = async () => {
    setLoading(true);
    setError(null);
    try {
      const promises = watchlist.map(ticker => 
        api.getPrice(ticker).catch(err => ({
          ticker,
          price: 0,
          error: true
        }))
      );
      const results = await Promise.all(promises);
      setWatchlistData(results);
    } catch (err) {
      setError('Failed to fetch watchlist prices');
    } finally {
      setLoading(false);
    }
  };

  const addToWatchlist = (ticker) => {
    const upperTicker = ticker.toUpperCase();
    if (!watchlist.includes(upperTicker)) {
      const updated = [...watchlist, upperTicker];
      setWatchlist(updated);
      localStorage.setItem('watchlist', JSON.stringify(updated));
      return true;
    }
    return false;
  };

  const removeFromWatchlist = (ticker) => {
    const updated = watchlist.filter(t => t !== ticker);
    setWatchlist(updated);
    localStorage.setItem('watchlist', JSON.stringify(updated));
  };

  const isInWatchlist = (ticker) => {
    return watchlist.includes(ticker.toUpperCase());
  };

  const refreshWatchlist = () => {
    fetchWatchlistData();
  };

  return {
    watchlist,
    watchlistData,
    loading,
    error,
    addToWatchlist,
    removeFromWatchlist,
    isInWatchlist,
    refreshWatchlist
  };
};