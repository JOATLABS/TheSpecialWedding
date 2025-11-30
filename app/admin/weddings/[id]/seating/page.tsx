'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';

// --- Types ---

interface Table {
  id: string;
  name: string;
  capacity: number;
  shape: 'circle' | 'rectangle';
  x: number;
  y: number;
  guests: Guest[];
}

interface Guest {
  id: string;
  _id: string;
  name: string;
  group_id?: string;
  table_id?: string;
  role: string;
}

interface UnassignedGroup {
  group_id: string;
  guests: Guest[];
}

// --- Icons ---
const PlusIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
);

const PrinterIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
    </svg>
);

const DownloadIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
);

const SaveIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
    </svg>
);

const UserIcon = () => (
    <svg className="w-3 h-3 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
    </svg>
);

// --- Components ---

// Draggable Guest Item
const GuestItem = ({ guest, index, isAssigned = false }: { guest: Guest, index: number, isAssigned?: boolean }) => {
  const guestId = guest.id || guest._id;
  return (
    <Draggable draggableId={guestId} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className={`
            group relative flex items-center justify-between
            p-3 mb-2 rounded-lg border transition-all duration-200 select-none
            ${snapshot.isDragging
              ? 'bg-wedding-navy text-white shadow-xl rotate-2 scale-105 z-50 border-transparent ring-2 ring-wedding-gold'
              : 'bg-white border-gray-100 shadow-sm hover:border-wedding-rose hover:shadow-md text-gray-700'}
            ${isAssigned ? 'py-2 px-3 mb-1 text-sm bg-gray-50/80 border-transparent hover:bg-white' : ''}
          `}
          style={provided.draggableProps.style}
        >
          <div className="flex items-center gap-3 overflow-hidden">
             {!isAssigned && (
                <div className={`p-1.5 rounded-full ${snapshot.isDragging ? 'bg-white/10' : 'bg-gray-100 text-gray-400'}`}>
                    <UserIcon />
                </div>
             )}
             <div className="flex flex-col min-w-0">
                 <span className={`truncate font-medium ${isAssigned ? 'text-sm' : 'text-sm'}`}>{guest.name}</span>
                 {!isAssigned && guest.group_id && (
                    <span className="text-[10px] text-gray-400 flex items-center gap-1 mt-0.5">
                       <span className="w-1.5 h-1.5 rounded-full bg-wedding-sage"></span>
                       {guest.group_id}
                    </span>
                 )}
             </div>
          </div>

          {guest.role !== 'guest' && (
             <span className={`
                text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded
                ${snapshot.isDragging ? 'bg-white/20 text-white' : 'bg-wedding-navy/5 text-wedding-navy'}
             `}>
                {guest.role}
             </span>
          )}
        </div>
      )}
    </Draggable>
  );
};

