import { useState, useEffect } from 'react';
import { Newspaper, RefreshCw, ExternalLink, Filter, TrendingUp, Calendar, Building2, ArrowUpCircle, ArrowDownCircle, MinusCircle, AlertCircle, ShoppingCart } from 'lucide-react';
import api from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

const News = () => {
  const [news, setNews] = useState([]);
  const [holdings, setHoldings] = useState([]);
  const [categories, setCategories] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('personalized');
  const [articlesPerStock, setArticlesPerStock] = useState(10); // New state for articles per stock

  useEffect(() => {
    loadCategories();
    loadNews();
  }, []);

  useEffect(() => {
    // Reload news when tab changes
    if (activeTab) {
      loadNews();
    }
  }, [activeTab]);

  const loadCategories = async () => {
    try {
      const data = await api.getCategories();
      setCategories(data.categories || {});
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  };

  const loadNews = async (refresh = false) => {
    try {
      if (refresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      let data;
      if (activeTab === 'personalized') {
        data = await api.getPersonalizedNewsWithRecommendations(50);
        setNews(data.articles || []);
        setHoldings(data.holdings || []);
      } else {
        // Category-based news
        data = await api.getCategoryNews(activeTab, 50);
        setNews(data.articles || []);
        setHoldings([]); // Categories don't use holdings filter
      }
    } catch (error) {
      console.error('Error loading news:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Date unknown';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'Date unknown';
    }
  };

  const getRecommendationBadge = (recommendation) => {
    if (!recommendation) return null;

    const { action, confidence, reasons, owned } = recommendation;

    const badges = {
      BUY: {
        icon: ArrowUpCircle,
        bgColor: 'bg-green-900/30',
        textColor: 'text-green-400',
        borderColor: 'border-green-500/50'
      },
      SELL: {
        icon: ArrowDownCircle,
        bgColor: 'bg-red-900/30',
        textColor: 'text-red-400',
        borderColor: 'border-red-500/50'
      },
      HOLD: {
        icon: MinusCircle,
        bgColor: 'bg-yellow-900/30',
        textColor: 'text-yellow-400',
        borderColor: 'border-yellow-500/50'
      },
      AVOID: {
        icon: AlertCircle,
        bgColor: 'bg-orange-900/30',
        textColor: 'text-orange-400',
        borderColor: 'border-orange-500/50'
      }
    };

    const config = badges[action] || badges.HOLD;
    const Icon = config.icon;

    return (
      <div className="mt-4 pt-4 border-t border-dark-border">
        <div className={`flex items-center justify-between p-3 rounded-lg border ${config.bgColor} ${config.borderColor}`}>
          <div className="flex items-center gap-2">
            <Icon className={`w-5 h-5 ${config.textColor}`} />
            <div>
              <div className="flex items-center gap-2">
                <span className={`font-semibold ${config.textColor}`}>{action}</span>
                {owned && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-blue-900/50 text-blue-300 border border-blue-500/30">
                    Owned
                  </span>
                )}
                {!owned && action === 'BUY' && (
                  <ShoppingCart className="w-3 h-3 text-green-400" />
                )}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {reasons && reasons.length > 0 ? reasons.join(', ') : 'Analysis based on market data'}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500">Confidence</div>
            <div className={`text-sm font-semibold ${config.textColor}`}>
              {Math.round(confidence * 100)}%
            </div>
          </div>
        </div>
      </div>
    );
  };

  // First filter by ticker and search
  const basicFilteredNews = news.filter(article => {
    const matchesTicker = selectedTicker === 'all' || article.ticker === selectedTicker;
    const matchesSearch = !searchTerm ||
      article.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      article.source?.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesTicker && matchesSearch;
  });

  // Then limit articles per stock
  const filteredNews = (() => {
    if (articlesPerStock === 'all') {
      return basicFilteredNews;
    }

    const tickerCounts = {};
    return basicFilteredNews.filter(article => {
      const ticker = article.ticker;
      tickerCounts[ticker] = (tickerCounts[ticker] || 0) + 1;
      return tickerCounts[ticker] <= parseInt(articlesPerStock);
    });
  })();

  if (loading) return <LoadingSpinner size="lg" />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-400">Market News</h1>
          <p className="text-sm text-gray-500 mt-1">
            {activeTab === 'personalized'
              ? holdings.length > 0
                ? `Personalized news for your ${holdings.length} holdings with AI recommendations`
                : 'General market news with AI recommendations'
              : `${categories[activeTab] || 'Category'} news with AI recommendations`
            }
          </p>
        </div>
        <button
          onClick={() => loadNews(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-dark-card border border-dark-border rounded-lg hover:bg-dark-hover disabled:opacity-50 text-gray-400"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Category Tabs */}
      <div className="bg-dark-card rounded-xl border border-dark-border p-4">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-4 h-4 text-gray-400" />
          <h3 className="text-sm font-medium text-gray-400">News Categories</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveTab('personalized')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'personalized'
                ? 'bg-blue-900 text-blue-400 border border-blue-500/50'
                : 'bg-black text-gray-400 border border-dark-border hover:bg-dark-hover'
            }`}
          >
            My Portfolio
          </button>
          {Object.entries(categories).map(([key, name]) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === key
                  ? 'bg-blue-900 text-blue-400 border border-blue-500/50'
                  : 'bg-black text-gray-400 border border-dark-border hover:bg-dark-hover'
              }`}
            >
              {name}
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      {activeTab === 'personalized' && holdings.length > 0 && (
        <div className="bg-dark-card rounded-xl border border-dark-border p-4">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Ticker Filter */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-400 mb-2">
                <Filter className="w-4 h-4 inline mr-1" />
                Filter by Stock
              </label>
              <select
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value)}
                className="w-full px-4 py-2 bg-black border border-dark-border rounded-lg text-white focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Stocks</option>
                {holdings.map(ticker => (
                  <option key={ticker} value={ticker}>{ticker}</option>
                ))}
              </select>
            </div>

            {/* Articles per Stock */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Articles per Stock
              </label>
              <select
                value={articlesPerStock}
                onChange={(e) => setArticlesPerStock(e.target.value)}
                className="w-full px-4 py-2 bg-black border border-dark-border rounded-lg text-white focus:ring-2 focus:ring-blue-500"
              >
                <option value="1">1 article</option>
                <option value="3">3 articles</option>
                <option value="5">5 articles</option>
                <option value="10">10 articles</option>
                <option value="15">15 articles</option>
                <option value="all">Show all</option>
              </select>
            </div>

            {/* Search */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Search News
              </label>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search headlines..."
                className="w-full px-4 py-2 bg-black border border-dark-border rounded-lg text-white placeholder-gray-600 focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="mt-3 text-sm text-gray-500">
            Showing {filteredNews.length} of {news.length} articles
          </div>
        </div>
      )}

      {/* Filters for category tabs */}
      {activeTab !== 'personalized' && (
        <div className="bg-dark-card rounded-xl border border-dark-border p-4">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Articles per Stock */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Articles per Stock
              </label>
              <select
                value={articlesPerStock}
                onChange={(e) => setArticlesPerStock(e.target.value)}
                className="w-full px-4 py-2 bg-black border border-dark-border rounded-lg text-white focus:ring-2 focus:ring-blue-500"
              >
                <option value="1">1 article</option>
                <option value="3">3 articles</option>
                <option value="5">5 articles</option>
                <option value="10">10 articles</option>
                <option value="15">15 articles</option>
                <option value="all">Show all</option>
              </select>
            </div>

            {/* Search */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Search News
              </label>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search headlines..."
                className="w-full px-4 py-2 bg-black border border-dark-border rounded-lg text-white placeholder-gray-600 focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="mt-3 text-sm text-gray-500">
            Showing {filteredNews.length} of {news.length} articles
          </div>
        </div>
      )}

      {/* News Grid */}
      {filteredNews.length === 0 ? (
        <div className="bg-dark-card rounded-xl border border-dark-border p-12 text-center">
          <Newspaper className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-400 mb-2">No news found</h3>
          <p className="text-gray-500">
            {searchTerm || selectedTicker !== 'all'
              ? 'Try adjusting your filters'
              : 'No news available at this time'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredNews.map((article, index) => (
            <div
              key={index}
              className="bg-dark-card rounded-xl border border-dark-border p-6 hover:bg-dark-hover transition-colors group flex flex-col"
            >
              {/* Article Header */}
              <div className="flex items-start justify-between mb-3">
                <span className="inline-flex items-center px-2 py-1 rounded-md bg-blue-900/30 text-blue-400 text-xs font-medium">
                  <TrendingUp className="w-3 h-3 mr-1" />
                  {article.ticker}
                </span>
                {article.url && (
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-500 hover:text-blue-400 transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                )}
              </div>

              {/* Article Title */}
              <h3 className="text-lg font-semibold text-gray-300 mb-3 line-clamp-3 group-hover:text-white transition-colors">
                {article.title}
              </h3>

              {/* Article Meta */}
              <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
                {article.source && (
                  <div className="flex items-center gap-1">
                    <Building2 className="w-3 h-3" />
                    <span>{article.source}</span>
                  </div>
                )}
                {article.published_at && (
                  <div className="flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    <span>{formatDate(article.published_at)}</span>
                  </div>
                )}
              </div>

              {/* AI Recommendation Badge */}
              {article.recommendation && getRecommendationBadge(article.recommendation)}

              {/* Read More Link */}
              {article.url && (
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 mt-4 text-sm text-blue-400 hover:text-blue-300 transition-colors"
                >
                  Read full article
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default News;
