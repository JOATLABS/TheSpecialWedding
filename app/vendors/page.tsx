'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Search, MapPin, Filter, ChevronLeft, ChevronRight } from 'lucide-react';
import SaasNav from '../components/saas/SaasNav';
import { getApiBaseUrl } from '@/utils/env';

/* ═══════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════ */

interface PublicVendor {
  _id: string;
  business_name: string;
  service_category: string;
  custom_service_category?: string;
  service_description?: string;
  city?: string;
  state?: string;
  country?: string;
  logo_url?: string;
  typical_price_min?: number;
  typical_price_max?: number;
  currency: string;
  weddings_count: number;
  is_preferred: boolean;
}

interface DirectoryResponse {
  vendors: PublicVendor[];
  total: number;
  categories: string[];
  page: number;
  page_size: number;
}

/* ═══════════════════════════════════════════════════════════
   Category helpers
   ═══════════════════════════════════════════════════════════ */

const CATEGORY_ICONS: Record<string, string> = {
  photography: '📸',
  videography: '🎥',
  florist: '💐',
  catering: '🍽️',
  venue: '🏛️',
  music: '🎵',
  dj: '🎧',
  cake: '🎂',
  hair_makeup: '💄',
  officiant: '💍',
  transportation: '🚗',
  stationery: '✉️',
  planner: '📋',
  decor: '✨',
  lighting: '💡',
  rentals: '🪑',
};

