'use client';

import { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import type { VendorQuote } from '../../types/budget';

interface VendorQuoteCardProps {
  quote: VendorQuote;
  onAccept: (quoteId: string) => void;
  onReject: (quoteId: string) => void;
  onRate: (quoteId: string, rating: number, notes?: string) => void;
  className?: string;
  showActions?: boolean;
}

export default function VendorQuoteCard({ 
  quote, 
  onAccept, 
  onReject, 
  onRate, 
  className = '',
  showActions = true
}: VendorQuoteCardProps) {
  const [showRatingModal, setShowRatingModal] = useState(false);
  const [rating, setRating] = useState(quote.rating || 0);
  const [ratingNotes, setRatingNotes] = useState(quote.notes || '');

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'accepted': return 'text-green-600 bg-green-100';
      case 'rejected': return 'text-red-600 bg-red-100';
      case 'expired': return 'text-gray-600 bg-gray-100';
      default: return 'text-yellow-600 bg-yellow-100';
    }
  };

  const isExpired = quote.valid_until && new Date(quote.valid_until) < new Date();

  const handleSubmitRating = () => {
    onRate(quote.id, rating, ratingNotes);
    setShowRatingModal(false);
  };

  const renderStars = (currentRating: number, interactive: boolean = false, onStarClick?: (rating: number) => void) => {
    return (
      <div className="flex items-center">
        {Array.from({ length: 5 }, (_, i) => (
          <svg
            key={i}
            className={`w-4 h-4 ${
              i < currentRating ? 'text-yellow-400' : 'text-gray-300'
            } ${interactive ? 'cursor-pointer hover:text-yellow-400' : ''}`}
            fill="currentColor"
            viewBox="0 0 20 20"
            onClick={() => interactive && onStarClick && onStarClick(i + 1)}
          >
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
        ))}
      </div>
    );
  };

  return (
    <>
      <Card className={`p-4 ${className}`}>
        {/* Header */}
        <div className="flex justify-between items-start mb-3">
          <div>
            <h3 className="font-semibold text-wedding-navy text-lg">
              {quote.vendor_name}
            </h3>
            <div className="text-sm text-gray-600">
              {quote.service_category.charAt(0).toUpperCase() + quote.service_category.slice(1)}
            </div>
          </div>
          
          <div className="text-right">
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(quote.status)}`}>
              {quote.status.charAt(0).toUpperCase() + quote.status.slice(1)}
            </span>
            {isExpired && (
              <div className="text-xs text-red-600 mt-1">Expired</div>
            )}
          </div>
        </div>

        {/* Quote amount */}
        <div className="mb-4">
          <div className="text-2xl font-bold text-wedding-rose">
            {formatCurrency(quote.quote_amount)}
          </div>
          {quote.valid_until && (
            <div className="text-sm text-gray-600">
              Valid until: {new Date(quote.valid_until).toLocaleDateString()}
            </div>
          )}
        </div>

        {/* Contact info */}
        {(quote.vendor_email || quote.vendor_phone) && (
          <div className="mb-4 text-sm">
            {quote.vendor_email && (
              <div className="text-gray-600">
                <span className="font-medium">Email:</span> {quote.vendor_email}
              </div>
            )}
            {quote.vendor_phone && (
              <div className="text-gray-600">
                <span className="font-medium">Phone:</span> {quote.vendor_phone}
              </div>
            )}
          </div>
        )}

        {/* Quote details */}
        {Object.keys(quote.quote_details).length > 0 && (
          <div className="mb-4">
            <h4 className="font-medium text-sm text-wedding-navy mb-2">Quote Details:</h4>
            <div className="text-sm space-y-1">
              {Object.entries(quote.quote_details).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="text-gray-600 capitalize">{key.replace(/_/g, ' ')}:</span>
                  <span className="font-medium">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Includes */}
        {quote.includes.length > 0 && (
          <div className="mb-4">
            <h4 className="font-medium text-sm text-wedding-navy mb-2">Includes:</h4>
            <ul className="text-sm space-y-1">
              {quote.includes.map((item, index) => (
                <li key={index} className="flex items-center">
                  <svg className="w-3 h-3 text-green-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Excludes */}
        {quote.excludes.length > 0 && (
          <div className="mb-4">
            <h4 className="font-medium text-sm text-wedding-navy mb-2">Excludes:</h4>
            <ul className="text-sm space-y-1">
              {quote.excludes.map((item, index) => (
                <li key={index} className="flex items-center">
                  <svg className="w-3 h-3 text-red-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Terms and conditions */}
        {quote.terms_conditions && (
          <div className="mb-4">
            <h4 className="font-medium text-sm text-wedding-navy mb-2">Terms & Conditions:</h4>
            <p className="text-sm text-gray-600 bg-gray-50 p-2 rounded">
              {quote.terms_conditions}
            </p>
          </div>
        )}

        {/* Rating display */}
        {quote.rating && (
          <div className="mb-4 p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Your Rating:</span>
              {renderStars(quote.rating)}
            </div>
            {quote.notes && (
              <p className="text-sm text-gray-600 mt-2">{quote.notes}</p>
            )}
          </div>
        )}

        {/* Action buttons */}
        {showActions && quote.status === 'pending' && !isExpired && (
          <div className="flex gap-2 mt-4 pt-4 border-t border-gray-200">
            <Button 
              onClick={() => onAccept(quote.id)}
              className="flex-1 text-sm"
            >
              Accept
            </Button>
            
            <Button 
              onClick={() => setShowRatingModal(true)}
              className="flex-1 text-sm bg-purple-600 hover:bg-purple-700"
            >
              Rate
            </Button>
            
            <Button 
              variant="danger"
              onClick={() => onReject(quote.id)}
              className="text-sm px-4"
            >
              Reject
            </Button>
          </div>
        )}

        {/* Quote dates */}
        <div className="mt-4 text-xs text-gray-500 text-center border-t border-gray-200 pt-2">
          Created: {new Date(quote.created_at).toLocaleDateString()}
          {quote.updated_at !== quote.created_at && (
            <span className="ml-2">• Updated: {new Date(quote.updated_at).toLocaleDateString()}</span>
          )}
        </div>
      </Card>

      {/* Rating Modal */}
      {showRatingModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold mb-4 text-wedding-navy">
              Rate Quote from {quote.vendor_name}
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Rating (1-5 stars)
                </label>
                <div className="flex justify-center">
                  {renderStars(rating, true, setRating)}
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notes (Optional)
                </label>
                <textarea
                  value={ratingNotes}
                  onChange={(e) => setRatingNotes(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  rows={3}
                  placeholder="Add your thoughts about this quote..."
                />
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <Button onClick={handleSubmitRating} className="flex-1">
                Submit Rating
              </Button>
              <Button 
                variant="danger" 
                onClick={() => setShowRatingModal(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}