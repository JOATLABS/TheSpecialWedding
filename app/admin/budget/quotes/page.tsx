'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import VendorQuoteCard from '../../../components/budget/VendorQuoteCard';
import { budgetApi } from '../../../services/budgetApi';
import type { VendorQuote, CreateVendorQuoteRequest } from '../../../types/budget';
import { formatDate } from '@/utils/dateFormat';
import PageHeader from '../../components/PageHeader';

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
}

const SERVICE_CATEGORIES = [
  'photography',
  'videography',
  'catering',
  'venue',
  'flowers',
  'music',
  'transportation',
  'cake',
  'decorations',
  'stationery',
  'hair_makeup',
  'other'
];

export default function VendorQuotesPage() {
  const { token } = useAdmin();
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [quotes, setQuotes] = useState<VendorQuote[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  // Filters
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'amount' | 'date' | 'rating' | 'vendor'>('date');

  // Modal state
  const [showQuoteModal, setShowQuoteModal] = useState(false);
  const [quoteForm, setQuoteForm] = useState({
    vendor_name: '',
    vendor_email: '',
    vendor_phone: '',
    service_category: 'photography',
    quote_amount: 0,
    quote_details: {} as Record<string, any>,
    includes: [] as string[],
    excludes: [] as string[],
    terms_conditions: '',
    valid_until: '',
    notes: ''
  });

  // Comparison mode
  const [comparisonMode, setComparisonMode] = useState(false);
  const [selectedQuotes, setSelectedQuotes] = useState<string[]>([]);

  const fetchWeddings = useCallback(async () => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/weddings`);
      const data = await response.json();
      setWeddings(Array.isArray(data) ? data : []);
    } catch (err) {
      setError('Failed to load weddings');
      toast.error('Failed to load weddings');
    }
  }, []);

  const fetchQuotes = useCallback(async () => {
    if (!token || !selectedWedding) return;

    setLoading(true);
    try {
      const quotesData = await budgetApi.getVendorQuotes(
        token,
        selectedWedding,
        categoryFilter === 'all' ? undefined : categoryFilter
      );
      setQuotes(quotesData);
      setError('');
    } catch (err: any) {
      setError(err.message || 'Failed to load vendor quotes');
      toast.error(err.message || 'Failed to load vendor quotes');
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, selectedWedding, token]);

  useEffect(() => {
    fetchWeddings();
  }, [fetchWeddings]);

  useEffect(() => {
    if (selectedWedding && token) {
      fetchQuotes();
    }
  }, [fetchQuotes, selectedWedding, token]);

  const handleCreateQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedWedding) return;

    try {
      const quoteData: CreateVendorQuoteRequest = {
        wedding_id: selectedWedding,
        ...quoteForm,
        includes: quoteForm.includes.filter(item => item.trim() !== ''),
        excludes: quoteForm.excludes.filter(item => item.trim() !== ''),
        valid_until: quoteForm.valid_until || undefined
      };

      const newQuote = await budgetApi.createVendorQuote(token, quoteData);
      setQuotes((prev) => [...prev, newQuote]);
      setShowQuoteModal(false);
      resetQuoteForm();
      toast.success('Vendor quote created successfully');
    } catch (err: any) {
      toast.error(err.message || 'Failed to create vendor quote');
    }
  };

  const handleAcceptQuote = useCallback(async (quoteId: string) => {
    if (!token) return;

    try {
      const updatedQuote = await budgetApi.updateVendorQuoteStatus(token, quoteId, 'accepted');
      setQuotes((prev) => prev.map((q) => (q.id === quoteId ? updatedQuote : q)));
      toast.success('Quote accepted successfully');
    } catch (err: any) {
      toast.error(err.message || 'Failed to accept quote');
    }
  }, [token]);

  const handleRejectQuote = useCallback(async (quoteId: string) => {
    if (!token) return;

    try {
      const updatedQuote = await budgetApi.updateVendorQuoteStatus(token, quoteId, 'rejected');
      setQuotes((prev) => prev.map((q) => (q.id === quoteId ? updatedQuote : q)));
      toast.success('Quote rejected');
    } catch (err: any) {
      toast.error(err.message || 'Failed to reject quote');
    }
  }, [token]);

  const handleRateQuote = useCallback(async (quoteId: string, rating: number, notes?: string) => {
    if (!token) return;

    try {
      const updatedQuote = await budgetApi.rateVendorQuote(token, quoteId, rating, notes);
      setQuotes((prev) => prev.map((q) => (q.id === quoteId ? updatedQuote : q)));
      toast.success('Quote rated successfully');
    } catch (err: any) {
      toast.error(err.message || 'Failed to rate quote');
    }
  }, [token]);

  const resetQuoteForm = () => {
    setQuoteForm({
      vendor_name: '',
      vendor_email: '',
      vendor_phone: '',
      service_category: 'photography',
      quote_amount: 0,
      quote_details: {},
      includes: [],
      excludes: [],
      terms_conditions: '',
      valid_until: '',
      notes: ''
    });
  };

  const addIncludeItem = () => {
    setQuoteForm({
      ...quoteForm,
      includes: [...quoteForm.includes, '']
    });
  };

  const addExcludeItem = () => {
    setQuoteForm({
      ...quoteForm,
      excludes: [...quoteForm.excludes, '']
    });
  };

  const updateIncludeItem = (index: number, value: string) => {
    const newIncludes = [...quoteForm.includes];
    newIncludes[index] = value;
    setQuoteForm({ ...quoteForm, includes: newIncludes });
  };

  const updateExcludeItem = (index: number, value: string) => {
    const newExcludes = [...quoteForm.excludes];
    newExcludes[index] = value;
    setQuoteForm({ ...quoteForm, excludes: newExcludes });
  };

  const removeIncludeItem = (index: number) => {
    setQuoteForm({
      ...quoteForm,
      includes: quoteForm.includes.filter((_, i) => i !== index)
    });
  };

  const removeExcludeItem = (index: number) => {
    setQuoteForm({
      ...quoteForm,
      excludes: quoteForm.excludes.filter((_, i) => i !== index)
    });
  };

  const toggleQuoteComparison = (quoteId: string) => {
    setSelectedQuotes(prev =>
      prev.includes(quoteId)
        ? prev.filter(id => id !== quoteId)
        : [...prev, quoteId]
    );
  };

  const compareQuotes = async () => {
    if (!token || !selectedWedding || selectedQuotes.length < 2) {
      toast.error('Please select at least 2 quotes to compare');
      return;
    }

    try {
      const comparison = await budgetApi.compareVendorQuotes(token, selectedWedding, categoryFilter);
      // Handle comparison results (could open a modal or navigate to comparison view)
      toast.success('Quote comparison generated');
    } catch (err: any) {
      toast.error(err.message || 'Failed to compare quotes');
    }
  };

  // Filter and sort quotes (memoized for performance)
  const filteredQuotes = useMemo(() =>
    quotes
      .filter(quote => {
        const matchesSearch = quote.vendor_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                             quote.service_category.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesStatus = statusFilter === 'all' || quote.status === statusFilter;
        const matchesCategory = categoryFilter === 'all' || quote.service_category === categoryFilter;
        return matchesSearch && matchesStatus && matchesCategory;
      })
      .sort((a, b) => {
        switch (sortBy) {
          case 'amount': return b.quote_amount - a.quote_amount;
          case 'vendor': return a.vendor_name.localeCompare(b.vendor_name);
          case 'rating': return (b.rating || 0) - (a.rating || 0);
          case 'date':
          default:
            return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        }
      }), [quotes, searchTerm, statusFilter, categoryFilter, sortBy]);

  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-wedding-navy mb-4">Access Denied</h2>
          <p>Please log in to access vendor quotes.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Vendor Quotes"
        description="Collect, compare and manage vendor quotes for your wedding"
      >
        <Button
          onClick={() => setComparisonMode(!comparisonMode)}
          className={comparisonMode ? 'bg-purple-600 hover:bg-purple-700' : ''}
        >
          {comparisonMode ? 'Exit Compare' : 'Compare Mode'}
        </Button>
        {comparisonMode && selectedQuotes.length >= 2 && (
          <Button onClick={compareQuotes}>
            Compare Selected ({selectedQuotes.length})
          </Button>
        )}
      </PageHeader>

      {/* Wedding Selection */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-4 items-center">
          <label className="font-medium text-wedding-navy whitespace-nowrap">
            Select Wedding:
          </label>
          <select
            value={selectedWedding}
            onChange={(e) => setSelectedWedding(e.target.value)}
            className="flex-1 p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
          >
            <option value="">Choose a wedding...</option>
            {weddings.map((wedding) => (
              <option key={wedding._id || wedding.id} value={wedding._id || wedding.id}>
                {wedding.couple_names} - {formatDate(wedding.date)}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {/* Filters and Controls */}
      {selectedWedding && (
        <>
          <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
            <div className="flex flex-col sm:flex-row gap-4 items-center flex-1">
              {/* Search */}
              <input
                type="text"
                placeholder="Search vendors..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              />
              {/* Category Filter */}
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              >
                <option value="all">All Categories</option>
                {SERVICE_CATEGORIES.map(category => (
                  <option key={category} value={category}>
                    {category.charAt(0).toUpperCase() + category.slice(1).replace('_', ' & ')}
                  </option>
                ))}
              </select>
              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="accepted">Accepted</option>
                <option value="rejected">Rejected</option>
                <option value="expired">Expired</option>
              </select>
              {/* Sort */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                className="p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              >
                <option value="date">Sort by Date</option>
                <option value="amount">Sort by Amount</option>
                <option value="vendor">Sort by Vendor</option>
                <option value="rating">Sort by Rating</option>
              </select>
            </div>

            <Button
              onClick={() => setShowQuoteModal(true)}
              className="whitespace-nowrap"
            >
              Add Quote
            </Button>
          </div>

          {/* Quotes Grid */}
          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-wedding-rose"></div>
              <p className="mt-2 text-gray-600 dark:text-gray-400">Loading quotes...</p>
            </div>
          ) : error ? (
            <Card className="p-8 text-center">
              <p className="text-red-600 dark:text-red-300 mb-4">{error}</p>
              <Button onClick={fetchQuotes}>Retry</Button>
            </Card>
          ) : filteredQuotes.length === 0 ? (
            <Card className="p-8 text-center">
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                {quotes.length === 0
                  ? "No vendor quotes found. Add your first quote to get started."
                  : "No quotes match your search criteria."
                }
              </p>
              {quotes.length === 0 && (
                <Button onClick={() => setShowQuoteModal(true)}>
                  Add First Quote
                </Button>
              )}
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {filteredQuotes.map((quote) => (
                <div key={quote.id} className="relative">
                  {comparisonMode && (
                    <div className="absolute top-2 right-2 z-10">
                      <input
                        type="checkbox"
                        checked={selectedQuotes.includes(quote.id)}
                        onChange={() => toggleQuoteComparison(quote.id)}
                        className="w-5 h-5 text-wedding-rose"
                      />
                    </div>
                  )}
                  <VendorQuoteCard
                    quote={quote}
                    onAccept={handleAcceptQuote}
                    onReject={handleRejectQuote}
                    onRate={handleRateQuote}
                    showActions={!comparisonMode}
                  />
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Quote Modal */}
      {showQuoteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 max-w-2xl w-full max-h-screen overflow-y-auto">
            <h2 className="text-xl font-bold mb-4 text-wedding-navy">
              Add New Vendor Quote
            </h2>
            <form onSubmit={handleCreateQuote}>
              <div className="space-y-4">
                {/* Basic Info */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                      Vendor Name *
                    </label>
                    <input
                      type="text"
                      value={quoteForm.vendor_name}
                      onChange={(e) => setQuoteForm({...quoteForm, vendor_name: e.target.value})}
                      className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                      Service Category *
                    </label>
                    <select
                      value={quoteForm.service_category}
                      onChange={(e) => setQuoteForm({...quoteForm, service_category: e.target.value})}
                      className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      required
                    >
                      {SERVICE_CATEGORIES.map(category => (
                        <option key={category} value={category}>
                          {category.charAt(0).toUpperCase() + category.slice(1).replace('_', ' & ')}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Contact Info */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                      Email
                    </label>
                    <input
                      type="email"
                      value={quoteForm.vendor_email}
                      onChange={(e) => setQuoteForm({...quoteForm, vendor_email: e.target.value})}
                      className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                      Phone
                    </label>
                    <input
                      type="tel"
                      value={quoteForm.vendor_phone}
                      onChange={(e) => setQuoteForm({...quoteForm, vendor_phone: e.target.value})}
                      className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    />
                  </div>
                </div>

                {/* Quote Amount */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                      Quote Amount *
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={quoteForm.quote_amount}
                      onChange={(e) => setQuoteForm({...quoteForm, quote_amount: parseFloat(e.target.value) || 0})}
                      className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                      Valid Until
                    </label>
                    <input
                      type="date"
                      value={quoteForm.valid_until}
                      onChange={(e) => setQuoteForm({...quoteForm, valid_until: e.target.value})}
                      className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    />
                  </div>
                </div>

                {/* What’s Included */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
                    What’s Included
                  </label>
                  {quoteForm.includes.map((item, index) => (
                    <div key={index} className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={item}
                        onChange={(e) => updateIncludeItem(index, e.target.value)}
                        placeholder="Enter included item..."
                        className="flex-1 p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      />
                      <Button
                        type="button"
                        variant="danger"
                        onClick={() => removeIncludeItem(index)}
                        className="px-3"
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    onClick={addIncludeItem}
                    className="text-sm"
                  >
                    Add Included Item
                  </Button>
                </div>

                {/* What’s Excluded */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
                    What’s Excluded
                  </label>
                  {quoteForm.excludes.map((item, index) => (
                    <div key={index} className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={item}
                        onChange={(e) => updateExcludeItem(index, e.target.value)}
                        placeholder="Enter excluded item..."
                        className="flex-1 p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      />
                      <Button
                        type="button"
                        variant="danger"
                        onClick={() => removeExcludeItem(index)}
                        className="px-3"
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    onClick={addExcludeItem}
                    className="text-sm"
                  >
                    Add Excluded Item
                  </Button>
                </div>

                {/* Terms & Notes */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Terms & Conditions
                  </label>
                  <textarea
                    value={quoteForm.terms_conditions}
                    onChange={(e) => setQuoteForm({...quoteForm, terms_conditions: e.target.value})}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    rows={3}
                    placeholder="Any terms, conditions, or payment requirements..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Notes
                  </label>
                  <textarea
                    value={quoteForm.notes}
                    onChange={(e) => setQuoteForm({...quoteForm, notes: e.target.value})}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    rows={2}
                    placeholder="Additional notes about this quote..."
                  />
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <Button type="submit" className="flex-1">
                  Create Quote
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => {
                    setShowQuoteModal(false);
                    resetQuoteForm();
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}