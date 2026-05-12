'use client';

import { useState, useMemo, useRef, useEffect, useId } from 'react';
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
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);
  const uid = useId();
  const listboxId = `${uid}-listbox`;
  const getOptionId = (index: number) => `${uid}-option-${index}`;

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

  // Reset active index whenever the filtered list changes or the dropdown closes.
  useEffect(() => {
    setActiveIndex(-1);
  }, [query, open]);

  // Scroll the active option into view when it changes.
  useEffect(() => {
    if (activeIndex < 0 || !listboxRef.current) return;
    const activeEl = listboxRef.current.querySelector<HTMLElement>(
      `#${CSS.escape(getOptionId(activeIndex))}`
    );
    activeEl?.scrollIntoView({ block: 'nearest' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeIndex]);

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open) return;
    const count = filteredOptions.length;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((prev) => (count === 0 ? -1 : (prev + 1) % count));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((prev) => (count === 0 ? -1 : prev <= 0 ? count - 1 : prev - 1));
        break;
      case 'Home':
        if (count > 0) { e.preventDefault(); setActiveIndex(0); }
        break;
      case 'End':
        if (count > 0) { e.preventDefault(); setActiveIndex(count - 1); }
        break;
      case 'Enter':
        if (activeIndex >= 0 && activeIndex < count) {
          e.preventDefault();
          toggleOption(filteredOptions[activeIndex].value);
        }
        break;
      case 'Escape':
        setOpen(false);
        setQuery('');
        break;
      case 'Tab':
        setOpen(false);
        setQuery('');
        break;
    }
  };

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
        <label
          htmlFor={`${uid}-toggle`}
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
        >
          {label}
        </label>
      )}
      <div ref={wrapperRef} className="relative">
        {/*
          The trigger is a plain <div> so that the real <button> elements used
          for chip removal and the chevron toggle are not nested inside another
          interactive element (invalid HTML per the spec).
        */}
        <div
          className="relative w-full cursor-pointer rounded-lg bg-white dark:bg-slate-700 border border-gray-300 dark:border-gray-600 text-left focus-within:ring-2 focus-within:ring-wedding-rose focus-within:border-transparent"
          onClick={() => setOpen((prev) => !prev)}
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
                    <button
                      type="button"
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
                    </button>
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
          {/* Dedicated toggle button — the only keyboard-focusable trigger control. */}
          <button
            type="button"
            id={`${uid}-toggle`}
            onClick={(e) => { e.stopPropagation(); setOpen((prev) => !prev); }}
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-label={open ? 'Close options' : 'Open options'}
            className="absolute inset-y-0 right-0 flex items-center pr-2 focus:outline-none"
          >
            <ChevronUpDownIcon
              className="h-5 w-5 text-gray-400"
              aria-hidden="true"
            />
          </button>
        </div>

        {open && (
          <div
            className="absolute z-50 mt-1 max-h-72 w-full overflow-auto rounded-lg bg-white dark:bg-slate-800 py-1 shadow-lg ring-1 ring-black/5 dark:ring-white/10 focus:outline-none"
          >
            <div className="sticky top-0 bg-white dark:bg-slate-800 px-3 py-2 border-b border-gray-100 dark:border-gray-700">
              <input
                ref={searchInputRef}
                type="text"
                role="combobox"
                aria-expanded={open}
                aria-controls={listboxId}
                aria-activedescendant={activeIndex >= 0 ? getOptionId(activeIndex) : undefined}
                aria-autocomplete="list"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleSearchKeyDown}
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
              <ul ref={listboxRef} id={listboxId} role="listbox" aria-multiselectable="true" aria-label={label || placeholder} className="py-1">
                {filteredOptions.map((option, index) => {
                  const isSelected = selected.includes(option.value);
                  const isActive = index === activeIndex;
                  return (
                    <li key={option.value} role="presentation">
                      <button
                        type="button"
                        id={getOptionId(index)}
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => toggleOption(option.value)}
                        className={`relative w-full text-left cursor-pointer select-none py-2.5 pl-10 pr-4 transition-colors hover:bg-wedding-rose/10 dark:hover:bg-wedding-rose/20 ${
                          isSelected ? 'bg-wedding-rose/5 dark:bg-wedding-rose/10' : ''
                        } ${isActive ? 'outline outline-2 outline-offset-[-2px] outline-wedding-rose/50' : ''}`}
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
