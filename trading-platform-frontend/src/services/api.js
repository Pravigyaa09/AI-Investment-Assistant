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

  async getPortfolio() {
    return this.request('/portfolio');
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

  async getNews() {
    return this.request('/news');
  }
}

const api = new ApiService();
export default api;