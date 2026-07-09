'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
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
import { getApiBaseUrl } from '@/utils/env';
import PageHeader from '../components/PageHeader';
import WeddingPicker from '../components/WeddingPicker';
import { useTables } from '@/admin/hooks/useTables';
import { useGuests } from '@/admin/hooks/useGuests';
import { useVenueLayout } from '@/admin/hooks/useVenueLayout';
import { SeatingCanvas } from '@/admin/components/seating/SeatingCanvas';
import { Sidebar } from '@/admin/components/seating/Sidebar';
import { GuestItem } from '@/admin/components/seating/GuestItem';
import {
  DEFAULT_FLOOR_PLAN_RECTANGLE,
  FloorPlanMode,
  pointsToSvgPoints,
} from '@/admin/components/seating/FloorPlanLayer';
import { GlassButton } from '@/admin/components/ui/glass/GlassButton';
import { SeatingConstraintsModal } from '@/admin/components/seating/SeatingConstraintsModal';
import { PrintableSeatingChart } from '@/admin/components/seating/PrintableSeatingChart';
import { getSeatingAiErrorMessage } from '@/admin/seating/aiErrorMessage';
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
  Map,
  MousePointer2,
  PenLine,
  Save,
  Undo2,
  Eraser,
  Upload,
  Lock,
  Unlock,
  PlusCircle,
  Ruler,
  AlertTriangle,
  Trash2,
  HelpCircle,
  ChevronRight,
} from 'lucide-react';
import { Table, Guest, VenueFixture, VenueFixtureType, VenueLayoutPoint } from '@/types/table';
import { validateSeatingLayout } from '@/admin/utils/seatingLayoutValidation';
import { seatingCollisionDetection } from '@/admin/utils/seatingCollisionDetection';
import {
  buildSeatingPlannerGuideSteps,
  getActiveSeatingGuideStep,
  type SeatingGuideAction,
} from '@/admin/utils/seatingPlannerGuide';

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
  | { type: 'fixture'; fixture: VenueFixture }
  | null;

const MAX_FLOOR_PLAN_IMAGE_BYTES = 1_500_000;
const MIN_FIXTURE_SIZE = 24;
const MAX_FIXTURE_SIZE = 2000;

const FIXTURE_TEMPLATES: Record<
  VenueFixtureType,
  { label: string; width: number; height: number }
> = {
  dance_floor: { label: 'Dance Floor', width: 260, height: 180 },
  bar: { label: 'Bar', width: 180, height: 90 },
  stage: { label: 'Stage', width: 260, height: 120 },
  entrance: { label: 'Entrance', width: 180, height: 80 },
  restrooms: { label: 'Restrooms', width: 180, height: 90 },
  kitchen: { label: 'Kitchen', width: 200, height: 100 },
  vendor_path: { label: 'Vendor Path', width: 320, height: 70 },
};

const FIXTURE_TYPES = Object.keys(FIXTURE_TEMPLATES) as VenueFixtureType[];

