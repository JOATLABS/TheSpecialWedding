'use client';

import React, { useEffect, useState, Suspense } from 'react';
import dynamic from 'next/dynamic';
import { useParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { useTables } from '@/admin/hooks/useTables';
import { useGuests } from '@/admin/hooks/useGuests';
import { SeatingCanvas } from '@/admin/components/seating/SeatingCanvas';
import { Sidebar } from '@/admin/components/seating/Sidebar';
import { GlassButton } from '@/admin/components/ui/glass/GlassButton';

/**
 * Lazy-load Three.js heavy component with SSR disabled
 *
 * This dynamic import prevents Three.js (~500KB+), React Three Fiber, and Drei
 * from being included in the main bundle. Instead, they're only downloaded when
 * the seating page is accessed. This provides significant performance improvements
 * for other pages that don't use 3D graphics.
 *
 * Key settings:
 * - ssr: false - Three.js requires browser APIs (window, WebGL) and cannot render on server
 * - loading: Custom loading component with gradient background matching page design
 *
 * See LAZY_LOADING_OPTIMIZATION.md for more details
 */
const LiquidBackground = dynamic(
  () => import('@/admin/components/seating/LiquidBackground').then(mod => ({ default: mod.LiquidBackground })),
  {
    ssr: false,
    loading: () => (
      <div className="absolute inset-0 w-full h-full pointer-events-none -z-10 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-900">
        <div className="absolute inset-0 animate-pulse" />
      </div>
    ),
  }
);
import { Plus, Download, Printer, Sparkles, X, Check } from 'lucide-react';
import { Table } from '@/types/table';

interface AISuggestion {
  tables: Array<{
    table_id: string;
    table_name: string;
    guests: Array<{ guest_id: string; guest_name: string; reason: string }>;
  }>;
  credits_used: number;
  cached: boolean;
}

export default function SeatingPage() {
  const params = useParams();
  const { token } = useAdmin();
  const weddingId = params?.id as string;

  const {
    tables,
    fetchTables,
    createTable,
    updateTable,
    deleteTable,
    assignGuests,
    setTables
  } = useTables(weddingId);

  const { guests, setGuests } = useGuests(weddingId);

  // AI state
  const [aiLoading, setAiLoading] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<AISuggestion | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [showAiModal, setShowAiModal] = useState(false);

  useEffect(() => {
    fetchTables();
  }, [fetchTables]);

  const handleAddTable = async () => {
    await createTable({
      wedding_id: weddingId,
      name: `Table ${tables.length + 1}`,
      shape: 'round',
      capacity: 8,
      x: 100 + (tables.length * 20),
      y: 100 + (tables.length * 20),
    });
  };

  const handleTableMove = (id: string, x: number, y: number) => {
    setTables(prev => prev.map(t => t.id === id ? { ...t, x, y } : t));
    updateTable(id, { x, y });
  };

  const handleGuestAssign = async (guestId: string, tableId: string) => {
    setGuests(prev => prev.map(g => g.id === guestId ? { ...g, table_id: tableId } : g));
    await assignGuests(tableId, [guestId]);
  };

  const handleTableDelete = async (id: string) => {
    if (confirm("Are you sure you want to delete this table? Guests will be unseated.")) {
      setGuests(prev => prev.map(g => g.table_id === id ? { ...g, table_id: null } : g));
      await deleteTable(id);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleExport = () => {
    const headers = ['Table', 'Guest Name', 'Group', 'Role'];
    const rows = tables.flatMap(table => {
      const tableGuests = guests.filter(g => g.table_id === table.id);
      if (tableGuests.length === 0) {
        return [[table.name, '(Empty)', '', '']];
      }
      return tableGuests.map(g => [
        table.name,
        g.name,
        g.group_id || '',
        g.role || ''
      ]);
    });

    const unseated = guests.filter(g => !g.table_id);
    unseated.forEach(g => {
      rows.push(['(Unseated)', g.name, g.group_id || '', g.role || '']);
    });

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    if (link.download !== undefined) {
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', 'seating_plan.csv');
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  // AI Seating Optimization
  const handleAISuggest = async () => {
    if (tables.length === 0) {
      setAiError("Please add at least one table before requesting AI suggestions.");
      return;
    }

    if (guests.length === 0) {
      setAiError("No guests available to seat.");
      return;
    }

    setAiLoading(true);
    setAiError(null);

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/ai/weddings/${weddingId}/seating-optimize`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          },
          credentials: 'include',
          body: JSON.stringify({
            guests: guests.map((g: any) => ({
              id: g.id,
              name: g.name,
              group_id: g.group_id,
              role: g.role,
              current_table_id: g.table_id,
              plus_one_allowed: g.plus_one_allowed,
              number_of_plus_ones_allowed: g.number_of_plus_ones_allowed,
              accessibility_needs: g.accessibility_needs,
              age_group: g.age_group,
              language_preference: g.language_preference,
              seating_preference: g.seating_preference,
              must_sit_with: g.must_sit_with || [],
              must_sit_apart: g.must_sit_apart || [],
            })),
            tables: tables.map(t => ({
              id: t.id,
              name: t.name,
              capacity: t.capacity,
              shape: t.shape
            })),
            constraints: {
              keep_groups_together: true,
              respect_roles: true
            }
          })
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get AI suggestions');
      }

      const data = await response.json();
      setAiSuggestions(data);
      setShowAiModal(true);
    } catch (e: any) {
      setAiError(e.message || 'Failed to get AI suggestions');
    } finally {
      setAiLoading(false);
    }
  };

  const applyAISuggestions = async () => {
    if (!aiSuggestions) return;

    // Optimistic update - apply all suggestions to UI immediately
    setGuests(prev => {
      const updatedGuests = [...prev];
      for (const tableSuggestion of aiSuggestions.tables) {
        const guestIds = tableSuggestion.guests.map(g => g.guest_id);
        for (let i = 0; i < updatedGuests.length; i++) {
          if (guestIds.includes(updatedGuests[i].id)) {
            updatedGuests[i] = { ...updatedGuests[i], table_id: tableSuggestion.table_id };
          }
        }
      }
      return updatedGuests;
    });

    // Batch API calls - run all assignments in parallel for better performance
    const assignmentPromises = aiSuggestions.tables
      .filter(tableSuggestion => tableSuggestion.guests.length > 0)
      .map(tableSuggestion => {
        const guestIds = tableSuggestion.guests.map(g => g.guest_id);
        return assignGuests(tableSuggestion.table_id, guestIds);
      });

    try {
      await Promise.all(assignmentPromises);
    } catch (error) {
      console.error('Error applying AI suggestions:', error);
      // Optionally refresh to get correct state on error
    }

    setShowAiModal(false);
    setAiSuggestions(null);
  };

  const dismissAISuggestions = () => {
    setShowAiModal(false);
    setAiSuggestions(null);
  };

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden print:h-auto print:overflow-visible relative">
      {/* Animated liquid background */}
      <div className="print:hidden">
        <LiquidBackground />
      </div>

      <div className="print:hidden relative z-10">
        <Sidebar guests={guests} />
      </div>

      <div className="flex-1 flex flex-col relative print:w-full z-10">
        <div className="h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur border-b border-gray-200 dark:border-slate-700 flex items-center justify-between px-6 z-20 print:hidden">
          <h1 className="text-xl sm:text-2xl font-semibold leading-tight text-slate-900 dark:text-white">Seating Plan</h1>

          <div className="flex gap-2">
            <GlassButton
              onClick={handleAISuggest}
              variant="secondary"
              size="sm"
              icon={<Sparkles className="w-4 h-4" />}
              disabled={aiLoading}
            >
              {aiLoading ? 'Thinking...' : 'AI Suggest'}
            </GlassButton>
            <GlassButton onClick={handlePrint} variant="secondary" size="sm" icon={<Printer className="w-4 h-4" />}>
              Print
            </GlassButton>
            <GlassButton onClick={handleExport} variant="secondary" size="sm" icon={<Download className="w-4 h-4" />}>
              Export
            </GlassButton>
            <GlassButton onClick={handleAddTable} size="sm" icon={<Plus className="w-4 h-4" />}>
              Add Table
            </GlassButton>
          </div>
        </div>

        {/* AI Error Banner */}
        {aiError && (
          <div className="mx-6 mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center justify-between">
            <span className="text-red-700 dark:text-red-400 text-sm">{aiError}</span>
            <button onClick={() => setAiError(null)} className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="flex-1 relative">
          <SeatingCanvas
            tables={tables}
            guests={guests}
            onTableMove={handleTableMove}
            onGuestAssign={handleGuestAssign}
            onTableDelete={handleTableDelete}
          />
        </div>
      </div>

      {/* AI Suggestions Modal */}
      {showAiModal && aiSuggestions && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-white" />
                <h2 className="text-lg font-semibold text-white">AI Seating Suggestions</h2>
              </div>
              <button onClick={dismissAISuggestions} className="text-white/80 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                {aiSuggestions.cached ? '(Cached result)' : `Used ${aiSuggestions.credits_used} AI credits`}
              </p>

              <div className="space-y-4">
                {aiSuggestions.tables.map((tableSuggestion) => (
                  <div key={tableSuggestion.table_id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                    <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                      {tableSuggestion.table_name}
                    </h3>
                    <ul className="space-y-1">
                      {tableSuggestion.guests.map((guest) => (
                        <li key={guest.guest_id} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                          <span className="font-medium text-gray-800 dark:text-gray-200">{guest.guest_name}</span>
                          {guest.reason && (
                            <span className="text-gray-500 dark:text-gray-500">— {guest.reason}</span>
                          )}
                        </li>
                      ))}
                      {tableSuggestion.guests.length === 0 && (
                        <li className="text-sm text-gray-400 italic">No guests assigned</li>
                      )}
                    </ul>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-gray-200 dark:border-gray-700 px-6 py-4 flex justify-end gap-3">
              <button
                onClick={dismissAISuggestions}
                className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={applyAISuggestions}
                className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:opacity-90 flex items-center gap-2"
              >
                <Check className="w-4 h-4" />
                Apply Suggestions
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
