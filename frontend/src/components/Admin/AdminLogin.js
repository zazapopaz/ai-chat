// frontend/src/components/Admin/AdminLogin.js
import React, { useState } from 'react';
import axios from 'axios';
import './Admin.css';

function AdminLogin({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await axios.post(
        '/api/v1/admin/login',
        { email, password },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 10000
        }
      );

      const { access_token, admin } = response.data;

      // Проверяем, что данные пришли
      if (!access_token) {
        console.error('Нет access_token в ответе');
        setError('Ошибка: сервер не вернул токен');
        return;
      }

      if (!admin) {
        console.error('Нет admin данных в ответе');
        setError('Ошибка: сервер не вернул данные администратора');
        return;
      }

      // Сохраняем только публичные данные профиля
      localStorage.setItem('admin_data', JSON.stringify(admin));

      // Вызываем колбэк
      if (onLogin) {
        onLogin(admin);
      }
    } catch (err) {
      console.error('Login error:', err);
      if (err.response) {
        console.error('Response data:', err.response.data);
        console.error('Response status:', err.response.status);
        setError(err.response.data?.detail || `Ошибка ${err.response.status}`);
      } else if (err.request) {
        console.error('No response:', err.request);
        setError('Сервер не отвечает. Проверьте, запущен ли бэкенд');
      } else {
        console.error('Error:', err.message);
        setError(`Ошибка: ${err.message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleEmailChange = (e) => {
    setEmail(e.target.value);
  };

  const handlePasswordChange = (e) => {
    setPassword(e.target.value);
  };

  return (
    <div className="admin-login-container">
      <div className="admin-login-box">
        <h1>🔐 Админ-панель</h1>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email:</label>
            <input
              type="email"
              id="email"
              name="email"
              value={email}
              onChange={handleEmailChange}
              required
              autoComplete="username"
              autoFocus
              disabled={loading}
              placeholder="gavriluklol228@gmail.com"
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Пароль:</label>
            <input
              type="password"
              id="password"
              name="password"
              value={password}
              onChange={handlePasswordChange}
              required
              autoComplete="current-password"
              disabled={loading}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn-primary"
            disabled={loading || !email || !password}
          >
            {loading ? 'Вход...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default AdminLogin;
