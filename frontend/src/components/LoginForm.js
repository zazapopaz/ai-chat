// src/components/LoginForm.js
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import '../App.css';

function LoginForm({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const response = await axios.post(
        'http://localhost:8000/api/v1/auth/login',
        formData,
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );

      await onLogin(email, password);
    } catch (err) {
      console.error('Login error:', err);

      if (err.response?.status === 401) {
        setError('Неверный email или пароль');
      } else if (err.response?.status === 403) {
        setError('Аккаунт не активирован. Подтвердите email.');
      } else if (err.response?.status === 429) {
        setError('Слишком много попыток входа. Попробуйте позже.');
      } else if (!err.response) {
        setError('Сервер не отвечает. Проверьте подключение.');
      } else {
        setError('Ошибка входа. Попробуйте позже.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>Агелар - Вход</h1>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email:</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
              placeholder="Введите ваш email"
            />
          </div>
          <div className="form-group">
            <label>Пароль:</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
              placeholder="Введите пароль"
            />
          </div>

          {error && (
            <div className="message error" style={{ marginBottom: '20px' }}>
              {error}
            </div>
          )}

          <div className="button-group">
            <button
              type="submit"
              className="btn-primary"
              disabled={loading}
            >
              {loading ? 'Вход...' : 'Войти'}
            </button>
          </div>

          <div className="register-link">
            Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
          </div>
        </form>
      </div>
    </div>
  );
}

export default LoginForm;