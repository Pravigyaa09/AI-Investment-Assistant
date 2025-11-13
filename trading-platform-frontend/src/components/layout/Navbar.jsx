import React from 'react';
import { Menu, Bell, Search, LogOut, TrendingUp } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const Navbar = ({ onMenuClick }) => {
  const { user, logout } = useAuth();

  return (
    <nav className="bg-dark-card border-b border-dark-border sticky top-0 z-40">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <button
              onClick={onMenuClick}
              className="p-2 rounded-lg text-gray-400 hover:bg-dark-hover lg:hidden"
            >
              <Menu className="w-6 h-6" />
            </button>
            <div className="flex items-center ml-3 lg:ml-0">
              <TrendingUp className="w-8 h-8 text-blue-500" />
              <span className="ml-2 text-xl font-bold text-gray-400">TradingPro</span>
            </div>
          </div>

          <div className="hidden md:flex items-center space-x-4">
            <button className="p-2 rounded-lg text-gray-400 hover:bg-dark-hover">
              <Search className="w-5 h-5" />
            </button>
            <button className="p-2 rounded-lg text-gray-400 hover:bg-dark-hover">
              <Bell className="w-5 h-5" />
            </button>
            <div className="flex items-center space-x-3">
              <div className="text-right">
                <p className="text-sm font-medium text-gray-400">{user?.username}</p>
                <p className="text-xs text-gray-500">{user?.email}</p>
              </div>
              <button
                onClick={logout}
                className="p-2 rounded-lg text-gray-400 hover:bg-dark-hover"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;