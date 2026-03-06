import React, { useState } from 'react';
import axios from 'axios';
import './CreateAdminModal.css';

function CreateAdminModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    is_superadmin: false
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('admin_token');
      await axios.post(
        'http://localhost:8000/api/v1/admin/create',
        formData,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      onSuccess();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка при создании администратора');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="create-admin-modal">
      <div className="modal-content">
        <div className="modal-header">
          <h2>👤 Создать администратора</h2>
          <button onClick={onClose} className="close-btn">✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email *</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              placeholder="admin@example.com"
            />
          </div>

          <div className="form-group">
            <label>Пароль *</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              minLength={6}
              placeholder="Минимум 6 символов"
            />
          </div>

          <div className="form-group">
            <label>Имя (необязательно)</label>
            <input
              type="text"
              name="full_name"
              value={formData.full_name}
              onChange={handleChange}
              placeholder="Иван Иванов"
            />
          </div>

          <div className="form-group checkbox">
            <label>
              <input
                type="checkbox"
                name="is_superadmin"
                checked={formData.is_superadmin}
                onChange={handleChange}
              />
              Супер-администратор
            </label>
            <small className="hint">
              Супер-админ может создавать других админов и управлять системой
            </small>
          </div>

          {error && <div className="error-message">{error}</div>}

          <div className="modal-actions">
            <button type="button" onClick={onClose} className="cancel-btn">
              Отмена
            </button>
            <button type="submit" className="create-btn" disabled={loading}>
              {loading ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CreateAdminModal;