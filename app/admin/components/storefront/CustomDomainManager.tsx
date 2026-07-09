'use client';

import React, { useState, useEffect } from 'react';
import { Globe, CheckCircle2, AlertCircle, Loader2, Copy, Trash2, ShieldCheck, ArrowRight } from 'lucide-react';
import { useAdmin } from '../../../contexts/AdminContext';

interface VerificationRecord {
  type: string;
  name: string;
  value: string;
}

interface CustomDomainProps {
  initialDomain?: string;
  initialStatus?: string;
  verification?: VerificationRecord;
  onDomainUpdate: (domain: string | null) => void;
}

export function CustomDomainManager({ initialDomain, initialStatus, verification, onDomainUpdate }: CustomDomainProps) {
  const { apiRequest } = useAdmin();
  const [domain, setDomain] = useState(initialDomain || '');
  const [status, setStatus] = useState(initialStatus || 'none');
  const [records, setRecords] = useState<VerificationRecord | null>(verification || null);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState('');

  const handleAddDomain = async () => {
    if (!domain) return;
    setLoading(true);
    setError('');
    try {
      const res = await apiRequest('/api/storefront/custom-domain', 'POST', { domain });
      if (res.status === 'success') {
        setStatus(res.data.cloudflare_hostname_status || 'pending');
        setRecords(res.data.ownership_verification);
        onDomainUpdate(domain);
      } else {
        setError('Failed to add domain');
      }
    } catch (err: any) {
      setError(err.message || 'Error adding custom domain');
    } finally {
      setLoading(false);
    }
  };

  const checkStatus = async () => {
    setChecking(true);
    try {
      const res = await apiRequest('/api/storefront/custom-domain/status', 'GET');
      if (res.status === 'success' && res.data) {
        setStatus(res.data.status);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setChecking(false);
    }
  };

  const handleRemove = async () => {
    setLoading(true);
    try {
      await apiRequest('/api/storefront/custom-domain', 'DELETE');
      setDomain('');
      setStatus('none');
      setRecords(null);
      onDomainUpdate(null);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, type: string) => {
    navigator.clipboard.writeText(text);
    setCopied(type);
    setTimeout(() => setCopied(''), 2000);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
          Custom Domain Configuration
        </label>
        {status === 'active' && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400">
            <CheckCircle2 className="h-3 w-3" /> Active
          </span>
        )}
        {(status === 'pending' || status === 'pending_validation') && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-500/20 dark:text-amber-400">
            <Loader2 className="h-3 w-3 animate-spin" /> Pending DNS
          </span>
        )}
      </div>

      {(!status || status === 'none') ? (
        <div className="space-y-3">
          <div className="flex rounded-lg overflow-hidden border border-slate-200/70 dark:border-slate-700/50 focus-within:ring-2 focus-within:ring-primary-400/40">
            <span className="inline-flex items-center bg-slate-50/80 dark:bg-slate-800/60 px-2.5 text-xs text-slate-400 border-r border-slate-200/70 dark:border-slate-700/50">https://</span>
            <input 
              type="text" 
              value={domain} 
              onChange={e => setDomain(e.target.value)} 
              className="flex-1 bg-white/60 dark:bg-slate-900/40 px-2.5 py-2 text-xs text-slate-900 dark:text-white outline-none" 
              placeholder="www.yourdomain.com" 
              disabled={loading}
            />
            <button 
              onClick={handleAddDomain}
              disabled={loading || !domain}
              className="px-3 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-xs font-medium text-slate-700 dark:text-slate-200 transition-colors border-l border-slate-200/70 dark:border-slate-700/50 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Connect'}
            </button>
          </div>
          {error && <p className="text-[11px] text-red-500 flex items-center gap-1"><AlertCircle className="h-3 w-3"/> {error}</p>}
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Enter your custom domain (e.g., weddings.janedoe.com). You will need access to your DNS settings.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/30 p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-medium text-slate-900 dark:text-white">{domain}</span>
            </div>
            <button 
              onClick={handleRemove}
              disabled={loading}
              className="text-slate-400 hover:text-red-500 transition-colors"
              title="Remove Domain"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>

          {status !== 'active' && records && (
            <div className="space-y-3">
              <div className="rounded-lg bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-700/50 p-3">
                <h4 className="text-[11px] font-semibold text-amber-800 dark:text-amber-400 flex items-center gap-1.5 mb-2">
                  <ShieldCheck className="h-3.5 w-3.5" /> Required DNS Records
                </h4>
                <p className="text-[11px] text-amber-700 dark:text-amber-500 mb-3">
                  Please add these records to your domain registrar (e.g., GoDaddy, Namecheap) to verify ownership and connect your domain.
                </p>

                <div className="space-y-2">
                  {/* CNAME Record */}
                  <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-2">
                    <div className="flex text-[10px] text-slate-500 dark:text-slate-400 mb-1">
                      <span className="w-16">Type</span>
                      <span className="w-1/3">Name</span>
                      <span>Target</span>
                    </div>
                    <div className="flex items-center text-[11px] font-mono text-slate-800 dark:text-slate-200">
                      <span className="w-16 font-semibold">CNAME</span>
                      <span className="w-1/3 truncate pr-2">{domain}</span>
                      <div className="flex-1 flex items-center justify-between bg-slate-50 dark:bg-slate-800 rounded px-1.5 py-0.5 border border-slate-100 dark:border-slate-700">
                        <span className="truncate">cname.thespecialwedding.com</span>
                        <button onClick={() => copyToClipboard('cname.thespecialwedding.com', 'cname')} className="text-slate-400 hover:text-primary-500">
                          {copied === 'cname' ? <CheckCircle2 className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* TXT Verification Record */}
                  {records.name && (
                    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-2">
                      <div className="flex text-[10px] text-slate-500 dark:text-slate-400 mb-1">
                        <span className="w-16">Type</span>
                        <span className="w-1/3">Name</span>
                        <span>Value</span>
                      </div>
                      <div className="flex items-center text-[11px] font-mono text-slate-800 dark:text-slate-200">
                        <span className="w-16 font-semibold uppercase">{records.type}</span>
                        <div className="w-1/3 pr-2 flex items-center gap-1 group">
                          <span className="truncate">{records.name}</span>
                          <button onClick={() => copyToClipboard(records.name, 'txt_name')} className="text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">
                            {copied === 'txt_name' ? <CheckCircle2 className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                          </button>
                        </div>
                        <div className="flex-1 flex items-center justify-between bg-slate-50 dark:bg-slate-800 rounded px-1.5 py-0.5 border border-slate-100 dark:border-slate-700">
                          <span className="truncate">{records.value}</span>
                          <button onClick={() => copyToClipboard(records.value, 'txt_val')} className="text-slate-400 hover:text-primary-500">
                            {copied === 'txt_val' ? <CheckCircle2 className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
              <button 
                onClick={checkStatus}
                disabled={checking}
                className="w-full flex items-center justify-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-200 shadow-sm transition hover:bg-slate-50 dark:hover:bg-slate-700/60 disabled:opacity-50"
              >
                {checking ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
                Verify Connection
              </button>
            </div>
          )}
          
          {status === 'active' && (
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Your domain is successfully connected and secured with SSL. It may take a few minutes for all DNS caches to update globally.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
