'use client';

import React, { useState, useEffect } from 'react';
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
} from 'lucide-react';
import { toast } from 'sonner';

type GoalType = 'visits' | 'quotes' | 'bookings';
type PlacementType = 'vendor_rail' | 'vendor_detail' | 'milestone_module';

interface WizardStep {
  id: number;
  title: string;
  description: string;
}

const WIZARD_STEPS: WizardStep[] = [
  { id: 1, title: 'Goal', description: 'What do you want to achieve?' },
  { id: 2, title: 'Where', description: 'Select placements and targeting' },
  { id: 3, title: 'Budget', description: 'Set your advertising budget' },
  { id: 4, title: 'Creative', description: 'Create your ad content' },
  { id: 5, title: 'Review', description: 'Review and submit' },
];

const PLACEMENT_OPTIONS = [
  { value: 'vendor_rail' as PlacementType, label: 'Dashboard Rail', description: 'Vendor profile shown in vendor rail on dashboard' },
  { value: 'vendor_detail' as PlacementType, label: 'Vendor Directory', description: 'Featured in the vendor directory search results' },
  { value: 'milestone_module' as PlacementType, label: 'Milestone Pages', description: 'Shown on wedding milestone and planning pages' },
];

const CATEGORY_OPTIONS = [
  'Photography',
  'Catering',
  'Venue',
  'Floral Design',
  'Music & DJ',
  'Decorations',
  'Cake & Desserts',
  'Invitations',
  'Beauty & Hair',
  'Other',
];

