'use client';

import { useState } from 'react';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import {
  Sparkles,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  DollarSign,
  AlertCircle,
  CheckCircle,
  X,
  Coins
} from 'lucide-react';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';

interface ServiceItem {
  name: string;
  description?: string;
  included: boolean;
}

interface ScheduleSuggestion {
  name: string;
  percentage: number;
  trigger: string;
  days_after?: number;
  days_before?: number;
}

interface PricingSuggestion {
  min_price: number;
  max_price: number;
  recommended: number;
  market_comparison: 'above' | 'at' | 'below';
  reasoning?: string;
  schedule_suggestion?: ScheduleSuggestion[];
}

interface AIPricingSuggestionProps {
  token: string;
  services: ServiceItem[];
  currentPrice: number;
  currency: string;
  onApplyPrice: (price: number) => void;
  onApplySchedule: (schedule: ScheduleSuggestion[]) => void;
}

export default function AIPricingSuggestion({
  token,
  services,
  currentPrice,
  currency,
  onApplyPrice,
  onApplySchedule
}: AIPricingSuggestionProps) {
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState<PricingSuggestion | null>(null);
  const [error, setError] = useState<string>('');
  const [creditsUsed, setCreditsUsed] = useState<number>(0);
  const [showModal, setShowModal] = useState(false);

  // Form state for additional context
  const [location, setLocation] = useState('');
  const [weddingSize, setWeddingSize] = useState<number>(100);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
    }).format(amount);
  };

  const fetchSuggestion = async () => {
    if (!token) {
      toast.error('Not authenticated');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/packages/ai-pricing`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          services: services.filter(s => s.included).map(s => ({
            name: s.name,
            description: s.description || '',
            included: true
          })),
          location: location || undefined,
          wedding_size: weddingSize || undefined
        }),
      });

      if (response.status === 402) {
        const data = await response.json();
        setError(`Insufficient credits. You need ${data.detail?.required || 3} credits but have ${data.detail?.available || 0}.`);
        return;
      }

      if (response.status === 503) {
        setError('AI features are not available. Please contact support.');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to get pricing suggestion');
      }

      const data = await response.json();
      setSuggestion(data.suggestion);
      setCreditsUsed(data.credits_used || 3);
      setShowModal(true);
    } catch (err) {
      setError('Failed to get AI pricing suggestion. Please try again.');
      toast.error('Failed to get pricing suggestion');
    } finally {
      setLoading(false);
    }
  };

  const getComparisonIcon = () => {
    if (!suggestion) return null;
    switch (suggestion.market_comparison) {
      case 'above':
        return <TrendingUp className="text-amber-500" size={20} />;
      case 'below':
        return <TrendingDown className="text-blue-500" size={20} />;
      default:
        return <Minus className="text-green-500" size={20} />;
    }
  };

  const getComparisonText = () => {
    if (!suggestion) return '';
    switch (suggestion.market_comparison) {
      case 'above':
        return 'Above market average';
      case 'below':
        return 'Below market average';
      default:
        return 'At market average';
    }
  };

  return (
    <>
      {/* Trigger Button */}
      <div className="p-4 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/50 rounded-lg">
              <Sparkles className="text-purple-600 dark:text-purple-400" size={20} />
            </div>
            <div>
              <h3 className="font-medium text-slate-900 dark:text-white">
                AI Pricing Assistant
              </h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Get competitive pricing suggestions based on your services
              </p>
            </div>
          </div>
          <Button
            type="button"
            onClick={fetchSuggestion}
            disabled={loading || services.filter(s => s.included).length === 0}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white"
          >
            {loading ? (
              <>
                <Loader2 className="animate-spin" size={16} />
                Analyzing...
              </>
            ) : (
              <>
                <Sparkles size={16} />
                Get AI Suggestion
                <span className="text-xs opacity-75">(3 credits)</span>
              </>
            )}
          </Button>
        </div>

        {/* Optional context inputs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Location (optional)
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g., New York, NY"
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Typical wedding size
            </label>
            <input
              type="number"
              value={weddingSize}
              onChange={(e) => setWeddingSize(parseInt(e.target.value) || 100)}
              placeholder="100"
              min="1"
              max="1000"
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
            />
          </div>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg flex items-start gap-2">
            <AlertCircle className="text-red-500 flex-shrink-0 mt-0.5" size={16} />
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}
      </div>

      {/* Results Modal */}
      {showModal && suggestion && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 dark:bg-purple-900/50 rounded-lg">
                    <Sparkles className="text-purple-600 dark:text-purple-400" size={20} />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                      AI Pricing Suggestion
                    </h2>
                    <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
                      <Coins size={12} />
                      {creditsUsed} credits used
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Recommended Price */}
              <div className="text-center p-6 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-xl mb-6">
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                  Recommended Price
                </p>
                <p className="text-4xl font-bold text-green-600 dark:text-green-400">
                  {formatCurrency(suggestion.recommended)}
                </p>
                <div className="flex items-center justify-center gap-2 mt-2">
                  {getComparisonIcon()}
                  <span className="text-sm text-slate-600 dark:text-slate-400">
                    {getComparisonText()}
                  </span>
                </div>
              </div>

              {/* Price Range */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg text-center">
                  <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Minimum</p>
                  <p className="text-xl font-semibold text-slate-900 dark:text-white">
                    {formatCurrency(suggestion.min_price)}
                  </p>
                </div>
                <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg text-center">
                  <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Maximum</p>
                  <p className="text-xl font-semibold text-slate-900 dark:text-white">
                    {formatCurrency(suggestion.max_price)}
                  </p>
                </div>
              </div>

              {/* Current Price Comparison */}
              {currentPrice > 0 && (
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg mb-6">
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    <span className="font-medium">Your current price:</span> {formatCurrency(currentPrice)}
                    {currentPrice < suggestion.min_price && (
                      <span className="text-amber-600 dark:text-amber-400 ml-2">
                        (Below suggested range)
                      </span>
                    )}
                    {currentPrice > suggestion.max_price && (
                      <span className="text-amber-600 dark:text-amber-400 ml-2">
                        (Above suggested range)
                      </span>
                    )}
                    {currentPrice >= suggestion.min_price && currentPrice <= suggestion.max_price && (
                      <span className="text-green-600 dark:text-green-400 ml-2">
                        (Within suggested range)
                      </span>
                    )}
                  </p>
                </div>
              )}

              {/* Reasoning */}
              {suggestion.reasoning && (
                <div className="mb-6">
                  <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Analysis
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    {suggestion.reasoning}
                  </p>
                </div>
              )}

              {/* Suggested Schedule */}
              {suggestion.schedule_suggestion && suggestion.schedule_suggestion.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Suggested Payment Schedule
                  </h3>
                  <div className="space-y-2">
                    {suggestion.schedule_suggestion.map((item, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 rounded-lg"
                      >
                        <span className="text-sm text-slate-900 dark:text-white">
                          {item.name}
                        </span>
                        <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
                          {item.percentage}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex flex-col sm:flex-row gap-3">
                <Button
                  onClick={() => {
                    onApplyPrice(suggestion.recommended);
                    toast.success('Recommended price applied');
                    setShowModal(false);
                  }}
                  className="flex-1 flex items-center justify-center gap-2"
                >
                  <DollarSign size={16} />
                  Apply Recommended Price
                </Button>
                {suggestion.schedule_suggestion && suggestion.schedule_suggestion.length > 0 && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      onApplySchedule(suggestion.schedule_suggestion as ScheduleSuggestion[]);
                      toast.success('Payment schedule applied');
                      setShowModal(false);
                    }}
                    className="flex-1 flex items-center justify-center gap-2"
                  >
                    <CheckCircle size={16} />
                    Apply Schedule
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
