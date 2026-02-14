import React, { useState } from 'react';
import { Guest } from '@/types/table';
import { GuestItem } from './GuestItem';
import { motion } from 'framer-motion';

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
    <div className="w-80 h-full flex flex-col z-20 bg-white/70 dark:bg-slate-800/70 backdrop-blur-xl border-r border-white/20 dark:border-slate-700/20 shadow-2xl">
      <div className="p-6 border-b border-white/20 dark:border-slate-700/20 bg-gradient-to-b from-white/50 dark:from-slate-800/50 to-transparent">
        <h2 className="font-playfair text-xl font-bold text-gray-800 dark:text-gray-100 mb-4 flex items-center gap-2">
          <span>Guest List</span>
          <span className="text-xs font-sans font-normal px-2 py-1 bg-black/5 dark:bg-white/10 rounded-full text-gray-500 dark:text-gray-400">
            {unassignedGuests.length} unseated
          </span>
        </h2>

        <div className="relative">
          <input
            type="text"
            placeholder="Search guests..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full px-4 py-2.5 pl-10 bg-white/50 dark:bg-slate-700/50 border border-white/30 dark:border-slate-600/30 rounded-xl text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-400/50 focus:bg-white dark:focus:bg-slate-700 transition-all
                     placeholder:text-gray-400 dark:placeholder:text-gray-500 text-gray-700 dark:text-gray-100 shadow-inner"
          />
          <svg className="w-4 h-4 absolute left-3 top-3 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-8 custom-scrollbar">
        {Object.entries(groups).map(([groupName, groupGuests]) => (
          <motion.div
            key={groupName}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <h3 className="flex items-center gap-2 text-xs font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-3 px-2">
              {groupName}
              <span className="w-full h-px bg-gray-200 dark:bg-slate-600" />
            </h3>
            <div className="space-y-2">
              {groupGuests.map(guest => (
                <GuestItem key={guest.id} guest={guest} />
              ))}
            </div>
          </motion.div>
        ))}
        {filteredGuests.length === 0 && (
          <div className="flex flex-col items-center justify-center text-gray-400 dark:text-gray-500 mt-20 gap-2">
            <div className="w-16 h-16 rounded-full bg-gray-50 dark:bg-slate-700 flex items-center justify-center text-2xl">🔍</div>
            <p className="text-sm font-medium">No guests found</p>
          </div>
        )}
      </div>
    </div>
  );
}
