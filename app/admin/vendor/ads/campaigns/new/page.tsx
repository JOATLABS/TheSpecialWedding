'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { createSponsoredVendor, type AdPlacement } from '@/services/advertisingApi';
import {
  ChevronRight,
  ChevronLeft,
  AlertCircle,
  CheckCircle2,
  MapPin,
  Zap,
  Image as ImageIcon,
  Eye,
  Check,
} from 'lucide-react';
import { toast } from 'sonner';

// ── Types ───────────────────────────────────────────────────────
type GoalType = 'visits' | 'quotes' | 'bookings';
type PlacementType = 'vendor_rail' | 'vendor_detail' | 'milestone_module' | 'directory_boost';
type BudgetType = 'daily' | 'lifetime';
type PacingType = 'standard' | 'accelerated';
type PricingModel = 'cpc' | 'cpl' | 'fixed';

// ── Constants ───────────────────────────────────────────────────

const WIZARD_STEPS = [
  { id: 1, title: 'Goal', description: 'What do you want to achieve?' },
  { id: 2, title: 'Targeting', description: 'Select placements and targeting' },
  { id: 3, title: 'Budget', description: 'Set your spending limits and schedule' },
  { id: 4, title: 'Pricing', description: 'Choose your pricing model' },
  { id: 5, title: 'Creative', description: 'Create your ad content' },
  { id: 6, title: 'Review', description: 'Review and submit for approval' },
];

const GOAL_OPTIONS: Array<{ value: GoalType; label: string; description: string; icon: string }> = [
  { value: 'visits', label: 'Get profile visits', description: 'Drive planners to view your profile and learn about your services', icon: '👁' },
  { value: 'quotes', label: 'Get quote requests', description: 'Generate quote requests directly from interested planners', icon: '💌' },
  { value: 'bookings', label: 'Boost bookings', description: 'Drive direct bookings and grow your wedding business', icon: '📅' },
];

const PLACEMENT_OPTIONS: Array<{ value: PlacementType; label: string; description: string }> = [
  { value: 'vendor_rail', label: 'Vendor Rail', description: 'Sidebar rail on the planner dashboard' },
  { value: 'vendor_detail', label: 'Vendor Detail', description: 'Featured on vendor profile pages' },
  { value: 'milestone_module', label: 'Milestone Module', description: 'Shown on wedding milestone pages' },
  { value: 'directory_boost', label: 'Directory Boost', description: 'Boosted card at top of the vendor directory' },
];

const CATEGORY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'photographer', label: 'Photography' },
  { value: 'catering', label: 'Catering' },
  { value: 'venue', label: 'Venue' },
  { value: 'florist', label: 'Floral Design' },
  { value: 'dj', label: 'Music & DJ' },
  { value: 'decorations', label: 'Decorations' },
  { value: 'cake_desserts', label: 'Cake & Desserts' },
  { value: 'invitations', label: 'Invitations' },
  { value: 'beauty_hair', label: 'Beauty & Hair' },
  { value: 'other', label: 'Other' },
];

const PRICING_OPTIONS: Array<{ value: PricingModel; label: string; description: string; badge?: string }> = [
  { value: 'cpc', label: 'Cost per Click (CPC)', description: 'Pay only when a planner clicks your ad' },
  { value: 'cpl', label: 'Cost per Lead (CPL)', description: 'Pay only when a planner submits a quote request' },
  { value: 'fixed', label: 'Fixed Monthly Slot', description: 'Reserved placement for a fixed monthly fee', badge: 'Premium' },
];

// ── Main Component ──────────────────────────────────────────────

