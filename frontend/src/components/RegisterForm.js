// src/components/RegisterForm.js
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import '../App.css';

function RegisterForm() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    code: ''
  });
  const [step, setStep] = useState(1);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [timer, setTimer] = useState(900);
  const [canResend, setCanResend] = useState(false);

  const startTimer = () => {
    setCanResend(false);
    setTimer(900);
    const interval = setInterval(() => {
      setTimer((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          setCanResend(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');

    if (formData.password !== formData.confirmPassword) {
      setError('Пароли не совпадают');
      return;
    }

    if (formData.password.length < 8) {
      setError('Пароль должен быть минимум 8 символов');
      return;
    }

    setIsLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/api/v1/auth/register', {
        email: formData.email,
        password: formData.password,
        full_name: formData.email.split('@')[0],
      });

      if (response.status === 201) {
        setMessage('Код подтверждения отправлен на ваш email');
        setStep(2);
        startTimer();
      }
    } catch (err) {
      console.error('Register error:', err);

      if (err.response?.status === 400) {
        if (err.response?.data?.detail === "Пользователь с таким email уже существует") {
          setError('Пользователь с таким email уже существует');
        } else {
          setError('Ошибка регистрации. Проверьте введенные данные.');
        }
      } else if (!err.response) {
        setError('Сервер не отвечает. Проверьте подключение.');
      } else {
        setError('Ошибка регистрации. Попробуйте позже.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyCode = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    setMessage('');

    try {
      const response = await axios.post('http://localhost:8000/api/v1/auth/verify-email', {
        email: formData.email,
        code: formData.code
      });

      if (response.data.verified) {
        setMessage('Email успешно подтвержден!');
        setTimeout(() => {
          navigate('/');
        }, 2000);
      }
    } catch (err) {
      console.error('Verify error:', err);

      if (err.response?.status === 400) {
        setError('Неверный или просроченный код подтверждения');
      } else {
        setError('Ошибка подтверждения. Попробуйте позже.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendCode = async () => {
    if (!canResend) return;

    setIsLoading(true);
    setError('');

    try {
      await axios.post('http://localhost:8000/api/v1/auth/resend-verification', {
        email: formData.email
      });
      setMessage('Код подтверждения отправлен повторно');
      startTimer();
    } catch (err) {
      setError('Ошибка при отправке кода');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>Агелар - Регистрация</h1>

        {step === 1 ? (
          <form onSubmit={handleRegister}>
            <div className="form-group">
              <label>Email:</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
                required
                disabled={isLoading}
                placeholder="Введите ваш email"
              />
            </div>

            <div className="form-group">
              <label>Пароль:</label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({...formData, password: e.target.value})}
                required
                disabled={isLoading}
                placeholder="Минимум 8 символов"
              />
            </div>

            <div className="form-group">
              <label>Подтверждение пароля:</label>
              <input
                type="password"
                value={formData.confirmPassword}
                onChange={(e) => setFormData({...formData, confirmPassword: e.target.value})}
                required
                disabled={isLoading}
                placeholder="Повторите пароль"
              />
            </div>

            {error && (
              <div className="message error" style={{ marginBottom: '20px' }}>
                {error}
              </div>
            )}

            {message && (
              <div className="message success" style={{ marginBottom: '20px' }}>
                {message}
              </div>
            )}

            <div className="button-group">
              <button
                type="submit"
                className="btn-primary"
                disabled={isLoading}
              >
                {isLoading ? 'Отправка...' : 'Зарегистрироваться'}
              </button>
            </div>

            <div className="register-link">
              Уже есть аккаунт? <Link to="/">Войти</Link>
            </div>
          </form>
        ) : (
          <form onSubmit={handleVerifyCode}>
            <div className="form-group">
              <label>Код подтверждения:</label>
              <input
                type="text"
                value={formData.code}
                onChange={(e) => setFormData({...formData, code: e.target.value.replace(/\D/g, '').slice(0, 6)})}
                required
                disabled={isLoading}
                placeholder="6-значный код"
                maxLength="6"
                pattern="\d{6}"
                inputMode="numeric"
              />
            </div>

            <p className="info-text" style={{ textAlign: 'center', marginBottom: '20px' }}>
              Код отправлен на <strong>{formData.email}</strong>
            </p>

            {error && (
              <div className="message error" style={{ marginBottom: '20px' }}>
                {error}
              </div>
            )}

            {message && (
              <div className="message success" style={{ marginBottom: '20px' }}>
                {message}
              </div>
            )}

            <div className="button-group">
              <button
                type="submit"
                className="btn-primary"
                disabled={isLoading || formData.code.length !== 6}
              >
                {isLoading ? 'Проверка...' : 'Подтвердить'}
              </button>
            </div>

            <div className="resend-section" style={{ textAlign: 'center', marginTop: '15px' }}>
              <button
                type="button"
                onClick={handleResendCode}
                disabled={isLoading || !canResend}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--accent-primary)',
                  textDecoration: 'underline',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Отправить код повторно
              </button>
              {!canResend && timer > 0 && (
                <span className="timer" style={{ display: 'block', marginTop: '5px' }}>
                  через {formatTime(timer)}
                </span>
              )}
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default RegisterForm;