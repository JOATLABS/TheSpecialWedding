'use client';

import { useState, useMemo, Fragment } from 'react';
import { Combobox, ComboboxButton, ComboboxInput, ComboboxOption, ComboboxOptions, Transition } from '@headlessui/react';
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

  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {label}
        </label>
      )}
      <Combobox as="div" value={selected} onChange={() => {}} multiple>
        <div className="relative">
          {/* Selected items display */}
          <div className="relative w-full cursor-default overflow-hidden rounded-lg bg-white dark:bg-slate-700 border border-gray-300 dark:border-gray-600 focus-within:ring-2 focus-within:ring-wedding-rose focus-within:border-transparent">
            <div className="flex flex-wrap gap-1.5 p-2 min-h-[48px]">
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
                        className="hover:bg-wedding-rose/20 rounded-full p-0.5 transition-colors"
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
            <ComboboxButton className="absolute inset-y-0 right-0 flex items-center pr-2">
              <ChevronUpDownIcon
                className="h-5 w-5 text-gray-400"
                aria-hidden="true"
              />
            </ComboboxButton>
          </div>

          <Transition
            as={Fragment}
            leave="transition ease-in duration-100"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
            afterLeave={() => setQuery('')}
          >
            <ComboboxOptions className="absolute z-50 mt-1 max-h-72 w-full overflow-auto rounded-lg bg-white dark:bg-slate-800 py-1 shadow-lg ring-1 ring-black/5 dark:ring-white/10 focus:outline-none">
              {/* Search input */}
              <div className="sticky top-0 bg-white dark:bg-slate-800 px-3 py-2 border-b border-gray-100 dark:border-gray-700">
                <ComboboxInput
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                  placeholder={searchPlaceholder}
                  onChange={(e) => setQuery(e.target.value)}
                  displayValue={() => query}
                  aria-label="Search options"
                />
              </div>

              {/* Quick actions */}
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

              {/* Options list */}
              {filteredOptions.length === 0 ? (
                <div className="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                  {emptyMessage}
                </div>
              ) : (
                <div className="py-1">
                  {filteredOptions.map((option) => (
                    <ComboboxOption
                      key={option.value}
                      value={option.value}
                      as={Fragment}
                    >
                      {({ active }) => (
                        <div
                          onClick={() => toggleOption(option.value)}
                          className={`relative cursor-pointer select-none py-2.5 pl-10 pr-4 transition-colors ${
                            active
                              ? 'bg-wedding-rose/10 dark:bg-wedding-rose/20'
                              : ''
                          }`}
                        >
                          <span className="absolute inset-y-0 left-0 flex items-center pl-3">
                            <div
                              className={`flex h-5 w-5 items-center justify-center rounded border transition-colors ${
                                selected.includes(option.value)
                                  ? 'bg-wedding-rose border-wedding-rose'
                                  : 'border-gray-300 dark:border-gray-500'
                              }`}
                            >
                              {selected.includes(option.value) && (
                                <CheckIcon className="h-3.5 w-3.5 text-white" />
                              )}
                            </div>
                          </span>
                          <div>
                            <span
                              className={`block truncate text-sm ${
                                selected.includes(option.value)
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
                          </div>
                        </div>
                      )}
                    </ComboboxOption>
                  ))}
                </div>
              )}
            </ComboboxOptions>
          </Transition>
        </div>
      </Combobox>
    </div>
  );
}
