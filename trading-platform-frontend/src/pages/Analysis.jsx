import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, BarChart3, RefreshCw, Calendar, DollarSign, Activity, Brain, AlertCircle } from 'lucide-react';
import { ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import api from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

const Analysis = () => {
  const [holdings, setHoldings] = useState([]);
  const [selectedTicker, setSelectedTicker] = useState('');
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [timeframe, setTimeframe] = useState('180'); // days
  const [chartData, setChartData] = useState([]);
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [priceChange, setPriceChange] = useState(null);

  useEffect(() => {
    loadHoldings();
  }, []);

  useEffect(() => {
    if (selectedTicker) {
      loadAnalysisData();
    }
  }, [selectedTicker, timeframe]);

  const loadHoldings = async () => {
    try {
      setLoading(true);
      const data = await api.getPortfolio(false);
      const holdingsList = data.holdings || [];
      setHoldings(holdingsList);

      // Auto-select first holding
      if (holdingsList.length > 0 && !selectedTicker) {
        setSelectedTicker(holdingsList[0].ticker);
      }
    } catch (error) {
      console.error('Error loading holdings:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAnalysisData = async () => {
    setChartLoading(true);
    try {
      // Load OHLCV chart data and AI analysis in parallel
      const [chartResponse, aiResponse, priceResponse] = await Promise.all([
        fetch(`http://localhost:8000/api/chart/ohlcv?ticker=${selectedTicker}&days=${timeframe}`).then(r => r.json()),
        fetch(`http://localhost:8000/api/ml/recommend?ticker=${selectedTicker}&horizon_days=21&top_n_news=6`).then(r => r.json()),
        api.getPrice(selectedTicker)
      ]);

      // Process OHLCV chart data with moving averages
      if (chartResponse.points) {
        const processed = processChartData(chartResponse.points);
        setChartData(processed);
      }

      setAiAnalysis(aiResponse);
      setCurrentPrice(priceResponse);

      // Calculate price change
      if (chartResponse.points && chartResponse.points.length > 1) {
        const firstPrice = chartResponse.points[0].close;
        const lastPrice = chartResponse.points[chartResponse.points.length - 1].close;
        const change = ((lastPrice - firstPrice) / firstPrice) * 100;
        setPriceChange(change);
      }
    } catch (error) {
      console.error('Error loading analysis data:', error);
    } finally {
      setChartLoading(false);
    }
  };

  const processChartData = (points) => {
    // Calculate moving averages and include OHLCV data
    return points.map((point, index) => {
      const ma20 = calculateMA(points, index, 20);
      const ma50 = calculateMA(points, index, 50);
      const ma200 = calculateMA(points, index, 200);

      return {
        date: point.date,
        open: point.open,
        high: point.high,
        low: point.low,
        close: point.close,
        volume: point.volume,
        price: point.close, // Keep for backward compatibility
        ma20,
        ma50,
        ma200
      };
    });
  };

  const calculateMA = (data, currentIndex, period) => {
    if (currentIndex < period - 1) return null;

    const sum = data
      .slice(currentIndex - period + 1, currentIndex + 1)
      .reduce((acc, point) => acc + point.close, 0);

    return sum / period;
  };

  const getTimeframeLabel = (days) => {
    const labels = {
      '1': '1D',
      '7': '1W',
      '30': '1M',
      '180': '6M',
      '365': '1Y'
    };
    return labels[days] || `${days}D`;
  };

  const getRecommendationColor = (action) => {
    const colors = {
      'Buy': 'text-green-400 bg-green-900/30 border-green-500/50',
      'Sell': 'text-red-400 bg-red-900/30 border-red-500/50',
      'Hold': 'text-yellow-400 bg-yellow-900/30 border-yellow-500/50'
    };
    return colors[action] || 'text-gray-400 bg-gray-900/30 border-gray-500/50';
  };

  const getSentimentColor = (label) => {
    const colors = {
      'positive': 'text-green-400',
      'negative': 'text-red-400',
      'neutral': 'text-gray-400'
    };
    return colors[label] || 'text-gray-400';
  };

  // Custom tooltip for OHLC data
  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0].payload;

    return (
      <div className="bg-dark-card border border-dark-border rounded-lg p-3 shadow-lg">
        <p className="text-gray-400 text-xs mb-2">{new Date(data.date).toLocaleDateString()}</p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <span className="text-gray-500">Open:</span>
            <span className="text-white font-medium">${data.open?.toFixed(2) || 'N/A'}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-gray-500">High:</span>
            <span className="text-green-400 font-medium">${data.high?.toFixed(2) || 'N/A'}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-gray-500">Low:</span>
            <span className="text-red-400 font-medium">${data.low?.toFixed(2) || 'N/A'}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-gray-500">Close:</span>
            <span className="text-blue-400 font-medium">${data.close?.toFixed(2) || 'N/A'}</span>
          </div>
          <div className="flex justify-between gap-4 pt-1 border-t border-dark-border">
            <span className="text-gray-500">Volume:</span>
            <span className="text-purple-400 font-medium">{data.volume?.toLocaleString() || 'N/A'}</span>
          </div>
        </div>
      </div>
    );
  };

  if (loading) return <LoadingSpinner size="lg" />;

  if (holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <AlertCircle className="w-16 h-16 text-gray-600 mb-4" />
        <h2 className="text-2xl font-bold text-gray-400 mb-2">No Holdings Found</h2>
        <p className="text-gray-500">Add some stocks to your portfolio to see analysis</p>
      </div>
    );
  }

  const selectedHolding = holdings.find(h => h.ticker === selectedTicker);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-400">Stock Analysis</h1>
          <p className="text-sm text-gray-500 mt-1">Deep dive into your holdings with AI-powered insights</p>
        </div>
        <button
          onClick={loadAnalysisData}
          disabled={chartLoading}
          className="flex items-center gap-2 px-4 py-2 bg-dark-card border border-dark-border rounded-lg hover:bg-dark-hover disabled:opacity-50 text-gray-400"
        >
          <RefreshCw className={`w-4 h-4 ${chartLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stock Selector */}
      <div className="bg-dark-card rounded-xl border border-dark-border p-4">
        <label className="block text-sm font-medium text-gray-400 mb-2">
          Select Holding to Analyze
        </label>
        <select
          value={selectedTicker}
          onChange={(e) => setSelectedTicker(e.target.value)}
          className="w-full md:w-1/3 px-4 py-2 bg-black border border-dark-border rounded-lg text-white focus:ring-2 focus:ring-blue-500"
        >
          {holdings.map(holding => (
            <option key={holding.ticker} value={holding.ticker}>
              {holding.ticker} - {holding.quantity} shares @ ${holding.avg_cost.toFixed(2)}
            </option>
          ))}
        </select>
      </div>

      {chartLoading ? (
        <LoadingSpinner size="lg" />
      ) : (
        <>
          {/* Overview Section */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Company & Price */}
            <div className="md:col-span-2 bg-dark-card rounded-xl border border-dark-border p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-3xl font-bold text-white">{selectedTicker}</h2>
                  <p className="text-gray-500 text-sm mt-1">
                    {timeframe === '1' ? '1 Day' :
                     timeframe === '7' ? '1 Week' :
                     timeframe === '30' ? '1 Month' :
                     timeframe === '180' ? '6 Month' : '1 Year'} Performance
                  </p>
                </div>
                {priceChange !== null && (
                  <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${priceChange >= 0 ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                    {priceChange >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                    <span className="font-bold text-lg">{priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%</span>
                  </div>
                )}
              </div>
              {currentPrice && (
                <div className="mt-4">
                  <div className="text-5xl font-bold text-white">${currentPrice.price.toFixed(2)}</div>
                  <div className="text-sm text-gray-500 mt-2">
                    Current Price • Last updated: {new Date().toLocaleTimeString()}
                  </div>
                </div>
              )}
            </div>

            {/* Holdings Info */}
            {selectedHolding && (
              <>
                <div className="bg-dark-card rounded-xl border border-dark-border p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <DollarSign className="w-5 h-5 text-blue-400" />
                    <span className="text-sm text-gray-500">Your Position</span>
                  </div>
                  <div className="text-2xl font-bold text-white">${selectedHolding.current_value.toFixed(2)}</div>
                  <div className="text-sm text-gray-500 mt-1">{selectedHolding.quantity} shares</div>
                </div>

                <div className="bg-dark-card rounded-xl border border-dark-border p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <Activity className="w-5 h-5 text-purple-400" />
                    <span className="text-sm text-gray-500">P&L</span>
                  </div>
                  <div className={`text-2xl font-bold ${selectedHolding.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {selectedHolding.pnl >= 0 ? '+' : ''}${selectedHolding.pnl.toFixed(2)}
                  </div>
                  <div className={`text-sm ${selectedHolding.pnl_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {selectedHolding.pnl_percent >= 0 ? '+' : ''}{selectedHolding.pnl_percent.toFixed(2)}%
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Price Chart */}
          <div className="bg-dark-card rounded-xl border border-dark-border p-6">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold text-gray-400">Price Chart</h3>
              <div className="flex gap-2">
                {['1', '7', '30', '180', '365'].map(days => (
                  <button
                    key={days}
                    onClick={() => setTimeframe(days)}
                    className={`px-3 py-1 rounded text-sm font-medium transition ${
                      timeframe === days
                        ? 'bg-blue-900 text-blue-400 border border-blue-500/50'
                        : 'bg-black text-gray-400 border border-dark-border hover:bg-dark-hover'
                    }`}
                  >
                    {getTimeframeLabel(days)}
                  </button>
                ))}
              </div>
            </div>

            <ResponsiveContainer width="100%" height={500}>
              <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
                <XAxis
                  dataKey="date"
                  stroke="#6b7280"
                  tick={{ fill: '#9ca3af' }}
                  tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                />
                <YAxis
                  yAxisId="price"
                  stroke="#6b7280"
                  tick={{ fill: '#9ca3af' }}
                  domain={['auto', 'auto']}
                  label={{ value: 'Price ($)', angle: -90, position: 'insideLeft', fill: '#9ca3af' }}
                />
                <YAxis
                  yAxisId="volume"
                  orientation="right"
                  stroke="#6b7280"
                  tick={{ fill: '#9ca3af' }}
                  domain={[0, 'auto']}
                  label={{ value: 'Volume', angle: 90, position: 'insideRight', fill: '#9ca3af' }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ color: '#9ca3af' }} />

                {/* Volume bars */}
                <Bar
                  yAxisId="volume"
                  dataKey="volume"
                  fill="#a78bfa"
                  opacity={0.3}
                  name="Volume"
                />

                {/* Price line */}
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="price"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="Price"
                />

                {/* Moving averages */}
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="ma20"
                  stroke="#10b981"
                  strokeWidth={1.5}
                  dot={false}
                  name="MA 20"
                  strokeDasharray="5 5"
                />
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="ma50"
                  stroke="#f59e0b"
                  strokeWidth={1.5}
                  dot={false}
                  name="MA 50"
                  strokeDasharray="5 5"
                />
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="ma200"
                  stroke="#ef4444"
                  strokeWidth={1.5}
                  dot={false}
                  name="MA 200"
                  strokeDasharray="5 5"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* AI Analysis Section */}
          {aiAnalysis && aiAnalysis.status === 'ok' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Trading Signal */}
              <div className="bg-dark-card rounded-xl border border-dark-border p-6">
                <div className="flex items-center gap-3 mb-4">
                  <Brain className="w-6 h-6 text-blue-400" />
                  <h3 className="text-xl font-bold text-gray-400">AI Trading Signal</h3>
                </div>

                <div className={`inline-flex items-center px-4 py-2 rounded-lg border font-semibold text-lg mb-4 ${getRecommendationColor(aiAnalysis.decision.action)}`}>
                  {aiAnalysis.decision.action.toUpperCase()}
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Confidence</span>
                    <span className="text-white font-semibold">{(aiAnalysis.decision.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${aiAnalysis.decision.confidence * 100}%` }}
                    />
                  </div>
                </div>

                <div className="mt-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">Key Metrics</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Trend Score</span>
                      <span className={`font-medium ${aiAnalysis.features.trend_score > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {aiAnalysis.features.trend_score.toFixed(3)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Volatility (Annual)</span>
                      <span className="text-white">{(aiAnalysis.features.volatility_annual * 100).toFixed(2)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Risk Level</span>
                      <span className={`font-medium ${
                        aiAnalysis.forecast.risk_level === 'low' ? 'text-green-400' :
                        aiAnalysis.forecast.risk_level === 'medium' ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {aiAnalysis.forecast.risk_level.toUpperCase()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Sentiment Analysis */}
              <div className="bg-dark-card rounded-xl border border-dark-border p-6">
                <div className="flex items-center gap-3 mb-4">
                  <BarChart3 className="w-6 h-6 text-purple-400" />
                  <h3 className="text-xl font-bold text-gray-400">News Sentiment</h3>
                </div>

                {aiAnalysis.news && (
                  <>
                    <div className="grid grid-cols-3 gap-4 mb-6">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-green-400">{aiAnalysis.news.counts.positive}</div>
                        <div className="text-sm text-gray-500">Positive</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-gray-400">{aiAnalysis.news.counts.neutral}</div>
                        <div className="text-sm text-gray-500">Neutral</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-red-400">{aiAnalysis.news.counts.negative}</div>
                        <div className="text-sm text-gray-500">Negative</div>
                      </div>
                    </div>

                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      <h4 className="text-sm font-semibold text-gray-400 mb-3 sticky top-0 bg-dark-card py-2">Recent Headlines</h4>
                      {aiAnalysis.news.headlines.map((headline, idx) => (
                        <div key={idx} className="p-3 bg-black rounded-lg border border-dark-border">
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-sm text-gray-300 flex-1">{headline.title}</p>
                            <span className={`text-xs font-semibold ${getSentimentColor(headline.label)}`}>
                              {headline.label.toUpperCase()}
                            </span>
                          </div>
                          {headline.url && (
                            <a
                              href={headline.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-blue-400 hover:underline mt-1 inline-block"
                            >
                              Read more →
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>

              {/* Forecast */}
              <div className="lg:col-span-2 bg-dark-card rounded-xl border border-dark-border p-6">
                <div className="flex items-center gap-3 mb-4">
                  <Calendar className="w-6 h-6 text-green-400" />
                  <h3 className="text-xl font-bold text-gray-400">21-Day Forecast</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <div className="text-sm text-gray-500 mb-2">Expected Return</div>
                    <div className={`text-3xl font-bold ${aiAnalysis.forecast.expected_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {aiAnalysis.forecast.expected_return_pct >= 0 ? '+' : ''}{aiAnalysis.forecast.expected_return_pct.toFixed(2)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500 mb-2">Value at Risk (95%)</div>
                    <div className="text-3xl font-bold text-orange-400">
                      {aiAnalysis.forecast.var95_pct.toFixed(2)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500 mb-2">Mean Daily Return</div>
                    <div className={`text-3xl font-bold ${aiAnalysis.features.mean_daily_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {aiAnalysis.features.mean_daily_return_pct >= 0 ? '+' : ''}{aiAnalysis.features.mean_daily_return_pct.toFixed(4)}%
                    </div>
                  </div>
                </div>

                <div className="mt-6 p-4 bg-yellow-900/20 border border-yellow-500/30 rounded-lg">
                  <p className="text-sm text-yellow-400">
                    ⚠️ {aiAnalysis.note}
                  </p>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default Analysis;
