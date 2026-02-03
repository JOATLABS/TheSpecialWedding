'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { DndContext, DragEndEvent, useSensor, useSensors, PointerSensor } from '@dnd-kit/core';
import { useAdmin } from '@/contexts/AdminContext';
import PageHeader from '../components/PageHeader';
import { useTables } from '@/admin/hooks/useTables';
import { useGuests } from '@/admin/hooks/useGuests';
import { SeatingCanvas } from '@/admin/components/seating/SeatingCanvas';
import { Sidebar } from '@/admin/components/seating/Sidebar';
import { GlassButton } from '@/admin/components/ui/glass/GlassButton';
import { SeatingConstraintsModal } from '@/admin/components/seating/SeatingConstraintsModal';
import { Plus, Download, Printer, Sparkles, X, Check, FileText, Users } from 'lucide-react';
import { Table, Guest } from '@/types/table';

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
}

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
  const { token } = useAdmin();

  // Wedding selection state
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [loadingWeddings, setLoadingWeddings] = useState(true);

  // Use hooks with selected wedding
  const {
    tables,
    fetchTables,
    createTable,
    updateTable,
    deleteTable,
    assignGuests,
    setTables
  } = useTables(selectedWedding);

  const { guests, setGuests, refetch: refetchGuests } = useGuests(selectedWedding);

  // AI state
  const [aiLoading, setAiLoading] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<AISuggestion | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [showAiModal, setShowAiModal] = useState(false);

  // PDF export state
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfMenuOpen, setPdfMenuOpen] = useState(false);

  // Seating constraints modal state
  const [showConstraintsModal, setShowConstraintsModal] = useState(false);

  // DnD-kit sensors for drag-and-drop
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    })
  );

  // Handle drag end for both tables and guests
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over, delta } = event;

    if (!active || !active.data.current) return;

    const type = active.data.current.type;

    if (type === 'table') {
      const table = active.data.current.table as Table;
      handleTableMove(table.id, table.x + delta.x, table.y + delta.y);
    } else if (type === 'guest' && over) {
      const guest = active.data.current.guest as Guest;

      // Check if dropped on a table drop zone
      if (over.data.current && over.data.current.type === 'table-drop') {
        const tableId = over.data.current.tableId;
        if (tableId !== guest.table_id) {
          handleGuestAssign(guest.id, tableId);
        }
      }
    }
  };

  // Fetch weddings on mount
  const fetchWeddings = useCallback(async () => {
    if (!token) return;
    setLoadingWeddings(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (response.ok) {
        const data = await response.json();
        setWeddings(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error('Failed to fetch weddings:', error);
    } finally {
      setLoadingWeddings(false);
    }
  }, [token]);

  useEffect(() => {
    fetchWeddings();
  }, [fetchWeddings]);

  // Fetch tables when wedding changes
  useEffect(() => {
    if (selectedWedding) {
      fetchTables();
    }
  }, [selectedWedding, fetchTables]);

  const handleAddTable = async () => {
    if (!selectedWedding) return;
    await createTable({
      wedding_id: selectedWedding,
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

  // PDF Export Handler
  const handleExportPDF = async (size: 'poster' | 'tabloid') => {
    if (!selectedWedding) return;

    setPdfLoading(true);
    setPdfMenuOpen(false);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await fetch(
        `${baseUrl}/admin/tables/${selectedWedding}/export/pdf?layout=visual&size=${size}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (!response.ok) {
        throw new Error('Failed to export PDF');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `seating_chart_${size}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('PDF export failed:', error);
      setAiError('Failed to export PDF. Please try again.');
    } finally {
      setPdfLoading(false);
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
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/ai/weddings/${selectedWedding}/seating-optimize`,
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
    }

    setShowAiModal(false);
    setAiSuggestions(null);
  };

  const dismissAISuggestions = () => {
    setShowAiModal(false);
    setAiSuggestions(null);
  };

  // Get selected wedding info for display
  const selectedWeddingInfo = weddings.find(w => (w.id || w._id) === selectedWedding);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Seating Plan"
        description={selectedWeddingInfo ? `${selectedWeddingInfo.couple_names} - ${selectedWeddingInfo.date}` : "Drag and drop guests to assign seating"}
      >
        {selectedWedding && (
          <div className="flex gap-2 print:hidden">
            <GlassButton
              onClick={() => setShowConstraintsModal(true)}
              variant="secondary"
              size="sm"
              icon={<Users className="w-4 h-4" />}
            >
              Constraints
            </GlassButton>
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
              Export CSV
            </GlassButton>
            <div className="relative">
              <GlassButton
                onClick={() => setPdfMenuOpen(!pdfMenuOpen)}
                variant="secondary"
                size="sm"
                icon={<FileText className="w-4 h-4" />}
                disabled={pdfLoading}
              >
                {pdfLoading ? 'Generating...' : 'Export PDF ▾'}
              </GlassButton>

              {pdfMenuOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-slate-700 rounded-lg shadow-lg border border-gray-200 dark:border-slate-600 z-20 overflow-hidden">
                  <button
                    onClick={() => handleExportPDF('poster')}
                    className="w-full px-4 py-3 text-left text-sm hover:bg-gray-100 dark:hover:bg-slate-600 transition-colors"
                  >
                    <span className="font-medium text-gray-900 dark:text-gray-100">Poster Size</span>
                    <span className="block text-xs text-gray-500 dark:text-gray-400 mt-0.5">24×18 inches (Large venue display)</span>
                  </button>
                  <button
                    onClick={() => handleExportPDF('tabloid')}
                    className="w-full px-4 py-3 text-left text-sm hover:bg-gray-100 dark:hover:bg-slate-600 border-t border-gray-100 dark:border-slate-600 transition-colors"
                  >
                    <span className="font-medium text-gray-900 dark:text-gray-100">Tabloid Size</span>
                    <span className="block text-xs text-gray-500 dark:text-gray-400 mt-0.5">11×17 inches (Standard print shop)</span>
                  </button>
                </div>
              )}
            </div>
            <GlassButton onClick={handleAddTable} size="sm" icon={<Plus className="w-4 h-4" />}>
              Add Table
            </GlassButton>
          </div>
        )}
      </PageHeader>

      {/* Wedding Selector */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 p-4">
        <div className="flex flex-col sm:flex-row gap-4 items-center">
          <label className="font-medium text-slate-700 dark:text-gray-200 whitespace-nowrap">
            Select Wedding:
          </label>
          <select
            id="wedding"
            value={selectedWedding}
            onChange={(e) => setSelectedWedding(e.target.value)}
            className="w-full sm:max-w-md px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            disabled={loadingWeddings}
          >
            <option value="">
              {loadingWeddings ? 'Loading weddings...' : 'Choose a wedding...'}
            </option>
            {weddings.map((wedding) => (
              <option key={wedding.id || wedding._id} value={wedding.id || wedding._id}>
                {wedding.couple_names} - {wedding.date}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* AI Error Banner */}
      {aiError && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center justify-between">
          <span className="text-red-700 dark:text-red-400 text-sm">{aiError}</span>
          <button onClick={() => setAiError(null)} className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Seating Canvas - only show when wedding selected */}
      {selectedWedding ? (
        <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
          <div className="flex h-[calc(100vh-280px)] overflow-hidden print:h-auto print:overflow-visible bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700">
            <div className="print:hidden">
              <Sidebar guests={guests} />
            </div>
            <div className="flex-1 relative">
              <SeatingCanvas
                tables={tables}
                guests={guests}
                onTableMove={handleTableMove}
                onTableDelete={handleTableDelete}
              />
            </div>
          </div>
        </DndContext>
      ) : (
        <div className="flex items-center justify-center h-[calc(100vh-280px)] bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-slate-700 flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">No Wedding Selected</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">Select a wedding above to manage seating arrangements</p>
          </div>
        </div>
      )}

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

      {/* Seating Constraints Modal */}
      <SeatingConstraintsModal
        isOpen={showConstraintsModal}
        onClose={() => setShowConstraintsModal(false)}
        weddingId={selectedWedding}
        guests={guests}
        token={token || ''}
        onConstraintsUpdated={() => {
          // Refetch guests to get updated constraint data
          refetchGuests();
        }}
      />
    </div>
  );
}
