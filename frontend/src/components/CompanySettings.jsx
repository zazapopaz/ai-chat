import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './CompanySettings.css';

function CompanySettings({ token, company, onUpdate }) {
  const [formData, setFormData] = useState({
    company_name: '',
    website_url: '',
    ai_prompt: '',
    company_knowledge_base: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);

  useEffect(() => {
    if (company) {
      setFormData({
        company_name: company.company_name || '',
        website_url: company.website_url || '',
        ai_prompt: company.ai_prompt || '',
        company_knowledge_base: company.company_knowledge_base || ''
      });
    }
  }, [company]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      const response = await axios.put(
        `http://localhost:8000/api/v1/tenants/${company.id}`,
        formData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      setMessage('Настройки успешно сохранены!');
      setIsSuccess(true);

      // Обновляем данные в родительском компоненте
      if (onUpdate) {
        onUpdate(response.data);
      }

      // Автоматически скрываем сообщение через 3 секунды
      setTimeout(() => {
        setMessage('');
        setIsSuccess(false);
      }, 3000);
    } catch (error) {
      setMessage(`Ошибка сохранения: ${error.response?.data?.detail || error.message}`);
      setIsSuccess(false);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFormData({
      company_name: company.company_name || '',
      website_url: company.website_url || '',
      ai_prompt: company.ai_prompt || '',
      company_knowledge_base: company.company_knowledge_base || ''
    });
  };

  return (
    <div className="company-settings">
      <div className="settings-header">
        <h2>Настройки компании</h2>
        <div className="company-id">
          ID: <code>{company?.id}</code>
        </div>
      </div>

      {message && (
        <div className={`message ${isSuccess ? 'success' : 'error'}`}>
          {message}
        </div>
      )}

      <form onSubmit={handleSubmit} className="settings-form">
        <div className="form-section">
          <h3>Основная информация</h3>

          <div className="form-group">
            <label htmlFor="company_name">
              Название компании *
            </label>
            <input
              type="text"
              id="company_name"
              name="company_name"
              value={formData.company_name}
              onChange={handleChange}
              required
              placeholder="Например: ООО 'Рога и Копыта'"
            />
          </div>

          <div className="form-group">
            <label htmlFor="website_url">
              URL сайта
            </label>
            <input
              type="url"
              id="website_url"
              name="website_url"
              value={formData.website_url}
              onChange={handleChange}
              placeholder="https://example.com"
            />
          </div>
        </div>

        <div className="form-section">
          <h3>Настройки AI-консультанта</h3>

          <div className="form-group">
            <label htmlFor="ai_prompt">
              Системный промпт для AI *
              <span className="hint">
                Определяет поведение и стиль общения бота
              </span>
            </label>
            <textarea
              id="ai_prompt"
              name="ai_prompt"
              value={formData.ai_prompt}
              onChange={handleChange}
              required
              rows={5}
              placeholder="Пример: Ты - профессиональный консультант компании 'Рога и Копыта'. Твоя задача - отвечать на вопросы клиентов, собирать контакты и помогать с выбором услуг. Будь вежливым, но не навязчивым. Если клиент спрашивает о ценах, уточни какие именно услуги его интересуют. В конце диалога обязательно попроси оставить контакты для связи с менеджером."
            />
            <div className="char-count">
              {formData.ai_prompt.length} символов
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="company_knowledge_base">
              База знаний о компании
              <span className="hint">
                Информация, которую должен знать бот (услуги, цены, контакты и т.д.)
              </span>
            </label>
            <textarea
              id="company_knowledge_base"
              name="company_knowledge_base"
              value={formData.company_knowledge_base}
              onChange={handleChange}
              rows={8}
              placeholder="Основные услуги:
1. Консультации по выбору продукции
2. Техническая поддержка
3. Обучение сотрудников

Цены:
- Базовая консультация: 5 000 руб.
- Расширенная поддержка: 15 000 руб./мес.
- Обучение: 10 000 руб./час

Контакты:
- Телефон: +7 (999) 123-45-67
- Email: info@company.com
- Адрес: г. Москва, ул. Примерная, д. 1"
            />
            <div className="char-count">
              {formData.company_knowledge_base.length} символов
            </div>
          </div>
        </div>

        <div className="form-actions">
          <button
            type="button"
            onClick={handleReset}
            className="btn btn-secondary"
            disabled={loading}
          >
            Сбросить изменения
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? 'Сохранение...' : 'Сохранить изменения'}
          </button>
        </div>
      </form>

      <div className="settings-info">
        <h4>💡 Как заполнять настройки AI:</h4>
        <ul>
          <li><strong>Промпт</strong> — это "инструкция" для бота, как себя вести</li>
          <li><strong>База знаний</strong> — факты о компании, которые должен знать бот</li>
          <li>Будьте конкретны в промпте, чтобы бот не отклонялся от темы</li>
          <li>Регулярно обновляйте базу знаний при изменениях в компании</li>
        </ul>
      </div>
    </div>
  );
}

export default CompanySettings;