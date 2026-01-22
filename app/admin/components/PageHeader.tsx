import React from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string | React.ReactNode;
  children?: React.ReactNode; // For actions/buttons
}

export default function PageHeader({ title, subtitle, children }: PageHeaderProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
      <div>
        <h1 className="text-3xl md:text-4xl font-semibold font-wedding text-slate-900 dark:text-white leading-tight">
          {title}
        </h1>
        {subtitle && (
          <div className="mt-2 text-base text-slate-600 dark:text-slate-400">
            {subtitle}
          </div>
        )}
      </div>
      {children && (
        <div className="flex items-center gap-3">
          {children}
        </div>
      )}
    </div>
  );
}