function createVenueFixture(type: VenueFixtureType, existing: VenueFixture[]): VenueFixture {
  const template = FIXTURE_TEMPLATES[type];
  const count = existing.filter((fixture) => fixture.type === type).length + 1;
  const suffix = count > 1 ? ` ${count}` : '';
  return {
    id: `${type}-${Date.now().toString(36)}-${count}`,
    type,
    label: `${template.label}${suffix}`,
    x: 180 + (existing.length % 4) * 170,
    y: 160 + Math.floor(existing.length / 4) * 120,
    width: template.width,
    height: template.height,
    rotation: 0,
  };
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function parseFixtureNumber(value: string, fallback: number, min: number, max: number): number {
  if (value.trim() === '') return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return clampNumber(parsed, min, max);
}

export default function SeatingPage() {
  const { token } = useAdmin();
  const apiBaseUrl = getApiBaseUrl();
  const searchParams = useSearchParams();

  // Wedding selection state
  // Pre-select from `?weddingId=` query (set when arriving from the
  // wedding configuration page's "Seating Plan" button). Lazy init so
  // useTables/useGuests start fetching on first render rather than after
  // the picker mounts.
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>(
    () => searchParams?.get('weddingId') ?? ''
  );
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
  const {
    layout: venueLayout,
    loading: venueLayoutLoading,
    saving: venueLayoutSaving,
    error: venueLayoutError,
    saveLayout: saveVenueLayout,
  } = useVenueLayout(selectedWedding);

  // Active drag state for DragOverlay
  const [activeDrag, setActiveDrag] = useState<ActiveDragData>(null);
  const [floorPlanMode, setFloorPlanMode] = useState<FloorPlanMode>('select');
  const [floorPlanOutline, setFloorPlanOutline] = useState<VenueLayoutPoint[]>([]);
  const [floorPlanBackgroundImageDataUrl, setFloorPlanBackgroundImageDataUrl] = useState<string | null>(null);
  const [floorPlanBackgroundImageName, setFloorPlanBackgroundImageName] = useState<string | null>(null);
  const [floorPlanBackgroundLocked, setFloorPlanBackgroundLocked] = useState(true);
  const [floorPlanScalePixels, setFloorPlanScalePixels] = useState<number | null>(null);
  const [floorPlanScaleDistance, setFloorPlanScaleDistance] = useState<number | null>(null);
  const [floorPlanScaleUnit, setFloorPlanScaleUnit] = useState<'ft' | 'm'>('ft');
  const [venueFixtures, setVenueFixtures] = useState<VenueFixture[]>([]);
  const [selectedFixtureId, setSelectedFixtureId] = useState<string | null>(null);
  const [fixtureMenuOpen, setFixtureMenuOpen] = useState(false);
  const [scaleMenuOpen, setScaleMenuOpen] = useState(false);
  const [seatingGuideOpen, setSeatingGuideOpen] = useState(false);
  const [seatingGuideDismissed, setSeatingGuideDismissed] = useState(false);
  const [floorPlanSaveState, setFloorPlanSaveState] = useState<'idle' | 'saved' | 'error'>('idle');
  const floorPlanImageInputRef = useRef<HTMLInputElement | null>(null);

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
    } else if (type === 'fixture') {
      setActiveDrag({ type: 'fixture', fixture: active.data.current.fixture as VenueFixture });
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
    } else if (type === 'fixture') {
      const fixture = active.data.current.fixture as VenueFixture;
      const newX = Math.min(
        Math.max(0, fixture.x + delta.x / canvasZoom),
        Math.max(0, venueLayout.canvas_width - fixture.width)
      );
      const newY = Math.min(
        Math.max(0, fixture.y + delta.y / canvasZoom),
        Math.max(0, venueLayout.canvas_height - fixture.height)
      );
      handleFixtureMove(fixture.id, newX, newY);
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
      const baseUrl = apiBaseUrl;
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
  }, [apiBaseUrl, token]);

  useEffect(() => {
    fetchWeddings();
  }, [fetchWeddings]);

  // Fetch tables when wedding changes
  useEffect(() => {
    if (selectedWedding) {
      fetchTables();
    }
  }, [selectedWedding, fetchTables]);

  useEffect(() => {
    setFloorPlanMode('select');
    setFloorPlanOutline(venueLayout.outline || []);
    setFloorPlanBackgroundImageDataUrl(venueLayout.background_image_data_url ?? null);
    setFloorPlanBackgroundImageName(venueLayout.background_image_name ?? null);
    setFloorPlanBackgroundLocked(venueLayout.background_locked ?? true);
    setFloorPlanScalePixels(venueLayout.scale_pixels ?? null);
    setFloorPlanScaleDistance(venueLayout.scale_distance ?? null);
    setFloorPlanScaleUnit(venueLayout.scale_unit ?? 'ft');
    setVenueFixtures(venueLayout.fixtures ?? []);
    setSelectedFixtureId((currentId) =>
      currentId && venueLayout.fixtures?.some((fixture) => fixture.id === currentId)
        ? currentId
        : null
    );
  }, [venueLayout.id, venueLayout.updated_at, venueLayout]);

  useEffect(() => {
    setFloorPlanSaveState('idle');
    setSeatingGuideDismissed(false);
  }, [selectedWedding]);

  useEffect(() => {
    if (!selectedWedding || seatingGuideDismissed || venueLayoutLoading) return;

    const hasVenueLayoutStarted =
      floorPlanOutline.length >= 3 ||
      Boolean(floorPlanBackgroundImageDataUrl) ||
      Boolean(floorPlanScalePixels && floorPlanScaleDistance) ||
      venueFixtures.length > 0;

    if (!hasVenueLayoutStarted) {
      setSeatingGuideOpen(true);
    }
  }, [
    selectedWedding,
    seatingGuideDismissed,
    venueLayoutLoading,
    floorPlanOutline.length,
    floorPlanBackgroundImageDataUrl,
    floorPlanScalePixels,
    floorPlanScaleDistance,
    venueFixtures.length,
  ]);

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

  const handleFixtureMove = (id: string, x: number, y: number) => {
    setFloorPlanSaveState('idle');
    setSelectedFixtureId(id);
    setVenueFixtures((prev) =>
      prev.map((fixture) =>
        fixture.id === id ? { ...fixture, x: Math.round(x), y: Math.round(y) } : fixture
      )
    );
  };

  const handleFixtureUpdate = (id: string, patch: Partial<VenueFixture>) => {
    setFloorPlanSaveState('idle');
    setSelectedFixtureId(id);
    setVenueFixtures((prev) =>
      prev.map((fixture) => (fixture.id === id ? { ...fixture, ...patch } : fixture))
    );
  };

  const handleFixtureDelete = (id: string) => {
    setFloorPlanSaveState('idle');
    setSelectedFixtureId((currentId) => (currentId === id ? null : currentId));
    setVenueFixtures((prev) => prev.filter((fixture) => fixture.id !== id));
  };

  const handleFloorPlanPointAdd = (point: VenueLayoutPoint) => {
    setFloorPlanSaveState('idle');
    setFloorPlanOutline((prev) => [...prev, point]);
  };

  const handleFloorPlanPointMove = (index: number, point: VenueLayoutPoint) => {
    setFloorPlanSaveState('idle');
    setFloorPlanOutline((prev) =>
      prev.map((currentPoint, currentIndex) =>
        currentIndex === index ? point : currentPoint
      )
    );
  };

  const handleFloorPlanUndo = () => {
    setFloorPlanSaveState('idle');
    setFloorPlanOutline((prev) => prev.slice(0, -1));
  };

  const handleFloorPlanClear = () => {
    setFloorPlanSaveState('idle');
    setFloorPlanOutline([]);
  };

  const handleFloorPlanRectangle = () => {
    setFloorPlanSaveState('idle');
    setFloorPlanMode('draw');
    setFloorPlanOutline(DEFAULT_FLOOR_PLAN_RECTANGLE);
  };

  const handleFloorPlanImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';

    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setFloorPlanSaveState('error');
      setAiError('Upload an image floor plan. PDF rendering will be added in a later pass.');
      return;
    }
    if (file.size > MAX_FLOOR_PLAN_IMAGE_BYTES) {
      setFloorPlanSaveState('error');
      setAiError('Floor plan images must be under 1.5 MB for this version.');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== 'string') return;
      setFloorPlanBackgroundImageDataUrl(reader.result);
      setFloorPlanBackgroundImageName(file.name);
      setFloorPlanBackgroundLocked(true);
      setFloorPlanSaveState('idle');
    };
    reader.onerror = () => {
      setFloorPlanSaveState('error');
      setAiError('Unable to read that floor plan image. Try another file.');
    };
    reader.readAsDataURL(file);
  };

  const handleFloorPlanImageClear = () => {
    setFloorPlanBackgroundImageDataUrl(null);
    setFloorPlanBackgroundImageName(null);
    setFloorPlanBackgroundLocked(true);
    setFloorPlanSaveState('idle');
  };

  const handleFixtureAdd = (type: VenueFixtureType) => {
    const nextFixture = createVenueFixture(type, venueFixtures);
    setFloorPlanMode('select');
    setVenueFixtures((prev) => [...prev, nextFixture]);
    setSelectedFixtureId(nextFixture.id);
    setFixtureMenuOpen(false);
    setFloorPlanSaveState('idle');
  };

  const handleScaleChange = (
    field: 'pixels' | 'distance',
    value: string
  ) => {
    const parsed = Number(value);
    const safeValue = Number.isFinite(parsed) && parsed > 0 ? parsed : null;
    if (field === 'pixels') {
      setFloorPlanScalePixels(safeValue);
    } else {
      setFloorPlanScaleDistance(safeValue);
    }
    setFloorPlanSaveState('idle');
  };

  const handleFloorPlanSave = async () => {
    if (floorPlanOutline.length > 0 && floorPlanOutline.length < 3) {
      setFloorPlanSaveState('error');
      return;
    }

    try {
      await saveVenueLayout({
        canvas_width: venueLayout.canvas_width,
        canvas_height: venueLayout.canvas_height,
        outline: floorPlanOutline.map((point) => ({
          x: Math.round(point.x),
          y: Math.round(point.y),
        })),
        background_image_data_url: floorPlanBackgroundImageDataUrl,
        background_image_name: floorPlanBackgroundImageName,
        background_locked: floorPlanBackgroundLocked,
        scale_pixels: floorPlanScalePixels,
        scale_distance: floorPlanScaleDistance,
        scale_unit: floorPlanScaleUnit,
        fixtures: venueFixtures.map((fixture) => ({
          ...fixture,
          label: fixture.label.trim() || FIXTURE_TEMPLATES[fixture.type].label,
          x: Math.round(fixture.x),
          y: Math.round(fixture.y),
          width: Math.round(clampNumber(fixture.width, MIN_FIXTURE_SIZE, MAX_FIXTURE_SIZE)),
          height: Math.round(clampNumber(fixture.height, MIN_FIXTURE_SIZE, MAX_FIXTURE_SIZE)),
          rotation: Math.round(fixture.rotation ?? 0),
        })),
      });
      setFloorPlanSaveState('saved');
      setFloorPlanMode('select');
    } catch (err) {
      console.error('Failed to save floor plan:', err);
      setFloorPlanSaveState('error');
    }
  };

  const handleSeatingGuideToggle = () => {
    if (seatingGuideOpen) {
      setSeatingGuideDismissed(true);
    }
    setSeatingGuideOpen((open) => !open);
  };

  const handleSeatingGuideAction = (action: SeatingGuideAction) => {
    setSeatingGuideOpen(true);
    switch (action) {
      case 'add-room':
        handleFloorPlanRectangle();
        break;
      case 'add-reference':
        setFixtureMenuOpen(false);
        setScaleMenuOpen(true);
        break;
      case 'add-fixture':
        setScaleMenuOpen(false);
        setFixtureMenuOpen(true);
        break;
      case 'add-table':
        void handleAddTable();
        break;
      case 'save-layout':
        void handleFloorPlanSave();
        break;
      default:
        break;
    }
  };

  const handleGuestAssign = async (guestId: string, tableId: string) => {
    // Save previous table_id for rollback
    const previousTableId = guests.find((g) => g.id === guestId)?.table_id ?? null;

    // Optimistic UI update
    setGuests((prev) =>
      prev.map((g) => (g.id === guestId ? { ...g, table_id: tableId } : g))
    );

    try {
      await assignGuests(tableId, [guestId]);
    } catch (err) {
      // Rollback optimistic update on failure
      console.error('Failed to assign guest:', err);
      setGuests((prev) =>
        prev.map((g) => (g.id === guestId ? { ...g, table_id: previousTableId } : g))
      );
    }
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
      const baseUrl = apiBaseUrl;
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
        `${apiBaseUrl}/admin/ai/weddings/${selectedWedding}/seating-optimize`,
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
        const error = await response.json().catch(() => null);
        throw new Error(getSeatingAiErrorMessage(error));
      }

      const data = await response.json();
      setAiSuggestions(data);
      setShowAiModal(true);
    } catch (e: any) {
      setAiError(getSeatingAiErrorMessage(e));
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
  const selectedFixture = venueFixtures.find((fixture) => fixture.id === selectedFixtureId) ?? null;
  const layoutIssues = useMemo(
    () => validateSeatingLayout({
      tables,
      fixtures: venueFixtures,
      outline: floorPlanOutline,
      canvasWidth: venueLayout.canvas_width,
      canvasHeight: venueLayout.canvas_height,
    }),
    [
      tables,
      venueFixtures,
      floorPlanOutline,
      venueLayout.canvas_width,
      venueLayout.canvas_height,
    ]
  );
  const tableWarningIds = useMemo(
    () => new Set(
      layoutIssues
        .filter((issue) => issue.targetType === 'table' && issue.targetId)
        .map((issue) => issue.targetId as string)
    ),
    [layoutIssues]
  );
  const fixtureWarningIds = useMemo(
    () => new Set(
      layoutIssues
        .filter((issue) => issue.targetType === 'fixture' && issue.targetId)
        .map((issue) => issue.targetId as string)
    ),
    [layoutIssues]
  );
  const savedFloorPlanSignature = JSON.stringify({
    outline: pointsToSvgPoints(venueLayout.outline || []),
    background: venueLayout.background_image_data_url ?? null,
    backgroundName: venueLayout.background_image_name ?? null,
    backgroundLocked: venueLayout.background_locked ?? true,
    scalePixels: venueLayout.scale_pixels ?? null,
    scaleDistance: venueLayout.scale_distance ?? null,
    scaleUnit: venueLayout.scale_unit ?? 'ft',
    fixtures: venueLayout.fixtures ?? [],
  });
  const draftFloorPlanSignature = JSON.stringify({
    outline: pointsToSvgPoints(floorPlanOutline),
    background: floorPlanBackgroundImageDataUrl,
    backgroundName: floorPlanBackgroundImageName,
    backgroundLocked: floorPlanBackgroundLocked,
    scalePixels: floorPlanScalePixels,
    scaleDistance: floorPlanScaleDistance,
    scaleUnit: floorPlanScaleUnit,
    fixtures: venueFixtures,
  });
  const floorPlanDirty = savedFloorPlanSignature !== draftFloorPlanSignature;
  const floorPlanCanSave = floorPlanOutline.length === 0 || floorPlanOutline.length >= 3;
  const floorPlanScaleLabel =
    floorPlanScalePixels && floorPlanScaleDistance
      ? `${floorPlanScalePixels}px = ${floorPlanScaleDistance}${floorPlanScaleUnit}`
      : null;
  const seatingGuideSteps = useMemo(
    () =>
      buildSeatingPlannerGuideSteps({
        hasRoomOutline: floorPlanOutline.length >= 3,
        hasVenueReference: Boolean(floorPlanBackgroundImageDataUrl) || Boolean(floorPlanScaleLabel),
        fixtureCount: venueFixtures.length,
        tableCount: tables.length,
        seatedGuestCount: seatedCount,
        unseatedGuestCount: unseatedCount,
        layoutIssueCount: layoutIssues.length,
        floorPlanDirty,
      }),
    [
      floorPlanOutline.length,
      floorPlanBackgroundImageDataUrl,
      floorPlanScaleLabel,
      venueFixtures.length,
      tables.length,
      seatedCount,
      unseatedCount,
      layoutIssues.length,
      floorPlanDirty,
    ]
  );
  const activeSeatingGuideStep = getActiveSeatingGuideStep(seatingGuideSteps);
  const seatingGuideCompleteCount = seatingGuideSteps.filter((step) => step.done).length;
  const floorPlanStatus = venueLayoutLoading
    ? 'Loading floor plan'
    : venueLayoutSaving
    ? 'Saving floor plan'
    : floorPlanSaveState === 'saved'
    ? 'Floor plan saved'
    : floorPlanSaveState === 'error' || venueLayoutError
    ? 'Floor plan needs attention'
    : floorPlanDirty
    ? 'Unsaved floor plan'
    : layoutIssues.length > 0
    ? `${layoutIssues.length} layout checks need review`
    : floorPlanScaleLabel
    ? `Floor plan ready · ${floorPlanScaleLabel}`
    : floorPlanOutline.length >= 3
    ? 'Floor plan ready'
    : 'No floor plan yet';
  const draftVenueLayout = {
    ...venueLayout,
    background_image_data_url: floorPlanBackgroundImageDataUrl,
    background_image_name: floorPlanBackgroundImageName,
    background_locked: floorPlanBackgroundLocked,
    scale_pixels: floorPlanScalePixels,
    scale_distance: floorPlanScaleDistance,
    scale_unit: floorPlanScaleUnit,
    fixtures: venueFixtures,
  };

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

        {/* Wedding picker — shared compact pill (see WeddingPicker.tsx) */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500 dark:text-gray-400">Wedding:</span>
          <WeddingPicker
            options={weddings.map((w) => ({
              id: (w.id || w._id) as string,
              label: `${w.couple_names} — ${w.date}`,
            }))}
            value={selectedWedding}
            onChange={setSelectedWedding}
            disabled={loadingWeddings}
            placeholder={loadingWeddings ? 'Loading weddings…' : 'Choose a wedding…'}
          />
        </div>

        {/* Stats Bar — text-xl matches the platform-wide stat density */}
        {selectedWedding && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border border-white/50 dark:border-slate-700/50 px-3 py-2 text-center">
              <p className="text-xl font-semibold text-slate-900 dark:text-white">{tables.length}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Tables</p>
            </div>
            <div className="bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border border-white/50 dark:border-slate-700/50 px-3 py-2 text-center">
              <p className="text-xl font-semibold text-emerald-600 dark:text-emerald-400">{seatedCount}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Seated</p>
            </div>
            <div className="bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border border-white/50 dark:border-slate-700/50 px-3 py-2 text-center">
              <p className="text-xl font-semibold text-amber-600 dark:text-amber-400">{unseatedCount}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Unseated</p>
            </div>
            <div className="bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border border-white/50 dark:border-slate-700/50 px-3 py-2 text-center">
              <p className="text-xl font-semibold text-slate-900 dark:text-white">{totalCapacity}</p>
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
          collisionDetection={seatingCollisionDetection}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <div className="print:hidden flex flex-col overflow-hidden bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-2xl shadow-sm border border-white/50 dark:border-slate-700/50 h-[calc(100vh-210px)] lg:flex-row">
            {/* Guest Sidebar */}
            <Sidebar guests={guests} />

            {/* Canvas Area */}
            <div className="flex flex-1 flex-col overflow-hidden">
              {/* Floor Plan Controls */}
              <div className="relative z-30 m-3 shrink-0 rounded-lg border border-white/30 dark:border-slate-700/30 bg-white/85 dark:bg-slate-800/85 backdrop-blur-md shadow-sm">
                <input
                  ref={floorPlanImageInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleFloorPlanImageUpload}
                  aria-label="Upload venue floor plan image"
                />
                <div className="flex flex-wrap items-center gap-1 p-1">
                  <div className="flex items-center gap-1 border-r border-slate-200/70 dark:border-slate-700/70 pr-1 mr-1">
                    <button
                      onClick={() => setFloorPlanMode('select')}
                      className={`inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium transition-colors ${
                        floorPlanMode === 'select'
                          ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                          : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700'
                      }`}
                      title="Select and move tables"
                      aria-label="Select and move tables"
                      aria-pressed={floorPlanMode === 'select'}
                    >
                      <MousePointer2 className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">Select</span>
                    </button>
                    <button
                      onClick={() => setFloorPlanMode('draw')}
                      className={`inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium transition-colors ${
                        floorPlanMode === 'draw'
                          ? 'bg-blue-600 text-white'
                          : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700'
                      }`}
                      title="Draw or adjust venue outline"
                      aria-label="Draw venue outline"
                      aria-pressed={floorPlanMode === 'draw'}
                    >
                      <PenLine className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">Draw</span>
                    </button>
                  </div>

                  <button
                    onClick={handleFloorPlanRectangle}
                    className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                    title="Start from a rectangular room"
                    aria-label="Start from a rectangular room"
                  >
                    <Map className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Room</span>
                  </button>
                  <button
                    onClick={() => floorPlanImageInputRef.current?.click()}
                    className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                    title="Upload venue floor plan image"
                    aria-label="Upload venue floor plan image"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Upload</span>
                  </button>
                  <button
                    onClick={() => {
                      setFloorPlanBackgroundLocked((locked) => !locked);
                      setFloorPlanSaveState('idle');
                    }}
                    disabled={!floorPlanBackgroundImageDataUrl}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-600 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40 dark:text-slate-300 dark:hover:bg-slate-700"
                    title={floorPlanBackgroundLocked ? 'Unlock backdrop' : 'Lock backdrop'}
                    aria-label={floorPlanBackgroundLocked ? 'Unlock backdrop' : 'Lock backdrop'}
                    aria-pressed={floorPlanBackgroundLocked}
                  >
                    {floorPlanBackgroundLocked ? (
                      <Lock className="h-3.5 w-3.5" />
                    ) : (
                      <Unlock className="h-3.5 w-3.5" />
                    )}
                  </button>
                  <button
                    onClick={() => setFixtureMenuOpen((open) => !open)}
                    className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                    title="Add venue fixture"
                    aria-label="Add venue fixture"
                    aria-expanded={fixtureMenuOpen}
                  >
                    <PlusCircle className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Fixture</span>
                  </button>
                  <button
                    onClick={() => setScaleMenuOpen((open) => !open)}
                    className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                    title="Set floor plan scale"
                    aria-label="Set floor plan scale"
                    aria-expanded={scaleMenuOpen}
                  >
                    <Ruler className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Scale</span>
                  </button>
                  <button
                    onClick={handleSeatingGuideToggle}
                    className={`inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium transition-colors ${
                      seatingGuideOpen
                        ? 'bg-emerald-600 text-white'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700'
                    }`}
                    title="Open seating setup guide"
                    aria-label="Open seating setup guide"
                    aria-expanded={seatingGuideOpen}
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Guide</span>
                    <span
                      className={`rounded px-1 text-[10px] font-semibold ${
                        seatingGuideOpen
                          ? 'bg-white/20 text-white'
                          : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300'
                      }`}
                    >
                      {seatingGuideCompleteCount}/{seatingGuideSteps.length}
                    </span>
                  </button>
                  <button
                    onClick={handleFloorPlanUndo}
                    disabled={floorPlanOutline.length === 0}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-600 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40 dark:text-slate-300 dark:hover:bg-slate-700"
                    title="Undo last floor plan point"
                    aria-label="Undo last floor plan point"
                  >
                    <Undo2 className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={handleFloorPlanClear}
                    disabled={floorPlanOutline.length === 0}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-600 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40 dark:text-slate-300 dark:hover:bg-slate-700"
                    title="Clear floor plan"
                    aria-label="Clear floor plan"
                  >
                    <Eraser className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={handleFloorPlanImageClear}
                    disabled={!floorPlanBackgroundImageDataUrl}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-600 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40 dark:text-slate-300 dark:hover:bg-slate-700"
                    title="Remove uploaded floor plan image"
                    aria-label="Remove uploaded floor plan image"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={handleFloorPlanSave}
                    disabled={!floorPlanDirty || !floorPlanCanSave || venueLayoutSaving}
                    className="inline-flex h-8 items-center gap-1.5 rounded-md bg-slate-900 px-2 text-xs font-semibold text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200 dark:disabled:bg-slate-700 dark:disabled:text-slate-400"
                    title="Save floor plan"
                    aria-label="Save floor plan"
                  >
                    <Save className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Save</span>
                  </button>
                </div>
                {fixtureMenuOpen && (
                  <div className="grid grid-cols-2 gap-1 border-t border-slate-200/70 p-1 dark:border-slate-700/70 sm:grid-cols-4">
                    {FIXTURE_TYPES.map((type) => (
                      <button
                        key={type}
                        onClick={() => handleFixtureAdd(type)}
                        className="rounded-md px-2 py-1.5 text-left text-[11px] font-semibold text-slate-600 transition-colors hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                      >
                        {FIXTURE_TEMPLATES[type].label}
                      </button>
                    ))}
                  </div>
                )}
                {scaleMenuOpen && (
                  <div className="flex flex-wrap items-center gap-1 border-t border-slate-200/70 p-1 text-[11px] font-medium text-slate-500 dark:border-slate-700/70 dark:text-slate-400">
                    <input
                      type="number"
                      min="1"
                      inputMode="decimal"
                      value={floorPlanScalePixels ?? ''}
                      onChange={(event) => handleScaleChange('pixels', event.target.value)}
                      placeholder="100"
                      className="h-7 w-16 rounded-md border border-slate-200 bg-white/80 px-2 text-xs text-slate-700 outline-none focus:ring-2 focus:ring-blue-400/30 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200"
                      aria-label="Scale pixels"
                    />
                    <span>px =</span>
                    <input
                      type="number"
                      min="0.1"
                      inputMode="decimal"
                      value={floorPlanScaleDistance ?? ''}
                      onChange={(event) => handleScaleChange('distance', event.target.value)}
                      placeholder="10"
                      className="h-7 w-16 rounded-md border border-slate-200 bg-white/80 px-2 text-xs text-slate-700 outline-none focus:ring-2 focus:ring-blue-400/30 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200"
                      aria-label="Scale distance"
                    />
                    <select
                      value={floorPlanScaleUnit}
                      onChange={(event) => {
                        setFloorPlanScaleUnit(event.target.value as 'ft' | 'm');
                        setFloorPlanSaveState('idle');
                      }}
                      className="h-7 rounded-md border border-slate-200 bg-white/80 px-1 text-xs text-slate-700 outline-none focus:ring-2 focus:ring-blue-400/30 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200"
                      aria-label="Scale unit"
                    >
                      <option value="ft">ft</option>
                      <option value="m">m</option>
                    </select>
                  </div>
                )}
                {selectedFixture && (
                  <div
                    data-testid="fixture-editor"
                    className="grid grid-cols-2 gap-1 border-t border-slate-200/70 p-1 text-[11px] font-medium text-slate-500 dark:border-slate-700/70 dark:text-slate-400 sm:grid-cols-[minmax(9rem,1.5fr)_repeat(3,4.5rem)_2rem]"
                  >
                    <input
                      type="text"
                      value={selectedFixture.label}
                      onChange={(event) =>
                        handleFixtureUpdate(selectedFixture.id, { label: event.target.value })
                      }
                      className="col-span-2 h-7 rounded-md border border-slate-200 bg-white/80 px-2 text-xs text-slate-700 outline-none focus:ring-2 focus:ring-blue-400/30 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 sm:col-span-1"
                      aria-label="Fixture label"
                    />
                    <input
                      type="number"
                      min={MIN_FIXTURE_SIZE}
                      max={MAX_FIXTURE_SIZE}
                      value={Math.round(selectedFixture.width)}
                      onChange={(event) =>
                        handleFixtureUpdate(selectedFixture.id, {
                          width: parseFixtureNumber(
                            event.target.value,
                            selectedFixture.width,
                            MIN_FIXTURE_SIZE,
                            MAX_FIXTURE_SIZE
                          ),
                        })
                      }
                      className="h-7 rounded-md border border-slate-200 bg-white/80 px-2 text-xs text-slate-700 outline-none focus:ring-2 focus:ring-blue-400/30 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200"
                      aria-label="Fixture width"
                    />
                    <input
                      type="number"
                      min={MIN_FIXTURE_SIZE}
                      max={MAX_FIXTURE_SIZE}
                      value={Math.round(selectedFixture.height)}
                      onChange={(event) =>
                        handleFixtureUpdate(selectedFixture.id, {
                          height: parseFixtureNumber(
                            event.target.value,
                            selectedFixture.height,
                            MIN_FIXTURE_SIZE,
                            MAX_FIXTURE_SIZE
                          ),
                        })
                      }
                      className="h-7 rounded-md border border-slate-200 bg-white/80 px-2 text-xs text-slate-700 outline-none focus:ring-2 focus:ring-blue-400/30 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200"
                      aria-label="Fixture height"
                    />
                    <input
                      type="number"
                      min="-360"
                      max="360"
                      value={Math.round(selectedFixture.rotation ?? 0)}
                      onChange={(event) =>
                        handleFixtureUpdate(selectedFixture.id, {
                          rotation: parseFixtureNumber(
                            event.target.value,
                            selectedFixture.rotation ?? 0,
                            -360,
                            360
                          ),
                        })
                      }
                      className="h-7 rounded-md border border-slate-200 bg-white/80 px-2 text-xs text-slate-700 outline-none focus:ring-2 focus:ring-blue-400/30 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200"
                      aria-label="Fixture rotation"
                    />
                    <button
                      type="button"
                      onClick={() => handleFixtureDelete(selectedFixture.id)}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-950/40 dark:hover:text-red-300"
                      title={`Delete ${selectedFixture.label}`}
                      aria-label={`Delete ${selectedFixture.label}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
                {seatingGuideOpen && (
                  <div
                    data-testid="seating-guide-panel"
                    className="border-t border-emerald-200/70 bg-emerald-50/80 p-2 text-slate-700 dark:border-emerald-500/30 dark:bg-emerald-950/30 dark:text-slate-200"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold text-emerald-800 dark:text-emerald-200">
                          <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
                          <span>Planner setup guide</span>
                          <span className="rounded bg-white/80 px-1.5 py-0.5 text-[10px] text-emerald-700 dark:bg-slate-900/60 dark:text-emerald-200">
                            {seatingGuideCompleteCount}/{seatingGuideSteps.length}
                          </span>
                        </div>
                        <p className="mt-1 text-[11px] font-medium leading-snug text-slate-600 dark:text-slate-300">
                          {activeSeatingGuideStep.description}
                        </p>
                      </div>
                      {activeSeatingGuideStep.action && (
                        <button
                          type="button"
                          onClick={() =>
                            handleSeatingGuideAction(activeSeatingGuideStep.action as SeatingGuideAction)
                          }
                          className="inline-flex h-7 shrink-0 items-center gap-1 rounded-md bg-emerald-700 px-2 text-[11px] font-semibold text-white transition-colors hover:bg-emerald-600 dark:bg-emerald-500 dark:text-emerald-950 dark:hover:bg-emerald-400"
                        >
                          {activeSeatingGuideStep.actionLabel}
                          <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
                        </button>
                      )}
                    </div>
                    <ol className="mt-2 flex gap-1 overflow-x-auto pb-1 sm:grid sm:grid-cols-3 sm:overflow-visible sm:pb-0">
                      {seatingGuideSteps.map((step, index) => {
                        const isCurrent = step.id === activeSeatingGuideStep.id;
                        return (
                          <li
                            key={step.id}
                            aria-current={isCurrent ? 'step' : undefined}
                            className={`flex w-36 shrink-0 items-center gap-1.5 rounded-md border px-2 py-1.5 text-[11px] font-semibold sm:w-auto ${
                              step.done
                                ? 'border-emerald-200 bg-white/70 text-emerald-800 dark:border-emerald-500/30 dark:bg-slate-900/50 dark:text-emerald-200'
                                : isCurrent
                                ? 'border-emerald-500 bg-white text-slate-800 dark:border-emerald-400 dark:bg-slate-900 dark:text-slate-100'
                                : 'border-emerald-100 bg-white/50 text-slate-500 dark:border-emerald-500/20 dark:bg-slate-900/30 dark:text-slate-400'
                            }`}
                          >
                            <span
                              className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] ${
                                step.done
                                  ? 'bg-emerald-600 text-white'
                                  : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300'
                              }`}
                            >
                              {step.done ? <Check className="h-3 w-3" aria-hidden="true" /> : index + 1}
                            </span>
                            <span className="min-w-0 truncate">{step.title}</span>
                          </li>
                        );
                      })}
                    </ol>
                  </div>
                )}
                <div className="border-t border-slate-200/70 px-2 py-1 text-[11px] font-medium leading-snug text-slate-500 dark:border-slate-700/70 dark:text-slate-400 break-words">
                  {floorPlanStatus}
                  {floorPlanBackgroundImageName ? ` · ${floorPlanBackgroundImageName}` : ''}
                  {venueFixtures.length > 0 ? ` · ${venueFixtures.length} fixtures` : ''}
                </div>
                {layoutIssues.length > 0 && (
                  <div
                    data-testid="layout-issues"
                    className="border-t border-amber-200/80 bg-amber-50/80 px-2 py-1.5 text-[11px] font-medium leading-snug text-amber-800 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-200"
                  >
                    <div className="mb-1 flex items-center gap-1 font-semibold">
                      <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>Layout checks</span>
                    </div>
                    <ul className="space-y-0.5">
                      {layoutIssues.slice(0, 3).map((issue) => (
                        <li key={issue.id}>{issue.message}</li>
                      ))}
                    </ul>
                    {layoutIssues.length > 3 && (
                      <div className="mt-0.5 text-amber-700/80 dark:text-amber-200/80">
                        +{layoutIssues.length - 3} more
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="relative flex-1 overflow-hidden">
                {/* Canvas Zoom Controls */}
                <div className="absolute bottom-3 right-3 z-30 flex items-center gap-1 bg-white/80 dark:bg-slate-800/80 backdrop-blur-md rounded-lg border border-white/30 dark:border-slate-700/30 p-1 sm:top-3 sm:bottom-auto">
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
                  venueLayout={draftVenueLayout}
                  floorPlanMode={floorPlanMode}
                  floorPlanOutline={floorPlanOutline}
                  venueFixtures={venueFixtures}
                  selectedFixtureId={selectedFixtureId}
                  tableWarningIds={tableWarningIds}
                  fixtureWarningIds={fixtureWarningIds}
                  onFloorPlanPointAdd={handleFloorPlanPointAdd}
                  onFloorPlanPointMove={handleFloorPlanPointMove}
                  onFixtureSelect={setSelectedFixtureId}
                />
              </div>
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
            ) : activeDrag?.type === 'fixture' ? (
              <div className="bg-white/85 dark:bg-slate-800/85 backdrop-blur-xl border border-slate-300/70 dark:border-slate-600/60 rounded-xl shadow-2xl px-3 py-2 pointer-events-none ring-2 ring-slate-300/40">
                <span className="font-semibold text-slate-800 dark:text-gray-100 text-xs">
                  {activeDrag.fixture.label}
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
          venueLayout={draftVenueLayout}
          onClose={() => setShowPrintPreview(false)}
        />
      )}
    </div>
  );
}
