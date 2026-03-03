'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  DndContext,
  DragEndEvent,
  DragStartEvent,
  DragOverlay,
  useSensor,
  useSensors,
  PointerSensor,
  KeyboardSensor,
} from '@dnd-kit/core';
import { useAdmin } from '@/contexts/AdminContext';
import PageHeader from '../components/PageHeader';
import { useTables } from '@/admin/hooks/useTables';
import { useGuests } from '@/admin/hooks/useGuests';
import { SeatingCanvas } from '@/admin/components/seating/SeatingCanvas';
import { Sidebar } from '@/admin/components/seating/Sidebar';
import { GuestItem } from '@/admin/components/seating/GuestItem';
import { GlassButton } from '@/admin/components/ui/glass/GlassButton';
import { SeatingConstraintsModal } from '@/admin/components/seating/SeatingConstraintsModal';
import { PrintableSeatingChart } from '@/admin/components/seating/PrintableSeatingChart';
import {
  Plus,
  Download,
  Printer,
  Sparkles,
  X,
  Check,
  FileText,
  Users,
  Eye,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from 'lucide-react';
import { Table, Guest } from '@/types/table';

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
}

interface AISuggestionGuest {
  // Backend may return `id`, `guest_id`, or `_id`
  id?: string;
  guest_id?: string;
  _id?: string;
  name?: string;
  guest_name?: string;
  reason?: string;
}

interface AISuggestionTable {
  // Backend may return `id`, `table_id`, or `_id`
  id?: string;
  table_id?: string;
  _id?: string;
  table_name?: string;
  name?: string;
  guests: AISuggestionGuest[];
}

interface AISuggestion {
  tables: AISuggestionTable[];
  credits_used: number;
  cached: boolean;
}

// Helpers to extract IDs from various response shapes
function extractTableId(t: AISuggestionTable): string {
  return t.table_id || t.id || t._id || '';
}

function extractGuestId(g: AISuggestionGuest): string {
  return g.guest_id || g.id || g._id || '';
}

function extractGuestName(g: AISuggestionGuest): string {
  return g.guest_name || g.name || 'Unknown';
}

function extractTableName(t: AISuggestionTable): string {
  return t.table_name || t.name || 'Table';
}

