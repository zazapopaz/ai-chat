// src/components/Notification.js
import React, { useState, useEffect } from 'react';
import './Notification.css';

function Notification({ message, type = 'success', duration = 3000, onClose }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => {
        if (onClose) onClose();
      }, 300);
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  if (!visible) return null;

  return (
    <div className={`notification notification-${type} slide-in`}>
      <div className="notification-icon">
        {type === 'success' ? '✅' :
         type === 'error' ? '❌' :
         type === 'warning' ? '⚠️' : 'ℹ️'}
      </div>
      <div className="notification-content">
        <div className="notification-message">{message}</div>
      </div>
      <button
        className="notification-close"
        onClick={() => {
          setVisible(false);
          if (onClose) onClose();
        }}
      >
        ×
      </button>
    </div>
  );
}

export default Notification;