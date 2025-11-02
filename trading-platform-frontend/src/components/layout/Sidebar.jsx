import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, TrendingUp, Briefcase, BarChart3, Newspaper, Brain } from 'lucide-react';

const Sidebar = ({ isOpen, onClose }) => {
  const location = useLocation();

  const navigation = [
    { path: '/dashboard', name: 'Dashboard', icon: Home },
    { path: '/trading', name: 'Trading', icon: TrendingUp },
    { path: '/portfolio', name: 'Portfolio', icon: Briefcase },
    { path: '/analysis', name: 'Analysis', icon: BarChart3 },
    { path: '/stock-analysis', name: 'Stock ML Analysis', icon: Brain },
    { path: '/news', name: 'News', icon: Newspaper },
  ];

  return (
    <>
      <aside className={`fixed lg:static inset-y-0 left-0 z-30 w-64 bg-dark-card border-r border-dark-border transform transition-transform lg:transform-none ${
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
                      ? 'bg-blue-900 text-blue-400'
                      : 'text-gray-400 hover:bg-dark-hover'
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
          className="fixed inset-0 z-20 bg-black bg-opacity-75 lg:hidden"
          onClick={onClose}
        />
      )}
    </>
  );
};

export default Sidebar;