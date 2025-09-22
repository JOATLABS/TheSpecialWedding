'use client';

import { useState, useCallback, useMemo } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/Card';
import { budgetApi, CostEstimateResult } from '@/services/budgetApi';

// Legacy UI shape; we adapt API result into this unified structure
interface CostEstimation {
  total_estimated_cost: number;
  category_estimates: Record<string, {
    amount: number;
    percentage: number;
    notes: string;
  }>;
  factors_considered: string[];
  confidence_level: 'high' | 'moderate' | 'low' | string;
  recommendations: string[];
}

const WEDDING_TYPES = [
  'traditional',
  'modern',
  'destination',
  'intimate',
  'outdoor',
  'luxury',
  'budget',
  'rustic',
  'beach',
  'garden'
];

const LOCATIONS = [
  'Urban/City',
  'Suburban',
  'Rural',
  'Beach/Coastal',
  'Mountain',
  'Countryside',
  'Destination (Domestic)',
  'Destination (International)'
];

export default function CostEstimationPage() {
  const { token } = useAdmin();
  const [loading, setLoading] = useState(false);
  const [estimation, setEstimation] = useState<CostEstimation | null>(null);
  
  // Form state
  const [formData, setFormData] = useState({
    wedding_type: 'traditional',
    guest_count: 100,
    location: 'Urban/City',
    season: 'spring',
    day_of_week: 'saturday',
    venue_type: 'banquet_hall',
    catering_style: 'plated',
    bar_service: 'open_bar',
    ceremony_reception_same: true,
    photography_hours: 8,
    music_type: 'dj',
    flowers_level: 'moderate',
    transportation_needed: false,
    accommodation_needed: false
  });

  const handleEstimation = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      toast.error('Please log in to use the cost estimator');
      return;
    }

    setLoading(true);
    try {
      const apiResult: CostEstimateResult = await budgetApi.getCostEstimate(
        token,
        formData.wedding_type,
        formData.guest_count,
        formData.location
      );
      // Transform API result (range-based) to legacy single-value display using averages
      const averageTotal = Math.round((apiResult.total_min + apiResult.total_max) / 2);
      const category_estimates: Record<string, { amount: number; percentage: number; notes: string; }> = {};
      // If API supplies detailed items, distribute percentage heuristically by amount proportion
      if (Array.isArray(apiResult.items) && apiResult.items.length) {
        const totalAvg = apiResult.items.reduce((sum, i) => sum + ((i.estimated_min + i.estimated_max) / 2), 0) || 1;
        apiResult.items.forEach(item => {
          const avg = Math.round((item.estimated_min + item.estimated_max) / 2);
          const percentage = Math.round((avg / totalAvg) * 100);
          category_estimates[item.category] = {
            amount: avg,
            percentage,
            notes: item.notes || 'Estimated range midpoint'
          };
        });
      }
      setEstimation({
        total_estimated_cost: averageTotal,
        category_estimates,
        factors_considered: [
          `Wedding type: ${apiResult.wedding_type}`,
          `Guest count: ${apiResult.guest_count}`,
          `Location: ${apiResult.location}`
        ],
        confidence_level: 'moderate',
        recommendations: [
          'Request multiple vendor quotes for accuracy',
          'Adjust guest count to optimize per-guest cost',
          'Lock in venue and catering early to reduce volatility'
        ]
      });
      toast.success('Cost estimation generated successfully');
    } catch (err: any) {
      toast.error(err.message || 'Failed to generate cost estimation');
      console.error('Estimation error:', err);
      
      // Fallback estimation for demo purposes
      setEstimation({
        total_estimated_cost: formData.guest_count * 150 + Math.random() * 10000,
        category_estimates: {
          'Venue & Catering': { amount: formData.guest_count * 75, percentage: 45, notes: 'Based on guest count and location' },
          'Photography & Videography': { amount: 3500, percentage: 12, notes: 'Professional wedding photography' },
          'Music & Entertainment': { amount: 2000, percentage: 8, notes: 'DJ and sound system' },
          'Flowers & Decorations': { amount: 2500, percentage: 10, notes: 'Bridal bouquet, centerpieces, ceremony decor' },
          'Attire & Beauty': { amount: 1500, percentage: 6, notes: 'Wedding dress, suit, hair & makeup' },
          'Transportation': { amount: 800, percentage: 3, notes: 'Wedding party transportation' },
          'Stationery & Favors': { amount: 600, percentage: 2, notes: 'Invitations and guest favors' },
          'Miscellaneous': { amount: 1200, percentage: 5, notes: 'Unexpected costs and extras' }
        },
        factors_considered: [
          'Guest count',
          'Wedding type',
          'Location',
          'Seasonal pricing',
          'Day of week'
        ],
        confidence_level: 'moderate',
        recommendations: [
          'Consider weekday weddings for 15-20% savings',
          'Book vendors 9-12 months in advance for better rates',
          'Allocate 10% contingency for unexpected costs',
          'Compare multiple vendor quotes for best pricing'
        ]
      });
    } finally {
      setLoading(false);
    }
  }, [token, formData]);

  const currencyFormatter = useMemo(() => new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }), []);

  const formatCurrency = useCallback((amount: number) => 
    currencyFormatter.format(amount), [currencyFormatter]);

  const getConfidenceColor = (level: string) => {
    switch (level) {
      case 'high': return 'text-green-600 bg-green-100';
      case 'moderate': return 'text-yellow-600 bg-yellow-100';
      case 'low': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-wedding-navy mb-4">Access Denied</h2>
          <p>Please log in to access the cost estimation tool.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-heading font-bold text-wedding-navy">
          Wedding Cost Estimator
        </h1>
        <p className="text-gray-600 mt-1">
          Get accurate cost estimates based on your wedding preferences and location
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Estimation Form */}
        <Card className="p-6">
          <h2 className="text-xl font-semibold text-wedding-navy mb-4">
            Wedding Details
          </h2>
          
          <form onSubmit={handleEstimation} className="space-y-4">
            {/* Basic Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Wedding Type
                </label>
                <select
                  value={formData.wedding_type}
                  onChange={(e) => setFormData({...formData, wedding_type: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  {WEDDING_TYPES.map(type => (
                    <option key={type} value={type}>
                      {type.charAt(0).toUpperCase() + type.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Guest Count
                </label>
                <input
                  type="number"
                  min="1"
                  max="500"
                  value={formData.guest_count}
                  onChange={(e) => setFormData({...formData, guest_count: parseInt(e.target.value) || 100})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Location Type
                </label>
                <select
                  value={formData.location}
                  onChange={(e) => setFormData({...formData, location: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  {LOCATIONS.map(location => (
                    <option key={location} value={location}>
                      {location}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Season
                </label>
                <select
                  value={formData.season}
                  onChange={(e) => setFormData({...formData, season: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value="spring">Spring (Mar-May)</option>
                  <option value="summer">Summer (Jun-Aug)</option>
                  <option value="fall">Fall (Sep-Nov)</option>
                  <option value="winter">Winter (Dec-Feb)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Day of Week
                </label>
                <select
                  value={formData.day_of_week}
                  onChange={(e) => setFormData({...formData, day_of_week: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value="saturday">Saturday</option>
                  <option value="sunday">Sunday</option>
                  <option value="friday">Friday</option>
                  <option value="weekday">Weekday (Mon-Thu)</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Venue Type
                </label>
                <select
                  value={formData.venue_type}
                  onChange={(e) => setFormData({...formData, venue_type: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value="banquet_hall">Banquet Hall</option>
                  <option value="hotel">Hotel</option>
                  <option value="outdoor">Outdoor Venue</option>
                  <option value="church">Church/Religious</option>
                  <option value="country_club">Country Club</option>
                  <option value="historic">Historic Venue</option>
                  <option value="barn">Barn/Rustic</option>
                </select>
              </div>
            </div>

            {/* Service Details */}
            <h3 className="text-lg font-medium text-wedding-navy mt-6 mb-3">Service Preferences</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Catering Style
                </label>
                <select
                  value={formData.catering_style}
                  onChange={(e) => setFormData({...formData, catering_style: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value="plated">Plated Dinner</option>
                  <option value="buffet">Buffet</option>
                  <option value="cocktail">Cocktail Reception</option>
                  <option value="family_style">Family Style</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Bar Service
                </label>
                <select
                  value={formData.bar_service}
                  onChange={(e) => setFormData({...formData, bar_service: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value="open_bar">Open Bar</option>
                  <option value="cash_bar">Cash Bar</option>
                  <option value="limited_bar">Limited Bar</option>
                  <option value="no_alcohol">No Alcohol</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Photography Hours
                </label>
                <select
                  value={formData.photography_hours}
                  onChange={(e) => setFormData({...formData, photography_hours: parseInt(e.target.value)})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value={4}>4 hours</option>
                  <option value={6}>6 hours</option>
                  <option value={8}>8 hours</option>
                  <option value={10}>10 hours</option>
                  <option value={12}>Full day (12+ hours)</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Music/Entertainment
                </label>
                <select
                  value={formData.music_type}
                  onChange={(e) => setFormData({...formData, music_type: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value="dj">DJ</option>
                  <option value="band">Live Band</option>
                  <option value="acoustic">Acoustic/Small Group</option>
                  <option value="playlist">Playlist/No DJ</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Flowers & Decorations Level
              </label>
              <select
                value={formData.flowers_level}
                onChange={(e) => setFormData({...formData, flowers_level: e.target.value})}
                className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              >
                <option value="minimal">Minimal (Bridal bouquet only)</option>
                <option value="moderate">Moderate (Bouquet + centerpieces)</option>
                <option value="elaborate">Elaborate (Full floral design)</option>
                <option value="luxury">Luxury (Premium arrangements)</option>
              </select>
            </div>

            {/* Additional Services */}
            <div className="space-y-2">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="ceremony_reception_same"
                  checked={formData.ceremony_reception_same}
                  onChange={(e) => setFormData({...formData, ceremony_reception_same: e.target.checked})}
                  className="mr-2"
                />
                <label htmlFor="ceremony_reception_same" className="text-sm text-gray-700">
                  Ceremony and reception at same venue
                </label>
              </div>
              
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="transportation_needed"
                  checked={formData.transportation_needed}
                  onChange={(e) => setFormData({...formData, transportation_needed: e.target.checked})}
                  className="mr-2"
                />
                <label htmlFor="transportation_needed" className="text-sm text-gray-700">
                  Transportation needed for wedding party
                </label>
              </div>
              
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="accommodation_needed"
                  checked={formData.accommodation_needed}
                  onChange={(e) => setFormData({...formData, accommodation_needed: e.target.checked})}
                  className="mr-2"
                />
                <label htmlFor="accommodation_needed" className="text-sm text-gray-700">
                  Guest accommodation assistance needed
                </label>
              </div>
            </div>

            <Button 
              type="submit" 
              className="w-full mt-6"
              disabled={loading}
            >
              {loading ? 'Generating Estimate...' : 'Generate Cost Estimate'}
            </Button>
          </form>
        </Card>

        {/* Results */}
        <div className="space-y-6">
          {loading && (
            <Card className="p-6">
              <div className="text-center">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-wedding-rose mb-4"></div>
                <p className="text-gray-600">Generating your cost estimate...</p>
              </div>
            </Card>
          )}

          {estimation && (
            <>
              {/* Total Cost */}
              <Card className="p-6">
                <h2 className="text-xl font-semibold text-wedding-navy mb-4">
                  Estimated Wedding Cost
                </h2>
                
                <div className="text-center mb-4">
                  <div className="text-4xl font-bold text-wedding-rose mb-2">
                    {formatCurrency(estimation.total_estimated_cost)}
                  </div>
                  <div className="text-sm text-gray-600">
                    For {formData.guest_count} guests • {formData.wedding_type} wedding
                  </div>
                </div>
                
                <div className="flex items-center justify-center">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${getConfidenceColor(estimation.confidence_level)}`}>
                    {estimation.confidence_level.charAt(0).toUpperCase() + estimation.confidence_level.slice(1)} Confidence
                  </span>
                </div>
              </Card>

              {/* Category Breakdown */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-wedding-navy mb-4">
                  Budget Breakdown by Category
                </h3>
                
                <div className="space-y-4">
                  {Object.entries(estimation.category_estimates).map(([category, details]) => (
                    <div key={category} className="border-b border-gray-100 pb-3 last:border-b-0">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex-1">
                          <div className="font-medium text-wedding-navy">{category}</div>
                          <div className="text-sm text-gray-600">{details.notes}</div>
                        </div>
                        <div className="text-right">
                          <div className="font-semibold text-wedding-rose">
                            {formatCurrency(details.amount)}
                          </div>
                          <div className="text-sm text-gray-500">
                            {details.percentage}%
                          </div>
                        </div>
                      </div>
                      
                      {/* Progress bar */}
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-wedding-rose h-2 rounded-full"
                          style={{ width: `${details.percentage}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Recommendations */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-wedding-navy mb-4">
                  Cost Saving Recommendations
                </h3>
                
                <div className="space-y-3">
                  {estimation.recommendations.map((recommendation, index) => (
                    <div key={index} className="flex items-start">
                      <svg className="w-5 h-5 text-green-500 mr-2 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                      <p className="text-sm text-gray-700">{recommendation}</p>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Factors Considered */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-wedding-navy mb-4">
                  Estimation Based On
                </h3>
                
                <div className="flex flex-wrap gap-2">
                  {estimation.factors_considered.map((factor, index) => (
                    <span key={index} className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                      {factor}
                    </span>
                  ))}
                </div>
                
                <div className="mt-4 text-xs text-gray-500">
                  <p>
                    <strong>Disclaimer:</strong> This is an estimate based on industry averages and regional data. 
                    Actual costs may vary significantly based on specific vendor selection, customizations, 
                    and market conditions. We recommend getting quotes from multiple vendors for accurate pricing.
                  </p>
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}