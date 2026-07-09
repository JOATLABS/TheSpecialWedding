'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import PageHeader from '../components/PageHeader';
import StorefrontSettingsModal from './StorefrontSettingsModal';
import {
  Plus,
  Settings,
  Package,
  Search,
  Filter,
  MoreHorizontal,
  Copy,
  Trash2,
  Edit,
  Send,
  FileText,
  CheckCircle,
  Clock,
  Archive
} from 'lucide-react';

interface PackageData {
  id: string;
  _id: string;
  name: string;
  description?: string;
  total_amount: number;
  currency: string;
  status: 'draft' | 'active' | 'archived';
  is_template: boolean;
  contracts_count: number;
  services: Array<{ name: string; description?: string; included: boolean }>;
  created_at: string;
  updated_at: string;
}

const statusConfig = {
  draft: {
    label: 'Draft',
    icon: Clock,
    className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
  },
  active: {
    label: 'Active',
    icon: CheckCircle,
    className: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
  },
  archived: {
    label: 'Archived',
    icon: Archive,
    className: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
  }
};

export default function PackagesPage() {
  const { token } = useAdmin();
  const [packages, setPackages] = useState<PackageData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [isStorefrontModalOpen, setIsStorefrontModalOpen] = useState(false);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showTemplates, setShowTemplates] = useState(false);

  // Dropdown menu state
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const fetchPackages = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');

    try {
      const baseUrl = getApiBaseUrl();
      const params = new URLSearchParams();
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (showTemplates) params.append('include_templates', 'true');

      const response = await fetch(`${baseUrl}/admin/packages?${params}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('Packages API error:', response.status, errorData);
        throw new Error(errorData.detail || `Failed to fetch packages (${response.status})`);
      }

      const data = await response.json();
      setPackages(data.packages || []);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load packages';
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, showTemplates]);

  useEffect(() => {
    fetchPackages();
  }, [fetchPackages]);

  const handleDuplicate = async (packageId: string) => {
    if (!token) return;

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/packages/${packageId}/duplicate`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to duplicate package');
      }

      toast.success('Package duplicated successfully');
      fetchPackages();
    } catch (err) {
      toast.error('Failed to duplicate package');
    }
    setOpenMenuId(null);
  };

  const handleDelete = async (packageId: string) => {
    if (!token) return;

    if (!confirm('Are you sure you want to delete this package? This cannot be undone.')) {
      return;
    }

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/packages/${packageId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to delete package');
      }

      toast.success('Package deleted successfully');
      fetchPackages();
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete package';
      toast.error(errorMessage);
    }
    setOpenMenuId(null);
  };

  const handleStatusChange = async (packageId: string, newStatus: string) => {
    if (!token) return;

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/packages/${packageId}`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) {
        throw new Error('Failed to update package status');
      }

      toast.success(`Package ${newStatus === 'active' ? 'activated' : 'updated'}`);
      fetchPackages();
    } catch (err) {
      toast.error('Failed to update package status');
    }
    setOpenMenuId(null);
  };

  // Filter packages by search term
  const filteredPackages = packages.filter(pkg => {
    if (!searchTerm) return true;
    return pkg.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
           pkg.description?.toLowerCase().includes(searchTerm.toLowerCase());
  });

  const formatCurrency = (amount: number, currency: string = 'usd') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
    }).format(amount);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Marketing & Packages"
        description="Manage your service packages and public storefront profile"
      >
        <div className="flex items-center gap-3">
          <Button variant="outline" className="flex items-center gap-2" onClick={() => setIsStorefrontModalOpen(true)}>
            <Settings size={18} />
            Configure Storefront
          </Button>
          <Link href="/admin/packages/new">
            <Button className="flex items-center gap-2">
              <Plus size={18} />
              New Package
            </Button>
          </Link>
        </div>
      </PageHeader>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search packages..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
            >
              <option value="all">All Status</option>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
          </div>

          {/* Templates Toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showTemplates}
              onChange={(e) => setShowTemplates(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-slate-600 dark:text-slate-400">
              Include Templates
            </span>
          </label>
        </div>
      </Card>

      {/* Packages Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="h-6 bg-slate-200 dark:bg-slate-700 rounded w-3/4 mb-4" />
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/2 mb-2" />
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/4" />
            </Card>
          ))}
        </div>
      ) : error ? (
        <Card className="p-12 text-center">
          <p className="text-red-600 dark:text-red-400">{error}</p>
          <Button onClick={fetchPackages} className="mt-4">
            Try Again
          </Button>
        </Card>
      ) : filteredPackages.length === 0 ? (
        <Card className="p-12 text-center">
          <Package className="w-12 h-12 mx-auto text-slate-400 mb-4" />
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
            {searchTerm || statusFilter !== 'all' ? 'No packages found' : 'No packages yet'}
          </h3>
          <p className="text-slate-600 dark:text-slate-400 mb-6">
            {searchTerm || statusFilter !== 'all'
              ? 'Try adjusting your filters'
              : 'Create your first service package to get started'}
          </p>
          {!searchTerm && statusFilter === 'all' && (
            <Link href="/admin/packages/new">
              <Button className="flex items-center gap-2 mx-auto">
                <Plus size={18} />
                Create Package
              </Button>
            </Link>
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPackages.map((pkg) => {
            const StatusIcon = statusConfig[pkg.status].icon;

            return (
              <Card key={pkg.id || pkg._id} className="p-6 hover:shadow-lg transition-shadow relative">
                {/* Template Badge */}
                {pkg.is_template && (
                  <div className="absolute top-3 right-3">
                    <span className="px-2 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                      Template
                    </span>
                  </div>
                )}

                {/* Status Badge */}
                <div className="flex items-center gap-2 mb-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full ${statusConfig[pkg.status].className}`}>
                    <StatusIcon size={12} />
                    {statusConfig[pkg.status].label}
                  </span>
                </div>

                {/* Package Info */}
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2 pr-8">
                  {pkg.name}
                </h3>

                {pkg.description && (
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 line-clamp-2">
                    {pkg.description}
                  </p>
                )}

                {/* Price */}
                <div className="text-2xl font-bold text-primary-600 dark:text-primary-400 mb-4">
                  {formatCurrency(pkg.total_amount, pkg.currency)}
                </div>

                {/* Services Count */}
                <div className="flex items-center gap-4 text-sm text-slate-600 dark:text-slate-400 mb-4">
                  <span className="flex items-center gap-1">
                    <FileText size={14} />
                    {pkg.services?.length || 0} services
                  </span>
                  <span className="flex items-center gap-1">
                    <Send size={14} />
                    {pkg.contracts_count || 0} contracts
                  </span>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 pt-4 border-t border-slate-200 dark:border-slate-700">
                  <Link href={`/admin/packages/${pkg.id || pkg._id}/edit`} className="flex-1">
                    <Button variant="outline" size="sm" className="w-full flex items-center justify-center gap-1">
                      <Edit size={14} />
                      Edit
                    </Button>
                  </Link>

                  {pkg.status === 'active' && (
                    <Link href={`/admin/packages/${pkg.id || pkg._id}/send`} className="flex-1">
                      <Button size="sm" className="w-full flex items-center justify-center gap-1">
                        <Send size={14} />
                        Send
                      </Button>
                    </Link>
                  )}

                  {/* More Menu */}
                  <div className="relative">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setOpenMenuId(openMenuId === (pkg.id || pkg._id) ? null : (pkg.id || pkg._id))}
                    >
                      <MoreHorizontal size={14} />
                    </Button>

                    {openMenuId === (pkg.id || pkg._id) && (
                      <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-10">
                        <button
                          onClick={() => handleDuplicate(pkg.id || pkg._id)}
                          className="w-full px-4 py-2 text-left text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2"
                        >
                          <Copy size={14} />
                          Duplicate
                        </button>

                        {pkg.status === 'draft' && (
                          <button
                            onClick={() => handleStatusChange(pkg.id || pkg._id, 'active')}
                            className="w-full px-4 py-2 text-left text-sm text-green-600 dark:text-green-400 hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2"
                          >
                            <CheckCircle size={14} />
                            Activate
                          </button>
                        )}

                        {pkg.status === 'active' && (
                          <button
                            onClick={() => handleStatusChange(pkg.id || pkg._id, 'archived')}
                            className="w-full px-4 py-2 text-left text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2"
                          >
                            <Archive size={14} />
                            Archive
                          </button>
                        )}

                        {pkg.status === 'draft' && pkg.contracts_count === 0 && (
                          <button
                            onClick={() => handleDelete(pkg.id || pkg._id)}
                            className="w-full px-4 py-2 text-left text-sm text-red-600 dark:text-red-400 hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2"
                          >
                            <Trash2 size={14} />
                            Delete
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Click outside to close menu */}
      {openMenuId && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => setOpenMenuId(null)}
        />
      )}
      
      <StorefrontSettingsModal 
        isOpen={isStorefrontModalOpen} 
        onClose={() => setIsStorefrontModalOpen(false)} 
      />
    </div>
  );
}
