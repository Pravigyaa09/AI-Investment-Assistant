import React from 'react';
import { Loader2 } from 'lucide-react';

export const LoadingSpinner = ({ size = 'md', text = '' }) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  return (
    <div className="flex flex-col items-center justify-center p-4">
      <Loader2 className={`${sizeClasses[size]} animate-spin text-blue-500`} />
      {text && <p className="mt-2 text-gray-600">{text}</p>}
    </div>
  );
};

export const SkeletonCard = () => (
  <div className="bg-white rounded-xl shadow-sm p-6 animate-pulse">
    <div className="h-4 w-32 bg-gray-200 rounded mb-4" />
    <div className="space-y-3">
      <div className="h-8 bg-gray-200 rounded" />
      <div className="h-4 w-3/4 bg-gray-200 rounded" />
    </div>
  </div>
);

export const SkeletonRow = () => (
  <div className="flex items-center justify-between p-4 animate-pulse">
    <div className="flex-1">
      <div className="h-4 w-24 bg-gray-200 rounded mb-2" />
      <div className="h-3 w-32 bg-gray-200 rounded" />
    </div>
    <div className="h-8 w-20 bg-gray-200 rounded" />
  </div>
);

export const TableSkeleton = ({ rows = 5 }) => (
  <div className="bg-white rounded-xl shadow-sm overflow-hidden">
    <div className="px-6 py-4 border-b border-gray-200">
      <div className="h-6 w-32 bg-gray-200 rounded animate-pulse" />
    </div>
    <div className="divide-y divide-gray-200">
      {[...Array(rows)].map((_, i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  </div>
);

export const LoadingOverlay = ({ show, children }) => {
  if (!show) return children;

  return (
    <div className="relative">
      <div className="absolute inset-0 bg-white bg-opacity-75 z-10 flex items-center justify-center rounded-lg">
        <LoadingSpinner />
      </div>
      <div className="opacity-50 pointer-events-none">
        {children}
      </div>
    </div>
  );
};