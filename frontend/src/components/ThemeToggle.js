// frontend/src/components/ThemeToggle.js
import React from 'react';
import { useTheme } from '../contexts/ThemeContext';
import './ThemeToggle.css';

function ThemeToggle() {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button
      className={`theme-toggle ${isDark ? 'dark' : 'light'}`}
      onClick={toggleTheme}
      title={isDark ? 'Переключить на светлую тему' : 'Переключить на тёмную тему'}
    >
      <span className="theme-toggle-icon">
        {isDark ? '🌕' : '🌑'}
      </span>
      <span className="theme-toggle-text">
        {isDark ? 'Светлая тема' : 'Тёмная тема'}
      </span>
    </button>
  );
}

export default ThemeToggle;