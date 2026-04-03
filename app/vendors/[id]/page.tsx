'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import {
  MapPin,
  Phone,
  Mail,
  Globe,
  ArrowLeft,
  Star,
  DollarSign,
  Clock,
  Tag,
} from 'lucide-react';
import Link from 'next/link';

interface PublicVendorProfile {
  _id: string;
  business_name: string;
  contact_name?: string;
  email: string;
  phone?: string;
  website?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  service_category: string;
  custom_service_category?: string;
  service_subcategories?: string[];
  service_description?: string;
  portfolio_urls?: string[];
  logo_url?: string;
  typical_price_min?: number;
  typical_price_max?: number;
  currency?: string;
  lead_time_days?: number;
  service_radius_miles?: number;
  is_preferred: boolean;
  weddings_count: number;
}

function formatCategory(cat: string): string {
  return cat.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

function getVendorCategoryLabel(vendor: Pick<PublicVendorProfile, 'service_category' | 'custom_service_category'>): string {
  if (vendor.service_category === 'other' && vendor.custom_service_category?.trim()) {
    return vendor.custom_service_category.trim();
  }
  if (vendor.service_category === 'mc') {
    return 'MC / Host';
  }
  return formatCategory(vendor.service_category);
}

const LoadingSkeleton = () => (
  <div className="min-h-screen bg-white">
    {/* Header skeleton */}
    <div className="bg-gradient-to-r from-primary-50 to-blue-50 border-b border-gray-200">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="h-10 bg-gray-200 rounded-md w-32 animate-pulse mb-4"></div>
      </div>
    </div>

    {/* Hero skeleton */}
    <div className="bg-gradient-to-b from-primary-50 to-white">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid md:grid-cols-3 gap-8">
          <div className="md:col-span-2">
            <div className="h-12 bg-gray-200 rounded-md w-2/3 animate-pulse mb-4"></div>
            <div className="h-6 bg-gray-200 rounded-md w-1/2 animate-pulse mb-8"></div>
            <div className="space-y-3">
              <div className="h-4 bg-gray-200 rounded-md w-full animate-pulse"></div>
              <div className="h-4 bg-gray-200 rounded-md w-5/6 animate-pulse"></div>
              <div className="h-4 bg-gray-200 rounded-md w-4/5 animate-pulse"></div>
            </div>
          </div>
          <div className="md:col-span-1">
            <div className="h-48 bg-gray-200 rounded-lg animate-pulse"></div>
          </div>
        </div>
      </div>
    </div>

    {/* Content skeleton */}
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-8">
      <div className="h-48 bg-gray-200 rounded-lg animate-pulse"></div>
      <div className="h-48 bg-gray-200 rounded-lg animate-pulse"></div>
    </div>
  </div>
);

const NotFound = () => (
  <div className="min-h-screen bg-white">
    <div className="bg-gradient-to-r from-primary-50 to-blue-50 border-b border-gray-200">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <Link
          href="/vendors"
          className="inline-flex items-center gap-2 text-primary-600 hover:text-primary-700 transition-colors"
        >
          <ArrowLeft size={18} />
          Back to Directory
        </Link>
      </div>
    </div>

    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
      <div className="mb-6">
        <Star size={48} className="mx-auto text-gray-300" />
      </div>
      <h1 className="text-3xl font-bold text-gray-900 mb-4">Vendor Not Found</h1>
      <p className="text-gray-600 mb-8">
        Sorry, we couldn't find the vendor you're looking for. It may have been removed or the URL is incorrect.
      </p>
      <Link
        href="/vendors"
        className="inline-block px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors"
      >
        Browse All Vendors
      </Link>
    </div>
  </div>
);

export default function VendorProfilePage() {
  const params = useParams();
  const router = useRouter();
  const vendorId = params.id as string;

  const [vendor, setVendor] = useState<PublicVendorProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVendor = async () => {
      try {
        setLoading(true);
        setError(null);

        const baseUrl = getApiBaseUrl();
        const response = await fetch(
          `${baseUrl}/api/v1/vendors/${vendorId}/public`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            },
          }
        );

        if (!response.ok) {
          if (response.status === 404) {
            setError('not-found');
          } else {
            setError('failed-to-load');
          }
          setLoading(false);
          return;
        }

        const data = await response.json();
        setVendor({
          ...data,
          service_subcategories: Array.isArray(data.service_subcategories) ? data.service_subcategories : [],
          portfolio_urls: Array.isArray(data.portfolio_urls) ? data.portfolio_urls : [],
          currency: data.currency || 'USD',
        });
      } catch (err) {
        console.error('Error fetching vendor:', err);
        setError('failed-to-load');
      } finally {
        setLoading(false);
      }
    };

    if (vendorId) {
      fetchVendor();
    }
  }, [vendorId]);

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (error === 'not-found' || !vendor) {
    return <NotFound />;
  }

  const fullAddress = [vendor.address, vendor.city, vendor.state, vendor.country]
    .filter(Boolean)
    .join(', ');
  const serviceSubcategories = Array.isArray(vendor.service_subcategories) ? vendor.service_subcategories : [];
  const portfolioUrls = Array.isArray(vendor.portfolio_urls) ? vendor.portfolio_urls : [];
  const categoryLabel = getVendorCategoryLabel(vendor);

  const priceRange =
    vendor.typical_price_min && vendor.typical_price_max
      ? `${vendor.currency || 'USD'} ${vendor.typical_price_min.toLocaleString()} - ${vendor.typical_price_max.toLocaleString()}`
      : null;

  return (
    <div className="min-h-screen bg-white">
      {/* Header Navigation */}
      <div className="bg-gradient-to-r from-primary-50 to-blue-50 border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <Link
            href="/vendors"
            className="inline-flex items-center gap-2 text-primary-600 hover:text-primary-700 transition-colors font-medium"
          >
            <ArrowLeft size={18} />
            Back to Directory
          </Link>
        </div>
      </div>

      {/* Hero Section */}
      <div className="bg-gradient-to-b from-primary-50 via-blue-50 to-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid md:grid-cols-3 gap-8 items-start">
            {/* Main Info */}
            <div className="md:col-span-2">
              <div className="mb-6">
                <h1 className="text-4xl font-bold text-gray-900 mb-2">
                  {vendor.business_name}
                </h1>
                <div className="flex flex-wrap items-center gap-4">
                  <span className="inline-block px-3 py-1 bg-primary-100 text-primary-700 rounded-full text-sm font-medium">
                    {categoryLabel}
                  </span>
                  {vendor.is_preferred && (
                    <span className="inline-flex items-center gap-1 px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-sm font-medium">
                      <Star size={14} fill="currentColor" />
                      Preferred Vendor
                    </span>
                  )}
                </div>
              </div>

              {vendor.service_description && (
                <p className="text-gray-700 text-lg leading-relaxed mb-6">
                  {vendor.service_description}
                </p>
              )}

              {/* Stats */}
              <div className="flex flex-wrap gap-6">
                {priceRange && (
                  <div className="flex items-center gap-2 text-gray-700">
                    <DollarSign size={20} className="text-primary-600" />
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide">
                        Typical Price
                      </p>
                      <p className="font-semibold">{priceRange}</p>
                    </div>
                  </div>
                )}

                {vendor.lead_time_days && (
                  <div className="flex items-center gap-2 text-gray-700">
                    <Clock size={20} className="text-primary-600" />
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide">
                        Lead Time
                      </p>
                      <p className="font-semibold">
                        {vendor.lead_time_days} days
                      </p>
                    </div>
                  </div>
                )}

                {vendor.weddings_count > 0 && (
                  <div className="flex items-center gap-2 text-gray-700">
                    <Star size={20} className="text-primary-600" />
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide">
                        Weddings
                      </p>
                      <p className="font-semibold">{vendor.weddings_count}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Logo */}
            {vendor.logo_url && (
              <div className="md:col-span-1">
                <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                  <img
                    src={vendor.logo_url}
                    alt={vendor.business_name}
                    className="w-full h-auto object-contain"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid md:grid-cols-3 gap-8">
          {/* Left Column - Details */}
          <div className="md:col-span-2 space-y-8">
            {/* Service Subcategories */}
            {serviceSubcategories.length > 0 && (
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  Specialties
                </h2>
                <div className="flex flex-wrap gap-2">
                  {serviceSubcategories.map((subcategory, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center gap-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-full text-sm font-medium hover:bg-gray-200 transition-colors"
                    >
                      <Tag size={14} />
                      {subcategory}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {/* Portfolio */}
            {portfolioUrls.length > 0 && (
              <section>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  Portfolio
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  {portfolioUrls.map((url, index) => (
                    <a
                      key={index}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group relative overflow-hidden rounded-lg shadow-sm hover:shadow-md transition-shadow bg-gray-100 aspect-square flex items-center justify-center"
                    >
                      <div className="absolute inset-0 bg-gradient-to-br from-primary-500 to-blue-600 opacity-0 group-hover:opacity-10 transition-opacity"></div>
                      <img
                        src={url}
                        alt={`Portfolio ${index + 1}`}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                      />
                      <div className="absolute inset-0 bg-black opacity-0 group-hover:opacity-10 transition-opacity flex items-center justify-center">
                        <Globe size={24} className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    </a>
                  ))}
                </div>
              </section>
            )}
          </div>

          {/* Right Column - Contact Info */}
          <div className="md:col-span-1">
            <div className="bg-gradient-to-br from-primary-50 to-blue-50 p-6 rounded-lg border border-primary-200 sticky top-4">
              <h2 className="text-xl font-bold text-gray-900 mb-6">
                Get in Touch
              </h2>

              <div className="space-y-4 mb-6">
                {/* Email */}
                <a
                  href={`mailto:${vendor.email}`}
                  className="flex items-start gap-3 text-gray-700 hover:text-primary-600 transition-colors group"
                >
                  <Mail
                    size={20}
                    className="text-primary-600 flex-shrink-0 mt-1"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">
                      Email
                    </p>
                    <p className="font-medium text-sm break-all group-hover:underline">
                      {vendor.email}
                    </p>
                  </div>
                </a>

                {/* Phone */}
                {vendor.phone && (
                  <a
                    href={`tel:${vendor.phone}`}
                    className="flex items-start gap-3 text-gray-700 hover:text-primary-600 transition-colors group"
                  >
                    <Phone
                      size={20}
                      className="text-primary-600 flex-shrink-0 mt-1"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">
                        Phone
                      </p>
                      <p className="font-medium text-sm group-hover:underline">
                        {vendor.phone}
                      </p>
                    </div>
                  </a>
                )}

                {/* Website */}
                {vendor.website && (
                  <a
                    href={vendor.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-3 text-gray-700 hover:text-primary-600 transition-colors group"
                  >
                    <Globe
                      size={20}
                      className="text-primary-600 flex-shrink-0 mt-1"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">
                        Website
                      </p>
                      <p className="font-medium text-sm break-all group-hover:underline">
                        {vendor.website}
                      </p>
                    </div>
                  </a>
                )}

                {/* Location */}
                {fullAddress && (
                  <div className="flex items-start gap-3 text-gray-700">
                    <MapPin
                      size={20}
                      className="text-primary-600 flex-shrink-0 mt-1"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">
                        Location
                      </p>
                      <p className="font-medium text-sm">{fullAddress}</p>
                    </div>
                  </div>
                )}

                {/* Service Radius */}
                {vendor.service_radius_miles && (
                  <div className="flex items-start gap-3 text-gray-700">
                    <MapPin
                      size={20}
                      className="text-primary-600 flex-shrink-0 mt-1"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">
                        Service Area
                      </p>
                      <p className="font-medium text-sm">
                        {vendor.service_radius_miles} miles
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* CTA Button */}
              <a
                href={`mailto:${vendor.email}`}
                className="block w-full py-3 px-4 bg-primary-600 hover:bg-primary-700 text-white font-semibold rounded-lg transition-colors text-center"
              >
                Contact Vendor
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="bg-gray-50 border-t border-gray-200 mt-12">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <p className="text-center text-gray-600 text-sm">
            © 2024 The Special Wedding. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
}
