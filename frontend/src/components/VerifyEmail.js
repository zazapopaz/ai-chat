// src/components/VerifyEmail.js
import React, { useState } from 'react';
import axios from 'axios';

function VerifyEmail() {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [message, setMessage] = useState('');
  const [isVerified, setIsVerified] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleVerify = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage('');

    try {
      const response = await axios.post('http://localhost:8000/api/v1/auth/verify-email', {
        email,
        code
      });

      if (response.data.verified) {
        setMessage('✅ Email успешно подтвержден! Теперь вы можете войти.');
        setIsVerified(true);
      }
    } catch (error) {
      setMessage(error.response?.data?.detail || '❌ Ошибка подтверждения');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendCode = async () => {
    setIsLoading(true);
    try {
      await axios.post('http://localhost:8000/api/v1/auth/resend-verification', {
        email
      });
      setMessage('📧 Код подтверждения отправлен повторно');
    } catch (error) {
      setMessage('❌ Ошибка при отправке кода');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="verify-container">
      <h2>Подтверждение email</h2>

      {!isVerified ? (
        <form onSubmit={handleVerify}>
          <div className="form-group">
            <label>Email:</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={isLoading}
              placeholder="Введите ваш email"
            />
          </div>

          <div className="form-group">
            <label>Код подтверждения:</label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              disabled={isLoading}
              placeholder="6-значный код из письма"
              maxLength="6"
            />
          </div>

          {message && <div className="message">{message}</div>}

          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Проверка...' : 'Подтвердить'}
          </button>

          <button
            type="button"
            onClick={handleResendCode}
            disabled={isLoading || !email}
            className="resend-btn"
          >
            Отправить код повторно
          </button>
        </form>
      ) : (
        <div className="success-message">
          <p>{message}</p>
          <button onClick={() => window.location.href = '/login'}>
            Перейти к входу
          </button>
        </div>
      )}

      <style jsx>{`
        .verify-container {
          max-width: 400px;
          margin: 50px auto;
          padding: 20px;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h2 {
          text-align: center;
          margin-bottom: 30px;
        }
        .form-group {
          margin-bottom: 20px;
        }
        label {
          display: block;
          margin-bottom: 5px;
          font-weight: 500;
        }
        input {
          width: 100%;
          padding: 10px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 16px;
        }
        button {
          width: 100%;
          padding: 12px;
          background: #007bff;
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 16px;
          cursor: pointer;
          margin-bottom: 10px;
        }
        button:hover {
          background: #0056b3;
        }
        button:disabled {
          background: #ccc;
          cursor: not-allowed;
        }
        .resend-btn {
          background: #6c757d;
        }
        .resend-btn:hover {
          background: #545b62;
        }
        .message {
          padding: 10px;
          margin-bottom: 15px;
          border-radius: 4px;
          text-align: center;
        }
        .success-message {
          text-align: center;
        }
        .success-message p {
          margin-bottom: 20px;
          color: #28a745;
        }
      `}</style>
    </div>
  );
}

export default VerifyEmail;