const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

class ApiService {
  constructor() {
    this.token = localStorage.getItem('token');
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(this.token && { Authorization: `Bearer ${this.token}` }),
        ...options.headers,
      },
    };

    const response = await fetch(url, config);
    
    if (response.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
      throw new Error('Authentication required');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  async register(email, password, username) {
    const response = await this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        username,
        password,
        confirm_password: password
      }),
    });

    return response;
  }

  async login(email, password) {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await this.request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    if (response.access_token) {
      this.token = response.access_token;
      localStorage.setItem('token', response.access_token);
    }

    return response;
  }

  async logout() {
    await this.request('/auth/logout', { method: 'POST' }).catch(() => {});
    this.token = null;
    localStorage.removeItem('token');
  }

  async getCurrentUser() {
    return this.request('/auth/me');
  }

  async getPortfolio(refreshPrices = false) {
    const params = refreshPrices ? '?refresh_prices=true' : '';
    return this.request(`/portfolio${params}`);
  }

  async executeTrade(data) {
    return this.request('/portfolio/trade', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async closePosition(ticker) {
    return this.request(`/portfolio/holdings/${ticker}`, {
      method: 'DELETE',
    });
  }

  async getTrades() {
    return this.request('/portfolio/trades');
  }

  async getPerformance() {
    return this.request('/portfolio/performance');
  }

  async getPrice(ticker) {
    return this.request(`/price?ticker=${ticker}`);
  }

  async getNews(ticker = 'AAPL') {
    return this.request(`/news?ticker=${ticker}`);
  }

  async getPersonalizedNews(limit = 50) {
    return this.request(`/news/personalized?limit=${limit}`);
  }

  async getPersonalizedNewsWithRecommendations(limit = 50) {
    return this.request(`/news/personalized/with-recommendations?limit=${limit}`);
  }

  async getCategories() {
    return this.request('/news/categories');
  }

  async getCategoryNews(categoryKey, limit = 50) {
    return this.request(`/news/category/${categoryKey}?limit=${limit}`);
  }

  async getStockAnalysis(ticker, days = 90, topNNews = 8, horizonDays = 21) {
    return this.request(`/stocks/${ticker}/analysis?days=${days}&top_n_news=${topNNews}&horizon_days=${horizonDays}`);
  }

  async getBatchStockAnalysis(tickers, days = 90, topNNews = 8, horizonDays = 21) {
    const tickersParam = tickers.join(',');
    return this.request(`/stocks/analysis?tickers=${tickersParam}&days=${days}&top_n_news=${topNNews}&horizon_days=${horizonDays}`);
  }
}

const api = new ApiService();
export default api;