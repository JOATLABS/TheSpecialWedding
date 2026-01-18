'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useTables } from '@/admin/hooks/useTables';
import { useGuests } from '@/admin/hooks/useGuests';
import { SeatingCanvas } from '@/admin/components/seating/SeatingCanvas';
import { Sidebar } from '@/admin/components/seating/Sidebar';
import { GlassButton } from '@/admin/components/ui/glass/GlassButton';
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
      const token = localStorage.getItem('admin_token');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/ai/weddings/${weddingId}/seating-optimize`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            guests: guests.map(g => ({
              id: g.id,
              name: g.name,
              group_id: g.group_id,
              role: g.role,
              current_table_id: g.table_id
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

    // Apply each table's guest assignments
    for (const tableSuggestion of aiSuggestions.tables) {
      const guestIds = tableSuggestion.guests.map(g => g.guest_id);
      if (guestIds.length > 0) {
        // Optimistic update
        setGuests(prev => prev.map(g =>
          guestIds.includes(g.id) ? { ...g, table_id: tableSuggestion.table_id } : g
        ));
        // API call
        await assignGuests(tableSuggestion.table_id, guestIds);
      }
    }

    setShowAiModal(false);
    setAiSuggestions(null);
  };

  const dismissAISuggestions = () => {
    setShowAiModal(false);
    setAiSuggestions(null);
  };

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden print:h-auto print:overflow-visible">
      <div className="print:hidden">
        <Sidebar guests={guests} />
      </div>

      <div className="flex-1 flex flex-col relative print:w-full">
        <div className="h-16 bg-white/80 backdrop-blur border-b border-gray-200 flex items-center justify-between px-6 z-20 print:hidden">
          <h1 className="font-playfair text-xl font-bold text-gray-800">Seating Plan</h1>

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
          <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between">
            <span className="text-red-700 text-sm">{aiError}</span>
            <button onClick={() => setAiError(null)} className="text-red-500 hover:text-red-700">
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