// Table Component (Droppable)
const TableNode = ({
    table,
    index,
    updateTablePosition,
    onDelete,
    onEdit
}: {
    table: Table,
    index: number,
    updateTablePosition: (id: string, x: number, y: number) => void,
    onDelete: (id: string) => void,
    onEdit: (table: Table) => void
}) => {
  const nodeRef = useRef<HTMLDivElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const handleMouseDown = (e: React.MouseEvent) => {
    // Only drag if clicking the header/handle, not the guest list
    if ((e.target as HTMLElement).closest('.table-handle')) {
        setIsDragging(true);
        // Calculate offset from top-left of element
        const rect = nodeRef.current?.getBoundingClientRect();
        if (rect) {
            setDragOffset({
                x: e.clientX - rect.left,
                y: e.clientY - rect.top
            });
        }
    }
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
        if (isDragging) {
             const canvas = document.getElementById('seating-canvas');
             if (canvas) {
                const canvasRect = canvas.getBoundingClientRect();
                const x = e.clientX - canvasRect.left - dragOffset.x;
                const y = e.clientY - canvasRect.top - dragOffset.y;
                updateTablePosition(table.id, x, y);
             }
        }
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    if (isDragging) {
        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragOffset, table.id, updateTablePosition]);

  const isFull = table.guests.length >= table.capacity;
  const isOverCapacity = table.guests.length > table.capacity;

  return (
    <div
      ref={nodeRef}
      onMouseDown={handleMouseDown}
      style={{
        position: 'absolute',
        left: table.x,
        top: table.y,
        width: table.shape === 'circle' ? '280px' : '220px',
        minHeight: table.shape === 'circle' ? '280px' : '320px',
        borderRadius: table.shape === 'circle' ? '50%' : '16px',
      }}
      className={`
        bg-white/95 backdrop-blur-sm border shadow-xl flex flex-col overflow-hidden z-10
        ${isDragging
            ? 'border-wedding-gold ring-4 ring-wedding-gold/20 shadow-2xl cursor-grabbing scale-105 z-50'
            : 'border-gray-200 hover:border-wedding-navy/30 hover:shadow-2xl'}
        transition-all duration-300 group
      `}
    >
        {/* Table Header/Handle */}
        <div className={`
            table-handle cursor-grab relative overflow-hidden transition-colors duration-300
            ${table.shape === 'circle'
                ? 'h-16 mt-6 mx-8 flex items-center justify-center border-b border-gray-100'
                : 'h-12 bg-gray-50 border-b border-gray-200 flex items-center justify-between px-4'}
            ${isDragging ? 'bg-wedding-navy/5' : ''}
        `}>
            <div className={`flex flex-col ${table.shape === 'circle' ? 'items-center text-center' : ''}`}>
                <span className="font-bold text-gray-800 text-sm truncate max-w-[140px]">{table.name}</span>
                <span className={`text-[10px] font-medium mt-0.5
                    ${isOverCapacity ? 'text-red-500' : isFull ? 'text-wedding-gold' : 'text-gray-400'}`}>
                    {table.guests.length}/{table.capacity} Seats
                </span>
            </div>

            {/* Action Buttons (visible on hover) */}
            <div className={`
                absolute flex gap-1 transition-opacity duration-200
                ${table.shape === 'circle' ? 'top-1 right-1 opacity-0 group-hover:opacity-100' : 'opacity-0 group-hover:opacity-100'}
            `}>
                <button onClick={() => onEdit(table)} className="p-1.5 rounded-full bg-white text-gray-400 hover:text-blue-500 hover:bg-blue-50 shadow-sm border border-gray-100">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                </button>
                <button onClick={() => onDelete(table.id)} className="p-1.5 rounded-full bg-white text-gray-400 hover:text-red-500 hover:bg-red-50 shadow-sm border border-gray-100">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
            </div>
        </div>

        {/* Droppable Area */}
        <Droppable droppableId={table.id}>
            {(provided, snapshot) => (
                <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={`
                        flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-200 scrollbar-track-transparent
                        transition-colors duration-300
                        ${snapshot.isDraggingOver ? 'bg-wedding-navy/5' : ''}
                        ${table.shape === 'circle' ? 'px-8 pb-10 pt-2' : 'p-2'}
                    `}
                >
                    {table.guests.length === 0 && !snapshot.isDraggingOver && (
                        <div className="h-full flex items-center justify-center text-gray-300 text-xs italic">
                            Drag guests here
                        </div>
                    )}
                    {table.guests.map((guest, index) => (
                        <GuestItem key={guest.id || guest._id} guest={guest} index={index} isAssigned={true} />
                    ))}
                    {provided.placeholder}
                </div>
            )}
        </Droppable>

        {/* Footer Decoration for Round Tables */}
        {table.shape === 'circle' && (
            <div className="absolute inset-0 pointer-events-none rounded-[50%] border-8 border-gray-100/50 -z-10"></div>
        )}
    </div>
  );
};


// --- Main Page ---

