'use client';

import { useState, useMemo, useRef, useEffect } from 'react';
import { CheckIcon, ChevronUpDownIcon, XMarkIcon } from '@heroicons/react/24/outline';

export interface MultiSelectOption {
  value: string;
  label: string;
  sublabel?: string;
}

interface MultiSelectProps {
  options: MultiSelectOption[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  label?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  className?: string;
}

export function MultiSelect({
  options,
  selected,
  onChange,
  placeholder = 'Select items...',
  label,
  searchPlaceholder = 'Search...',
  emptyMessage = 'No items found',
  className = '',
}: MultiSelectProps) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const filteredOptions = useMemo(() => {
    if (!query) return options;
    const lowerQuery = query.toLowerCase();
    return options.filter(
      (option) =>
        option.label.toLowerCase().includes(lowerQuery) ||
        option.sublabel?.toLowerCase().includes(lowerQuery)
    );
  }, [options, query]);

  const selectedOptions = useMemo(() => {
    return options.filter((option) => selected.includes(option.value));
  }, [options, selected]);

  const toggleOption = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  const removeOption = (value: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(selected.filter((v) => v !== value));
  };

  const selectAll = () => {
    onChange(options.map((o) => o.value));
  };

  const clearAll = () => {
    onChange([]);
  };

  useEffect(() => {
    if (!open) return;

    const handleMouseDown = (event: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
        setQuery('');
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        setQuery('');
      }
    };

    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (open) {
      const id = window.setTimeout(() => searchInputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
  }, [open]);

  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {label}
        </label>
      )}
      <div ref={wrapperRef} className="relative">
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          aria-haspopup="listbox"
          aria-expanded={open}
          className="relative w-full cursor-pointer overflow-hidden rounded-lg bg-white dark:bg-slate-700 border border-gray-300 dark:border-gray-600 text-left focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
        >
          <div className="flex flex-wrap gap-1.5 p-2 pr-8 min-h-[48px]">
            {selectedOptions.length > 0 ? (
              <>
                {selectedOptions.slice(0, 3).map((option) => (
                  <span
                    key={option.value}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-sm bg-wedding-rose/10 text-wedding-rose dark:bg-wedding-rose/20 dark:text-wedding-rose-light border border-wedding-rose/20"
                  >
                    <span className="truncate max-w-[120px]">{option.label}</span>
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(e) => removeOption(option.value, e)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          e.stopPropagation();
                          onChange(selected.filter((v) => v !== option.value));
                        }
                      }}
                      className="hover:bg-wedding-rose/20 rounded-full p-0.5 transition-colors cursor-pointer"
                      aria-label={`Remove ${option.label}`}
                    >
                      <XMarkIcon className="h-3.5 w-3.5" />
                    </span>
                  </span>
                ))}
                {selectedOptions.length > 3 && (
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-sm bg-gray-100 dark:bg-slate-600 text-gray-600 dark:text-gray-300">
                    +{selectedOptions.length - 3} more
                  </span>
                )}
              </>
            ) : (
              <span className="text-gray-400 dark:text-gray-500 py-1 px-1">
                {placeholder}
              </span>
            )}
          </div>
          <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
            <ChevronUpDownIcon
              className="h-5 w-5 text-gray-400"
              aria-hidden="true"
            />
          </span>
        </button>

        {open && (
          <div
            className="absolute z-50 mt-1 max-h-72 w-full overflow-auto rounded-lg bg-white dark:bg-slate-800 py-1 shadow-lg ring-1 ring-black/5 dark:ring-white/10 focus:outline-none"
            role="listbox"
          >
            <div className="sticky top-0 bg-white dark:bg-slate-800 px-3 py-2 border-b border-gray-100 dark:border-gray-700">
              <input
                ref={searchInputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={searchPlaceholder}
                aria-label="Search options"
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-wedding-rose"
              />
            </div>

            <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 dark:border-gray-700">
              <button
                type="button"
                onClick={selectAll}
                className="text-xs text-wedding-rose hover:text-wedding-rose-dark font-medium transition-colors"
              >
                Select All ({options.length})
              </button>
              <span className="text-gray-300 dark:text-gray-600">|</span>
              <button
                type="button"
                onClick={clearAll}
                className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 font-medium transition-colors"
              >
                Clear All
              </button>
              {selected.length > 0 && (
                <>
                  <span className="text-gray-300 dark:text-gray-600">|</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {selected.length} selected
                  </span>
                </>
              )}
            </div>

            {filteredOptions.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                {emptyMessage}
              </div>
            ) : (
              <ul className="py-1">
                {filteredOptions.map((option) => {
                  const isSelected = selected.includes(option.value);
                  return (
                    <li key={option.value}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => toggleOption(option.value)}
                        className={`relative w-full text-left cursor-pointer select-none py-2.5 pl-10 pr-4 transition-colors hover:bg-wedding-rose/10 dark:hover:bg-wedding-rose/20 ${
                          isSelected ? 'bg-wedding-rose/5 dark:bg-wedding-rose/10' : ''
                        }`}
                      >
                        <span className="absolute inset-y-0 left-0 flex items-center pl-3">
                          <span
                            className={`flex h-5 w-5 items-center justify-center rounded border transition-colors ${
                              isSelected
                                ? 'bg-wedding-rose border-wedding-rose'
                                : 'border-gray-300 dark:border-gray-500'
                            }`}
                          >
                            {isSelected && (
                              <CheckIcon className="h-3.5 w-3.5 text-white" />
                            )}
                          </span>
                        </span>
                        <span
                          className={`block truncate text-sm ${
                            isSelected
                              ? 'font-semibold text-wedding-rose dark:text-wedding-rose-light'
                              : 'text-gray-900 dark:text-gray-100'
                          }`}
                        >
                          {option.label}
                        </span>
                        {option.sublabel && (
                          <span className="block truncate text-xs text-gray-500 dark:text-gray-400">
                            {option.sublabel}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
