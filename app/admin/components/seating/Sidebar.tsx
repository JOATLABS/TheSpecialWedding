import React, { useState } from 'react';
import { Guest } from '@/types/table';
import { GuestItem } from './GuestItem';
import { Search, Users } from 'lucide-react';

interface SidebarProps {
  guests: Guest[];
}

export function Sidebar({ guests }: SidebarProps) {
  const [filter, setFilter] = useState('');

  // Group unassigned guests
  const unassignedGuests = guests.filter((g) => !g.table_id);

  const filteredGuests = unassignedGuests.filter(
    (g) =>
      g.name.toLowerCase().includes(filter.toLowerCase()) ||
      (g.group_id && g.group_id.toLowerCase().includes(filter.toLowerCase()))
  );

  // Group by group_id
  const groups: { [key: string]: Guest[] } = {};
  filteredGuests.forEach((g) => {
    const group = g.group_id || 'Ungrouped';
    if (!groups[group]) groups[group] = [];
    groups[group].push(g);
  });

  return (
    <div className="h-80 w-full flex-shrink-0 flex flex-col z-20 border-b border-white/30 bg-white/50 backdrop-blur-md print:hidden dark:border-slate-700/30 dark:bg-slate-900/40 lg:h-full lg:w-80 lg:border-b-0 lg:border-r" role="region" aria-label="Unseated guests sidebar">
      {/* Header */}
      <div className="p-4 border-b border-white/20 dark:border-slate-700/20 lg:p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-slate-800 dark:text-gray-100 flex items-center gap-2">
            <Users className="w-4 h-4 text-slate-500 dark:text-slate-400" aria-hidden="true" />
            Guest List
          </h2>
          <span className="text-xs font-medium px-2.5 py-1 bg-amber-50/80 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 rounded-full border border-amber-200/50 dark:border-amber-800/30" aria-label={`${unassignedGuests.length} guests unseated`}>
            {unassignedGuests.length} unseated
          </span>
        </div>

        <div className="relative">
          <input
            type="text"
            placeholder="Search guests..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full px-4 py-2.5 pl-9 bg-white/50 dark:bg-slate-800/50 border border-white/30 dark:border-slate-600/30 rounded-xl text-sm
                     focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-300/50 dark:focus:ring-primary-600/30 dark:focus:border-primary-700/30
                     transition-all backdrop-blur-md
                     placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-700 dark:text-gray-100"
            aria-label="Search guests by name or group"
          />
          <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400 dark:text-slate-500" aria-hidden="true" />
        </div>
      </div>

      {/* Guest List */}
      <div
        className="flex-1 overflow-y-auto p-3 space-y-4 sm:p-4 lg:space-y-6"
        style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(148,163,184,0.3) transparent' }}
      >
        {Object.entries(groups).map(([groupName, groupGuests]) => (
          <div key={groupName}>
            <h3 className="flex items-center gap-2 text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-2 px-1">
              <span>{groupName}</span>
              <span className="flex-1 h-px bg-slate-200/50 dark:bg-slate-700/50" />
              <span className="text-slate-400/60 dark:text-slate-500/60 normal-case font-normal">
                {groupGuests.length}
              </span>
            </h3>
            <div className="space-y-1">
              {groupGuests.map((guest) => (
                <GuestItem key={guest.id} guest={guest} />
              ))}
            </div>
          </div>
        ))}

        {filteredGuests.length === 0 && (
          <div className="flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 mt-16 gap-2">
            <div className="w-14 h-14 rounded-full bg-white/50 dark:bg-slate-800/50 border border-white/30 dark:border-slate-700/30 flex items-center justify-center">
              <Search className="w-6 h-6 text-slate-300 dark:text-slate-600" aria-hidden="true" />
            </div>
            <p className="text-sm font-medium">
              {filter ? 'No matches found' : 'All guests are seated'}
            </p>
            {filter && (
              <button
                onClick={() => setFilter('')}
                className="text-xs text-primary-500 dark:text-primary-400 hover:underline"
                aria-label="Clear search filter"
              >
                Clear search
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