export default function CampaignWizardPage() {
  const router = useRouter();
  const { token, userProfile } = useAdmin();

  // Wizard state
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form data
  const [goal, setGoal] = useState<GoalType | null>(null);
  const [selectedPlacements, setSelectedPlacements] = useState<PlacementType[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [region, setRegion] = useState('');
  const [city, setCity] = useState('');
  const [dailyBudget, setDailyBudget] = useState('50');
  const [lifetimeBudget, setLifetimeBudget] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [pacing, setPacing] = useState<'standard' | 'accelerated'>('standard');
  const [imageUrl, setImageUrl] = useState('');
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [offer, setOffer] = useState('');
  const [cta, setCta] = useState('Get Quote');

  // Authentication check
  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
      return;
    }

    if (!userProfile?.is_vendor) {
      router.push('/admin');
      return;
    }
  }, [token, router, userProfile?.is_vendor]);

  // Validation functions
  const isStepValid = (): boolean => {
    switch (currentStep) {
      case 1:
        return goal !== null;
      case 2:
        return selectedPlacements.length > 0 && selectedCategories.length > 0;
      case 3:
        return dailyBudget !== '' && parseInt(dailyBudget) > 0;
      case 4:
        return headline.trim() !== '' && imageUrl.trim() !== '';
      case 5:
        return true; // Review page is always valid
      default:
        return false;
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
    if (currentStep > 1) {
      setError(null);
      setCurrentStep(currentStep - 1);
    }
  };

  const togglePlacement = (placement: PlacementType) => {
    setSelectedPlacements((prev) =>
      prev.includes(placement) ? prev.filter((p) => p !== placement) : [...prev, placement]
    );
  };

  const toggleCategory = (category: string) => {
    setSelectedCategories((prev) =>
      prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]
    );
  };

  const handleSubmit = async () => {
    if (!token || !userProfile?.user_data?.vendor_id) {
      toast.error('Unable to create campaign. Please check your profile.');
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);

      // Map goal to placement (vendor can create multiple placements per campaign)
      const placementsForSubmission: AdPlacement[] = selectedPlacements.map((p) => p as AdPlacement);

      // Create campaign for each placement
      const promises = placementsForSubmission.map((placement) =>
        createSponsoredVendor(token, {
          vendor_profile_id: userProfile.user_data.vendor_id,
          placement,
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
            daily_budget: parseFloat(dailyBudget),
            lifetime_budget: lifetimeBudget ? parseFloat(lifetimeBudget) : undefined,
            pacing,
            region: region || undefined,
            city: city || undefined,
          },
        })
      );

      await Promise.all(promises);

      toast.success('Campaign created successfully!');
      router.push('/admin/vendor/ads');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create campaign';
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getGoalDescription = (goalType: GoalType): string => {
    switch (goalType) {
      case 'visits':
        return 'Get more planners to visit your profile';
      case 'quotes':
        return 'Generate quote requests from planners';
      case 'bookings':
        return 'Drive direct bookings for your services';
      default:
        return '';
    }
  };

  const goalOptions: Array<{ value: GoalType; label: string }> = [
    { value: 'visits', label: 'Get profile visits' },
    { value: 'quotes', label: 'Get quote requests' },
    { value: 'bookings', label: 'Boost bookings' },
  ];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">Create New Campaign</h1>
          <p className="text-slate-600 dark:text-slate-400">Launch your first advertising campaign in 5 easy steps</p>
        </div>

        {/* Progress indicator */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            {WIZARD_STEPS.map((step, index) => (
              <React.Fragment key={step.id}>
                <div
                  className={`flex-1 h-1.5 rounded-full transition-colors ${
                    index < currentStep - 1
                      ? 'bg-wedding-rose'
                      : index === currentStep - 1
                      ? 'bg-wedding-rose'
                      : 'bg-slate-300 dark:bg-slate-700'
                  }`}
                />
              </React.Fragment>
            ))}
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-wedding-rose">Step {currentStep} of {WIZARD_STEPS.length}</p>
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white mt-1">
                {WIZARD_STEPS[currentStep - 1].title}
              </h2>
            </div>
            <div className="text-right">
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {WIZARD_STEPS[currentStep - 1].description}
              </p>
            </div>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-6 rounded-lg border border-red-200 dark:border-red-900/30 bg-red-50 dark:bg-red-900/10 p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-red-900 dark:text-red-200">{error}</p>
            </div>
          </div>
        )}

        {/* Content area */}
        <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-8 mb-6">
          {/* STEP 1: Goal */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                Choose what you want to achieve with your ad campaign
              </p>
              {goalOptions.map((option) => (
                <label
                  key={option.value}
                  className={`flex items-start gap-4 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    goal === option.value
                      ? 'border-wedding-rose bg-wedding-rose/5'
                      : 'border-slate-200 dark:border-slate-700 hover:border-wedding-rose/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="goal"
                    value={option.value}
                    checked={goal === option.value}
                    onChange={(e) => setGoal(e.target.value as GoalType)}
                    className="mt-1"
                  />
                  <div className="flex-1">
                    <p className="font-semibold text-slate-900 dark:text-white">{option.label}</p>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                      {getGoalDescription(option.value)}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          )}

          {/* STEP 2: Where */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div>
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <MapPin className="w-4 h-4" />
                  Placements
                </h3>
                <div className="space-y-3">
                  {PLACEMENT_OPTIONS.map((option) => (
                    <label
                      key={option.value}
                      className={`flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                        selectedPlacements.includes(option.value)
                          ? 'border-wedding-rose bg-wedding-rose/5'
                          : 'border-slate-200 dark:border-slate-700 hover:border-wedding-rose/50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedPlacements.includes(option.value)}
                        onChange={() => togglePlacement(option.value)}
                        className="mt-1"
                      />
                      <div className="flex-1">
                        <p className="font-semibold text-slate-900 dark:text-white">{option.label}</p>
                        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">{option.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="font-semibold text-slate-900 dark:text-white">Location Targeting (Optional)</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Region/State
                    </label>
                    <input
                      type="text"
                      value={region}
                      onChange={(e) => setRegion(e.target.value)}
                      placeholder="e.g., California"
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      City
                    </label>
                    <input
                      type="text"
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      placeholder="e.g., San Francisco"
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                    />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3">Service Categories</h3>
                <div className="grid grid-cols-2 gap-2">
                  {CATEGORY_OPTIONS.map((category) => (
                    <label
                      key={category}
                      className="flex items-center gap-2 p-2 rounded cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={selectedCategories.includes(category)}
                        onChange={() => toggleCategory(category)}
                        className="rounded"
                      />
                      <span className="text-sm text-slate-700 dark:text-slate-300">{category}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: Budget */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Daily Budget *
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-700 dark:text-slate-400">$</span>
                    <input
                      type="number"
                      value={dailyBudget}
                      onChange={(e) => setDailyBudget(e.target.value)}
                      min="1"
                      step="5"
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 pl-7 pr-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                    />
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Minimum $5 per day</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Lifetime Budget (Optional)
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-700 dark:text-slate-400">$</span>
                    <input
                      type="number"
                      value={lifetimeBudget}
                      onChange={(e) => setLifetimeBudget(e.target.value)}
                      placeholder="Leave blank for unlimited"
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 pl-7 pr-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Start Date
                    </label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      End Date (Optional)
                    </label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                    />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Zap className="w-4 h-4" />
                  Pacing Strategy
                </h3>
                <div className="space-y-2">
                  {['standard', 'accelerated'].map((pacingOption) => (
                    <label
                      key={pacingOption}
                      className="flex items-center gap-3 p-3 rounded-lg border border-slate-300 dark:border-slate-600 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                    >
                      <input
                        type="radio"
                        name="pacing"
                        value={pacingOption}
                        checked={pacing === pacingOption}
                        onChange={(e) => setPacing(e.target.value as 'standard' | 'accelerated')}
                      />
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white capitalize">{pacingOption}</p>
                        <p className="text-xs text-slate-600 dark:text-slate-400">
                          {pacingOption === 'standard'
                            ? 'Spread your budget evenly throughout the day'
                            : 'Spend budget faster when performance is good'}
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 4: Creative */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-2">
                  <ImageIcon className="w-4 h-4" />
                  Image URL *
                </label>
                <input
                  type="url"
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  placeholder="https://example.com/image.jpg"
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                />
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Best size: 1200x628px, max 5MB</p>

                {imageUrl && (
                  <div className="mt-4 rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700">
                    <img
                      src={imageUrl}
                      alt="Preview"
                      className="w-full h-auto object-cover max-h-64"
                      onError={() => toast.error('Invalid image URL')}
                    />
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Headline *
                </label>
                <input
                  type="text"
                  value={headline}
                  onChange={(e) => setHeadline(e.target.value)}
                  placeholder="e.g., Award-Winning Wedding Photography"
                  maxLength={60}
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                />
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  {headline.length}/60 characters
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Tell planners more about your service..."
                  maxLength={150}
                  rows={3}
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose resize-none"
                />
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  {description.length}/150 characters
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Special Offer (Optional)
                </label>
                <input
                  type="text"
                  value={offer}
                  onChange={(e) => setOffer(e.target.value)}
                  placeholder="e.g., 10% off for bookings this month"
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Call-to-Action
                </label>
                <select
                  value={cta}
                  onChange={(e) => setCta(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-slate-900 dark:text-white focus:border-wedding-rose focus:outline-none focus:ring-1 focus:ring-wedding-rose"
                >
                  <option>Get Quote</option>
                  <option>Learn More</option>
                  <option>View Profile</option>
                  <option>Book Now</option>
                  <option>Contact Me</option>
                </select>
              </div>

              {/* Preview */}
              <div className="mt-8 pt-8 border-t border-slate-200 dark:border-slate-700">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <Eye className="w-4 h-4" />
                  Preview
                </h3>
                <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 overflow-hidden max-w-sm">
                  {imageUrl && (
                    <img
                      src={imageUrl}
                      alt="Ad preview"
                      className="w-full h-48 object-cover"
                      onError={() => null}
                    />
                  )}
                  <div className="p-4">
                    <h4 className="font-bold text-slate-900 dark:text-white">{headline || 'Your Headline'}</h4>
                    {description && (
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-2">{description}</p>
                    )}
                    {offer && (
                      <p className="text-sm font-semibold text-wedding-rose mt-3">{offer}</p>
                    )}
                    <button className="mt-3 w-full bg-wedding-rose text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-wedding-rose/90 transition-colors">
                      {cta}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 5: Review */}
          {currentStep === 5 && (
            <div className="space-y-6">
              <div className="rounded-lg bg-emerald-50 dark:bg-emerald-900/10 border border-emerald-200 dark:border-emerald-900/30 p-4 flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-emerald-900 dark:text-emerald-200">Almost there!</p>
                  <p className="text-sm text-emerald-800 dark:text-emerald-300 mt-1">
                    Review your campaign details below and click Submit to launch
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-4">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Goal</p>
                  <p className="font-semibold text-slate-900 dark:text-white capitalize">{goal && goalOptions.find((g) => g.value === goal)?.label}</p>
                </div>

                <div className="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-4">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Placements</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedPlacements.map((p) => (
                      <span
                        key={p}
                        className="px-2 py-1 rounded-lg bg-wedding-rose/20 text-wedding-rose dark:text-wedding-rose text-sm font-medium"
                      >
                        {PLACEMENT_OPTIONS.find((opt) => opt.value === p)?.label}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-4">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Categories</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedCategories.map((c) => (
                      <span
                        key={c}
                        className="px-2 py-1 rounded-lg bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-200 text-sm font-medium"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-4">
                    <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Daily Budget</p>
                    <p className="font-semibold text-slate-900 dark:text-white">${dailyBudget}</p>
                  </div>
                  {lifetimeBudget && (
                    <div className="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-4">
                      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Lifetime Budget</p>
                      <p className="font-semibold text-slate-900 dark:text-white">${lifetimeBudget}</p>
                    </div>
                  )}
                </div>

                <div className="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-4">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Headline</p>
                  <p className="font-semibold text-slate-900 dark:text-white">{headline}</p>
                </div>

                {description && (
                  <div className="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-4">
                    <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Description</p>
                    <p className="text-slate-700 dark:text-slate-300">{description}</p>
                  </div>
                )}

                {offer && (
                  <div className="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-4">
                    <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Special Offer</p>
                    <p className="text-slate-700 dark:text-slate-300">{offer}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        <div className="flex items-center justify-between gap-4">
          <button
            onClick={handlePrevious}
            disabled={currentStep === 1}
            className={`flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-colors ${
              currentStep === 1
                ? 'text-slate-400 dark:text-slate-600 cursor-not-allowed'
                : 'text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-700/50'
            }`}
          >
            <ChevronLeft className="w-4 h-4" />
            Previous
          </button>

          {currentStep === WIZARD_STEPS.length ? (
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="flex items-center gap-2 px-8 py-2 rounded-lg bg-wedding-rose text-white font-medium hover:bg-wedding-rose/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Submitting...' : 'Submit for Review'}
            </button>
          ) : (
            <button
              onClick={handleNext}
              className="flex items-center gap-2 px-8 py-2 rounded-lg bg-wedding-rose text-white font-medium hover:bg-wedding-rose/90 transition-colors"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
