import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './WidgetSettings.css';

function WidgetSettings({ token, company, onUpdate }) {
  const [formData, setFormData] = useState({
    consultant_name: 'Консультант',
    consultant_avatar: null,
    button_color: '#007bff',
    welcome_message: 'Здравствуйте! Чем могу помочь?',
    typing_delay: 1000,
    response_delay: 500,
    widget_position: 'bottom-right'
  });
  const [avatarPreview, setAvatarPreview] = useState(null);
  const [avatarFile, setAvatarFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);
  const [widgetCode, setWidgetCode] = useState('');
  const [showCode, setShowCode] = useState(false);

  useEffect(() => {
    if (company && company.widget_config) {
      const avatar = company.widget_config.consultant_avatar || null;
      setFormData({
        consultant_name: company.widget_config.consultant_name || 'Консультант',
        consultant_avatar: avatar,
        button_color: company.widget_config.button_color || '#007bff',
        welcome_message: company.widget_config.welcome_message || 'Здравствуйте! Чем могу помочь?',
        typing_delay: company.widget_config.typing_delay || 1000,
        response_delay: company.widget_config.response_delay || 500,
        widget_position: company.widget_config.widget_position || 'bottom-right'
      });
      setAvatarPreview(avatar);
    }
  }, [company]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleAvatarChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      // Проверяем размер (макс 2MB)
      if (file.size > 2 * 1024 * 1024) {
        alert('Файл слишком большой. Максимальный размер 2MB');
        return;
      }

      // Проверяем тип файла
      if (!file.type.startsWith('image/')) {
        alert('Пожалуйста, выберите изображение');
        return;
      }

      setAvatarFile(file);

      // Создаем превью
      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarPreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      let avatarUrl = formData.consultant_avatar;

      // Если есть новый файл аватара, загружаем его
      if (avatarFile) {
        // Здесь должен быть код загрузки файла на сервер
        // Например, через FormData и отдельный эндпоинт
        // Пока просто сохраняем как data URL
        avatarUrl = avatarPreview;
      }

      const updateData = {
        widget_config: {
          ...formData,
          consultant_avatar: avatarUrl
        }
      };

      const response = await axios.put(
        `http://localhost:8000/api/v1/tenants/${company.id}`,
        updateData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      setMessage('Настройки виджета сохранены!');
      setIsSuccess(true);
      setAvatarFile(null);

      if (onUpdate) {
        onUpdate(response.data);
      }

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

  const getWidgetCode = async () => {
    try {
      const response = await axios.get(
        `http://localhost:8000/api/v1/tenants/${company.id}/widget-code`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setWidgetCode(response.data.widget_code);
      setShowCode(true);
    } catch (error) {
      alert('Ошибка получения кода: ' + error.response?.data?.detail);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(widgetCode).then(() => {
      alert('Код скопирован!');
    });
  };

  const removeAvatar = () => {
    setAvatarPreview(null);
    setAvatarFile(null);
    setFormData(prev => ({
      ...prev,
      consultant_avatar: null
    }));
  };

  const positions = [
    { value: 'bottom-right', label: 'Справа внизу' },
    { value: 'bottom-left', label: 'Слева внизу' },
    { value: 'top-right', label: 'Справа вверху' },
    { value: 'top-left', label: 'Слева вверху' }
  ];

  const colorPresets = [
    '#007bff', '#28a745', '#dc3545', '#ffc107',
    '#17a2b8', '#6f42c1', '#fd7e14', '#343a40'
  ];

  return (
    <div className="widget-settings">
      <div className="widget-header">
        <h2>Настройки виджета чата</h2>
        <button onClick={getWidgetCode} className="btn-get-code">
            Получить код для сайта
        </button>
      </div>

      {showCode && (
        <div className="widget-code-modal">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Код для вставки на сайт</h3>
              <button onClick={() => setShowCode(false)} className="close-modal">
                ✕
              </button>
            </div>
            <div className="code-container">
              <pre>{widgetCode}</pre>
            </div>
            <div className="modal-actions">
              <button onClick={copyToClipboard} className="btn-copy">
                 Копировать код
              </button>
              <button
                onClick={() => {
                  window.open(`/test-widget.html?tenant=${company.id}`, '_blank');
                }}
                className="btn-test"
              >
                Тестировать виджет
              </button>
            </div>
            <div className="instructions">
              <h4>Инструкция по установке:</h4>
              <ol>
                <li>Скопируйте код выше</li>
                <li>Вставьте его на ваш сайт перед закрывающим тегом <code>&lt;/body&gt;</code></li>
                <li>Сохраните изменения на сайте</li>
                <li>Обновите страницу сайта - виджет должен появиться</li>
              </ol>
            </div>
          </div>
        </div>
      )}

      {message && (
        <div className={`message ${isSuccess ? 'success' : 'error'}`}>
          {message}
        </div>
      )}

      <form onSubmit={handleSubmit} className="settings-form">
        <div className="form-section">
          <h3>Внешний вид</h3>

          <div className="form-group">
            <label>Фото консультанта</label>
            <div className="avatar-upload">
              <div className="avatar-preview">
                {avatarPreview ? (
                  <img src={avatarPreview} alt="avatar" className="avatar-image" />
                ) : (
                  <div className="avatar-placeholder">
                    <span>👤</span>
                  </div>
                )}
              </div>
              <div className="avatar-controls">
                <input
                  type="file"
                  id="avatar-input"
                  accept="image/*"
                  onChange={handleAvatarChange}
                  style={{ display: 'none' }}
                />
                <button
                  type="button"
                  className="btn-upload"
                  onClick={() => document.getElementById('avatar-input').click()}
                >
                  Загрузить фото
                </button>
                {avatarPreview && (
                  <button
                    type="button"
                    className="btn-remove"
                    onClick={removeAvatar}
                  >
                    Удалить
                  </button>
                )}
              </div>
              <div className="avatar-hint">
                PNG, JPG до 2MB. Квадратное изображение
              </div>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="consultant_name">
                Имя консультанта
              </label>
              <input
                type="text"
                id="consultant_name"
                name="consultant_name"
                value={formData.consultant_name}
                onChange={handleChange}
                placeholder="Например: Анна, Консультант"
              />
            </div>

            <div className="form-group">
              <label htmlFor="widget_position">
                Положение на экране
              </label>
              <select
                id="widget_position"
                name="widget_position"
                value={formData.widget_position}
                onChange={handleChange}
              >
                {positions.map(pos => (
                  <option key={pos.value} value={pos.value}>
                    {pos.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>
              Цвет кнопки и заголовка
            </label>
            <div className="color-picker">
              <input
                type="color"
                id="button_color"
                name="button_color"
                value={formData.button_color}
                onChange={handleChange}
              />
              <span className="color-value">{formData.button_color}</span>

              <div className="color-presets">
                {colorPresets.map(color => (
                  <button
                    key={color}
                    type="button"
                    className="color-preset"
                    style={{ backgroundColor: color }}
                    onClick={() => setFormData(prev => ({
                      ...prev,
                      button_color: color
                    }))}
                    title={color}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="form-section">
          <h3>Сообщения и поведение</h3>

          <div className="form-group">
            <label htmlFor="welcome_message">
              Приветственное сообщение
            </label>
            <textarea
              id="welcome_message"
              name="welcome_message"
              value={formData.welcome_message}
              onChange={handleChange}
              rows={3}
              placeholder="Первое сообщение, которое видит клиент при открытии чата"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="typing_delay">
                Задержка "печатает..." (мс)
                <span className="hint">
                  Как долго показывается индикатор набора текста
                </span>
              </label>
              <input
                type="number"
                id="typing_delay"
                name="typing_delay"
                value={formData.typing_delay}
                onChange={handleChange}
                min="0"
                max="5000"
                step="100"
              />
              <div className="range-hint">
                {`Быстрее (<500 мс) — Медленнее (>1500 мс)`}
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="response_delay">
                Задержка ответа (мс)
                <span className="hint">
                  Пауза перед отправкой ответа от AI
                </span>
              </label>
              <input
                type="number"
                id="response_delay"
                name="response_delay"
                value={formData.response_delay}
                onChange={handleChange}
                min="0"
                max="10000"
                step="100"
              />
              <div className="range-hint">
                {'Быстрее (<300 мс) — Медленнее (>1000 мс)'}
              </div>
            </div>
          </div>
        </div>

                {/* Предпросмотр виджета */}
        <div className="form-section">
          <h3>Предпросмотр виджета</h3>

          <div className="widget-preview-container">
            <div className="widget-preview">
              <div className="preview-position-container">
                {/* Кнопка виджета - ТОЛЬКО ИКОНКА */}
                <div
                  className={`preview-button ${formData.widget_position}`}
                  style={{ backgroundColor: formData.button_color }}
                >
                  💬
                </div>

                {/* Окно чата */}
                <div className={`preview-window ${formData.widget_position}`}>
                  <div className="preview-header" style={{ backgroundColor: formData.button_color }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      {avatarPreview ? (
                        <div className="preview-avatar">
                          <img src={avatarPreview} alt="avatar" />
                        </div>
                      ) : (
                        <div className="preview-avatar-placeholder">👤</div>
                      )}
                      <div>
                        <strong>{formData.consultant_name}</strong>
                        <div>Онлайн</div>
                      </div>
                    </div>
                  </div>
                  <div className="preview-messages">
                    <div className="preview-message bot">
                      {formData.welcome_message}
                    </div>
                    <div className="preview-message user">
                      Привет! Есть вопросы по услугам
                    </div>
                    <div className="preview-typing">
                      <div className="typing-dot"></div>
                      <div className="typing-dot"></div>
                      <div className="typing-dot"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="form-actions">
          <button
            type="button"
            onClick={getWidgetCode}
            className="btn btn-secondary"
          >
            Получить код
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? 'Сохранение...' : 'Сохранить настройки'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default WidgetSettings;