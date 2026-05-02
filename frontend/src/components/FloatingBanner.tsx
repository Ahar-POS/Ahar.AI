import React, { useEffect, useState } from 'react';
import './FloatingBanner.css';

interface FloatingBannerProps {
  message: string;
  onClose: () => void;
  duration?: number;
}

export default function FloatingBanner({ message, onClose, duration = 3500 }: FloatingBannerProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Small delay to trigger animation
    const timer = setTimeout(() => setVisible(true), 10);
    
    const hideTimer = setTimeout(() => {
      setVisible(false);
      // Wait for exit animation
      setTimeout(onClose, 300);
    }, duration);

    return () => {
      clearTimeout(timer);
      clearTimeout(hideTimer);
    };
  }, [duration, onClose]);

  return (
    <div className={`floating-banner ${visible ? 'visible' : ''}`}>
      <div className="floating-banner-content">
        <span className="floating-banner-icon">✓</span>
        <span className="floating-banner-message">{message}</span>
      </div>
    </div>
  );
}
