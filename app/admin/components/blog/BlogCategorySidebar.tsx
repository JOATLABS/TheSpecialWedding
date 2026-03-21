'use client';

import {
  Layers,
  Rocket,
  DollarSign,
  Users,
  GitCompare,
  FileText,
  Cpu,
  MapPin,
  Lightbulb,
  MessageSquare,
} from 'lucide-react';

interface BlogCategorySidebarProps {
  selectedCategory: string;
  onCategoryChange: (category: string) => void;
  categoryCounts: Record<string, number>;
  totalArticles: number;
}

const BLOG_CATEGORIES = [
  { value: 'platform-updates', label: 'Platform Updates', icon: Rocket, color: 'text-blue-400' },
  { value: 'pricing-strategy', label: 'Pricing Strategy', icon: DollarSign, color: 'text-amber-400' },
  { value: 'guest-management', label: 'Guest Management', icon: Users, color: 'text-cyan-400' },
  { value: 'industry-comparison', label: 'Industry Comparison', icon: GitCompare, color: 'text-purple-400' },
  { value: 'contracts-legal', label: 'Contracts & Legal', icon: FileText, color: 'text-orange-400' },
  { value: 'ai-technology', label: 'AI & Technology', icon: Cpu, color: 'text-violet-400' },
  { value: 'event-logistics', label: 'Event Logistics', icon: MapPin, color: 'text-teal-400' },
  { value: 'tips-guides', label: 'Tips & Guides', icon: Lightbulb, color: 'text-emerald-400' },
  { value: 'general', label: 'General', icon: MessageSquare, color: 'text-slate-400' },
];

export default function BlogCategorySidebar({
  selectedCategory,
  onCategoryChange,
  categoryCounts,
  totalArticles,
}: BlogCategorySidebarProps) {
  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5 sticky top-4">
      <div className="flex items-center gap-2 mb-4">
        <Layers className="w-4 h-4 text-wedding-rose" />
        <h3 className="text-sm font-semibold text-white">Categories</h3>
      </div>

      <div className="space-y-1">
        {/* All Articles */}
        <button
          onClick={() => onCategoryChange('all')}
          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition ${
            selectedCategory === 'all'
              ? 'bg-wedding-rose/15 text-wedding-rose font-medium'
              : 'text-slate-400 hover:bg-white/5 hover:text-white'
          }`}
        >
          <span className="flex items-center gap-2">
            <Layers className="w-3.5 h-3.5" />
            All Articles
          </span>
          <span className={`px-2 py-0.5 text-[10px] rounded-full ${
            selectedCategory === 'all'
              ? 'bg-wedding-rose/20 text-wedding-rose'
              : 'bg-slate-700/50 text-slate-500'
          }`}>
            {totalArticles}
          </span>
        </button>

        {/* Category list */}
        {BLOG_CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          const count = categoryCounts[cat.value] || 0;
          const isSelected = selectedCategory === cat.value;

          return (
            <button
              key={cat.value}
              onClick={() => onCategoryChange(cat.value)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition ${
                isSelected
                  ? 'bg-wedding-rose/15 text-wedding-rose font-medium'
                  : 'text-slate-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <span className="flex items-center gap-2">
                <Icon className={`w-3.5 h-3.5 ${isSelected ? 'text-wedding-rose' : cat.color}`} />
                {cat.label}
              </span>
              {count > 0 && (
                <span className={`px-2 py-0.5 text-[10px] rounded-full ${
                  isSelected
                    ? 'bg-wedding-rose/20 text-wedding-rose'
                    : 'bg-slate-700/50 text-slate-500'
                }`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Status filter section */}
      <div className="mt-6 pt-4 border-t border-slate-700/50">
        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Status</h4>
        <div className="space-y-1">
          {['published', 'draft', 'archived'].map((status) => (
            <button
              key={status}
              onClick={() => onCategoryChange(`status:${status}`)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition ${
                selectedCategory === `status:${status}`
                  ? 'bg-wedding-rose/15 text-wedding-rose font-medium'
                  : 'text-slate-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${
                status === 'published' ? 'bg-emerald-400' :
                status === 'draft' ? 'bg-yellow-400' : 'bg-slate-500'
              }`} />
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