export default function CampaignWizardPage() {
  const router = useRouter();
  const { token, userProfile } = useAdmin();

  // Wizard navigation
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: Goal
  const [goal, setGoal] = useState<GoalType | null>(null);

  // Step 2: Targeting
  const [selectedPlacements, setSelectedPlacements] = useState<PlacementType[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [region, setRegion] = useState('');
  const [city, setCity] = useState('');

  // Step 3: Budget & Schedule
  const [budgetType, setBudgetType] = useState<BudgetType>('daily');
  const [dailyBudget, setDailyBudget] = useState('50');
  const [lifetimeBudget, setLifetimeBudget] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [pacing, setPacing] = useState<PacingType>('standard');

  // Step 4: Pricing
  const [pricingModel, setPricingModel] = useState<PricingModel>('cpc');
  const [cpcBid, setCpcBid] = useState('1.50');
  const [cplBid, setCplBid] = useState('25.00');

  // Step 5: Creative
  const [imageUrl, setImageUrl] = useState('');
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [offer, setOffer] = useState('');
  const [cta, setCta] = useState('Get Quote');

  // Auth check
  useEffect(() => {
    if (!token) { router.push('/admin/login'); return; }
    if (!userProfile?.is_vendor) { router.push('/admin'); return; }
  }, [token, router, userProfile?.is_vendor]);

  // Estimated totals
  const estimatedDays = useMemo(() => {
    if (!startDate || !endDate) return 0;
    const diff = new Date(endDate).getTime() - new Date(startDate).getTime();
    return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
  }, [startDate, endDate]);

  const estimatedTotalSpend = useMemo(() => {
    if (budgetType === 'lifetime' && lifetimeBudget) return parseFloat(lifetimeBudget);
    if (dailyBudget && estimatedDays > 0) return parseFloat(dailyBudget) * estimatedDays;
    return 0;
  }, [budgetType, dailyBudget, lifetimeBudget, estimatedDays]);

  // Validation
  const isStepValid = (): boolean => {
    switch (currentStep) {
      case 1: return goal !== null;
      case 2: return selectedPlacements.length > 0 && selectedCategories.length > 0;
      case 3: {
        const budgetValid = budgetType === 'daily' ? (dailyBudget !== '' && parseFloat(dailyBudget) > 0) : (lifetimeBudget !== '' && parseFloat(lifetimeBudget) > 0);
        const datesValid = !startDate || !endDate || new Date(endDate) >= new Date(startDate);
        return budgetValid && datesValid;
      }
      case 4: return pricingModel !== null;
      case 5: return headline.trim() !== '';
      case 6: return true;
      default: return false;
    }
  };

  const handleNext = () => {
    if (isStepValid() && currentStep < WIZARD_STEPS.length) {
      setError(null);
      setCurrentStep(currentStep + 1);
    } else if (!isStepValid()) {
      setError('Please fill in all required fields on this step');
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) { setError(null); setCurrentStep(currentStep - 1); }
  };

  const togglePlacement = (p: PlacementType) =>
    setSelectedPlacements(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]);

  const toggleCategory = (c: string) =>
    setSelectedCategories(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]);

  const handleSubmit = async () => {
    if (!token || !userProfile?.user_data?.vendor_id) {
      toast.error('Unable to create campaign. Please check your profile.');
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);

      const promises = selectedPlacements.map((placement) =>
        createSponsoredVendor(token, {
          vendor_profile_id: userProfile.user_data.vendor_id,
          placement: placement as AdPlacement,
          priority: 1,
          headline,
          description,
          is_active: true,
          start_date: startDate || new Date().toISOString().split('T')[0],
          end_date: endDate,
          target_categories: selectedCategories,
          target_wedding_stages: [],
          metadata: {
            image_url: imageUrl,
            offer_text: offer,
            cta_text: cta,
            goal,
            budget_type: budgetType,
            daily_budget: budgetType === 'daily' ? parseFloat(dailyBudget) : undefined,
            lifetime_budget: lifetimeBudget ? parseFloat(lifetimeBudget) : undefined,
            pacing,
            pricing_model: pricingModel,
            cpc_bid: pricingModel === 'cpc' ? parseFloat(cpcBid) : undefined,
            cpl_bid: pricingModel === 'cpl' ? parseFloat(cplBid) : undefined,
            region: region || undefined,
            city: city || undefined,
          },
        })
      );

      await Promise.all(promises);
      toast.success('Campaign submitted for review!');
      router.push('/admin/vendor/ads');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create campaign';
      setError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Shared card style helper ──
  const cardClass = (selected: boolean) =>
    `flex-1 p-3 rounded-lg border-2 cursor-pointer transition-all text-left ${
      selected
        ? 'border-wedding-sage bg-wedding-sage/5'
        : 'border-gray-200 hover:border-wedding-sage/50'
    }`;

  // ── Render ──────────────────────────────────────────────────

  return (
    <div className="max-w-3xl mx-auto py-6">
      {/* Header */}
      <h2 className="text-[22px] font-extrabold text-wedding-navy mb-6">Create New Campaign</h2>

      {/* ── Wizard Step Indicator (matching mockup) ── */}
      <div className="flex items-center gap-0 mb-8" role="navigation" aria-label="Campaign creation steps">
        {WIZARD_STEPS.map((step, i) => {
          const isCompleted = currentStep > step.id;
          const isActive = currentStep === step.id;
          const isFuture = currentStep < step.id;

          return (
            <React.Fragment key={step.id}>
              <div className="flex flex-col items-center" style={{ minWidth: '60px' }}>
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-bold transition-colors ${
                    isCompleted ? 'bg-wedding-sage text-white' :
                    isActive ? 'bg-wedding-navy text-white' :
                    'bg-gray-200 text-gray-500'
                  }`}
                  aria-current={isActive ? 'step' : undefined}
                >
                  {isCompleted ? <Check size={14} /> : step.id}
                </div>
                <span className={`text-[10px] mt-1 font-medium ${
                  isActive ? 'text-wedding-navy' : isCompleted ? 'text-wedding-sage' : 'text-gray-400'
                }`}>
                  {step.title}
                </span>
              </div>
              {i < WIZARD_STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-1 mt-[-12px] ${isCompleted ? 'bg-wedding-sage' : 'bg-gray-200'}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 flex items-center gap-2 text-sm">
          <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
          <p className="text-red-800 font-medium">{error}</p>
        </div>
      )}

      {/* ── Wizard Body ── */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
        <h3 className="text-[16px] font-bold text-wedding-navy mb-1">
          Step {currentStep}: {WIZARD_STEPS[currentStep - 1].title}
        </h3>
        <p className="text-[12px] text-gray-500 mb-6">{WIZARD_STEPS[currentStep - 1].description}</p>

        {/* ─── STEP 1: Goal ─── */}
        {currentStep === 1 && (
          <div className="space-y-3">
            {GOAL_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setGoal(opt.value)}
                className={cardClass(goal === opt.value)}
                aria-label={`Goal: ${opt.label}`}
                aria-pressed={goal === opt.value}
              >
                <div className="flex items-start gap-3">
                  <span className="text-[24px]" aria-hidden="true">{opt.icon}</span>
                  <div>
                    <p className="font-bold text-[14px] text-wedding-navy">{opt.label}</p>
                    <p className="text-[12px] text-gray-500 mt-0.5">{opt.description}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* ─── STEP 2: Targeting ─── */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div>
              <h4 className="font-bold text-[13px] text-wedding-navy mb-3 flex items-center gap-2">
                <MapPin className="w-4 h-4" /> Placements
              </h4>
              <div className="grid grid-cols-2 gap-2">
                {PLACEMENT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => togglePlacement(opt.value)}
                    className={cardClass(selectedPlacements.includes(opt.value))}
                    aria-label={`Placement: ${opt.label}`}
                    aria-pressed={selectedPlacements.includes(opt.value)}
                  >
                    <p className="font-semibold text-[12px] text-wedding-navy">{opt.label}</p>
                    <p className="text-[11px] text-gray-500 mt-0.5">{opt.description}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[12px] font-semibold text-wedding-navy mb-1.5">Region/State</label>
                <input
                  type="text"
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  placeholder="e.g., Texas"
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
                />
              </div>
              <div>
                <label className="block text-[12px] font-semibold text-wedding-navy mb-1.5">City</label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="e.g., Austin"
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
                />
              </div>
            </div>

            <div>
              <h4 className="font-bold text-[13px] text-wedding-navy mb-2">Service Categories</h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {CATEGORY_OPTIONS.map((cat) => (
                  <button
                    key={cat.value}
                    onClick={() => toggleCategory(cat.value)}
                    aria-label={`Category: ${cat.label}`}
                    aria-pressed={selectedCategories.includes(cat.value)}
                    className={`px-3 py-2 rounded-lg text-[12px] font-medium border transition-colors ${
                      selectedCategories.includes(cat.value)
                        ? 'border-wedding-sage bg-wedding-sage/10 text-wedding-navy'
                        : 'border-gray-200 text-gray-600 hover:border-wedding-sage/50'
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ─── STEP 3: Budget & Schedule ─── */}
        {currentStep === 3 && (
          <div className="space-y-6">
            {/* Budget Type Cards */}
            <div>
              <label className="block text-[12px] font-semibold text-wedding-navy mb-2">Budget Type</label>
              <div className="flex gap-2">
                <button onClick={() => setBudgetType('daily')} className={cardClass(budgetType === 'daily')} aria-label="Budget type: Daily" aria-pressed={budgetType === 'daily'}>
                  <p className="font-bold text-[13px] text-wedding-navy">Daily Budget</p>
                  <p className="text-[11px] text-gray-500 mt-0.5">Spend up to this amount each day</p>
                </button>
                <button onClick={() => setBudgetType('lifetime')} className={cardClass(budgetType === 'lifetime')} aria-label="Budget type: Lifetime" aria-pressed={budgetType === 'lifetime'}>
                  <p className="font-bold text-[13px] text-wedding-navy">Lifetime Budget</p>
                  <p className="text-[11px] text-gray-500 mt-0.5">Total spend for entire campaign</p>
                </button>
              </div>
            </div>

            {/* Budget Amount */}
            <div>
              <label className="block text-[12px] font-semibold text-wedding-navy mb-1">
                {budgetType === 'daily' ? 'Daily Budget Amount' : 'Lifetime Budget Amount'}
              </label>
              <p className="text-[11px] text-gray-400 mb-2">
                {budgetType === 'daily' ? 'Suggested: $25–$75/day for your category' : 'Total amount for the entire campaign duration'}
              </p>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-wedding-navy font-bold">$</span>
                <input
                  type="number"
                  value={budgetType === 'daily' ? dailyBudget : lifetimeBudget}
                  onChange={(e) => budgetType === 'daily' ? setDailyBudget(e.target.value) : setLifetimeBudget(e.target.value)}
                  min="1"
                  step="5"
                  className="w-full rounded-lg border border-gray-200 pl-7 pr-3 py-2.5 text-[20px] font-bold text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
                />
              </div>
              {budgetType === 'daily' && dailyBudget && (
                <p className="text-[11px] text-gray-400 mt-1">
                  Estimated {Math.round(parseFloat(dailyBudget) / 0.6)}–{Math.round(parseFloat(dailyBudget) / 0.3)} impressions/day · {Math.round(parseFloat(dailyBudget) / 12)}–{Math.round(parseFloat(dailyBudget) / 8)} clicks/day
                </p>
              )}
            </div>

            {/* Date Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[12px] font-semibold text-wedding-navy mb-1.5">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
                />
              </div>
              <div>
                <label className="block text-[12px] font-semibold text-wedding-navy mb-1.5">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
                />
                {estimatedDays > 0 && (
                  <p className="text-[11px] text-gray-400 mt-1">
                    {estimatedDays} days · Estimated total spend: ${estimatedTotalSpend.toLocaleString()}
                  </p>
                )}
              </div>
            </div>

            {/* Pacing Strategy */}
            <div>
              <label className="block text-[12px] font-semibold text-wedding-navy mb-2">Pacing Strategy</label>
              <div className="flex gap-2">
                <button onClick={() => setPacing('standard')} className={cardClass(pacing === 'standard')} aria-label="Pacing: Standard" aria-pressed={pacing === 'standard'}>
                  <p className="font-bold text-[13px] text-wedding-navy">Standard</p>
                  <p className="text-[11px] text-gray-500 mt-0.5">Spread budget evenly throughout each day for consistent visibility</p>
                </button>
                <button onClick={() => setPacing('accelerated')} className={cardClass(pacing === 'accelerated')} aria-label="Pacing: Accelerated" aria-pressed={pacing === 'accelerated'}>
                  <p className="font-bold text-[13px] text-wedding-navy">Accelerated</p>
                  <p className="text-[11px] text-gray-500 mt-0.5">Spend budget as quickly as possible to maximize reach early</p>
                </button>
              </div>
            </div>

            {/* Budget Recommendation Box */}
            <div className="bg-wedding-sage/5 border border-wedding-sage/15 rounded-lg p-3.5">
              <p className="text-[12px] font-bold text-wedding-navy mb-1">Budget Recommendation</p>
              <p className="text-[12px] text-gray-600 leading-relaxed">
                Based on competition in your category, we recommend a daily budget of <strong>$40–$75</strong> to maintain consistent visibility.
                Similar vendors average <strong>$52/day</strong> with a cost per lead of <strong>$22–$35</strong>.
              </p>
            </div>
          </div>
        )}

        {/* ─── STEP 4: Pricing ─── */}
        {currentStep === 4 && (
          <div className="space-y-6">
            <div className="space-y-3">
              {PRICING_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setPricingModel(opt.value)}
                  className={cardClass(pricingModel === opt.value)}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-bold text-[14px] text-wedding-navy">{opt.label}</p>
                      <p className="text-[12px] text-gray-500 mt-0.5">{opt.description}</p>
                    </div>
                    {opt.badge && (
                      <span className="text-[9px] font-bold uppercase tracking-wide bg-wedding-gold/20 text-wedding-gold px-2 py-0.5 rounded-full">
                        {opt.badge}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>

            {/* Bid Amount */}
            {pricingModel === 'cpc' && (
              <div>
                <label className="block text-[12px] font-semibold text-wedding-navy mb-1">CPC Bid</label>
                <p className="text-[11px] text-gray-400 mb-2">Suggested: $1.00–$3.00 for your category</p>
                <div className="relative max-w-[200px]">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-wedding-navy font-bold">$</span>
                  <input
                    type="number"
                    value={cpcBid}
                    onChange={(e) => setCpcBid(e.target.value)}
                    min="0.10"
                    step="0.10"
                    className="w-full rounded-lg border border-gray-200 pl-7 pr-3 py-2 text-[16px] font-bold text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
                  />
                </div>
              </div>
            )}

            {pricingModel === 'cpl' && (
              <div>
                <label className="block text-[12px] font-semibold text-wedding-navy mb-1">CPL Bid</label>
                <p className="text-[11px] text-gray-400 mb-2">Suggested: $20–$40 for your category</p>
                <div className="relative max-w-[200px]">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-wedding-navy font-bold">$</span>
                  <input
                    type="number"
                    value={cplBid}
                    onChange={(e) => setCplBid(e.target.value)}
                    min="1"
                    step="1"
                    className="w-full rounded-lg border border-gray-200 pl-7 pr-3 py-2 text-[16px] font-bold text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
                  />
                </div>
              </div>
            )}

            {pricingModel === 'fixed' && (
              <div className="bg-wedding-gold/5 border border-wedding-gold/20 rounded-lg p-3.5">
                <p className="text-[12px] font-bold text-wedding-navy mb-1">Fixed Monthly Slot</p>
                <p className="text-[12px] text-gray-600 leading-relaxed">
                  Contact us for fixed monthly slot pricing. Slots guarantee your placement in a specific position for the entire month.
                </p>
              </div>
            )}
          </div>
        )}

        {/* ─── STEP 5: Creative ─── */}
        {currentStep === 5 && (
          <div className="space-y-5">
            <div>
              <label className="block text-[12px] font-semibold text-wedding-navy mb-1.5 flex items-center gap-1.5">
                <ImageIcon className="w-3.5 h-3.5" /> Image URL
              </label>
              <input
                type="url"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="https://example.com/image.jpg"
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
              />
              <p className="text-[10px] text-gray-400 mt-1">Best size: 1200x628px, max 5MB</p>
            </div>

            <div>
              <label className="block text-[12px] font-semibold text-wedding-navy mb-1.5">Headline *</label>
              <input
                type="text"
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                placeholder="e.g., Award-Winning Wedding Photography"
                maxLength={60}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
              />
              <p className="text-[10px] text-gray-400 mt-1">{headline.length}/60 characters</p>
            </div>

            <div>
              <label className="block text-[12px] font-semibold text-wedding-navy mb-1.5">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Tell planners about your service..."
                maxLength={150}
                rows={3}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage resize-none"
              />
              <p className="text-[10px] text-gray-400 mt-1">{description.length}/150 characters</p>
            </div>

            <div>
              <label className="block text-[12px] font-semibold text-wedding-navy mb-1.5">Special Offer (Optional)</label>
              <input
                type="text"
                value={offer}
                onChange={(e) => setOffer(e.target.value)}
                placeholder="e.g., 10% off for bookings this month"
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
              />
            </div>

            <div>
              <label className="block text-[12px] font-semibold text-wedding-navy mb-1.5">Call-to-Action</label>
              <select
                value={cta}
                onChange={(e) => setCta(e.target.value)}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-wedding-navy focus:border-wedding-sage focus:outline-none focus:ring-1 focus:ring-wedding-sage"
              >
                <option>Get Quote</option>
                <option>Learn More</option>
                <option>View Profile</option>
                <option>Book Now</option>
                <option>Contact Me</option>
              </select>
            </div>

            {/* Preview */}
            <div className="pt-5 border-t border-gray-200">
              <h4 className="font-bold text-[13px] text-wedding-navy mb-3 flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5" /> Preview
              </h4>
              <div className="rounded-xl border border-gray-200 bg-gray-50 overflow-hidden max-w-sm">
                {imageUrl && (
                  <img src={imageUrl} alt="Preview" className="w-full h-32 object-cover" onError={() => null} />
                )}
                <div className="p-3">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide rounded bg-amber-50 text-amber-700 mb-1.5">
                    ✦ Sponsored
                  </span>
                  <h5 className="font-bold text-[14px] text-wedding-navy">{headline || 'Your Headline'}</h5>
                  {description && <p className="text-[12px] text-gray-500 mt-1">{description}</p>}
                  {offer && <p className="text-[11px] font-semibold text-wedding-sage mt-2">{offer}</p>}
                  <button className="mt-2 w-full bg-wedding-sage text-white px-3 py-1.5 rounded-md text-[12px] font-semibold hover:bg-wedding-navy transition-colors min-h-[44px]">
                    {cta}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ─── STEP 6: Review ─── */}
        {currentStep === 6 && (
          <div className="space-y-4">
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 flex items-start gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-[13px] text-emerald-900">Almost there!</p>
                <p className="text-[12px] text-emerald-700 mt-0.5">Review your campaign details and submit for creative review</p>
              </div>
            </div>

            {/* Summary cards */}
            <div className="space-y-3">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Goal</p>
                <p className="font-bold text-[13px] text-wedding-navy">{GOAL_OPTIONS.find(g => g.value === goal)?.label}</p>
              </div>

              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Placements</p>
                <div className="flex flex-wrap gap-1.5">
                  {selectedPlacements.map(p => (
                    <span key={p} className="px-2 py-0.5 rounded-full bg-wedding-sage/15 text-wedding-navy text-[11px] font-medium">
                      {PLACEMENT_OPTIONS.find(opt => opt.value === p)?.label}
                    </span>
                  ))}
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Categories</p>
                <div className="flex flex-wrap gap-1.5">
                  {selectedCategories.map(c => (
                    <span key={c} className="px-2 py-0.5 rounded-full bg-gray-200 text-gray-700 text-[11px] font-medium">
                      {CATEGORY_OPTIONS.find(opt => opt.value === c)?.label || c}
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Budget</p>
                  <p className="font-bold text-[13px] text-wedding-navy">
                    ${budgetType === 'daily' ? dailyBudget : lifetimeBudget}/{budgetType === 'daily' ? 'day' : 'total'}
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Pricing</p>
                  <p className="font-bold text-[13px] text-wedding-navy">{PRICING_OPTIONS.find(p => p.value === pricingModel)?.label || pricingModel}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Pacing</p>
                  <p className="font-bold text-[13px] text-wedding-navy capitalize">{pacing}</p>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Creative</p>
                <p className="font-bold text-[13px] text-wedding-navy">{headline}</p>
                {description && <p className="text-[12px] text-gray-500 mt-0.5">{description}</p>}
                {offer && <p className="text-[11px] font-semibold text-wedding-sage mt-1">{offer}</p>}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Navigation Footer ── */}
      <div className="flex items-center justify-between pt-5 border-t border-gray-200">
        <button
          onClick={handlePrevious}
          disabled={currentStep === 1}
          className={`flex items-center gap-1.5 px-5 py-2.5 rounded-lg font-semibold text-[13px] transition-colors min-h-[44px] ${
            currentStep === 1
              ? 'text-gray-300 cursor-not-allowed'
              : 'text-gray-600 hover:text-wedding-navy hover:bg-gray-100'
          }`}
        >
          <ChevronLeft className="w-4 h-4" /> Back
        </button>

        {currentStep === WIZARD_STEPS.length ? (
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 px-8 py-2.5 rounded-lg bg-wedding-navy text-white font-semibold text-[13px] hover:bg-wedding-sage transition-colors min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Submitting...' : 'Submit for Review'}
          </button>
        ) : (
          <button
            onClick={handleNext}
            className="flex items-center gap-1.5 px-8 py-2.5 rounded-lg bg-wedding-sage text-white font-semibold text-[13px] hover:bg-wedding-navy transition-colors min-h-[44px]"
          >
            Continue to {WIZARD_STEPS[currentStep]?.title || 'Next'} <ChevronRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
