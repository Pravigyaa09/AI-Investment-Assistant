import React from 'react';
import { CheckCircle, XCircle, AlertCircle, Info } from 'lucide-react';

const Alert = ({ type = 'info', message, onClose }) => {
  const configs = {
    success: {
      bgColor: 'bg-green-900/20',
      borderColor: 'border-green-800',
      textColor: 'text-green-400',
      Icon: CheckCircle,
    },
    error: {
      bgColor: 'bg-red-900/20',
      borderColor: 'border-red-800',
      textColor: 'text-red-400',
      Icon: XCircle,
    },
    warning: {
      bgColor: 'bg-yellow-900/20',
      borderColor: 'border-yellow-800',
      textColor: 'text-yellow-400',
      Icon: AlertCircle,
    },
    info: {
      bgColor: 'bg-blue-900/20',
      borderColor: 'border-blue-800',
      textColor: 'text-blue-400',
      Icon: Info,
    },
  };

  const config = configs[type] || configs.info;
  const { bgColor, borderColor, textColor, Icon } = config;

  return (
    <div className={`p-4 rounded-lg border ${bgColor} ${borderColor} ${textColor} flex items-center`}>
      <Icon className="w-5 h-5 mr-2" />
      <span className="flex-1">{message}</span>
      {onClose && (
        <button onClick={onClose} className="ml-2 hover:opacity-70">
          <XCircle className="w-5 h-5" />
        </button>
      )}
    </div>
  );
};

export default Alert;