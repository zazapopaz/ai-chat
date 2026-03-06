import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './LeadsList.css';

function LeadsList({ token, company }) {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, with-phone, with-email

  useEffect(() => {
    if (company) {
      loadLeads();
    }
  }, [company]);

  const loadLeads = async () => {
    try {
      const response = await axios.get(
        `http://localhost:8000/api/v1/dashboard/${company.id}/leads`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setLeads(response.data);
    } catch (error) {
      console.error('Ошибка загрузки лидов:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredLeads = leads.filter((lead) => {
    if (filter === 'with-phone') return lead.lead_phone;
    if (filter === 'with-email') return lead.lead_email;
    return true;
  });

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU');
  };

  // ПРОСТАЯ И РАБОЧАЯ ФУНКЦИЯ ЭКСПОРТА В EXCEL
  const exportToExcel = () => {
    // Разделитель для русской версии Excel - точка с запятой
    const delimiter = ';';

    // Заголовки
    const headers = [
      'Имя',
      'Телефон',
      'Email',
      'Дата первого контакта',
      'Сообщений',
      'Страница'
    ];

    // Данные
    const rows = filteredLeads.map(lead => [
      lead.lead_name || '',
      lead.lead_phone || '',
      lead.lead_email || '',
      formatDate(lead.first_message_at),
      lead.messages_count,
      lead.page_url || ''
    ]);

    // Простое экранирование
    const escapeCell = (cell) => {
      const str = String(cell);
      // Если есть спецсимволы - оборачиваем в кавычки
      if (str.includes(delimiter) || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    // Собираем CSV
    const csvRows = [
      headers.map(escapeCell).join(delimiter),
      ...rows.map(row => row.map(escapeCell).join(delimiter))
    ];

    const csvString = csvRows.join('\n');

    // Добавляем BOM для русских букв
    const blob = new Blob(['\uFEFF' + csvString], {
      type: 'text/csv;charset=utf-8;'
    });

    // Скачиваем файл
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `leads_${company.company_name}_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  if (loading) {
    return <div className="leads-list-loading">Загрузка лидов...</div>;
  }

  return (
    <div className="leads-list">
      <div className="leads-header">
        <div className="header-left">
          <h2>Лиды ({filteredLeads.length})</h2>
          <div className="lead-filters">
            <button
              className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}
            >
              Все
            </button>
            <button
              className={`filter-btn ${filter === 'with-phone' ? 'active' : ''}`}
              onClick={() => setFilter('with-phone')}
            >
              С телефоном
            </button>
            <button
              className={`filter-btn ${filter === 'with-email' ? 'active' : ''}`}
              onClick={() => setFilter('with-email')}
            >
              С email
            </button>
          </div>
        </div>
        <div className="header-right">
          <button onClick={exportToExcel} className="export-btn">
             Экспорт в Excel
          </button>
          <button onClick={loadLeads} className="refresh-btn">
             Обновить
          </button>
        </div>
      </div>

      <div className="leads-table-container">
        <table className="leads-table">
          <thead>
            <tr>
              <th>Имя</th>
              <th>Телефон</th>
              <th>Email</th>
              <th>Первый контакт</th>
              <th>Последний контакт</th>
              <th>Сообщений</th>
              <th>Страница</th>
            </tr>
          </thead>
          <tbody>
            {filteredLeads.length === 0 ? (
              <tr>
                <td colSpan="7" className="no-data">
                  Нет лидов
                </td>
              </tr>
            ) : (
              filteredLeads.map((lead) => (
                <tr key={lead.session_id}>
                  <td>
                    <div className="lead-name">
                      {lead.lead_name || 'Не указано'}
                    </div>
                  </td>
                  <td>
                    {lead.lead_phone ? (
                      <a href={`tel:${lead.lead_phone}`} className="phone-link">
                        {lead.lead_phone}
                      </a>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    {lead.lead_email ? (
                      <a href={`mailto:${lead.lead_email}`} className="email-link">
                        {lead.lead_email}
                      </a>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>{formatDate(lead.first_message_at)}</td>
                  <td>{formatDate(lead.last_message_at)}</td>
                  <td>{lead.messages_count}</td>
                  <td>
                    {lead.page_url ? (
                      <a
                        href={lead.page_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="page-link"
                      >
                        {new URL(lead.page_url).pathname}
                      </a>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="leads-stats">
        <div className="stat-item">
          <span className="stat-label">Всего лидов:</span>
          <span className="stat-value">{leads.length}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">С телефоном:</span>
          <span className="stat-value">
            {leads.filter(l => l.lead_phone).length}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">С email:</span>
          <span className="stat-value">
            {leads.filter(l => l.lead_email).length}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">С контактами:</span>
          <span className="stat-value">
            {leads.filter(l => l.lead_phone || l.lead_email).length}
          </span>
        </div>
      </div>
    </div>
  );
}

export default LeadsList;