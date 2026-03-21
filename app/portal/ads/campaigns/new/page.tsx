'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useVendorAuth } from '../../layout';
import { toast } from 'sonner';
import {
  createCampaign,
  createCreative,
  submitCampaignForReview,
  type CreateCampaignRequest,
  type CreateCreativeRequest,
  type CampaignGoal,
  type PacingStrategy,
} from '@/services/campaignAdvertisingApi';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Megaphone,
  Target,
  Image,
  DollarSign,
  Calendar,
  Send,
} from 'lucide-react';

type WizardStep = 'basics' | 'targeting' | 'creative' | 'budget' | 'schedule' | 'review';

const STEPS: { id: WizardStep; label: string; icon: React.ElementType }[] = [
  { id: 'basics', label: 'Basics', icon: Megaphone },
  { id: 'targeting', label: 'Targeting', icon: Target },
  { id: 'creative', label: 'Creative', icon: Image },
  { id: 'budget', label: 'Budget', icon: DollarSign },
  { id: 'schedule', label: 'Schedule', icon: Calendar },
  { id: 'review', label: 'Review & Submit', icon: Send },
];

const VENDOR_CATEGORIES: { value: string; label: string }[] = [
  { value: 'photographer', label: 'Photographer' },
  { value: 'videographer', label: 'Videographer' },
  { value: 'florist', label: 'Florist' },
  { value: 'caterer', label: 'Caterer' },
  { value: 'dj', label: 'DJ' },
  { value: 'live_music', label: 'Live Music' },
  { value: 'venue', label: 'Venue' },
  { value: 'wedding_planner', label: 'Wedding Planner' },
  { value: 'cake_baker', label: 'Cake & Bakery' },
  { value: 'officiant', label: 'Officiant' },
  { value: 'hair_makeup', label: 'Hair & Makeup' },
  { value: 'transportation', label: 'Transportation' },
  { value: 'rentals', label: 'Rentals' },
  { value: 'stationery', label: 'Stationery' },
  { value: 'jewelry', label: 'Jewelry' },
  { value: 'other', label: 'Other' },
];

const WEDDING_STAGES: { value: string; label: string }[] = [
  { value: 'just_engaged', label: 'Just Engaged' },
  { value: 'planning', label: 'Planning' },
  { value: 'booking_vendors', label: 'Booking Vendors' },
  { value: 'final_details', label: 'Final Details' },
  { value: 'wedding_week', label: 'Wedding Week' },
];

const GOAL_OPTIONS: { value: CampaignGoal; label: string; description: string }[] = [
  { value: 'profile_visits', label: 'Profile Visits', description: 'Drive planners to view your portfolio' },
  { value: 'quote_requests', label: 'Quote Requests', description: 'Get quote requests from interested planners' },
  { value: 'bookings', label: 'Bookings', description: 'Encourage direct bookings' },
];

