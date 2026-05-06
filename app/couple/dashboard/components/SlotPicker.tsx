'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import {
  AvailabilitySlot,
  bookMeeting,
  getAvailability,
} from '@/couple/lib/calendarApi';

interface SlotPickerProps {
  durationMinutes?: number;
  defaultStaffId?: string;
}

function generateIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `couple-book-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatSlot(slot: AvailabilitySlot): string {
  const start = new Date(slot.start);
  const end = new Date(slot.end);
  const dateText = start.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
  const startText = start.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  });
  const endText = end.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  });
  return `${dateText} • ${startText} – ${endText}`;
}

export default function SlotPicker({
  durationMinutes = 30,
  defaultStaffId,
}: SlotPickerProps) {
  const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AvailabilitySlot | null>(null);
  // Frozen for the lifetime of the current selection so retries with the same
  // slot replay against the same idempotency record on the server.
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [title, setTitle] = useState('Planner check-in');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const browserTimezone = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
      return 'UTC';
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getAvailability({
          durationMinutes,
          staffId: defaultStaffId,
        });
        if (!cancelled) setSlots(data.slots);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load availability');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [durationMinutes, defaultStaffId]);

  const handleBook = async () => {
    if (!selected || !idempotencyKey) return;
    setSubmitting(true);
    try {
      await bookMeeting({
        staff_id: selected.staff_id,
        start: selected.start,
        end: selected.end,
        title,
        notes: notes || undefined,
        timezone: browserTimezone,
        idempotency_key: idempotencyKey,
      });
      toast.success('Meeting booked. Check your email for the calendar invite.');
      setSlots((current) =>
        current.filter((s) => !(s.start === selected.start && s.staff_id === selected.staff_id))
      );
      setSelected(null);
      setIdempotencyKey(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to book meeting');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSelectSlot = (slot: AvailabilitySlot) => {
    setSelected(slot);
    setIdempotencyKey(generateIdempotencyKey());
  };

  const handleCancelSelection = () => {
    setSelected(null);
    setIdempotencyKey(null);
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Book a meeting with your planner
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Pick any free slot. Times are shown in your local timezone ({browserTimezone}).
        </p>
      </div>

      {loading && (
        <p className="text-sm text-slate-500 dark:text-slate-400">Loading availability...</p>
      )}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          {error}
        </div>
      )}
      {!loading && !error && slots.length === 0 && (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No openings in the next 60 days. Try again later or message your planner.
        </p>
      )}

      <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {slots.map((slot) => {
          const isSelected =
            !!selected && selected.start === slot.start && selected.staff_id === slot.staff_id;
          return (
            <li key={`${slot.staff_id}-${slot.start}`}>
              <button
                onClick={() => handleSelectSlot(slot)}
                className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                  isSelected
                    ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700/60'
                }`}
              >
                <div className="font-medium">{formatSlot(slot)}</div>
                {slot.staff_email && (
                  <div className="mt-1 text-xs opacity-75">with {slot.staff_email}</div>
                )}
              </button>
            </li>
          );
        })}
      </ul>

      {selected && (
        <div className="mt-6 space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/60">
          <div className="text-sm">
            <p className="font-medium text-slate-900 dark:text-slate-100">Confirm booking</p>
            <p className="mt-1 text-slate-500 dark:text-slate-400">{formatSlot(selected)}</p>
          </div>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-slate-200">Title</span>
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-slate-200">
              Notes (optional)
            </span>
            <textarea
              rows={3}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>
          <div className="flex gap-2">
            <button
              onClick={handleBook}
              disabled={submitting || !title}
              className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
            >
              {submitting ? 'Booking...' : 'Confirm booking'}
            </button>
            <button
              onClick={handleCancelSelection}
              disabled={submitting}
              className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
