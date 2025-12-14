import React, { useState } from 'react';
import { Guest } from '@/types/table';
import { GuestItem } from './GuestItem';

interface SidebarProps {
  guests: Guest[];
}

export function Sidebar({ guests }: SidebarProps) {
  const [filter, setFilter] = useState('');

  // Group unassigned guests
  const unassignedGuests = guests.filter(g => !g.table_id);

  const filteredGuests = unassignedGuests.filter(g =>
    g.name.toLowerCase().includes(filter.toLowerCase()) ||
    (g.group_id && g.group_id.toLowerCase().includes(filter.toLowerCase()))
  );

  // Group by group_id
  const groups: { [key: string]: Guest[] } = {};
  filteredGuests.forEach(g => {
    const group = g.group_id || 'Ungrouped';
    if (!groups[group]) groups[group] = [];
    groups[group].push(g);
  });

  return (
    <div className="w-80 bg-white border-r border-gray-200 h-full flex flex-col shadow-lg z-10">
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <h2 className="font-playfair text-lg font-semibold text-gray-800 mb-2">Guest List</h2>
        <input
          type="text"
          placeholder="Search guests..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="mt-2 text-xs text-gray-500 flex justify-between">
          <span>Unseated: {unassignedGuests.length}</span>
          <span>Total: {guests.length}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {Object.entries(groups).map(([groupName, groupGuests]) => (
          <div key={groupName}>
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
              {groupName} ({groupGuests.length})
            </h3>
            <div className="space-y-2">
              {groupGuests.map(guest => (
                <GuestItem key={guest.id} guest={guest} />
              ))}
            </div>
          </div>
        ))}
        {filteredGuests.length === 0 && (
          <div className="text-center text-gray-400 mt-10">
            No guests found
          </div>
        )}
      </div>
    </div>
  );
}
