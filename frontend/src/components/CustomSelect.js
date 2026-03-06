// src/components/CustomSelect.js
import React, { useState, useRef, useEffect } from 'react';

function CustomSelect({ options, value, onChange, placeholder = "Выберите компанию" }) {
  const [isOpen, setIsOpen] = useState(false);
  const selectRef = useRef(null);

  const selectedOption = options.find(opt => opt.id === value) || options[0];

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (selectRef.current && !selectRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (option) => {
    onChange(option);
    setIsOpen(false);
  };

  return (
    <div className="custom-select" ref={selectRef}>
      <div
        className={`custom-select-trigger ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="company-info">
          <span className="company-name">
            {selectedOption ? selectedOption.company_name : placeholder}
          </span>
        </div>
        <span className="trigger-arrow">▼</span>
      </div>

      {isOpen && (
        <div className="custom-select-dropdown">
          {options.map((option) => (
            <div
              key={option.id}
              className={`custom-select-option ${selectedOption?.id === option.id ? 'selected' : ''}`}
              onClick={() => handleSelect(option)}
            >
              <div className="option-content">
                <div className="option-name">{option.company_name}</div>
                <div className="option-balance">
                  Баланс: <strong>{option.message_balance}</strong> сообщ.
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default CustomSelect;