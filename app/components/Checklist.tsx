'use client';

import React, { useState, useEffect } from 'react';

interface ChecklistItem {
  id: string;
  text: string;
  completed: boolean;
}

interface ChecklistProps {
  weddingId: string;
  token: string;
}

export default function Checklist({ weddingId, token }: ChecklistProps) {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchChecklist = async () => {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
        const response = await fetch(`${baseUrl}/admin/weddings/${weddingId}/checklist`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setItems(data);
        } else {
          setError('Failed to fetch checklist');
        }
      } catch (error) {
        setError('Failed to fetch checklist');
      } finally {
        setLoading(false);
      }
    };

    fetchChecklist();
  }, [weddingId, token]);

  const handleToggle = async (itemId: string) => {
    const item = items.find(i => i.id === itemId);
    if (!item) return;

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      await fetch(`${baseUrl}/admin/weddings/${weddingId}/checklist/${itemId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ completed: !item.completed }),
      });

      setItems(items.map(i => (i.id === itemId ? { ...i, completed: !i.completed } : i)));
    } catch (error) {
      setError('Failed to update checklist item');
    }
  };

  if (loading) {
    return <div>Loading checklist...</div>;
  }

  if (error) {
    return <div className="text-red-500">{error}</div>;
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Wedding Checklist</h2>
      <ul className="space-y-3">
        {items.map(item => (
          <li key={item.id} className="flex items-center">
            <input
              type="checkbox"
              checked={item.completed}
              onChange={() => handleToggle(item.id)}
              className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <label
              className={`ml-3 block text-sm font-medium ${
                item.completed ? 'text-gray-500 line-through' : 'text-gray-700'
              }`}
            >
              {item.text}
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}
