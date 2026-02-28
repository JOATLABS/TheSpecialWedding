'use client';

import React, { useRef, useCallback } from 'react';
import { Table, Guest } from '@/types/table';
import { X, Printer, Download } from 'lucide-react';

interface PrintableSeatingChartProps {
  tables: Table[];
  guests: Guest[];
  coupleName: string;
  weddingDate: string;
  onClose: () => void;
}

export function PrintableSeatingChart({
  tables,
  guests,
  coupleName,
  weddingDate,
  onClose,
}: PrintableSeatingChartProps) {
  const printRef = useRef<HTMLDivElement>(null);

  // Calculate canvas bounds from table positions
  const padding = 120;
  const tableCardW = 260;
  const tableCardH = 240;

  const maxX = tables.length > 0
    ? Math.max(...tables.map((t) => t.x)) + tableCardW + padding
    : 1200;
  const maxY = tables.length > 0
    ? Math.max(...tables.map((t) => t.y)) + tableCardH + padding
    : 800;

  const canvasW = Math.max(1200, maxX + padding);
  const canvasH = Math.max(800, maxY + padding + 160); // extra for header

  // Group guests per table
  const guestsByTable = (tableId: string) => guests.filter((g) => g.table_id === tableId);
  const unseatedGuests = guests.filter((g) => !g.table_id);
  const seatedCount = guests.filter((g) => g.table_id).length;

  const handlePrint = useCallback(() => {
    const printContent = printRef.current;
    if (!printContent) return;

    const printWindow = window.open('', '_blank', 'width=1400,height=900');
    if (!printWindow) return;

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Seating Chart — ${coupleName}</title>
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');

          * { margin: 0; padding: 0; box-sizing: border-box; }

          @page {
            size: 24in 18in landscape;
            margin: 0.5in;
          }

          body {
            font-family: 'Inter', system-ui, sans-serif;
            background: #FAFBFC;
            color: #1E293B;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }

          .print-canvas {
            position: relative;
            width: ${canvasW}px;
            min-height: ${canvasH}px;
            background: linear-gradient(135deg, #FFF5F5 0%, #F8FAFC 40%, #F0FDFA 100%);
            border: 2px solid #E9C46A;
            border-radius: 16px;
            overflow: hidden;
            page-break-inside: avoid;
          }

          /* Decorative corners */
          .print-canvas::before, .print-canvas::after {
            content: '';
            position: absolute;
            width: 60px;
            height: 60px;
            border: 3px solid #E9C46A;
            opacity: 0.5;
          }
          .print-canvas::before {
            top: 12px; left: 12px;
            border-right: none; border-bottom: none;
            border-radius: 8px 0 0 0;
          }
          .print-canvas::after {
            bottom: 12px; right: 12px;
            border-left: none; border-top: none;
            border-radius: 0 0 8px 0;
          }

          .print-header {
            text-align: center;
            padding: 40px 20px 30px;
            border-bottom: 1px solid rgba(233, 196, 106, 0.3);
            background: linear-gradient(to bottom, rgba(255,255,255,0.8), transparent);
          }

          .print-header h1 {
            font-family: 'Playfair Display', serif;
            font-size: 42px;
            font-weight: 700;
            color: #1D3557;
            letter-spacing: 0.02em;
            margin-bottom: 8px;
          }

          .print-header .subtitle {
            font-size: 16px;
            color: #64748B;
            font-weight: 300;
            letter-spacing: 0.05em;
          }

          .print-header .divider {
            width: 80px;
            height: 2px;
            background: linear-gradient(to right, transparent, #E9C46A, transparent);
            margin: 16px auto 8px;
          }

          .print-header .stats {
            font-size: 13px;
            color: #94A3B8;
            margin-top: 8px;
          }

          .tables-area {
            position: relative;
            min-height: ${canvasH - 200}px;
            padding: 20px;
          }

          .table-card {
            position: absolute;
            width: ${tableCardW}px;
            border-radius: 16px;
            background: white;
            border: 1px solid rgba(233, 196, 106, 0.4);
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
            overflow: hidden;
          }

          .table-card-round {
            border-radius: 24px;
          }

          .table-header {
            padding: 12px 16px;
            background: linear-gradient(135deg, #1D3557, #264673);
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
          }

          .table-name {
            font-family: 'Playfair Display', serif;
            font-size: 16px;
            font-weight: 600;
          }

          .table-count {
            font-size: 12px;
            opacity: 0.8;
            background: rgba(255,255,255,0.15);
            padding: 2px 10px;
            border-radius: 20px;
          }

          .table-guests {
            padding: 10px 16px 14px;
          }

          .guest-row {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 5px 0;
            border-bottom: 1px solid #F1F5F9;
            font-size: 13px;
          }

          .guest-row:last-child {
            border-bottom: none;
          }

          .guest-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #E9C46A;
            flex-shrink: 0;
          }

          .guest-name {
            font-weight: 500;
            color: #334155;
          }

          .guest-group {
            font-size: 11px;
            color: #94A3B8;
            margin-left: auto;
          }

          .empty-table {
            padding: 16px;
            text-align: center;
            color: #CBD5E1;
            font-style: italic;
            font-size: 13px;
          }

          .unseated-section {
            margin: 20px ${padding}px 30px;
            padding: 16px 20px;
            background: rgba(251, 191, 36, 0.06);
            border: 1px solid rgba(251, 191, 36, 0.2);
            border-radius: 12px;
          }

          .unseated-title {
            font-family: 'Playfair Display', serif;
            font-size: 14px;
            font-weight: 600;
            color: #92400E;
            margin-bottom: 10px;
          }

          .unseated-list {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
          }

          .unseated-chip {
            font-size: 12px;
            padding: 4px 12px;
            background: white;
            border: 1px solid rgba(251, 191, 36, 0.3);
            border-radius: 20px;
            color: #78350F;
          }

          .print-footer {
            text-align: center;
            padding: 16px;
            font-size: 11px;
            color: #CBD5E1;
            letter-spacing: 0.05em;
          }

          @media print {
            body { background: white; }
            .no-print { display: none !important; }
            .print-canvas { border: none; border-radius: 0; }
          }
        </style>
      </head>
      <body>
        ${printContent.innerHTML}
        <script>
          window.onload = function() {
            setTimeout(function() { window.print(); window.close(); }, 400);
          };
        </script>
      </body>
      </html>
    `);
    printWindow.document.close();
  }, [coupleName, canvasW, canvasH, padding, tableCardW]);

  return (
    <div className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm flex flex-col">
      {/* Toolbar */}
      <div className="flex-shrink-0 bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border-b border-slate-200 dark:border-slate-700 px-6 py-3 flex items-center justify-between no-print">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            Print Preview
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Banner-ready layout ({tables.length} tables, {seatedCount} seated)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handlePrint}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-xl transition-colors"
          >
            <Printer className="w-4 h-4" />
            Print / Save as PDF
          </button>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Scrollable preview area */}
      <div className="flex-1 overflow-auto bg-slate-100 dark:bg-slate-800 p-8">
        <div className="mx-auto" style={{ maxWidth: canvasW + 40 }}>
          {/* The printable content */}
          <div ref={printRef}>
            <div className="print-canvas" style={{ width: canvasW, minHeight: canvasH, position: 'relative', background: 'linear-gradient(135deg, #FFF5F5 0%, #F8FAFC 40%, #F0FDFA 100%)', border: '2px solid #E9C46A', borderRadius: 16, overflow: 'hidden' }}>
              {/* Decorative corner accents */}
              <div style={{ position: 'absolute', top: 12, left: 12, width: 60, height: 60, borderTop: '3px solid #E9C46A', borderLeft: '3px solid #E9C46A', borderRadius: '8px 0 0 0', opacity: 0.5 }} />
              <div style={{ position: 'absolute', top: 12, right: 12, width: 60, height: 60, borderTop: '3px solid #E9C46A', borderRight: '3px solid #E9C46A', borderRadius: '0 8px 0 0', opacity: 0.5 }} />
              <div style={{ position: 'absolute', bottom: 12, left: 12, width: 60, height: 60, borderBottom: '3px solid #E9C46A', borderLeft: '3px solid #E9C46A', borderRadius: '0 0 0 8px', opacity: 0.5 }} />
              <div style={{ position: 'absolute', bottom: 12, right: 12, width: 60, height: 60, borderBottom: '3px solid #E9C46A', borderRight: '3px solid #E9C46A', borderRadius: '0 0 8px 0', opacity: 0.5 }} />

              {/* Header */}
              <div style={{ textAlign: 'center', padding: '40px 20px 30px', borderBottom: '1px solid rgba(233,196,106,0.3)', background: 'linear-gradient(to bottom, rgba(255,255,255,0.8), transparent)' }}>
                <h1 style={{ fontFamily: "'Playfair Display', serif", fontSize: 42, fontWeight: 700, color: '#1D3557', letterSpacing: '0.02em', marginBottom: 8 }}>
                  {coupleName}
                </h1>
                <div style={{ width: 80, height: 2, background: 'linear-gradient(to right, transparent, #E9C46A, transparent)', margin: '12px auto' }} />
                <p style={{ fontSize: 16, color: '#64748B', fontWeight: 300, letterSpacing: '0.05em' }}>
                  Seating Arrangement
                </p>
                <p style={{ fontSize: 13, color: '#94A3B8', marginTop: 8 }}>
                  {weddingDate} &bull; {tables.length} Tables &bull; {seatedCount} Guests Seated
                </p>
              </div>

              {/* Tables positioned on canvas */}
              <div style={{ position: 'relative', minHeight: canvasH - 200, padding: 20 }}>
                {tables.map((table) => {
                  const tableGuests = guestsByTable(table.id);
                  const isRound = table.shape === 'round';

                  return (
                    <div
                      key={table.id}
                      style={{
                        position: 'absolute',
                        left: table.x,
                        top: table.y,
                        width: tableCardW,
                        borderRadius: isRound ? 24 : 16,
                        background: 'white',
                        border: '1px solid rgba(233,196,106,0.4)',
                        boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
                        overflow: 'hidden',
                      }}
                    >
                      {/* Table header */}
                      <div
                        style={{
                          padding: '12px 16px',
                          background: 'linear-gradient(135deg, #1D3557, #264673)',
                          color: 'white',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span style={{ fontFamily: "'Playfair Display', serif", fontSize: 16, fontWeight: 600 }}>
                          {table.name}
                        </span>
                        <span style={{ fontSize: 12, opacity: 0.8, background: 'rgba(255,255,255,0.15)', padding: '2px 10px', borderRadius: 20 }}>
                          {tableGuests.length}/{table.capacity}
                        </span>
                      </div>

                      {/* Guest list */}
                      <div style={{ padding: '10px 16px 14px' }}>
                        {tableGuests.length > 0 ? (
                          tableGuests.map((guest) => (
                            <div
                              key={guest.id}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '5px 0',
                                borderBottom: '1px solid #F1F5F9',
                                fontSize: 13,
                              }}
                            >
                              <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#E9C46A', flexShrink: 0 }} />
                              <span style={{ fontWeight: 500, color: '#334155' }}>{guest.name}</span>
                              {guest.group_id && (
                                <span style={{ fontSize: 11, color: '#94A3B8', marginLeft: 'auto' }}>
                                  {guest.group_id}
                                </span>
                              )}
                            </div>
                          ))
                        ) : (
                          <div style={{ padding: 16, textAlign: 'center', color: '#CBD5E1', fontStyle: 'italic', fontSize: 13 }}>
                            No guests assigned
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Unseated guests section */}
              {unseatedGuests.length > 0 && (
                <div style={{ margin: `20px ${padding}px 30px`, padding: '16px 20px', background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: 12 }}>
                  <p style={{ fontFamily: "'Playfair Display', serif", fontSize: 14, fontWeight: 600, color: '#92400E', marginBottom: 10 }}>
                    Awaiting Seating ({unseatedGuests.length})
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {unseatedGuests.map((g) => (
                      <span key={g.id} style={{ fontSize: 12, padding: '4px 12px', background: 'white', border: '1px solid rgba(251,191,36,0.3)', borderRadius: 20, color: '#78350F' }}>
                        {g.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Footer */}
              <div style={{ textAlign: 'center', padding: 16, fontSize: 11, color: '#CBD5E1', letterSpacing: '0.05em' }}>
                The Special Wedding &bull; Crafted with care
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