function formatCategory(cat: string): string {
  return cat.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

function getVendorCategoryLabel(vendor: Pick<PublicVendor, 'service_category' | 'custom_service_category'>): string {
  if (vendor.service_category === 'other' && vendor.custom_service_category?.trim()) {
    return vendor.custom_service_category.trim();
  }
  if (vendor.service_category === 'mc') {
    return 'MC / Host';
  }
  return formatCategory(vendor.service_category);
}

function getCategoryIcon(cat: string): string {
  return CATEGORY_ICONS[cat.toLowerCase()] || '🤝';
}

/* ═══════════════════════════════════════════════════════════
   Vendor Card
   ═══════════════════════════════════════════════════════════ */

function VendorCard({ vendor }: { vendor: PublicVendor }) {
  const location = [vendor.city, vendor.state].filter(Boolean).join(', ');
  const priceRange =
    vendor.typical_price_min && vendor.typical_price_max
      ? `$${vendor.typical_price_min.toLocaleString()} – $${vendor.typical_price_max.toLocaleString()}`
      : null;

  return (
    <Link
      href={`/vendors/${vendor._id}`}
      className="group block rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm p-5 hover:border-wedding-rose/40 hover:bg-slate-800/80 transition-all duration-300"
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        {vendor.logo_url ? (
          <img
            src={vendor.logo_url}
            alt={vendor.business_name}
            className="w-12 h-12 rounded-xl object-cover border border-slate-700"
          />
        ) : (
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-wedding-rose/20 to-wedding-gold/20 flex items-center justify-center text-xl border border-slate-700">
            {getCategoryIcon(vendor.service_category)}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white group-hover:text-wedding-rose transition-colors truncate">
            {vendor.business_name}
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            {getCategoryIcon(vendor.service_category)}{' '}
            {getVendorCategoryLabel(vendor)}
          </p>
        </div>
        {vendor.is_preferred && (
          <span className="shrink-0 text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full bg-wedding-gold/20 text-wedding-gold border border-wedding-gold/30">
            Preferred
          </span>
        )}
      </div>

      {/* Description */}
      {vendor.service_description && (
        <p className="text-sm text-slate-400 line-clamp-2 mb-3">
          {vendor.service_description}
        </p>
      )}

      {/* Footer meta */}
      <div className="flex items-center gap-3 text-xs text-slate-500">
        {location && (
          <span className="flex items-center gap-1">
            <MapPin size={12} /> {location}
          </span>
        )}
        {priceRange && (
          <span className="ml-auto text-slate-400 font-medium">{priceRange}</span>
        )}
        {vendor.weddings_count > 0 && (
          <span className="text-slate-500">
            {vendor.weddings_count} wedding{vendor.weddings_count !== 1 ? 's' : ''}
          </span>
        )}
      </div>
    </Link>
  );
}

/* ═══════════════════════════════════════════════════════════
   Loading Skeleton
   ═══════════════════════════════════════════════════════════ */

function VendorSkeleton() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 animate-pulse">
      <div className="flex items-start gap-3 mb-3">
        <div className="w-12 h-12 rounded-xl bg-slate-800" />
        <div className="flex-1">
          <div className="h-4 bg-slate-800 rounded w-2/3 mb-2" />
          <div className="h-3 bg-slate-800 rounded w-1/3" />
        </div>
      </div>
      <div className="h-3 bg-slate-800 rounded w-full mb-2" />
      <div className="h-3 bg-slate-800 rounded w-4/5" />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Page
   ═══════════════════════════════════════════════════════════ */

const PAGE_SIZE = 24;

export default function VendorsPage() {
  const [vendors, setVendors] = useState<PublicVendor[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  // Filters
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [location, setLocation] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  const fetchVendors = useCallback(async () => {
    try {
      setLoading(true);
      const baseUrl = getApiBaseUrl();
      const params = new URLSearchParams();
      if (category) params.set('category', category);
      if (location) params.set('location', location);
      if (debouncedSearch) params.set('search', debouncedSearch);
      params.set('limit', String(PAGE_SIZE));
      params.set('skip', String((page - 1) * PAGE_SIZE));

      const res = await fetch(`${baseUrl}/api/v1/vendors/directory?${params}`);
      if (!res.ok) throw new Error('Failed to fetch');
      const data: DirectoryResponse = await res.json();

      setVendors(data.vendors);
      setTotal(data.total);
      if (data.categories.length > 0) setCategories(data.categories);
    } catch (err) {
      console.error('Error fetching vendor directory:', err);
    } finally {
      setLoading(false);
    }
  }, [category, location, debouncedSearch, page]);

  useEffect(() => {
    fetchVendors();
  }, [fetchVendors]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [category, location, debouncedSearch]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />

      {/* ── Hero ── */}
      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-50"
          style={{
            background:
              'radial-gradient(800px 500px at 20% -10%, rgba(212,165,165,0.3), transparent 70%), radial-gradient(1000px 600px at 85% -10%, rgba(232,196,106,0.2), transparent 65%)',
          }}
        />
        <div className="relative mx-auto max-w-5xl px-6 pt-32 pb-12 text-center sm:px-10">
          <p className="text-[11px] uppercase tracking-[0.5em] text-wedding-rose/80 mb-4">
            Vendor Directory
          </p>
          <h1 className="text-3xl font-semibold text-white sm:text-4xl md:text-5xl leading-tight">
            Find the perfect vendors<br />for every wedding.
          </h1>
          <p className="mt-5 text-base text-slate-300 max-w-2xl mx-auto">
            Browse our curated directory of wedding professionals — photographers, florists, caterers, venues, and more. Filter by category or location to find your match.
          </p>
        </div>
      </section>

      {/* ── Filters ── */}
      <section className="mx-auto max-w-6xl px-6 sm:px-10 pb-8">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search vendors..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-wedding-rose/50 transition"
            />
          </div>

          {/* Category filter */}
          <div className="relative">
            <Filter size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="pl-9 pr-8 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white appearance-none cursor-pointer focus:outline-none focus:border-wedding-rose/50 transition min-w-[180px]"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {getCategoryIcon(cat)} {formatCategory(cat)}
                </option>
              ))}
            </select>
          </div>

          {/* Location filter */}
          <div className="relative">
            <MapPin size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="City or state..."
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="pl-9 pr-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-wedding-rose/50 transition w-full sm:w-44"
            />
          </div>
        </div>

        {/* Results count */}
        <p className="mt-4 text-sm text-slate-500">
          {loading ? 'Searching...' : `${total} vendor${total !== 1 ? 's' : ''} found`}
          {category && ` in ${formatCategory(category)}`}
          {location && ` near "${location}"`}
        </p>
      </section>

      {/* ── Grid ── */}
      <section className="mx-auto max-w-6xl px-6 sm:px-10 pb-16">
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <VendorSkeleton key={i} />
            ))}
          </div>
        ) : vendors.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-5xl mb-4">🔍</p>
            <h2 className="text-xl font-semibold text-white mb-2">No vendors found</h2>
            <p className="text-slate-400">
              Try adjusting your search or filters to find what you&apos;re looking for.
            </p>
            {(search || category || location) && (
              <button
                onClick={() => { setSearch(''); setCategory(''); setLocation(''); }}
                className="mt-4 px-4 py-2 rounded-lg bg-slate-800 text-sm text-white hover:bg-slate-700 transition"
              >
                Clear all filters
              </button>
            )}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {vendors.map((vendor) => (
              <VendorCard key={vendor._id} vendor={vendor} />
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-10">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              <ChevronLeft size={18} />
            </button>
            <span className="text-sm text-slate-400 px-3">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        )}
      </section>

      {/* ── CTA ── */}
      <section className="border-t border-slate-800 py-16 text-center">
        <h2 className="text-2xl font-semibold text-white mb-3">Are you a wedding vendor?</h2>
        <p className="text-slate-400 mb-6 max-w-lg mx-auto">
          Join our directory and advertise your services to wedding planners
          across the platform. Sign up in minutes.
        </p>
        <Link
          href="/portal/ads/signup"
          className="inline-block rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-wedding-rose/30 transition hover:bg-wedding-blush"
        >
          List Your Business
        </Link>
      </section>
    </main>
  );
}
