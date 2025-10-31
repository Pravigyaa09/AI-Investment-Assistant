import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, TrendingUp, Briefcase, BarChart3, Newspaper, Settings } from 'lucide-react';

const Sidebar = ({ isOpen, onClose }) => {
  const location = useLocation();

  const navigation = [
    { path: '/dashboard', name: 'Dashboard', icon: Home },
    { path: '/trading', name: 'Trading', icon: TrendingUp },
    { path: '/portfolio', name: 'Portfolio', icon: Briefcase },
  ];

  return (
    <>
      <aside className={`fixed lg:static inset-y-0 left-0 z-30 w-64 bg-white border-r border-gray-200 transform transition-transform lg:transform-none ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        <div className="h-full pt-20 lg:pt-4 pb-4 overflow-y-auto">
          <nav className="px-3 space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={onClose}
                  className={`w-full flex items-center px-3 py-2 text-sm font-medium rounded-lg transition ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <Icon className="w-5 h-5 mr-3" />
                  {item.name}
                </Link>
              );
            })}
          </nav>
        </div>
      </aside>
      
      {isOpen && (
        <div
          className="fixed inset-0 z-20 bg-black bg-opacity-50 lg:hidden"
          onClick={onClose}
        />
      )}
    </>
  );
};

export default Sidebar;