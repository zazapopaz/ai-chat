// src/components/DialogList.js
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useNotification } from './NotificationManager';
import './DialogList.css';

function DialogList({ token, company }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSession, setSelectedSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [filter, setFilter] = useState('all');
  const [stats, setStats] = useState({
    total: 0,
    withContacts: 0,
    anonymous: 0
  });

  // Состояния для удаления
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const { showNotification } = useNotification();

  // 🔥 ОБЪЕДИНЕННАЯ ФУНКЦИЯ ЗАГРУЗКИ СЕССИЙ
  const loadSessions = useCallback(async () => {
    if (!company) return;

    setLoading(true);
    setErrorMessage('');

    try {
      const response = await axios.get(
        `/api/v1/dashboard/${company.id}/all-sessions?include_anonymous=true`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const allSessions = response.data.sessions || response.data;

      // Статистика
      const withContacts = allSessions.filter(s => s.lead_phone || s.lead_email).length;

      setStats({
        total: allSessions.length,
        withContacts: withContacts,
        anonymous: allSessions.length - withContacts
      });

      // Фильтрация
      let filteredSessions = allSessions;
      if (filter === 'with-contacts') {
        filteredSessions = allSessions.filter(s => s.lead_phone || s.lead_email);
      } else if (filter === 'anonymous') {
        filteredSessions = allSessions.filter(s => !s.lead_phone && !s.lead_email);
      }

      setSessions(filteredSessions);
    } catch (error) {
      console.error('Ошибка загрузки диалогов:', error);
      showNotification(`Ошибка загрузки: ${error.message}`, 'error');

      // Fallback на старый endpoint
      try {
        const response = await axios.get(
          `/api/v1/dashboard/${company.id}/leads`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
        setSessions(response.data);
        setStats({
          total: response.data.length,
          withContacts: response.data.length,
          anonymous: 0
        });
      } catch (fallbackError) {
        console.error('Ошибка загрузки через старый endpoint:', fallbackError);
        showNotification(`Ошибка загрузки: ${fallbackError.message}`, 'error');
      }
    } finally {
      setLoading(false);
    }
  }, [company, token, filter, showNotification]); // ✅ filter в зависимостях

  // 🔥 ЕДИНСТВЕННЫЙ useEffect для загрузки данных
  useEffect(() => {
    loadSessions();
  }, [loadSessions]); // ✅ Зависимость от мемоизированной функции

  const loadSessionMessages = async (sessionId) => {
    try {
      const response = await axios.get(
        `/api/v1/dashboard/${company.id}/sessions/${sessionId}/messages`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setMessages(response.data);
      setSelectedSession(sessionId);
    } catch (error) {
      console.error('Ошибка загрузки сообщений:', error);
      showNotification(`Ошибка загрузки сообщений: ${error.response?.data?.detail || error.message}`, 'error');
    }
  };

  const openDeleteConfirm = (sessionId, event) => {
    if (event) {
      event.stopPropagation();
    }
    setSessionToDelete(sessionId);
    setShowDeleteConfirm(true);
  };

  const confirmDeleteSession = async () => {
    if (!sessionToDelete || !company || !company.id) {
      showNotification('Ошибка: отсутствуют данные для удаления', 'error');
      return;
    }

    setDeleting(true);
    setErrorMessage('');

    try {
      const tenantId = company.id.trim();
      if (!tenantId || tenantId.length < 10) {
        throw new Error(`Некорректный ID компании: ${tenantId}`);
      }

      const response = await axios.delete(
        `/api/v1/dashboard/${tenantId}/sessions/${sessionToDelete}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      showNotification(response.data.message || 'Диалог успешно удален', 'success');

      if (selectedSession === sessionToDelete) {
        setSelectedSession(null);
        setMessages([]);
      }

      // 🔥 Перезагружаем сессии после удаления
      await loadSessions();

    } catch (error) {
      console.error('Ошибка удаления диалога:', error);

      const errorMsg = error.response?.data?.detail ||
                      error.response?.data?.message ||
                      error.message;

      setErrorMessage(`Ошибка удаления: ${errorMsg}`);
      showNotification(`Ошибка удаления: ${errorMsg}`, 'error');

      if (error.response?.status === 404) {
        try {
          const altResponse = await axios.delete(
            `/api/v1/tenants/${company.id}/sessions/${sessionToDelete}`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            }
          );
          showNotification(`Диалог удален: ${altResponse.data.message}`, 'success');
          await loadSessions();
        } catch (altError) {
          console.error('Альтернативное удаление также не сработало:', altError);
        }
      }
    } finally {
      setDeleting(false);
      setShowDeleteConfirm(false);
      setSessionToDelete(null);
    }
  };

  const cancelDelete = () => {
    setShowDeleteConfirm(false);
    setSessionToDelete(null);
    setErrorMessage('');
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU');
  };

  const formatShortDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) {
      return `${diffMins} мин назад`;
    } else if (diffHours < 24) {
      return `${diffHours} ч назад`;
    } else if (diffDays < 7) {
      return `${diffDays} д назад`;
    } else {
      return date.toLocaleDateString('ru-RU');
    }
  };

  // 🔥 Функция для смены фильтра (теперь просто меняет состояние)
  const handleFilterChange = (newFilter) => {
    setFilter(newFilter);
    // Не нужно вызывать loadSessions здесь - useEffect сделает это автоматически
  };

  const refreshDialogList = () => {
    loadSessions();
  };

  const getSessionInfo = () => {
    if (!sessionToDelete) return null;
    return sessions.find(s => s.session_id === sessionToDelete);
  };

  const sessionInfo = getSessionInfo();

  if (loading) {
    return (
      <div className="dialog-list-loading">
        <div className="loading-spinner"></div>
        Загрузка диалогов...
      </div>
    );
  }

  return (
    <div className="dialog-list">
      {/* Модальное окно подтверждения удаления */}
      {showDeleteConfirm && (
        <div className="delete-confirm-modal">
          <div className="delete-confirm-content">
            <h3>Подтверждение удаления</h3>

            {sessionInfo && (
              <div className="session-info-preview">
                <div className="preview-header">
                  <strong>Информация о диалоге:</strong>
                </div>
                <div className="preview-details">
                  <div className="preview-row">
                    <span className="preview-label">Клиент:</span>
                    <span className="preview-value">{sessionInfo.lead_name || "Аноним"}</span>
                  </div>
                  {sessionInfo.lead_phone && (
                    <div className="preview-row">
                      <span className="preview-label">Телефон:</span>
                      <span className="preview-value">{sessionInfo.lead_phone}</span>
                    </div>
                  )}
                  {sessionInfo.lead_email && (
                    <div className="preview-row">
                      <span className="preview-label">Email:</span>
                      <span className="preview-value">{sessionInfo.lead_email}</span>
                    </div>
                  )}
                  <div className="preview-row">
                    <span className="preview-label">Сообщений:</span>
                    <span className="preview-value">{sessionInfo.messages_count}</span>
                  </div>
                  <div className="preview-row">
                    <span className="preview-label">Начало диалога:</span>
                    <span className="preview-value">{formatDate(sessionInfo.first_message_at)}</span>
                  </div>
                </div>
              </div>
            )}

            {errorMessage && (
              <div className="error-message">
                {errorMessage}
              </div>
            )}

            <div className="warning-message">
              <div className="warning-icon">️</div>
              <div className="warning-text">
                <p><strong>Внимание! Это действие нельзя отменить.</strong></p>
                <p>Все сообщения этого диалога будут <strong>безвозвратно удалены</strong> из базы данных.</p>
                <p>Рекомендуем экспортировать важные данные перед удалением.</p>
              </div>
            </div>

            <div className="delete-confirm-actions">
              <button
                onClick={cancelDelete}
                className="delete-confirm-btn cancel"
                disabled={deleting}
              >
                Отмена
              </button>
              <button
                onClick={confirmDeleteSession}
                className="delete-confirm-btn confirm"
                disabled={deleting}
              >
                {deleting ? (
                  <>
                    <span className="deleting-spinner"></span>
                    Удаление...
                  </>
                ) : (
                  'Удалить навсегда'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="dialog-list-header">
        <div className="header-left">
          <h2>Все диалоги</h2>
          <div className="dialog-filters">
            <button
              className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
              onClick={() => handleFilterChange('all')}
            >
              Все ({stats.total})
            </button>
            <button
              className={`filter-btn ${filter === 'with-contacts' ? 'active' : ''}`}
              onClick={() => handleFilterChange('with-contacts')}
            >
              С контактами ({stats.withContacts})
            </button>
            <button
              className={`filter-btn ${filter === 'anonymous' ? 'active' : ''}`}
              onClick={() => handleFilterChange('anonymous')}
            >
              Анонимные ({stats.anonymous})
            </button>
          </div>
        </div>
        <div className="header-right">
          <div className="session-count">
            {sessions.length} из {stats.total} диалогов
          </div>
          <button onClick={refreshDialogList} className="refresh-btn">
            Обновить
          </button>
        </div>
      </div>

      <div className="dialog-container">
        <div className="sessions-sidebar">
          <div className="sessions-list">
            {sessions.length === 0 ? (
              <div className="no-sessions">
                {filter === 'all' ? 'Нет диалогов' :
                 filter === 'with-contacts' ? 'Нет диалогов с контактами' :
                 'Нет анонимных диалогов'}
                <button
                  onClick={refreshDialogList}
                  className="retry-btn"
                >
                  Попробовать снова
                </button>
              </div>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.session_id}
                  className={`session-item ${
                    selectedSession === session.session_id ? 'active' : ''
                  }`}
                  onClick={() => loadSessionMessages(session.session_id)}
                >
                  <div className="session-header">
                    <div className="session-name">
                      {session.lead_name || "Аноним"}
                    </div>
                    <div className="session-actions">
                      <div className="session-date">
                        {formatShortDate(session.last_message_at)}
                      </div>
                    </div>
                  </div>

                  {session.preview_message && (
                    <div className="session-preview" title={session.preview_message}>
                      {session.preview_message}
                    </div>
                  )}

                  <div className="session-info">
                    {session.lead_phone && (
                      <span className="contact-info" title="Телефон">{session.lead_phone}</span>
                    )}
                    {session.lead_email && (
                      <span className="contact-info" title="Email">{session.lead_email}</span>
                    )}
                    <span className="message-count">
                      {session.messages_count} сообщ.
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="messages-panel">
          {selectedSession ? (
            <div className="messages-container">
              <div className="messages-header">
                <h3>История переписки</h3>
                <div className="messages-actions">
                  <button
                    onClick={() => openDeleteConfirm(selectedSession)}
                    className="delete-messages-btn"
                    title="Удалить диалог"
                  >
                    <span className="delete-icon">🗑️</span>
                    <span className="delete-text">Удалить диалог</span>
                  </button>
                  <button
                    onClick={() => setSelectedSession(null)}
                    className="close-messages"
                    title="Закрыть"
                  >
                    ✕
                  </button>
                </div>
              </div>
              <div className="messages-list">
                {messages.length === 0 ? (
                  <div className="no-messages">
                    Нет сообщений в этой сессии
                  </div>
                ) : (
                  messages.map((message) => (
                    <div
                      key={message.id}
                      className={`message ${
                        message.is_from_lead ? 'from-lead' : 'from-bot'
                      }`}
                    >
                      <div className="message-sender">
                        {message.is_from_lead ? 'Клиент' : 'Бот'}
                      </div>
                      <div className="message-content">{message.content}</div>
                      <div className="message-time">
                        {formatDate(message.created_at)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div className="no-selection">
              <div className="no-selection-icon"></div>
              <h3>Выберите диалог</h3>
              <p>Выберите диалог из списка слева, чтобы просмотреть переписку</p>
              <div className="no-selection-stats">
                <div className="stat-item">
                  <div className="stat-value">{stats.total}</div>
                  <div className="stat-label">Всего диалогов</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">{stats.withContacts}</div>
                  <div className="stat-label">С контактами</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">{stats.anonymous}</div>
                  <div className="stat-label">Анонимных</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DialogList;