export default function NewCampaignWizard() {
  const { token } = useVendorAuth();
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState<WizardStep>('basics');
  const [submitting, setSubmitting] = useState(false);

  // Campaign data
  const [campaignData, setCampaignData] = useState<CreateCampaignRequest>({
    campaign_name: '',
    campaign_description: '',
    goal: 'profile_visits',
    target_categories: [],
    target_wedding_stages: [],
    target_placements: [],
    target_regions: [],
    daily_budget: 0,
    total_budget: 0,
    pacing_strategy: 'even',
    vendor_category: '',
    vendor_service_area: '',
  });

  // Creative data
  const [creativeData, setCreativeData] = useState<CreateCreativeRequest>({
    headline: '',
    description: '',
    offer: '',
    call_to_action: 'View Portfolio',
    is_primary: true,
  });

  const stepIndex = STEPS.findIndex((s) => s.id === currentStep);
  const canGoBack = stepIndex > 0;
  const canGoForward = stepIndex < STEPS.length - 1;

  const goNext = () => {
    if (canGoForward) setCurrentStep(STEPS[stepIndex + 1].id);
  };

  const goBack = () => {
    if (canGoBack) setCurrentStep(STEPS[stepIndex - 1].id);
  };

  const updateCampaign = (updates: Partial<CreateCampaignRequest>) => {
    setCampaignData((prev) => ({ ...prev, ...updates }));
  };

  const updateCreative = (updates: Partial<CreateCreativeRequest>) => {
    setCreativeData((prev) => ({ ...prev, ...updates }));
  };

  const toggleArrayItem = (field: keyof CreateCampaignRequest, item: string) => {
    const arr = (campaignData[field] as string[]) || [];
    const updated = arr.includes(item) ? arr.filter((i) => i !== item) : [...arr, item];
    updateCampaign({ [field]: updated });
  };

  const handleSubmit = async () => {
    if (!token) return;
    if (!campaignData.campaign_name.trim()) {
      toast.error('Campaign name is required');
      setCurrentStep('basics');
      return;
    }
    if (!creativeData.headline.trim() || !creativeData.description.trim()) {
      toast.error('Creative headline and description are required');
      setCurrentStep('creative');
      return;
    }

    try {
      setSubmitting(true);

      // 1. Create campaign
      const campaign = await createCampaign(token, campaignData);

      // 2. Create creative
      await createCreative(token, campaign._id, creativeData);

      // 3. Submit for review
      await submitCampaignForReview(token, campaign._id);

      toast.success('Campaign created and submitted for review!');
      router.push('/portal/ads/campaigns');
    } catch (err: any) {
      toast.error(err.message || 'Failed to create campaign');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!token || !campaignData.campaign_name.trim()) {
      toast.error('Campaign name is required');
      return;
    }

    try {
      setSubmitting(true);
      const campaign = await createCampaign(token, campaignData);

      if (creativeData.headline.trim() && creativeData.description.trim()) {
        await createCreative(token, campaign._id, creativeData);
      }

      toast.success('Campaign saved as draft');
      router.push('/portal/ads/campaigns');
    } catch (err: any) {
      toast.error(err.message || 'Failed to save draft');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button onClick={() => router.push('/portal/ads/campaigns')} className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-2">
          <ArrowLeft size={14} /> Back to Campaigns
        </button>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Create New Campaign</h1>
      </div>

      {/* Step Indicator */}
      <div className="flex items-center gap-1 mb-8 overflow-x-auto pb-2">
        {STEPS.map((step, i) => {
          const Icon = step.icon;
          const isActive = step.id === currentStep;
          const isPast = i < stepIndex;
          return (
            <React.Fragment key={step.id}>
              <button
                onClick={() => setCurrentStep(step.id)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                  isActive ? 'bg-primary-500 text-white' :
                  isPast ? 'bg-primary-100 text-primary-700' :
                  'bg-slate-100 dark:bg-slate-700 text-slate-500'
                }`}
              >
                {isPast ? <CheckCircle2 size={14} /> : <Icon size={14} />}
                <span className="hidden sm:inline">{step.label}</span>
              </button>
              {i < STEPS.length - 1 && <div className="w-4 h-0.5 bg-slate-200 dark:bg-slate-700 flex-shrink-0" />}
            </React.Fragment>
          );
        })}
      </div>

      {/* Step Content */}
      <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-6">
        {currentStep === 'basics' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Campaign Basics</h2>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Campaign Name *</label>
              <input
                type="text"
                value={campaignData.campaign_name}
                onChange={(e) => updateCampaign({ campaign_name: e.target.value })}
                className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
                placeholder="e.g. Spring Wedding Photography Special"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Description</label>
              <textarea
                value={campaignData.campaign_description || ''}
                onChange={(e) => updateCampaign({ campaign_description: e.target.value })}
                rows={3}
                className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700 resize-none"
                placeholder="Brief description of your campaign"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Campaign Goal</label>
              <div className="grid grid-cols-3 gap-3">
                {GOAL_OPTIONS.map((goal) => (
                  <button
                    key={goal.value}
                    onClick={() => updateCampaign({ goal: goal.value })}
                    className={`p-3 rounded-lg border-2 text-center transition-colors text-sm ${
                      campaignData.goal === goal.value
                        ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                        : 'border-slate-200 dark:border-slate-600 hover:border-slate-300'
                    }`}
                  >
                    <p className="font-medium text-slate-900 dark:text-white">{goal.label}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{goal.description}</p>
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Your Category</label>
                <select
                  value={campaignData.vendor_category || ''}
                  onChange={(e) => updateCampaign({ vendor_category: e.target.value })}
                  className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
                >
                  <option value="">Select category</option>
                  {VENDOR_CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Service Area</label>
                <input
                  type="text"
                  value={campaignData.vendor_service_area || ''}
                  onChange={(e) => updateCampaign({ vendor_service_area: e.target.value })}
                  placeholder="e.g. Austin, TX"
                  className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
                />
              </div>
            </div>
          </div>
        )}

        {currentStep === 'targeting' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Targeting</h2>
            <p className="text-sm text-slate-500">Select which planners should see your ads. Leave empty for all.</p>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-2">Target Vendor Categories</label>
              <div className="flex flex-wrap gap-2">
                {VENDOR_CATEGORIES.map((cat) => (
                  <button
                    key={cat.value}
                    onClick={() => toggleArrayItem('target_categories', cat.value)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                      campaignData.target_categories?.includes(cat.value)
                        ? 'bg-primary-500 text-white'
                        : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-2">Target Wedding Stages</label>
              <div className="flex flex-wrap gap-2">
                {WEDDING_STAGES.map((stage) => (
                  <button
                    key={stage.value}
                    onClick={() => toggleArrayItem('target_wedding_stages', stage.value)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                      campaignData.target_wedding_stages?.includes(stage.value)
                        ? 'bg-primary-500 text-white'
                        : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                    }`}
                  >
                    {stage.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Target Regions</label>
              <input
                type="text"
                value={campaignData.target_regions?.join(', ') || ''}
                onChange={(e) => updateCampaign({ target_regions: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                placeholder="e.g. Austin TX, San Antonio TX, Houston TX"
                className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
              />
              <p className="text-xs text-slate-400 mt-1">Comma-separated cities or regions</p>
            </div>
          </div>
        )}

        {currentStep === 'creative' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Ad Creative</h2>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Headline *</label>
              <input
                type="text"
                value={creativeData.headline}
                onChange={(e) => updateCreative({ headline: e.target.value })}
                maxLength={100}
                className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
                placeholder="e.g. Award-Winning Wedding Photography"
              />
              <p className="text-xs text-slate-400 mt-1">{creativeData.headline.length}/100</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Description *</label>
              <textarea
                value={creativeData.description}
                onChange={(e) => updateCreative({ description: e.target.value })}
                maxLength={300}
                rows={3}
                className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700 resize-none"
                placeholder="Describe your services in 2-3 sentences"
              />
              <p className="text-xs text-slate-400 mt-1">{creativeData.description.length}/300</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Special Offer (optional)</label>
              <input
                type="text"
                value={creativeData.offer || ''}
                onChange={(e) => updateCreative({ offer: e.target.value })}
                className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
                placeholder="e.g. 20% off bookings before March 31"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Call to Action</label>
              <select
                value={creativeData.call_to_action || 'View Portfolio'}
                onChange={(e) => updateCreative({ call_to_action: e.target.value })}
                className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
              >
                <option>View Portfolio</option>
                <option>Get a Quote</option>
                <option>Book Now</option>
                <option>Learn More</option>
                <option>Contact Us</option>
              </select>
            </div>
          </div>
        )}

        {currentStep === 'budget' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Budget</h2>
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <p className="text-sm text-blue-700 dark:text-blue-300">
                <strong>Free Tier Active</strong> — No charges apply right now. You can optionally set a budget so it&apos;s ready when paid plans launch, or skip this step entirely.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Daily Budget ($)</label>
                <input
                  type="number"
                  value={campaignData.daily_budget || ''}
                  onChange={(e) => updateCampaign({ daily_budget: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
                  placeholder="0.00"
                  min={0}
                  step={0.01}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Total Budget ($)</label>
                <input
                  type="number"
                  value={campaignData.total_budget || ''}
                  onChange={(e) => updateCampaign({ total_budget: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
                  placeholder="0.00"
                  min={0}
                  step={0.01}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Pacing Strategy</label>
              <div className="grid grid-cols-2 gap-3">
                {(['even', 'accelerated'] as PacingStrategy[]).map((strategy) => (
                  <button
                    key={strategy}
                    onClick={() => updateCampaign({ pacing_strategy: strategy })}
                    className={`p-3 rounded-lg border-2 text-center transition-colors ${
                      campaignData.pacing_strategy === strategy
                        ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                        : 'border-slate-200 dark:border-slate-600'
                    }`}
                  >
                    <p className="text-sm font-medium text-slate-900 dark:text-white capitalize">{strategy}</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {strategy === 'even' ? 'Spread evenly over time' : 'Spend budget quickly'}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {currentStep === 'schedule' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Schedule</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Start Date</label>
                <input
                  type="date"
                  value={campaignData.start_date || ''}
                  onChange={(e) => updateCampaign({ start_date: e.target.value })}
                  className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">End Date</label>
                <input
                  type="date"
                  value={campaignData.end_date || ''}
                  onChange={(e) => updateCampaign({ end_date: e.target.value })}
                  className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
                />
              </div>
            </div>
            <p className="text-sm text-slate-500">
              Leave dates blank to start as soon as your campaign is approved and run until you pause it.
            </p>
          </div>
        )}

        {currentStep === 'review' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Review & Submit</h2>
            <div className="space-y-3">
              <ReviewSection title="Campaign">
                <ReviewItem label="Name" value={campaignData.campaign_name || '—'} />
                <ReviewItem label="Goal" value={GOAL_OPTIONS.find((g) => g.value === campaignData.goal)?.label || '—'} />
                <ReviewItem label="Category" value={VENDOR_CATEGORIES.find((c) => c.value === campaignData.vendor_category)?.label || 'Not set'} />
                <ReviewItem label="Service Area" value={campaignData.vendor_service_area || 'Not set'} />
              </ReviewSection>
              <ReviewSection title="Targeting">
                <ReviewItem label="Categories" value={campaignData.target_categories?.map((c) => VENDOR_CATEGORIES.find((v) => v.value === c)?.label || c).join(', ') || 'All'} />
                <ReviewItem label="Wedding Stages" value={campaignData.target_wedding_stages?.map((s) => WEDDING_STAGES.find((w) => w.value === s)?.label || s).join(', ') || 'All'} />
                <ReviewItem label="Regions" value={campaignData.target_regions?.join(', ') || 'All'} />
              </ReviewSection>
              <ReviewSection title="Creative">
                <ReviewItem label="Headline" value={creativeData.headline || '—'} />
                <ReviewItem label="Description" value={creativeData.description || '—'} />
                <ReviewItem label="Offer" value={creativeData.offer || 'None'} />
                <ReviewItem label="CTA" value={creativeData.call_to_action || 'View Portfolio'} />
              </ReviewSection>
              <ReviewSection title="Budget & Schedule">
                <ReviewItem label="Daily Budget" value={campaignData.daily_budget ? `$${campaignData.daily_budget}` : 'Free Tier'} />
                <ReviewItem label="Total Budget" value={campaignData.total_budget ? `$${campaignData.total_budget}` : 'Free Tier'} />
                <ReviewItem label="Pacing" value={campaignData.pacing_strategy === 'accelerated' ? 'Accelerated' : 'Even'} />
                <ReviewItem label="Start" value={campaignData.start_date || 'After approval'} />
                <ReviewItem label="End" value={campaignData.end_date || 'Until paused'} />
              </ReviewSection>
            </div>
          </div>
        )}
      </div>

      {/* Navigation Buttons */}
      <div className="flex items-center justify-between mt-6">
        <button
          onClick={goBack}
          disabled={!canGoBack}
          className="flex items-center gap-1.5 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-30 disabled:pointer-events-none"
        >
          <ArrowLeft size={14} /> Back
        </button>
        <div className="flex items-center gap-3">
          {currentStep === 'review' ? (
            <>
              <button
                onClick={handleSaveDraft}
                disabled={submitting}
                className="px-4 py-2 text-sm border border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
              >
                Save as Draft
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="flex items-center gap-2 px-5 py-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                <Send size={14} /> {submitting ? 'Creating campaign...' : 'Submit for Review'}
              </button>
            </>
          ) : (
            <button
              onClick={goNext}
              className="flex items-center gap-1.5 px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Next <ArrowRight size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ReviewSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">{title}</h3>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-900 dark:text-white font-medium text-right max-w-[60%] truncate">{value}</span>
    </div>
  );
}
