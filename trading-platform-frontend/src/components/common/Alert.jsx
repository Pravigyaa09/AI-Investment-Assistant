import React from 'react';
import { CheckCircle, XCircle, AlertCircle, Info } from 'lucide-react';

const Alert = ({ type = 'info', message, onClose }) => {
  const configs = {
    success: {
      bgColor: 'bg-green-50',
      textColor: 'text-green-700',
      Icon: CheckCircle,
    },
    error: {
      bgColor: 'bg-red-50',
      textColor: 'text-red-700',
      Icon: XCircle,
    },
    warning: {
      bgColor: 'bg-yellow-50',
      textColor: 'text-yellow-700',
      Icon: AlertCircle,
    },
    info: {
      bgColor: 'bg-blue-50',
      textColor: 'text-blue-700',
      Icon: Info,
    },
  };

  const config = configs[type] || configs.info;
  const { bgColor, textColor, Icon } = config;

  return (
    <div className={`p-4 rounded-lg ${bgColor} ${textColor} flex items-center`}>
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