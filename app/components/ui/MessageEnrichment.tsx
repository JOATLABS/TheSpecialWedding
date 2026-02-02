'use client';

import { useState } from 'react';
import { LinkIcon, MapPinIcon, DocumentTextIcon, XMarkIcon, PlusIcon } from '@heroicons/react/24/outline';

interface EnrichmentItem {
  type: 'url' | 'location' | 'form';
  value: string;
  label?: string;
}

interface MessageEnrichmentProps {
  onInsert: (text: string) => void;
  className?: string;
}

export function MessageEnrichment({ onInsert, className = '' }: MessageEnrichmentProps) {
  const [activePanel, setActivePanel] = useState<'url' | 'location' | 'form' | null>(null);
  const [url, setUrl] = useState('');
  const [urlLabel, setUrlLabel] = useState('');
  const [location, setLocation] = useState('');
  const [locationUrl, setLocationUrl] = useState('');
  const [selectedForm, setSelectedForm] = useState('');

  const handleInsertUrl = () => {
    if (!url) return;
    const text = urlLabel ? `${urlLabel}: ${url}` : url;
    onInsert(text);
    setUrl('');
    setUrlLabel('');
    setActivePanel(null);
  };

  const handleInsertLocation = () => {
    if (!location) return;
    let text = `Location: ${location}`;
    if (locationUrl) {
      text += ` (Map: ${locationUrl})`;
    }
    onInsert(text);
    setLocation('');
    setLocationUrl('');
    setActivePanel(null);
  };

  const handleInsertForm = () => {
    if (!selectedForm) return;
    // This would ideally link to actual forms in your system
    const formUrl = `{form_url:${selectedForm}}`;
    onInsert(`Fill out the ${selectedForm} form: ${formUrl}`);
    setSelectedForm('');
    setActivePanel(null);
  };

  const buttons = [
    {
      type: 'url' as const,
      icon: LinkIcon,
      label: 'Add Link',
      color: 'bg-blue-500 hover:bg-blue-600',
    },
    {
      type: 'location' as const,
      icon: MapPinIcon,
      label: 'Add Location',
      color: 'bg-green-500 hover:bg-green-600',
    },
    {
      type: 'form' as const,
      icon: DocumentTextIcon,
      label: 'Add Form',
      color: 'bg-purple-500 hover:bg-purple-600',
    },
  ];

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Toggle buttons */}
      <div className="flex flex-wrap gap-2">
        {buttons.map(({ type, icon: Icon, label, color }) => (
          <button
            key={type}
            type="button"
            onClick={() => setActivePanel(activePanel === type ? null : type)}
            aria-expanded={activePanel === type}
            aria-controls={`panel-${type}`}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
              activePanel === type
                ? `${color} text-white shadow-md`
                : 'bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-600'
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* URL Panel */}
      {activePanel === 'url' && (
        <div
          id="panel-url"
          className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800 space-y-3"
        >
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-blue-900 dark:text-blue-300 flex items-center gap-2">
              <LinkIcon className="h-4 w-4" />
              Insert Link
            </h4>
            <button
              type="button"
              onClick={() => setActivePanel(null)}
              aria-label="Close panel"
              className="text-blue-600 dark:text-blue-400 hover:text-blue-800"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input
              type="text"
              autoFocus
              value={urlLabel}
              onChange={(e) => setUrlLabel(e.target.value)}
              placeholder="Link label (optional)"
              className="px-3 py-2 rounded-md border border-blue-200 dark:border-blue-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              className="px-3 py-2 rounded-md border border-blue-200 dark:border-blue-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            type="button"
            onClick={handleInsertUrl}
            disabled={!url}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-500 text-white rounded-md text-sm font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            Insert Link
          </button>
        </div>
      )}

      {/* Location Panel */}
      {activePanel === 'location' && (
        <div
          id="panel-location"
          className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800 space-y-3"
        >
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-green-900 dark:text-green-300 flex items-center gap-2">
              <MapPinIcon className="h-4 w-4" />
              Insert Location
            </h4>
            <button
              type="button"
              onClick={() => setActivePanel(null)}
              aria-label="Close panel"
              className="text-green-600 dark:text-green-400 hover:text-green-800"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
          <div className="space-y-3">
            <input
              type="text"
              autoFocus
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Venue name or address"
              className="w-full px-3 py-2 rounded-md border border-green-200 dark:border-green-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
            <input
              type="url"
              value={locationUrl}
              onChange={(e) => setLocationUrl(e.target.value)}
              placeholder="Google Maps link (optional)"
              className="w-full px-3 py-2 rounded-md border border-green-200 dark:border-green-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
          </div>
          <button
            type="button"
            onClick={handleInsertLocation}
            disabled={!location}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-green-500 text-white rounded-md text-sm font-medium hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            Insert Location
          </button>
        </div>
      )}

      {/* Form Panel */}
      {activePanel === 'form' && (
        <div
          id="panel-form"
          className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800 space-y-3"
        >
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-purple-900 dark:text-purple-300 flex items-center gap-2">
              <DocumentTextIcon className="h-4 w-4" />
              Insert Form Link
            </h4>
            <button
              type="button"
              onClick={() => setActivePanel(null)}
              aria-label="Close panel"
              className="text-purple-600 dark:text-purple-400 hover:text-purple-800"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
          <select
            autoFocus
            value={selectedForm}
            onChange={(e) => setSelectedForm(e.target.value)}
            className="w-full px-3 py-2 rounded-md border border-purple-200 dark:border-purple-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          >
            <option value="">Select a form...</option>
            <option value="rsvp">RSVP Form</option>
            <option value="dietary">Dietary Preferences</option>
            <option value="song_request">Song Request</option>
            <option value="accommodation">Accommodation</option>
            <option value="transportation">Transportation</option>
          </select>
          <button
            type="button"
            onClick={handleInsertForm}
            disabled={!selectedForm}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-purple-500 text-white rounded-md text-sm font-medium hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            Insert Form Link
          </button>
        </div>
      )}
    </div>
  );
}