export default function SeatingPage() {
  const { token } = useAdmin();
  const params = useParams();
  const router = useRouter();
  const weddingId = params.id as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tables, setTables] = useState<Table[]>([]);
  const [unassignedGuests, setUnassignedGuests] = useState<Guest[]>([]);
  const [unassignedGroups, setUnassignedGroups] = useState<UnassignedGroup[]>([]);
  const [weddingName, setWeddingName] = useState('');

  // Edit/Add Table State
  const [showTableModal, setShowTableModal] = useState(false);
  const [editingTable, setEditingTable] = useState<Table | null>(null);
  const [tableForm, setTableForm] = useState({ name: '', capacity: 10, shape: 'circle' as 'circle'|'rectangle' });
  const [saving, setSaving] = useState(false);

  // Fetch Data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

      // 1. Fetch Wedding Info
      const weddingRes = await fetch(`${baseUrl}/admin/weddings`, {
         headers: { 'Authorization': `Bearer ${token}` }
      });
      const weddings = await weddingRes.json();
      const wedding = weddings.find((w: any) => (w.id || w._id) === weddingId);
      if (wedding) setWeddingName(wedding.couple_names);

      // 2. Fetch Tables
      const tablesRes = await fetch(`${baseUrl}/admin/tables/${weddingId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
      });
      const tablesData = await tablesRes.json();

      // 3. Fetch Guests
      const guestsRes = await fetch(`${baseUrl}/admin/guests?wedding_id=${weddingId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
      });
      const guestsData = await guestsRes.json();

      // Process Data
      const allGuests: Guest[] = Array.isArray(guestsData) ? guestsData : [];

      // Map guests to tables
      const processedTables = tablesData.map((t: any) => ({
          ...t,
          guests: allGuests.filter(g => g.table_id === t.id)
      }));
      setTables(processedTables);

      // Filter unassigned guests
      const unassigned = allGuests.filter(g => !g.table_id);
      setUnassignedGuests(unassigned);

      // Group unassigned guests
      const groups: { [key: string]: Guest[] } = {};
      const noGroup: Guest[] = [];

      unassigned.forEach(g => {
          if (g.group_id) {
              if (!groups[g.group_id]) groups[g.group_id] = [];
              groups[g.group_id].push(g);
          } else {
              noGroup.push(g);
          }
      });

      const groupArray: UnassignedGroup[] = Object.keys(groups).map(gid => ({
          group_id: gid,
          guests: groups[gid]
      }));

      // Add "No Group" as a special group at the end or beginning
      if (noGroup.length > 0) {
          groupArray.push({ group_id: 'Ungrouped', guests: noGroup });
      }

      setUnassignedGroups(groupArray);

    } catch (err) {
      console.error(err);
      setError('Failed to load seating data');
    } finally {
      setLoading(false);
    }
  }, [token, weddingId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);


  // --- Actions ---

  const handleDragEnd = async (result: DropResult) => {
    const { source, destination, draggableId } = result;

    if (!destination) return;
    if (source.droppableId === destination.droppableId && source.index === destination.index) return;

    // Optimistic UI Update

    let movedGuest: Guest | undefined;
    let sourceGroupIndex = -1;
    let sourceTableIndex = -1;

    // Check if source is sidebar
    if (source.droppableId.startsWith('group-')) {
        const groupId = source.droppableId.replace('group-', '');
        const groupIndex = unassignedGroups.findIndex(g => g.group_id === groupId);
        if (groupIndex !== -1) {
            movedGuest = unassignedGroups[groupIndex].guests[source.index];
            sourceGroupIndex = groupIndex;
        }
    } else {
        // Source is a table
        const tableIndex = tables.findIndex(t => t.id === source.droppableId);
        if (tableIndex !== -1) {
            movedGuest = tables[tableIndex].guests[source.index];
            sourceTableIndex = tableIndex;
        }
    }

    if (!movedGuest) return;

    // 2. Remove from source
    const newUnassignedGroups = [...unassignedGroups];
    const newTables = [...tables];

    if (sourceGroupIndex !== -1) {
        newUnassignedGroups[sourceGroupIndex].guests.splice(source.index, 1);
        setUnassignedGroups(newUnassignedGroups);
    } else if (sourceTableIndex !== -1) {
        newTables[sourceTableIndex].guests.splice(source.index, 1);
    }

    // 3. Add to destination
    let targetTableId: string | null = null;

    if (destination.droppableId.startsWith('group-')) {
        // Moved back to sidebar
        const groupId = destination.droppableId.replace('group-', '');
        const targetGroupIndex = newUnassignedGroups.findIndex(g => g.group_id === groupId);

        movedGuest.table_id = undefined;

        if (targetGroupIndex !== -1) {
            newUnassignedGroups[targetGroupIndex].guests.splice(destination.index, 0, movedGuest);
        }
        setUnassignedGroups(newUnassignedGroups);
        targetTableId = null;

    } else {
        // Moved to a table
        const targetTableIndex = newTables.findIndex(t => t.id === destination.droppableId);
        if (targetTableIndex !== -1) {
            movedGuest.table_id = newTables[targetTableIndex].id;
            newTables[targetTableIndex].guests.splice(destination.index, 0, movedGuest);
            targetTableId = newTables[targetTableIndex].id;
        }
    }

    setTables(newTables);

    // 4. API Call
    try {
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
        await fetch(`${baseUrl}/admin/tables/assign`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                table_id: targetTableId,
                guest_ids: [draggableId]
            })
        });
    } catch (err) {
        console.error("Failed to save assignment", err);
        alert("Failed to save assignment. Please refresh.");
    }
  };

  const handleUpdateTablePosition = async (id: string, x: number, y: number) => {
     const newTables = tables.map(t => t.id === id ? { ...t, x, y } : t);
     setTables(newTables);
  };

  const saveLayout = async () => {
     setSaving(true);
     try {
         const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
         const promises = tables.map(table =>
             fetch(`${baseUrl}/admin/tables/${table.id}`, {
                 method: 'PUT',
                 headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ x: table.x, y: table.y })
             })
         );
         await Promise.all(promises);
     } catch(err) {
         alert("Failed to save layout");
     } finally {
         setSaving(false);
     }
  };

  const handleAddTable = async () => {
    try {
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
        const payload = {
            wedding_id: weddingId,
            name: tableForm.name,
            capacity: tableForm.capacity,
            shape: tableForm.shape,
            x: 100 + (tables.length * 30),
            y: 100 + (tables.length * 30)
        };

        const res = await fetch(`${baseUrl}/admin/tables`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            const newTable = await res.json();
            setTables([...tables, { ...newTable, guests: [] }]);
            setShowTableModal(false);
            setTableForm({ name: '', capacity: 10, shape: 'circle' });
        }
    } catch (err) {
        alert("Failed to add table");
    }
  };

  const handleUpdateTable = async () => {
     if (!editingTable) return;
     try {
         const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
         const res = await fetch(`${baseUrl}/admin/tables/${editingTable.id}`, {
            method: 'PUT',
             headers: {
                 'Authorization': `Bearer ${token}`,
                 'Content-Type': 'application/json'
             },
             body: JSON.stringify({
                 name: tableForm.name,
                 capacity: tableForm.capacity,
                 shape: tableForm.shape
             })
         });

         if (res.ok) {
             const updated = await res.json();
             setTables(tables.map(t => t.id === editingTable.id ? { ...t, ...updated, guests: t.guests, x: t.x, y: t.y } : t));
             setShowTableModal(false);
             setEditingTable(null);
             setTableForm({ name: '', capacity: 10, shape: 'circle' });
         }
     } catch (err) {
         alert("Failed to update table");
     }
  };

  const handleDeleteTable = async (id: string) => {
      if (!confirm("Delete this table? Guests will be unassigned.")) return;
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
        await fetch(`${baseUrl}/admin/tables/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        fetchData();
      } catch (err) {
          alert("Failed to delete table");
      }
  };

  const openAddModal = () => {
      setEditingTable(null);
      setTableForm({ name: `Table ${tables.length + 1}`, capacity: 10, shape: 'circle' });
      setShowTableModal(true);
  };

  const openEditModal = (table: Table) => {
      setEditingTable(table);
      setTableForm({ name: table.name, capacity: table.capacity, shape: table.shape });
      setShowTableModal(true);
  };

  const downloadCSV = () => {
    let csv = 'Table,Guest Name,Role,Group\n';
    tables.forEach(table => {
        table.guests.forEach(guest => {
            csv += `"${table.name}","${guest.name}","${guest.role}","${guest.group_id || ''}"\n`;
        });
    });
    unassignedGroups.forEach(group => {
        group.guests.forEach(guest => {
            csv += `Unassigned,"${guest.name}","${guest.role}","${guest.group_id || ''}"\n`;
        });
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `seating-chart-${weddingName.replace(/\s+/g, '-')}.csv`;
    a.click();
  };

  const handlePrint = () => {
      window.print();
  };

  if (loading) return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-wedding-navy mx-auto mb-4"></div>
              <p className="text-gray-500 font-medium">Preparing your seating chart...</p>
          </div>
      </div>
  );

  return (
    <div className="h-screen flex flex-col bg-gray-50 overflow-hidden font-sans">

      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center shadow-sm z-30">
        <div className="flex items-center gap-4">
            <button onClick={() => router.push(`/admin/weddings/${weddingId}`)} className="text-gray-400 hover:text-gray-600 transition-colors">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
            </button>
            <div>
                <h1 className="text-xl font-bold text-gray-900">{weddingName || 'Wedding'}</h1>
                <div className="flex items-center gap-2 text-sm text-gray-500">
                    <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full text-xs font-medium">Active</span>
                    <span>• Seating Orchestration</span>
                </div>
            </div>
        </div>

        <div className="flex items-center gap-3">
            <div className="h-8 w-px bg-gray-200 mx-2"></div>

            <button onClick={downloadCSV} className="flex items-center gap-2 px-4 py-2 text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all text-sm font-medium shadow-sm">
                <DownloadIcon />
                <span className="hidden sm:inline">Export CSV</span>
            </button>

             <button onClick={handlePrint} className="flex items-center gap-2 px-4 py-2 text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all text-sm font-medium shadow-sm">
                <PrinterIcon />
                <span className="hidden sm:inline">Print</span>
            </button>

            <button
                onClick={saveLayout}
                disabled={saving}
                className={`
                    flex items-center gap-2 px-6 py-2 rounded-lg text-white font-medium shadow-md transition-all transform active:scale-95
                    ${saving ? 'bg-gray-400 cursor-not-allowed' : 'bg-wedding-navy hover:bg-opacity-90 hover:shadow-lg'}
                `}
            >
                {saving ? (
                    <>
                        <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                        <span>Saving...</span>
                    </>
                ) : (
                    <>
                        <SaveIcon />
                        <span>Save Layout</span>
                    </>
                )}
            </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
         <DragDropContext onDragEnd={handleDragEnd}>

            {/* Sidebar - Unassigned Guests */}
            <div className="w-96 bg-white border-r border-gray-200 flex flex-col shadow-xl z-20 print:hidden transition-all duration-300">
                <div className="p-5 border-b border-gray-100 bg-gray-50/50">
                    <div className="flex justify-between items-center mb-1">
                        <h2 className="font-bold text-gray-800 text-lg">Guest List</h2>
                        <span className="bg-gray-200 text-gray-600 text-xs font-bold px-2 py-1 rounded-full">{unassignedGuests.length} Unassigned</span>
                    </div>
                    <p className="text-xs text-gray-500">Drag guests to tables on the canvas.</p>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-gray-200">
                    {unassignedGroups.map(group => (
                        <div key={group.group_id} className="animate-in fade-in slide-in-from-left-4 duration-500">
                            <div className="flex items-center gap-2 mb-3">
                                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                    {group.group_id}
                                </h3>
                                <div className="h-px flex-1 bg-gray-100"></div>
                                <span className="text-[10px] text-gray-400 font-mono">{group.guests.length}</span>
                            </div>

                            <Droppable droppableId={`group-${group.group_id}`}>
                                {(provided, snapshot) => (
                                    <div
                                        ref={provided.innerRef}
                                        {...provided.droppableProps}
                                        className={`
                                            min-h-[60px] rounded-xl transition-colors duration-200
                                            ${snapshot.isDraggingOver ? 'bg-wedding-navy/5 ring-2 ring-wedding-navy/20 p-2' : ''}
                                        `}
                                    >
                                        {group.guests.map((guest, index) => (
                                            <GuestItem key={guest.id || guest._id} guest={guest} index={index} />
                                        ))}
                                        {provided.placeholder}
                                    </div>
                                )}
                            </Droppable>
                        </div>
                    ))}

                    {unassignedGroups.length === 0 && (
                        <div className="flex flex-col items-center justify-center h-64 text-center p-6 border-2 border-dashed border-gray-200 rounded-xl m-4">
                            <div className="bg-green-100 text-green-600 p-3 rounded-full mb-3">
                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                            <h3 className="text-gray-900 font-medium">All Set!</h3>
                            <p className="text-gray-500 text-sm mt-1">Every guest has been assigned a seat.</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Canvas - Tables */}
            <div className="flex-1 bg-gray-50/50 relative overflow-hidden" id="seating-canvas">

                {/* Canvas Background Grid */}
                <div className="absolute inset-0 pointer-events-none opacity-40"
                     style={{
                         backgroundImage: `
                            linear-gradient(#e5e7eb 1px, transparent 1px),
                            linear-gradient(90deg, #e5e7eb 1px, transparent 1px)
                         `,
                         backgroundSize: '40px 40px'
                     }}>
                </div>

                {/* Toolbar Floating */}
                <div className="absolute top-6 left-6 z-20 print:hidden animate-in fade-in slide-in-from-top-4 duration-700">
                    <button
                        onClick={openAddModal}
                        className="
                            flex items-center gap-3 bg-white px-6 py-4 rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.12)]
                            text-wedding-navy font-bold hover:shadow-[0_8px_30px_rgb(0,0,0,0.16)]
                            transition-all hover:-translate-y-1 border border-white/50 backdrop-blur-sm
                        "
                    >
                        <div className="bg-wedding-gold text-white p-1 rounded-lg">
                            <PlusIcon />
                        </div>
                        <span className="text-lg">Add Table</span>
                    </button>
                </div>

                {/* Tables Layer */}
                <div className="w-full h-full relative">
                    {tables.map((table, index) => (
                        <TableNode
                            key={table.id}
                            table={table}
                            index={index}
                            updateTablePosition={handleUpdateTablePosition}
                            onDelete={handleDeleteTable}
                            onEdit={openEditModal}
                        />
                    ))}

                    {tables.length === 0 && !loading && (
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                            <div className="text-center opacity-40">
                                <div className="text-6xl mb-4">🍽️</div>
                                <h3 className="text-2xl font-bold text-gray-400">The floor is empty</h3>
                                <p className="text-gray-400">Click "Add Table" to start organizing</p>
                            </div>
                        </div>
                    )}
                </div>

            </div>
         </DragDropContext>
      </div>

      {/* Modal */}
      {showTableModal && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-200">
              <div className="bg-white rounded-2xl p-8 w-[400px] shadow-2xl transform transition-all scale-100">
                  <h2 className="text-2xl font-bold mb-6 text-gray-900">{editingTable ? 'Edit Table' : 'Add New Table'}</h2>

                  <div className="space-y-5">
                      <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">Table Name / Number</label>
                          <input
                              type="text"
                              value={tableForm.name}
                              onChange={e => setTableForm({...tableForm, name: e.target.value})}
                              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-wedding-gold focus:border-transparent outline-none transition-all"
                              placeholder="e.g. Table 1 or Head Table"
                              autoFocus
                          />
                      </div>

                      <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">Seating Capacity</label>
                          <div className="relative">
                              <input
                                  type="number"
                                  value={tableForm.capacity}
                                  onChange={e => setTableForm({...tableForm, capacity: parseInt(e.target.value)})}
                                  className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-wedding-gold focus:border-transparent outline-none transition-all"
                                  min="1"
                                  max="20"
                              />
                              <div className="absolute right-4 top-3 text-gray-400 text-sm">Seats</div>
                          </div>
                      </div>

                      <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">Table Shape</label>
                          <div className="grid grid-cols-2 gap-3">
                              <button
                                  onClick={() => setTableForm({...tableForm, shape: 'circle'})}
                                  className={`
                                      flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all
                                      ${tableForm.shape === 'circle'
                                          ? 'border-wedding-gold bg-wedding-gold/5 text-wedding-navy'
                                          : 'border-gray-200 hover:border-gray-300 text-gray-500'}
                                  `}
                              >
                                  <div className="w-8 h-8 rounded-full border-2 border-current mb-2"></div>
                                  <span className="text-sm font-medium">Round</span>
                              </button>

                              <button
                                  onClick={() => setTableForm({...tableForm, shape: 'rectangle'})}
                                  className={`
                                      flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all
                                      ${tableForm.shape === 'rectangle'
                                          ? 'border-wedding-gold bg-wedding-gold/5 text-wedding-navy'
                                          : 'border-gray-200 hover:border-gray-300 text-gray-500'}
                                  `}
                              >
                                  <div className="w-10 h-6 border-2 border-current mb-2 rounded-sm"></div>
                                  <span className="text-sm font-medium">Rectangle</span>
                              </button>
                          </div>
                      </div>
                  </div>

                  <div className="flex gap-3 mt-8">
                      <button onClick={() => setShowTableModal(false)} className="flex-1 bg-gray-100 text-gray-700 py-3 rounded-xl font-medium hover:bg-gray-200 transition-colors">
                          Cancel
                      </button>
                      <button onClick={editingTable ? handleUpdateTable : handleAddTable} className="flex-1 bg-wedding-navy text-white py-3 rounded-xl font-medium hover:bg-opacity-90 transition-colors shadow-lg shadow-blue-900/20">
                          {editingTable ? 'Update Table' : 'Create Table'}
                      </button>
                  </div>
              </div>
          </div>
      )}

      {/* Print View Styles */}
      <style jsx global>{`
        @media print {
            body * {
                visibility: hidden;
            }
            #seating-canvas, #seating-canvas * {
                visibility: visible;
            }
            #seating-canvas {
                position: absolute;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                overflow: visible;
                background: white;
            }
            .table-handle button {
                display: none;
            }
             /* Force background printing */
            * {
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
             .print-list-view {
                display: block !important;
                visibility: visible !important;
             }
        }
      `}</style>

      {/* Hidden Print List View (Only shows on print if needed, but we prioritize canvas print) */}
      <div className="hidden print:block fixed inset-0 bg-white z-[100] p-8 overflow-auto">
         <div className="text-center mb-10">
             <h1 className="text-4xl font-bold mb-2 text-gray-900">{weddingName}</h1>
             <p className="text-xl text-gray-500 uppercase tracking-widest">Seating Arrangement</p>
         </div>

         <div className="grid grid-cols-2 gap-10">
             {tables.map(table => (
                 <div key={table.id} className="border border-gray-200 rounded-xl p-6 break-inside-avoid shadow-sm">
                     <div className="flex justify-between items-center border-b border-gray-100 pb-3 mb-4">
                        <h2 className="font-bold text-2xl text-gray-800">{table.name}</h2>
                        <span className="text-sm font-medium bg-gray-100 px-3 py-1 rounded-full text-gray-600">
                            {table.guests.length} guests
                        </span>
                     </div>
                     <ul className="grid grid-cols-2 gap-2">
                         {table.guests.map(guest => (
                             <li key={guest.id || guest._id} className="text-sm py-1 border-b border-gray-50 flex items-center gap-2">
                                 <span className="w-1.5 h-1.5 bg-gray-300 rounded-full"></span>
                                 {guest.name}
                             </li>
                         ))}
                     </ul>
                 </div>
             ))}
         </div>
      </div>

    </div>
  );
}