type ActiveDragData =
  | { type: 'guest'; guest: Guest }
  | { type: 'table'; table: Table }
  | null;

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
    setTables,
  } = useTables(selectedWedding);

  const { guests, setGuests, refetch: refetchGuests } = useGuests(selectedWedding);

  // Active drag state for DragOverlay
  const [activeDrag, setActiveDrag] = useState<ActiveDragData>(null);

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

  // Print preview state
  const [showPrintPreview, setShowPrintPreview] = useState(false);

  // Canvas zoom state
  const [canvasZoom, setCanvasZoom] = useState(1);

  // DnD-kit sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor)
  );

  // Track drag start for DragOverlay
  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    if (!active?.data.current) return;

    const type = active.data.current.type;
    if (type === 'guest') {
      setActiveDrag({ type: 'guest', guest: active.data.current.guest as Guest });
    } else if (type === 'table') {
      setActiveDrag({ type: 'table', table: active.data.current.table as Table });
    }
  };

  // Handle drag end for both tables and guests
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over, delta } = event;
    setActiveDrag(null);

    if (!active || !active.data.current) return;

    const type = active.data.current.type;

    if (type === 'table') {
      const table = active.data.current.table as Table;
      const newX = Math.max(0, table.x + delta.x / canvasZoom);
      const newY = Math.max(0, table.y + delta.y / canvasZoom);
      handleTableMove(table.id, newX, newY);
    } else if (type === 'guest' && over) {
      const guest = active.data.current.guest as Guest;

      if (over.data.current && over.data.current.type === 'table-drop') {
        const tableId = over.data.current.tableId;
        if (tableId !== guest.table_id) {
          handleGuestAssign(guest.id, tableId);
        }
      }
    }
  };

  const handleDragCancel = () => {
    setActiveDrag(null);
  };

  // Fetch weddings on mount
  const fetchWeddings = useCallback(async () => {
    if (!token) return;
    setLoadingWeddings(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
        headers: {
          Authorization: `Bearer ${token}`,
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
      x: 100 + (tables.length % 4) * 300,
      y: 80 + Math.floor(tables.length / 4) * 280,
    });
  };

  const handleTableMove = (id: string, x: number, y: number) => {
    setTables((prev) => prev.map((t) => (t.id === id ? { ...t, x, y } : t)));
    updateTable(id, { x: Math.round(x), y: Math.round(y) });
  };

  const handleGuestAssign = async (guestId: string, tableId: string) => {
    setGuests((prev) =>
      prev.map((g) => (g.id === guestId ? { ...g, table_id: tableId } : g))
    );
    await assignGuests(tableId, [guestId]);
  };

  const handleTableDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this table? Guests will be unseated.')) {
      setGuests((prev) =>
        prev.map((g) => (g.table_id === id ? { ...g, table_id: null } : g))
      );
      await deleteTable(id);
    }
  };

  const handlePrint = () => {
    setShowPrintPreview(true);
  };

  const handleExport = () => {
    const headers = ['Table', 'Guest Name', 'Group', 'Role'];
    const rows = tables.flatMap((table) => {
      const tableGuests = guests.filter((g) => g.table_id === table.id);
      if (tableGuests.length === 0) {
        return [[table.name, '(Empty)', '', '']];
      }
      return tableGuests.map((g) => [
        table.name,
        g.name,
        g.group_id || '',
        g.role || '',
      ]);
    });

    const unseated = guests.filter((g) => !g.table_id);
    unseated.forEach((g) => {
      rows.push(['(Unseated)', g.name, g.group_id || '', g.role || '']);
    });

    const csvContent = [
      headers.join(','),
      ...rows.map((row) => row.map((cell) => `"${cell}"`).join(',')),
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
            Authorization: `Bearer ${token}`,
          },
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
      setAiError('Please add at least one table before requesting AI suggestions.');
      return;
    }

    if (guests.length === 0) {
      setAiError('No guests available to seat.');
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
            Authorization: `Bearer ${token}`,
          },
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
            tables: tables.map((t) => ({
              id: t.id,
              name: t.name,
              capacity: t.capacity,
              shape: t.shape,
            })),
            constraints: {
              keep_groups_together: true,
              respect_roles: true,
            },
          }),
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

    // Build a map of tableId → [guestIds] using defensive ID extraction
    const assignments: Array<{ tableId: string; guestIds: string[] }> = [];

    for (const tableSuggestion of aiSuggestions.tables) {
      const tableId = extractTableId(tableSuggestion);
      const guestIds = tableSuggestion.guests
        .map((g) => extractGuestId(g))
        .filter(Boolean);

      if (tableId && guestIds.length > 0) {
        assignments.push({ tableId, guestIds });
      }
    }

    if (assignments.length === 0) {
      setAiError('No valid assignments found in AI suggestions. The response may have an unexpected format.');
      setShowAiModal(false);
      setAiSuggestions(null);
      return;
    }

    // Optimistic UI update
    setGuests((prev) => {
      const updatedGuests = [...prev];
      for (const { tableId, guestIds } of assignments) {
        for (let i = 0; i < updatedGuests.length; i++) {
          if (guestIds.includes(updatedGuests[i].id)) {
            updatedGuests[i] = {
              ...updatedGuests[i],
              table_id: tableId,
            };
          }
        }
      }
      return updatedGuests;
    });

    // Persist to backend
    const assignmentPromises = assignments.map(({ tableId, guestIds }) =>
      assignGuests(tableId, guestIds)
    );

    try {
      await Promise.all(assignmentPromises);
    } catch (error) {
      console.error('Error applying AI suggestions:', error);
      setAiError('Some seat assignments failed to save. Try refreshing the page.');
    }

    setShowAiModal(false);
    setAiSuggestions(null);
  };

  const dismissAISuggestions = () => {
    setShowAiModal(false);
    setAiSuggestions(null);
  };

  // Get selected wedding info for display
  const selectedWeddingInfo = weddings.find(
    (w) => (w.id || w._id) === selectedWedding
  );

  // Stats
  const seatedCount = guests.filter((g) => g.table_id).length;
  const unseatedCount = guests.filter((g) => !g.table_id).length;
  const totalCapacity = tables.reduce((sum, t) => sum + t.capacity, 0);

  return (
    <div className="space-y-6 print:space-y-0">
      {/* Screen UI - hidden on print */}
      <div className="print:hidden">
        <PageHeader
          title="Seating Arrangement"
          description={
            selectedWeddingInfo
              ? `${selectedWeddingInfo.couple_names} \u2022 ${selectedWeddingInfo.date}`
              : 'Design your perfect seating layout'
          }
        >
          {selectedWedding && (
            <div className="flex flex-wrap gap-2">
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
              <GlassButton
                onClick={handlePrint}
                variant="secondary"
                size="sm"
                icon={<Eye className="w-4 h-4" />}
              >
                Print Preview
              </GlassButton>
              <GlassButton
                onClick={handleExport}
                variant="secondary"
                size="sm"
                icon={<Download className="w-4 h-4" />}
              >
                CSV
              </GlassButton>
              <div className="relative">
                <GlassButton
                  onClick={() => setPdfMenuOpen(!pdfMenuOpen)}
                  variant="secondary"
                  size="sm"
                  icon={<FileText className="w-4 h-4" />}
                  disabled={pdfLoading}
                >
                  {pdfLoading ? 'Generating...' : 'PDF'}
                </GlassButton>

                {pdfMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-white/90 dark:bg-slate-800/90 backdrop-blur-xl rounded-xl shadow-xl border border-white/30 dark:border-slate-700/30 z-20 overflow-hidden">
                    <button
                      onClick={() => handleExportPDF('poster')}
                      className="w-full px-4 py-3 text-left text-sm hover:bg-white/60 dark:hover:bg-slate-700/60 transition-colors"
                    >
                      <span className="font-medium text-slate-900 dark:text-gray-100">
                        Poster Size
                      </span>
                      <span className="block text-xs text-slate-500 dark:text-gray-400 mt-0.5">
                        24x18 in — Large venue display
                      </span>
                    </button>
                    <button
                      onClick={() => handleExportPDF('tabloid')}
                      className="w-full px-4 py-3 text-left text-sm hover:bg-white/60 dark:hover:bg-slate-700/60 border-t border-white/20 dark:border-slate-700/30 transition-colors"
                    >
                      <span className="font-medium text-slate-900 dark:text-gray-100">
                        Tabloid Size
                      </span>
                      <span className="block text-xs text-slate-500 dark:text-gray-400 mt-0.5">
                        11x17 in — Standard print shop
                      </span>
                    </button>
                  </div>
                )}
              </div>
              <GlassButton
                onClick={handleAddTable}
                size="sm"
                icon={<Plus className="w-4 h-4" />}
              >
                Add Table
              </GlassButton>
            </div>
          )}
        </PageHeader>

        {/* Wedding Selector */}
        <div className="bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-2xl shadow-sm border border-white/50 dark:border-slate-700/50 p-4">
          <div className="flex flex-col sm:flex-row gap-4 items-center">
            <label className="font-medium text-slate-700 dark:text-gray-200 whitespace-nowrap">
              Select Wedding:
            </label>
            <select
              id="wedding"
              value={selectedWedding}
              onChange={(e) => setSelectedWedding(e.target.value)}
              className="w-full sm:max-w-md px-4 py-3 border border-white/30 dark:border-slate-600/30 rounded-xl bg-white/50 dark:bg-slate-700/50 text-slate-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-400/50 focus:border-transparent backdrop-blur-md transition-all"
              disabled={loadingWeddings}
            >
              <option value="">
                {loadingWeddings ? 'Loading weddings...' : 'Choose a wedding...'}
              </option>
              {weddings.map((wedding) => (
                <option key={wedding.id || wedding._id} value={wedding.id || wedding._id}>
                  {wedding.couple_names} — {wedding.date}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Stats Bar */}
        {selectedWedding && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border border-white/50 dark:border-slate-700/50 p-3 text-center">
              <p className="text-2xl font-semibold text-slate-900 dark:text-white">{tables.length}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Tables</p>
            </div>
            <div className="bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border border-white/50 dark:border-slate-700/50 p-3 text-center">
              <p className="text-2xl font-semibold text-emerald-600 dark:text-emerald-400">{seatedCount}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Seated</p>
            </div>
            <div className="bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border border-white/50 dark:border-slate-700/50 p-3 text-center">
              <p className="text-2xl font-semibold text-amber-600 dark:text-amber-400">{unseatedCount}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Unseated</p>
            </div>
            <div className="bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border border-white/50 dark:border-slate-700/50 p-3 text-center">
              <p className="text-2xl font-semibold text-slate-900 dark:text-white">{totalCapacity}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Total Capacity</p>
            </div>
          </div>
        )}

        {/* AI Error Banner */}
        {aiError && (
          <div className="p-3 bg-red-50/80 dark:bg-red-900/20 backdrop-blur-md border border-red-200/50 dark:border-red-800/50 rounded-xl flex items-center justify-between">
            <span className="text-red-700 dark:text-red-400 text-sm">{aiError}</span>
            <button
              onClick={() => setAiError(null)}
              className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Seating Canvas Area */}
      {selectedWedding ? (
        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <div className="print:hidden flex h-[calc(100vh-340px)] overflow-hidden bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-2xl shadow-sm border border-white/50 dark:border-slate-700/50">
            {/* Guest Sidebar */}
            <Sidebar guests={guests} />

            {/* Canvas Area */}
            <div className="flex-1 relative">
              {/* Canvas Zoom Controls */}
              <div className="absolute top-3 right-3 z-20 flex items-center gap-1 bg-white/80 dark:bg-slate-800/80 backdrop-blur-md rounded-lg border border-white/30 dark:border-slate-700/30 p-1">
                <button
                  onClick={() => setCanvasZoom((z) => Math.max(0.25, z - 0.15))}
                  className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors"
                  title="Zoom out"
                >
                  <ZoomOut className="w-4 h-4" />
                </button>
                <span className="text-xs font-medium text-slate-600 dark:text-slate-300 min-w-[40px] text-center">
                  {Math.round(canvasZoom * 100)}%
                </span>
                <button
                  onClick={() => setCanvasZoom((z) => Math.min(2, z + 0.15))}
                  className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors"
                  title="Zoom in"
                >
                  <ZoomIn className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setCanvasZoom(1)}
                  className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors"
                  title="Reset zoom"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
              </div>

              <SeatingCanvas
                tables={tables}
                guests={guests}
                onTableMove={handleTableMove}
                onTableDelete={handleTableDelete}
                zoom={canvasZoom}
              />
            </div>
          </div>

          {/* Drag Overlay — renders above everything, not clipped by containers */}
          <DragOverlay dropAnimation={null}>
            {activeDrag?.type === 'guest' ? (
              <div className="p-3 rounded-xl text-sm bg-blue-50/90 dark:bg-blue-900/60 border border-blue-300 dark:border-blue-600 backdrop-blur-xl shadow-2xl ring-2 ring-blue-400/40 max-w-[200px] pointer-events-none">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-blue-400" />
                  <span className="font-medium text-slate-800 dark:text-gray-100">
                    {activeDrag.guest.name}
                  </span>
                </div>
                {activeDrag.guest.group_id && (
                  <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 ml-4">
                    {activeDrag.guest.group_id}
                  </div>
                )}
              </div>
            ) : activeDrag?.type === 'table' ? (
              <div className="bg-white/80 dark:bg-slate-800/80 backdrop-blur-xl border border-primary-300/50 dark:border-primary-600/50 rounded-2xl shadow-2xl px-4 py-2 pointer-events-none ring-2 ring-primary-400/30">
                <span className="font-semibold text-slate-800 dark:text-gray-100 text-sm">
                  {activeDrag.table.name}
                </span>
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      ) : (
        <div className="print:hidden flex items-center justify-center h-[calc(100vh-280px)] bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-2xl shadow-sm border border-white/50 dark:border-slate-700/50">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-white/50 dark:bg-slate-700/50 border border-white/30 dark:border-slate-600/30 flex items-center justify-center">
              <svg
                className="w-8 h-8 text-slate-400 dark:text-slate-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-slate-900 dark:text-gray-100 mb-1">
              No Wedding Selected
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Select a wedding above to design your seating arrangement
            </p>
          </div>
        </div>
      )}

      {/* AI Suggestions Modal */}
      {showAiModal && aiSuggestions && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden border border-white/30 dark:border-slate-700/30">
            <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-white" />
                <h2 className="text-lg font-semibold text-white">AI Seating Suggestions</h2>
              </div>
              <button
                onClick={dismissAISuggestions}
                className="text-white/80 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                {aiSuggestions.cached
                  ? '(Cached result)'
                  : `Used ${aiSuggestions.credits_used} AI credits`}
              </p>

              <div className="space-y-4">
                {aiSuggestions.tables.map((tableSuggestion, idx) => (
                  <div
                    key={extractTableId(tableSuggestion) || idx}
                    className="border border-white/30 dark:border-slate-700/30 rounded-xl p-4 bg-white/50 dark:bg-slate-800/50"
                  >
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
                      {extractTableName(tableSuggestion)}
                    </h3>
                    <ul className="space-y-1">
                      {tableSuggestion.guests.map((guest, gIdx) => (
                        <li
                          key={extractGuestId(guest) || gIdx}
                          className="text-sm text-slate-600 dark:text-slate-400 flex items-start gap-2"
                        >
                          <span className="font-medium text-slate-800 dark:text-gray-200">
                            {extractGuestName(guest)}
                          </span>
                          {guest.reason && (
                            <span className="text-slate-500 dark:text-slate-500">
                              — {guest.reason}
                            </span>
                          )}
                        </li>
                      ))}
                      {tableSuggestion.guests.length === 0 && (
                        <li className="text-sm text-slate-400 italic">No guests assigned</li>
                      )}
                    </ul>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-white/20 dark:border-slate-700/30 px-6 py-4 flex justify-end gap-3">
              <button
                onClick={dismissAISuggestions}
                className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={applyAISuggestions}
                className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:opacity-90 flex items-center gap-2 transition-opacity"
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
          refetchGuests();
        }}
      />

      {/* Print Preview Modal */}
      {showPrintPreview && selectedWeddingInfo && (
        <PrintableSeatingChart
          tables={tables}
          guests={guests}
          coupleName={selectedWeddingInfo.couple_names}
          weddingDate={selectedWeddingInfo.date}
          onClose={() => setShowPrintPreview(false)}
        />
      )}
    </div>
  );
}
