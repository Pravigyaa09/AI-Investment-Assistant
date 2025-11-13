import { useState } from 'react';
import { Search, TrendingUp, TrendingDown, AlertCircle, Activity, BarChart3, Brain, Target, Shield, Sparkles } from 'lucide-react';
import api from '../services/api';
import Alert from '../components/common/Alert';

const StockAnalysis = () => {
  const [ticker, setTicker] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [params, setParams] = useState({
    days: 90,
    topNNews: 8,
    horizonDays: 21
  });

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!ticker.trim()) {
      setError('Please enter a ticker symbol');
      return;
    }

    setLoading(true);
    setError('');
    setAnalysis(null);

    try {
      const data = await api.getStockAnalysis(
        ticker.toUpperCase(),
        params.days,
        params.topNNews,
        params.horizonDays
      );
      setAnalysis(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch analysis');
    } finally {
      setLoading(false);
    }
  };

  const getSuggestionColor = (suggestion) => {
    if (!suggestion || typeof suggestion !== 'string') return 'gray';
    const lower = suggestion.toLowerCase();
    if (lower === 'buy') return 'green';
    if (lower === 'sell') return 'red';
    if (lower === "don't buy" || lower === 'dont buy') return 'red';
    if (lower === 'hold') return 'yellow';
    return 'gray';
  };

  const getSuggestionIcon = (suggestion) => {
    if (!suggestion || typeof suggestion !== 'string') return AlertCircle;
    const lower = suggestion.toLowerCase();
    if (lower === 'buy') return TrendingUp;
    if (lower === 'sell') return TrendingDown;
    if (lower === "don't buy" || lower === 'dont buy') return AlertCircle;
    if (lower === 'hold') return Activity;
    return AlertCircle;
  };

  const formatPercent = (value) => {
    if (value === null || value === undefined) return 'N/A';
    return `${(value * 100).toFixed(2)}%`;
  };

  const formatNumber = (value, decimals = 2) => {
    if (value === null || value === undefined) return 'N/A';
    return value.toFixed(decimals);
  };

  const getColorClasses = (color) => {
    const colorMap = {
      blue: { icon: 'text-blue-400', value: 'text-blue-400' },
      green: { icon: 'text-green-400', value: 'text-green-400' },
      red: { icon: 'text-red-400', value: 'text-red-400' },
      yellow: { icon: 'text-yellow-400', value: 'text-yellow-400' },
      orange: { icon: 'text-orange-400', value: 'text-orange-400' },
      cyan: { icon: 'text-cyan-400', value: 'text-cyan-400' },
      purple: { icon: 'text-purple-400', value: 'text-purple-400' },
      indigo: { icon: 'text-indigo-400', value: 'text-indigo-400' },
      gray: { icon: 'text-gray-400', value: 'text-gray-400' },
    };
    return colorMap[color] || colorMap.blue;
  };

  const MetricCard = ({ title, value, icon: Icon, color = 'blue', subtitle }) => {
    const colors = getColorClasses(color);
    return (
      <div className="bg-gray-800/50 backdrop-blur-xl rounded-xl border border-gray-700 p-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-gray-400 text-sm font-medium">{title}</span>
          {Icon && <Icon className={`w-5 h-5 ${colors.icon}`} />}
        </div>
        <div className={`text-2xl font-bold ${colors.value} mb-1`}>
          {value}
        </div>
        {subtitle && <div className="text-xs text-gray-500">{subtitle}</div>}
      </div>
    );
  };

  const SentimentBar = ({ positive, negative, neutral, total }) => {
    const posPercent = total > 0 ? (positive / total) * 100 : 0;
    const negPercent = total > 0 ? (negative / total) * 100 : 0;
    const neuPercent = total > 0 ? (neutral / total) * 100 : 0;

    return (
      <div className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-green-400">Positive: {positive}</span>
          <span className="text-gray-400">Neutral: {neutral}</span>
          <span className="text-red-400">Negative: {negative}</span>
        </div>
        <div className="w-full h-4 bg-gray-700 rounded-full overflow-hidden flex">
          <div
            className="bg-green-500 transition-all duration-500"
            style={{ width: `${posPercent}%` }}
            title={`Positive: ${posPercent.toFixed(1)}%`}
          />
          <div
            className="bg-gray-500 transition-all duration-500"
            style={{ width: `${neuPercent}%` }}
            title={`Neutral: ${neuPercent.toFixed(1)}%`}
          />
          <div
            className="bg-red-500 transition-all duration-500"
            style={{ width: `${negPercent}%` }}
            title={`Negative: ${negPercent.toFixed(1)}%`}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-500">
          <span>{posPercent.toFixed(1)}%</span>
          <span>{neuPercent.toFixed(1)}%</span>
          <span>{negPercent.toFixed(1)}%</span>
        </div>
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-2">
            <Brain className="w-8 h-8 text-blue-400" />
            Stock ML Analysis
          </h1>
          <p className="text-gray-400 mt-1">
            Advanced machine learning analysis with sentiment, technical indicators, and recommendations
          </p>
        </div>
      </div>

      {/* Search Form */}
      <div className="bg-gray-800/50 backdrop-blur-xl rounded-xl border border-gray-700 p-6">
        <form onSubmit={handleAnalyze} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Ticker Symbol
              </label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                className="w-full px-4 py-3 bg-gray-900/50 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white placeholder-gray-500 uppercase"
                placeholder="AAPL"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Lookback Days
              </label>
              <input
                type="number"
                value={params.days}
                onChange={(e) => setParams({ ...params, days: parseInt(e.target.value) })}
                className="w-full px-4 py-3 bg-gray-900/50 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white"
                min="10"
                max="365"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                News Articles
              </label>
              <input
                type="number"
                value={params.topNNews}
                onChange={(e) => setParams({ ...params, topNNews: parseInt(e.target.value) })}
                className="w-full px-4 py-3 bg-gray-900/50 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white"
                min="1"
                max="25"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Horizon Days
              </label>
              <input
                type="number"
                value={params.horizonDays}
                onChange={(e) => setParams({ ...params, horizonDays: parseInt(e.target.value) })}
                className="w-full px-4 py-3 bg-gray-900/50 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white"
                min="5"
                max="90"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full md:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition duration-200 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Search className="w-5 h-5" />
            {loading ? 'Analyzing...' : 'Analyze Stock'}
          </button>
        </form>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert type="error" message={error} onClose={() => setError('')} />
      )}

      {/* Analysis Results */}
      {analysis && (
        <div className="space-y-6">
          {/* Recommendation Card */}
          {(() => {
            // Handle both string and object suggestion formats
            const suggestionText = typeof analysis.suggestion === 'object'
              ? analysis.suggestion?.action
              : analysis.suggestion;
            const suggestionConfidence = typeof analysis.suggestion === 'object'
              ? analysis.suggestion?.confidence
              : analysis.confidence;
            const trendHint = typeof analysis.suggestion === 'object'
              ? analysis.suggestion?.trend_hint
              : null;

            const suggestionColor = getSuggestionColor(suggestionText);
            const Icon = getSuggestionIcon(suggestionText);

            const bgClasses = {
              green: 'bg-gradient-to-br from-green-900/20 to-green-800/10 border-green-700/50',
              red: 'bg-gradient-to-br from-red-900/20 to-red-800/10 border-red-700/50',
              yellow: 'bg-gradient-to-br from-yellow-900/20 to-yellow-800/10 border-yellow-700/50',
              gray: 'bg-gradient-to-br from-gray-900/20 to-gray-800/10 border-gray-700/50',
            };

            const textClasses = {
              green: 'text-green-400',
              red: 'text-red-400',
              yellow: 'text-yellow-400',
              gray: 'text-gray-400',
            };

            return (
              <div className={`${bgClasses[suggestionColor]} backdrop-blur-xl rounded-xl border p-8`}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <Icon className={`w-12 h-12 ${textClasses[suggestionColor]}`} />
                      <div>
                        <h2 className="text-3xl font-bold text-white">
                          {analysis.ticker}
                        </h2>
                        <p className="text-gray-400">
                          {analysis.has_position ? 'Current Position' : 'Not in Portfolio'}
                        </p>
                      </div>
                    </div>
                    <div className={`text-5xl font-bold ${textClasses[suggestionColor]} mt-4`}>
                      {suggestionText || 'N/A'}
                    </div>
                    {suggestionConfidence !== null && suggestionConfidence !== undefined && (
                      <div className="mt-2 text-lg text-gray-300">
                        Confidence: <span className="font-semibold">{formatPercent(suggestionConfidence)}</span>
                      </div>
                    )}
                    {trendHint && (
                      <div className="mt-1 text-sm text-gray-500">
                        {trendHint}
                      </div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-gray-400 text-sm">Current Price</div>
                    <div className="text-4xl font-bold text-white">
                      ${formatNumber(analysis.current_price, 2)}
                    </div>
                    {analysis.expected_return !== null && (
                      <div className={`mt-2 text-lg ${analysis.expected_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        Expected Return: {formatPercent(analysis.expected_return)}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })()}

          {/* News Sentiment Analysis */}
          <div className="bg-gray-800/50 backdrop-blur-xl rounded-xl border border-gray-700 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-6 h-6 text-purple-400" />
              <h3 className="text-xl font-bold text-white">News Sentiment Analysis</h3>
              <span className="ml-auto bg-purple-500/20 text-purple-400 px-3 py-1 rounded-full text-sm font-medium">
                {analysis.news_count || 0} Articles Analyzed
              </span>
            </div>
            <SentimentBar
              positive={analysis.news_positive_count || 0}
              negative={analysis.news_negative_count || 0}
              neutral={analysis.news_neutral_count || 0}
              total={analysis.news_count || 0}
            />
            {analysis.sentiment_index !== null && (
              <div className="mt-4 p-4 bg-gray-900/50 rounded-lg">
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Sentiment Index</span>
                  <span className={`text-xl font-bold ${analysis.sentiment_index >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatNumber(analysis.sentiment_index, 3)}
                  </span>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  Range: -1.0 (Very Negative) to +1.0 (Very Positive)
                </div>
              </div>
            )}
          </div>

          {/* Technical Indicators */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-6 h-6 text-blue-400" />
              <h3 className="text-xl font-bold text-white">Technical Indicators</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                title="Trend Score"
                value={formatNumber(analysis.trend_score, 4)}
                icon={analysis.trend_score >= 0 ? TrendingUp : TrendingDown}
                color={analysis.trend_score >= 0.04 ? 'green' : analysis.trend_score <= -0.06 ? 'red' : 'yellow'}
                subtitle="(Last - SMA20) / SMA20"
              />
              <MetricCard
                title="Volatility (Annual)"
                value={formatPercent(analysis.volatility)}
                icon={Shield}
                color={analysis.volatility <= 0.25 ? 'green' : analysis.volatility >= 0.70 ? 'red' : 'yellow'}
                subtitle="Daily StdDev × √252"
              />
              <MetricCard
                title="RSI (14)"
                value={formatNumber(analysis.rsi14, 2)}
                icon={BarChart3}
                color={analysis.rsi14 > 70 ? 'red' : analysis.rsi14 < 30 ? 'green' : 'blue'}
                subtitle={analysis.rsi14 > 70 ? 'Overbought' : analysis.rsi14 < 30 ? 'Oversold' : 'Neutral'}
              />
              <MetricCard
                title="Value at Risk (95%)"
                value={formatPercent(analysis.var_95)}
                icon={AlertCircle}
                color="orange"
                subtitle="1.65 × σ - μ (adjusted)"
              />
            </div>
          </div>

          {/* Moving Averages & Returns */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Target className="w-6 h-6 text-green-400" />
              <h3 className="text-xl font-bold text-white">Moving Averages & Returns</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                title="SMA 20"
                value={`$${formatNumber(analysis.sma20, 2)}`}
                color="cyan"
              />
              <MetricCard
                title="SMA 50"
                value={`$${formatNumber(analysis.sma50, 2)}`}
                color="cyan"
              />
              <MetricCard
                title="Daily Return"
                value={formatPercent(analysis.daily_return)}
                color={analysis.daily_return >= 0 ? 'green' : 'red'}
              />
              <MetricCard
                title="5-Day Return"
                value={formatPercent(analysis.ret_5)}
                color={analysis.ret_5 >= 0 ? 'green' : 'red'}
              />
            </div>
          </div>

          {/* Additional Metrics */}
          <div className="bg-gray-800/50 backdrop-blur-xl rounded-xl border border-gray-700 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Brain className="w-6 h-6 text-indigo-400" />
              <h3 className="text-xl font-bold text-white">ML Model Insights</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-gray-900/50 rounded-lg">
                <div className="text-gray-400 text-sm mb-1">10-Day Return</div>
                <div className={`text-2xl font-bold ${analysis.ret_10 >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {formatPercent(analysis.ret_10)}
                </div>
              </div>
              <div className="p-4 bg-gray-900/50 rounded-lg">
                <div className="text-gray-400 text-sm mb-1">20-Day Return</div>
                <div className={`text-2xl font-bold ${analysis.ret_20 >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {formatPercent(analysis.ret_20)}
                </div>
              </div>
              <div className="p-4 bg-gray-900/50 rounded-lg">
                <div className="text-gray-400 text-sm mb-1">Analysis Lookback</div>
                <div className="text-2xl font-bold text-blue-400">
                  {params.days} days
                </div>
              </div>
            </div>
          </div>

          {/* Parameters Used */}
          <div className="bg-gray-900/30 rounded-lg p-4 border border-gray-800">
            <div className="text-xs text-gray-500 space-y-1">
              <div>Analysis Parameters: Lookback = {params.days} days, News Articles = {params.topNNews}, Forecast Horizon = {params.horizonDays} days</div>
              <div>Data freshness may vary based on market hours and data provider availability</div>
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!analysis && !loading && (
        <div className="bg-gray-800/30 rounded-xl border-2 border-dashed border-gray-700 p-12 text-center">
          <Brain className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-400 mb-2">
            No Analysis Yet
          </h3>
          <p className="text-gray-500">
            Enter a ticker symbol and click Analyze Stock to see ML-powered insights
          </p>
        </div>
      )}
    </div>
  );
};

export default StockAnalysis;
