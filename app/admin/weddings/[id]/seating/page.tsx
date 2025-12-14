'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useTables } from '@/admin/hooks/useTables';
import { SeatingCanvas } from '@/admin/components/seating/SeatingCanvas';
import { Sidebar } from '@/admin/components/seating/Sidebar';
import { GlassButton } from '@/admin/components/ui/glass/GlassButton';
import { Plus, Download, Printer } from 'lucide-react';
import { Guest } from '@/types/table';

// Minimal mock for guest fetching hook (should use real one)
function useGuests(weddingId: string) {
  const [guests, setGuests] = useState<Guest[]>([]);

  useEffect(() => {
    if (!weddingId) return;
    const fetchGuests = async () => {
      // In real app, use existing useGuests hook or fetch directly
      const token = localStorage.getItem('admin_token');
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/guests/${weddingId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          // Map to Guest interface (ensure table_id is present)
          setGuests(data.map((g: any) => ({
            id: g._id, // Map MongoDB _id to id
            wedding_id: g.wedding_id,
            name: g.name,
            email: g.email,
            group_id: g.group_id,
            table_id: g.table_id || null, // Ensure null if undefined
            role: g.role
          })));
        }
      } catch (e) {
        console.error("Failed to fetch guests", e);
      }
    };
    fetchGuests();
  }, [weddingId]);

  return { guests, setGuests };
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
    setTables // exposed for optimistic updates if needed
  } = useTables(weddingId);

  const { guests, setGuests } = useGuests(weddingId);

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
    // Optimistic update
    setTables(prev => prev.map(t => t.id === id ? { ...t, x, y } : t));
    // Debounced API call could be better, but direct update for now
    updateTable(id, { x, y });
  };

  const handleGuestAssign = async (guestId: string, tableId: string) => {
    // Optimistic update
    setGuests(prev => prev.map(g => g.id === guestId ? { ...g, table_id: tableId } : g));
    await assignGuests(tableId, [guestId]);
  };

  const handleTableDelete = async (id: string) => {
    if (confirm("Are you sure you want to delete this table? Guests will be unseated.")) {
      // Optimistic update
      setGuests(prev => prev.map(g => g.table_id === id ? { ...g, table_id: null } : g));
      await deleteTable(id);
    }
  };

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden">
      <Sidebar guests={guests} />

      <div className="flex-1 flex flex-col relative">
        <div className="h-16 bg-white/80 backdrop-blur border-b border-gray-200 flex items-center justify-between px-6 z-20">
          <h1 className="font-playfair text-xl font-bold text-gray-800">Seating Plan</h1>

          <div className="flex gap-2">
            <GlassButton variant="secondary" size="sm" icon={<Printer className="w-4 h-4" />}>
              Print
            </GlassButton>
            <GlassButton variant="secondary" size="sm" icon={<Download className="w-4 h-4" />}>
              Export
            </GlassButton>
            <GlassButton onClick={handleAddTable} size="sm" icon={<Plus className="w-4 h-4" />}>
              Add Table
            </GlassButton>
          </div>
        </div>

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
    </div>
  );
}
