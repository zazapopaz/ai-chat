// frontend/src/components/AddCompanyModal.js
import React, { useState } from 'react';
import './AddCompanyModal.css';

function AddCompanyModal({ isOpen, onClose, onAdd }) {
  const [companyName, setCompanyName] = useState('');
  const [website, setWebsite] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!companyName.trim()) return;

    setLoading(true);
    try {
      await onAdd(companyName.trim(), website.trim());
      setCompanyName('');
      setWebsite('');
      onClose();
    } catch (error) {
      console.error('Ошибка при создании компании:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h3>Добавить новую компанию</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="companyName">Название компании *</label>
            <input
              type="text"
              id="companyName"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Например: ООО Рога и Копыта"
              autoFocus
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="website">Веб-сайт (необязательно)</label>
            <input
              type="url"
              id="website"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              placeholder="https://example.com"
            />
          </div>

          <div className="modal-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={loading}
            >
              Отмена
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={loading || !companyName.trim()}
            >
              {loading ? 'Создание...' : 'Создать компанию'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AddCompanyModal;