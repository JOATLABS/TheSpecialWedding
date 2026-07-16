'use client';

import {
  ExternalLink,
  Eye,
  Globe2,
  Loader2,
  Paintbrush,
  Save,
  Sparkles,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import { StorefrontImagePicker } from '@/components/storefront/StorefrontImagePicker';
import { StorefrontView } from '@/components/storefront/StorefrontView';
import { useAdmin } from '@/contexts/AdminContext';
import { useFocusTrap } from '@/hooks/useFocusTrap';
import {
  buildStorefrontSettingsPatch,
  deleteStorefrontUpload,
  getStorefrontPreviewSeed,
  getStorefrontPreviewUrl,
  getStorefrontSettings,
  normalizeStorefrontError,
  saveStorefrontSettings,
  uploadStorefrontImage,
  type StorefrontAccess,
  type StorefrontApiTransport,
  type StorefrontImageSlot,
  type StorefrontPreviewData,
  type StorefrontSettings,
  type StorefrontSettingsField,
  type StorefrontSettingsUpdate,
} from '@/services/storefrontApi';

import { CustomDomainPanel } from '../components/storefront/CustomDomainManager';

export type StorefrontSettingsTab = 'design' | 'content' | 'domain';

interface StorefrontSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  access: StorefrontAccess;
  initialTab?: StorefrontSettingsTab;
  domainAttemptId?: string | null;
  onDomainResumeHandled?: () => void;
}

interface StorefrontSettingsDialogProps extends StorefrontSettingsModalProps {
  transport: StorefrontApiTransport;
}

interface StorefrontDraft {
  slug: string;
  title: string;
  description: string;
  contact_email: string;
  contact_phone: string;
  hero_asset_id: string | null;
  about_asset_id: string | null;
  hero_image_url: string | null;
  about_image_url: string | null;
  theme_color: string;
  packages_enabled: boolean;
  reviews_enabled: boolean;
  is_published: boolean;
}

type LoadState = 'idle' | 'loading' | 'ready' | 'error';

const STOREFRONT_TABS: ReadonlyArray<{
  id: StorefrontSettingsTab;
  label: string;
}> = [
  { id: 'design', label: 'Design' },
  { id: 'content', label: 'Content & publish' },
  { id: 'domain', label: 'Domain' },
];

const EMPTY_DRAFT: StorefrontDraft = {
  slug: '',
  title: '',
  description: '',
  contact_email: '',
  contact_phone: '',
  hero_asset_id: null,
  about_asset_id: null,
  hero_image_url: null,
  about_image_url: null,
  theme_color: '#0f172a',
  packages_enabled: true,
  reviews_enabled: true,
  is_published: false,
};

function formatStorefrontError(caught: unknown, fallbackMessage: string): string {
  const normalized = normalizeStorefrontError(caught, fallbackMessage);
  const details = [normalized.message];
  if (normalized.customerAction) details.push(normalized.customerAction);
  if (normalized.supportId) details.push(`Support ID: ${normalized.supportId}.`);
  return details.join(' ');
}

function toDraft(
  settings: StorefrontSettings | null,
  preview: StorefrontPreviewData | null,
): StorefrontDraft {
  if (!settings) {
    return {
      ...EMPTY_DRAFT,
      slug: preview?.slug ?? '',
      title: preview?.storefront.title ?? '',
      description: preview?.storefront.description ?? '',
      contact_email: preview?.storefront.contact_email ?? '',
      contact_phone: preview?.storefront.contact_phone ?? '',
      hero_image_url: preview?.storefront.hero_image_url ?? null,
      about_image_url: preview?.storefront.about_image_url ?? null,
      theme_color: preview?.storefront.theme_color ?? EMPTY_DRAFT.theme_color,
      packages_enabled:
        preview?.storefront.packages_enabled ?? EMPTY_DRAFT.packages_enabled,
      reviews_enabled: preview?.storefront.reviews_enabled ?? EMPTY_DRAFT.reviews_enabled,
    };
  }
  return {
    slug: settings.slug,
    title: settings.title ?? '',
    description: settings.description ?? '',
    contact_email: settings.contact_email ?? '',
    contact_phone: settings.contact_phone ?? '',
    hero_asset_id: settings.hero_asset_id,
    about_asset_id: settings.about_asset_id,
    hero_image_url: preview?.storefront.hero_image_url ?? null,
    about_image_url: preview?.storefront.about_image_url ?? null,
    theme_color: settings.theme_color,
    packages_enabled: settings.packages_enabled,
    reviews_enabled: settings.reviews_enabled,
    is_published: settings.is_published,
  };
}

function toSettingsCandidate(draft: StorefrontDraft): StorefrontSettingsUpdate {
  return {
    ...(draft.slug.trim() ? { slug: draft.slug.trim() } : {}),
    title: draft.title.trim() || null,
    description: draft.description.trim() || null,
    contact_email: draft.contact_email.trim() || null,
    contact_phone: draft.contact_phone.trim() || null,
    hero_asset_id: draft.hero_asset_id,
    about_asset_id: draft.about_asset_id,
    theme_color: draft.theme_color,
    packages_enabled: draft.packages_enabled,
    reviews_enabled: draft.reviews_enabled,
    is_published: draft.is_published,
  };
}

function canonicalMatchesPatch(
  settings: StorefrontSettings,
  patch: StorefrontSettingsUpdate,
): boolean {
  return Object.entries(patch).every(([field, value]) => {
    if (field === 'slug' && typeof value === 'string') {
      const normalizedCandidate = value
        .normalize('NFKD')
        .replace(/[^\x00-\x7F]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
      return settings.slug === normalizedCandidate;
    }
    return settings[field as StorefrontSettingsField] === value;
  });
}

function ToggleSwitch({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900/40">
      <div>
        <p className="text-base font-semibold text-slate-900 dark:text-slate-100">{label}</p>
        <p className="mt-1 text-base leading-6 text-slate-600 dark:text-slate-300">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-label={label}
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className="relative inline-flex h-11 w-14 shrink-0 items-center justify-center rounded-full transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2"
      >
        <span
          aria-hidden="true"
          className={`relative inline-flex h-6 w-11 rounded-full transition ${
            checked ? 'bg-primary-600' : 'bg-slate-300 dark:bg-slate-600'
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 translate-y-0.5 rounded-full bg-white shadow transition ${
              checked ? 'translate-x-5' : 'translate-x-0.5'
            }`}
          />
        </span>
      </button>
    </div>
  );
}

export default function StorefrontSettingsModal(props: StorefrontSettingsModalProps) {
  const { apiRequest } = useAdmin();
  const apiRequestRef = useRef(apiRequest);
  useEffect(() => {
    apiRequestRef.current = apiRequest;
  }, [apiRequest]);
  const stableTransport = useCallback(
    async <T,>(path: string, method?: string, body?: unknown): Promise<T | undefined> =>
      apiRequestRef.current<T>(path, method, body),
    [],
  );

  return <StorefrontSettingsDialog {...props} transport={stableTransport} />;
}

export function StorefrontSettingsDialog({
  isOpen,
  onClose,
  access,
  transport,
  initialTab = 'design',
  domainAttemptId = null,
  onDomainResumeHandled,
}: StorefrontSettingsDialogProps) {
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [saving, setSaving] = useState(false);
  const [uploadingSlots, setUploadingSlots] = useState<Set<StorefrontImageSlot>>(
    () => new Set(),
  );
  const [activeTab, setActiveTab] = useState<StorefrontSettingsTab>(initialTab);
  const [showLivePreview, setShowLivePreview] = useState(false);
  const [savedSettings, setSavedSettings] = useState<StorefrontSettings | null>(null);
  const [previewSeed, setPreviewSeed] = useState<StorefrontPreviewData | null>(null);
  const [draft, setDraft] = useState<StorefrontDraft>(() => ({ ...EMPTY_DRAFT }));
  const [savedPreviewUrl, setSavedPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    setPortalTarget(document.body);
  }, []);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const pendingAssetIds = useRef(new Set<string>());
  const localObjectUrls = useRef<Partial<Record<StorefrontImageSlot, string>>>({});
  const draftRef = useRef<StorefrontDraft>({ ...EMPTY_DRAFT });
  const dirtyFieldsRef = useRef(new Set<StorefrontSettingsField>());
  const generationRef = useRef(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const revokeLocalUrl = useCallback((slot: StorefrontImageSlot) => {
    const url = localObjectUrls.current[slot];
    if (url) {
      URL.revokeObjectURL(url);
      delete localObjectUrls.current[slot];
    }
  }, []);

  const revokeAllLocalUrls = useCallback(() => {
    revokeLocalUrl('hero');
    revokeLocalUrl('about');
  }, [revokeLocalUrl]);

  const cleanupPendingAssets = useCallback(
    async (keep: ReadonlySet<string> = new Set()): Promise<string[]> => {
      const cleanupIds = [...pendingAssetIds.current].filter((assetId) => !keep.has(assetId));
      const results = await Promise.allSettled(
        cleanupIds.map((assetId) => deleteStorefrontUpload(assetId, transport)),
      );
      const failedIds: string[] = [];
      for (const [index, result] of results.entries()) {
        const assetId = cleanupIds[index];
        if (result.status === 'fulfilled') {
          pendingAssetIds.current.delete(assetId);
        } else {
          failedIds.push(assetId);
        }
      }
      return failedIds;
    },
    [transport],
  );

  const loadStorefront = useCallback(async () => {
    const generation = ++generationRef.current;
    setLoadState('loading');
    setError(null);
    setMessage(null);
    setSavedPreviewUrl(null);
    setActiveTab(access.storefront_enabled ? initialTab : 'domain');
    setShowLivePreview(false);
    try {
      const [settings, preview] = await Promise.all([
        getStorefrontSettings(transport),
        access.storefront_enabled
          ? getStorefrontPreviewSeed(transport)
          : Promise.resolve(null),
      ]);
      if (generationRef.current !== generation) {
        return;
      }
      const canonicalAssetIds = new Set(
        [settings?.hero_asset_id, settings?.about_asset_id].filter(
          (value): value is string => Boolean(value),
        ),
      );
      for (const assetId of canonicalAssetIds) {
        pendingAssetIds.current.delete(assetId);
      }
      const failedCleanup = await cleanupPendingAssets(canonicalAssetIds);
      if (generationRef.current !== generation) {
        return;
      }
      revokeAllLocalUrls();
      setSavedSettings(settings);
      setPreviewSeed(preview);
      const canonicalDraft = toDraft(settings, preview);
      draftRef.current = canonicalDraft;
      setDraft(canonicalDraft);
      dirtyFieldsRef.current = new Set();
      setLoadState('ready');
      if (failedCleanup.length > 0) {
        setError('Current settings loaded, but an abandoned upload still needs cleanup.');
      }
    } catch (caught) {
      if (generationRef.current !== generation) {
        return;
      }
      setLoadState('error');
      setError(formatStorefrontError(caught, 'Unable to load storefront settings.'));
    }
  }, [
    access.storefront_enabled,
    cleanupPendingAssets,
    initialTab,
    revokeAllLocalUrls,
    transport,
  ]);

  useEffect(() => {
    if (!isOpen) {
      generationRef.current += 1;
      setLoadState('idle');
      return;
    }
    void loadStorefront();
    return () => {
      generationRef.current += 1;
    };
  }, [isOpen, loadStorefront]);

  useEffect(
    () => () => {
      generationRef.current += 1;
      revokeAllLocalUrls();
      for (const assetId of pendingAssetIds.current) {
        void deleteStorefrontUpload(assetId, transport).catch(() => undefined);
      }
      pendingAssetIds.current.clear();
    },
    [revokeAllLocalUrls, transport],
  );

  const updateDraftField = useCallback(
    <Field extends StorefrontSettingsField>(field: Field, value: StorefrontDraft[Field]) => {
      const next = { ...draftRef.current, [field]: value };
      draftRef.current = next;
      setDraft(next);
      dirtyFieldsRef.current.add(field);
    },
    [],
  );

  const livePreviewData = useMemo<StorefrontPreviewData>(
    () => ({
      slug: draft.slug || 'draft-storefront',
      storefront: {
        title: draft.title || null,
        description: draft.description || null,
        contact_email: draft.contact_email || null,
        contact_phone: draft.contact_phone || null,
        hero_image_url: draft.hero_image_url,
        about_image_url: draft.about_image_url,
        theme_color: draft.theme_color,
        packages_enabled: draft.packages_enabled,
        reviews_enabled: draft.reviews_enabled,
      },
      planner: previewSeed?.planner ?? {
        company_name: null,
        first_name: null,
        profile_image_url: null,
      },
      packages: previewSeed?.packages ?? [],
      reviews: previewSeed?.reviews ?? [],
    }),
    [draft, previewSeed],
  );

  const handleImageUpload = async (slot: StorefrontImageSlot, file: File) => {
    if (loadState !== 'ready' || saving) {
      return;
    }
    const generation = generationRef.current;
    const assetField = slot === 'hero' ? 'hero_asset_id' : 'about_asset_id';
    const imageField = slot === 'hero' ? 'hero_image_url' : 'about_image_url';
    const previousAssetId = draft[assetField];
    const previousPreview = draft[imageField];
    const previousLocalUrl = localObjectUrls.current[slot];
    const localPreview = URL.createObjectURL(file);

    localObjectUrls.current[slot] = localPreview;
    draftRef.current = { ...draftRef.current, [imageField]: localPreview };
    setDraft(draftRef.current);
    setUploadingSlots((current) => new Set(current).add(slot));
    setError(null);
    setMessage(null);

    try {
      const asset = await uploadStorefrontImage(file, slot, transport, fetch, {
        isActive: () => generationRef.current === generation,
      });
      if (generationRef.current !== generation) {
        return;
      }
      pendingAssetIds.current.add(asset.asset_id);
      dirtyFieldsRef.current.add(assetField);
      draftRef.current = {
        ...draftRef.current,
        [assetField]: asset.asset_id,
        [imageField]: localPreview,
      };
      setDraft(draftRef.current);
      if (previousLocalUrl && previousLocalUrl !== localPreview) {
        URL.revokeObjectURL(previousLocalUrl);
      }
      if (
        previousAssetId &&
        previousAssetId !== asset.asset_id &&
        pendingAssetIds.current.has(previousAssetId)
      ) {
        try {
          await deleteStorefrontUpload(previousAssetId, transport);
          pendingAssetIds.current.delete(previousAssetId);
        } catch {
          setError('The replaced upload could not be cleaned up yet. Retry before closing.');
        }
      }
      setMessage(`${slot === 'hero' ? 'Hero' : 'About'} image ready to save.`);
    } catch (caught) {
      URL.revokeObjectURL(localPreview);
      if (generationRef.current !== generation) {
        return;
      }
      if (previousLocalUrl) {
        localObjectUrls.current[slot] = previousLocalUrl;
      } else {
        delete localObjectUrls.current[slot];
      }
      draftRef.current = {
        ...draftRef.current,
        [assetField]: previousAssetId,
        [imageField]: previousPreview,
      };
      setDraft(draftRef.current);
      setError(formatStorefrontError(caught, 'Unable to upload the image.'));
    } finally {
      if (generationRef.current === generation) {
        setUploadingSlots((current) => {
          const next = new Set(current);
          next.delete(slot);
          return next;
        });
      }
    }
  };

  const handleRemoveImage = async (slot: StorefrontImageSlot) => {
    if (loadState !== 'ready' || saving) {
      return;
    }
    const assetField = slot === 'hero' ? 'hero_asset_id' : 'about_asset_id';
    const imageField = slot === 'hero' ? 'hero_image_url' : 'about_image_url';
    const assetId = draft[assetField];
    revokeLocalUrl(slot);
    draftRef.current = { ...draftRef.current, [assetField]: null, [imageField]: null };
    setDraft(draftRef.current);
    dirtyFieldsRef.current.add(assetField);
    if (assetId && pendingAssetIds.current.has(assetId)) {
      try {
        await deleteStorefrontUpload(assetId, transport);
        pendingAssetIds.current.delete(assetId);
      } catch {
        setError('The removed upload could not be cleaned up yet. Retry before closing.');
      }
    }
  };

  const restoreSavedImagesAfterFailure = () => {
    revokeAllLocalUrls();
    draftRef.current = {
      ...draftRef.current,
      hero_asset_id: savedSettings?.hero_asset_id ?? null,
      about_asset_id: savedSettings?.about_asset_id ?? null,
      hero_image_url: previewSeed?.storefront.hero_image_url ?? null,
      about_image_url: previewSeed?.storefront.about_image_url ?? null,
    };
    setDraft(draftRef.current);
    dirtyFieldsRef.current.delete('hero_asset_id');
    dirtyFieldsRef.current.delete('about_asset_id');
  };

  const performSave = async (
    generation: number,
  ): Promise<{
    saved: StorefrontSettings;
    stableCleanupWarning: boolean;
    recoveredAmbiguousWrite: boolean;
  }> => {
    const priorHeroAsset = savedSettings?.hero_asset_id ?? null;
    const priorAboutAsset = savedSettings?.about_asset_id ?? null;
    const dirtySnapshot = new Set(dirtyFieldsRef.current);
    if (savedSettings && dirtySnapshot.size === 0) {
      return {
        saved: savedSettings,
        stableCleanupWarning: false,
        recoveredAmbiguousWrite: false,
      };
    }
    const patch = buildStorefrontSettingsPatch(
      toSettingsCandidate(draftRef.current),
      dirtySnapshot,
    );
    let writeCommitted = false;
    try {
      const saved = await saveStorefrontSettings(patch, transport);
      writeCommitted = true;
      const retainedAssetIds = new Set(
        [saved.hero_asset_id, saved.about_asset_id].filter((value): value is string => Boolean(value)),
      );
      for (const assetId of retainedAssetIds) {
        pendingAssetIds.current.delete(assetId);
      }
      const failedPendingCleanup = await cleanupPendingAssets(retainedAssetIds);
      const displacedStableAssets = [
        dirtySnapshot.has('hero_asset_id') && priorHeroAsset !== saved.hero_asset_id
          ? priorHeroAsset
          : null,
        dirtySnapshot.has('about_asset_id') && priorAboutAsset !== saved.about_asset_id
          ? priorAboutAsset
          : null,
      ].filter((assetId): assetId is string => Boolean(assetId));
      const displacedCleanup = await Promise.allSettled(
        displacedStableAssets.map((assetId) => deleteStorefrontUpload(assetId, transport)),
      );
      const [canonicalSettings, canonicalPreview] = await Promise.all([
        getStorefrontSettings(transport),
        getStorefrontPreviewSeed(transport),
      ]);
      if (!canonicalSettings) {
        throw new Error('Storefront settings were not readable after saving');
      }
      if (generationRef.current !== generation) {
        return {
          saved: canonicalSettings,
          stableCleanupWarning: displacedCleanup.some((result) => result.status === 'rejected'),
          recoveredAmbiguousWrite: false,
        };
      }
      setSavedSettings(canonicalSettings);
      setPreviewSeed(canonicalPreview);
      const canonicalDraft = toDraft(canonicalSettings, canonicalPreview);
      draftRef.current = canonicalDraft;
      setDraft(canonicalDraft);
      dirtyFieldsRef.current = new Set();
      revokeAllLocalUrls();
      if (failedPendingCleanup.length > 0) {
        setError('Storefront saved, but an abandoned upload still needs cleanup before closing.');
      }
      return {
        saved: canonicalSettings,
        stableCleanupWarning: displacedCleanup.some((result) => result.status === 'rejected'),
        recoveredAmbiguousWrite: false,
      };
    } catch (caught) {
      if (writeCommitted) {
        if (generationRef.current === generation) {
          setLoadState('error');
        }
        throw new Error(
          'Storefront saved, but canonical state could not be refreshed. Reload before editing again.',
        );
      }
      try {
        const [canonicalSettings, canonicalPreview] = await Promise.all([
          getStorefrontSettings(transport),
          getStorefrontPreviewSeed(transport),
        ]);
        if (canonicalSettings && canonicalMatchesPatch(canonicalSettings, patch)) {
          const retainedAssetIds = new Set(
            [canonicalSettings.hero_asset_id, canonicalSettings.about_asset_id].filter(
              (value): value is string => Boolean(value),
            ),
          );
          for (const assetId of retainedAssetIds) {
            pendingAssetIds.current.delete(assetId);
          }
          await cleanupPendingAssets(retainedAssetIds);
          if (generationRef.current === generation) {
            setSavedSettings(canonicalSettings);
            setPreviewSeed(canonicalPreview);
            const canonicalDraft = toDraft(canonicalSettings, canonicalPreview);
            draftRef.current = canonicalDraft;
            setDraft(canonicalDraft);
            dirtyFieldsRef.current = new Set();
            revokeAllLocalUrls();
          }
          return {
            saved: canonicalSettings,
            stableCleanupWarning: false,
            recoveredAmbiguousWrite: true,
          };
        }
      } catch {
        // The original save error remains authoritative when reconciliation fails.
      }
      const failedCleanup = await cleanupPendingAssets();
      if (generationRef.current === generation) {
        restoreSavedImagesAfterFailure();
      }
      if (failedCleanup.length > 0) {
        const saveMessage = formatStorefrontError(caught, 'Unable to save settings.');
        throw new Error(
          `${saveMessage}. An upload also could not be cleaned up; retry before closing.`,
        );
      }
      throw caught;
    }
  };

  const handleSave = async (openPreview: boolean) => {
    if (loadState !== 'ready') {
      return;
    }
    if (savedSettings?.slug_editable !== false && !draftRef.current.slug.trim()) {
      setActiveTab('design');
      setShowLivePreview(false);
      setError('A storefront URL is required before saving.');
      setMessage(null);
      return;
    }
    const generation = generationRef.current;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const { saved, stableCleanupWarning, recoveredAmbiguousWrite } =
        await performSave(generation);
      if (generationRef.current !== generation) {
        return;
      }
      const successMessage = recoveredAmbiguousWrite
        ? 'Storefront saved; canonical state was reconciled after an uncertain response.'
        : stableCleanupWarning
          ? 'Storefront saved. An old image will be cleaned up by lifecycle recovery.'
          : saved.is_published
            ? 'Storefront saved and published.'
            : 'Storefront draft saved.';
      if (openPreview) {
        const url = new URL(getStorefrontPreviewUrl(saved.slug), window.location.origin).toString();
        setSavedPreviewUrl(url);
        setMessage(`${successMessage} Preview link ready.`);
      } else {
        setSavedPreviewUrl(null);
        setMessage(successMessage);
      }
    } catch (caught) {
      if (generationRef.current === generation) {
        setError(formatStorefrontError(caught, 'Unable to save storefront settings.'));
      }
    } finally {
      if (generationRef.current === generation) {
        setSaving(false);
      }
    }
  };

  const handleClose = useCallback(async () => {
    if (saving || uploadingSlots.size > 0) {
      return;
    }
    setError(null);
    const failedCleanup = await cleanupPendingAssets();
    if (failedCleanup.length > 0) {
      setError('An unsaved upload could not be cleaned up. Please retry before closing.');
      return;
    }
    generationRef.current += 1;
    revokeAllLocalUrls();
    onClose();
  }, [
    cleanupPendingAssets,
    onClose,
    revokeAllLocalUrls,
    saving,
    uploadingSlots.size,
  ]);

  useFocusTrap(dialogRef, isOpen && Boolean(portalTarget));

  const handleTabKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ) => {
    const enabledIndexes = STOREFRONT_TABS.map((_tab, index) => index).filter(
      (index) => access.storefront_enabled || STOREFRONT_TABS[index].id === 'domain',
    );
    const currentPosition = Math.max(enabledIndexes.indexOf(currentIndex), 0);
    let nextIndex: number | null = null;
    if (event.key === 'ArrowRight') {
      nextIndex = enabledIndexes[(currentPosition + 1) % enabledIndexes.length];
    }
    if (event.key === 'ArrowLeft') {
      nextIndex =
        enabledIndexes[
          (currentPosition - 1 + enabledIndexes.length) % enabledIndexes.length
        ];
    }
    if (event.key === 'Home') nextIndex = enabledIndexes[0];
    if (event.key === 'End') nextIndex = enabledIndexes.at(-1) ?? null;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextTab = STOREFRONT_TABS[nextIndex];
    setActiveTab(nextTab.id);
    setShowLivePreview(false);
    tabRefs.current[nextIndex]?.focus();
  };

  useEffect(() => {
    if (!isOpen || !portalTarget) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }
      if (dialogRef.current?.querySelector('[data-storefront-nested-dialog="true"]')) {
        return;
      }
      event.stopPropagation();
      void handleClose();
    };

    window.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown, true);
    };
  }, [handleClose, isOpen, portalTarget]);

  if (!isOpen || !portalTarget) {
    return null;
  }

  const platformPath = draft.slug
    ? `/storefront/${encodeURIComponent(draft.slug)}`
    : '/storefront/your-storefront-slug';
  const savedPlatformPath = savedSettings?.slug
    ? `/storefront/${encodeURIComponent(savedSettings.slug)}`
    : '/storefront/your-storefront-slug';
  const platformPreviewPath = draft.slug ? getStorefrontPreviewUrl(draft.slug) : null;
  const savedStorefrontPreviewPath = savedSettings?.slug
    ? getStorefrontPreviewUrl(savedSettings.slug)
    : null;
  const busy = saving || uploadingSlots.size > 0;

  const renderLoadBoundary = () => {
    if (loadState === 'loading' || loadState === 'idle') {
      return (
        <div className="flex min-h-[28rem] items-center justify-center gap-3 p-6 text-base text-slate-700 dark:text-slate-200">
          <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
          Loading storefront settings…
        </div>
      );
    }
    if (loadState === 'error') {
      return (
        <div className="flex min-h-[28rem] flex-col items-center justify-center gap-4 px-6 text-center">
          <div>
            <h3 className="text-[16px] font-semibold text-slate-950 dark:text-slate-100">
              Storefront settings could not be loaded
            </h3>
            <p className="mt-2 max-w-md text-base leading-6 text-slate-600 dark:text-slate-300">
              Saving and previewing are disabled until the current owner state loads successfully.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadStorefront()}
            className="min-h-11 rounded-lg bg-primary-800 px-4 text-base font-semibold text-white transition hover:bg-primary-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
          >
            Retry loading storefront
          </button>
        </div>
      );
    }
    return null;
  };

  const editorInputClass =
    'mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-[16px] text-slate-900 outline-none placeholder:text-slate-500 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/30 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-400 dark:disabled:bg-slate-800';

  return createPortal(
    <div className="fixed inset-0 z-[9999] overflow-hidden bg-slate-950/70 p-0 backdrop-blur-sm sm:p-6">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="storefront-settings-title"
        aria-describedby="storefront-settings-description"
        className="mx-auto flex h-[100dvh] max-h-[100dvh] w-full max-w-5xl flex-col overflow-hidden rounded-none bg-white text-slate-900 shadow-2xl dark:bg-slate-950 dark:text-slate-100 sm:h-auto sm:max-h-[calc(100vh-3rem)] sm:rounded-2xl"
      >
        <header className="relative sticky top-0 z-20 border-b border-slate-200 bg-white px-4 py-4 dark:border-slate-700 dark:bg-slate-950 sm:px-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-3 pr-12">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-600 text-white">
                <Sparkles className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h2 id="storefront-settings-title" className="text-lg font-bold text-slate-950 dark:text-slate-100">
                  Planner Storefront
                </h2>
                <p id="storefront-settings-description" className="mt-1 text-base leading-6 text-slate-600 dark:text-slate-300">
                  Design, publish, preview, and connect a domain while your platform URL stays available.
                </p>
              </div>
            </div>
          </div>

          <div
            className="mt-4 grid max-w-full grid-cols-3 gap-1 rounded-xl border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-900"
            role="tablist"
            aria-label="Storefront settings sections"
          >
            {STOREFRONT_TABS.map((tab, index) => {
              const selected = activeTab === tab.id;
              const enabled = access.storefront_enabled || tab.id === 'domain';
              return (
                <button
                  key={tab.id}
                  ref={(element) => {
                    tabRefs.current[index] = element;
                  }}
                  id={`storefront-tab-${tab.id}`}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  aria-disabled={!enabled}
                  aria-controls={`storefront-panel-${tab.id}`}
                  tabIndex={selected ? 0 : -1}
                  disabled={!enabled}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setShowLivePreview(false);
                  }}
                  onKeyDown={(event) => handleTabKeyDown(event, index)}
                  className={`min-h-11 min-w-0 rounded-lg px-2 text-sm font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:cursor-not-allowed disabled:opacity-100 sm:px-4 sm:text-base ${
                    selected
                      ? 'bg-white text-slate-950 shadow-sm dark:bg-slate-800 dark:text-slate-100'
                      : 'text-slate-600 hover:bg-white/70 hover:text-slate-950 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white'
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {access.storefront_enabled ? (
              <button
                type="button"
                aria-pressed={showLivePreview}
                onClick={() => setShowLivePreview((current) => !current)}
                className={`inline-flex min-h-11 items-center gap-2 rounded-lg border px-4 text-base font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
                  showLivePreview
                    ? 'border-primary-300 bg-primary-50 text-primary-800 dark:border-primary-800 dark:bg-primary-950/50 dark:text-primary-200'
                    : 'border-slate-300 bg-white text-slate-800 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <Eye className="h-4 w-4" aria-hidden="true" />
                Live preview
              </button>
            ) : null}
            {savedStorefrontPreviewPath ? (
              <a
                href={savedStorefrontPreviewPath}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-base font-semibold text-slate-800 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
              >
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
                Preview storefront
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
            ) : (
              <button
                type="button"
                disabled
                title="Save the storefront URL before opening the saved preview"
                className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-300 bg-slate-100 px-4 text-base font-semibold text-slate-500 disabled:cursor-not-allowed dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500"
              >
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
                Preview storefront
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => void handleClose()}
            disabled={busy}
            aria-label="Close storefront settings"
            className="absolute right-4 top-4 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:cursor-not-allowed disabled:text-slate-600 dark:text-slate-300 dark:hover:bg-slate-800 dark:disabled:text-slate-300 sm:right-6"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto bg-slate-50 dark:bg-slate-950">
          <section
            id="storefront-panel-design"
            role="tabpanel"
            aria-labelledby="storefront-tab-design"
            hidden={showLivePreview || activeTab !== 'design'}
          >
            {!showLivePreview && activeTab === 'design' && loadState !== 'ready' ? renderLoadBoundary() : null}
            {!showLivePreview && activeTab === 'design' && loadState === 'ready' ? (
              <fieldset disabled={saving} className="contents">
                <div className="mx-auto grid max-w-5xl gap-6 p-4 sm:p-6 lg:grid-cols-2">
                  <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                    <div className="flex items-center gap-2">
                      <Globe2 className="h-5 w-5 text-slate-600 dark:text-slate-300" aria-hidden="true" />
                      <h3 className="text-[16px] font-semibold">Storefront identity</h3>
                    </div>
                    <div>
                      <label htmlFor="storefront-slug" className="text-base font-semibold">Storefront URL</label>
                      <div className="mt-2 flex min-h-11 overflow-hidden rounded-lg border border-slate-300 bg-white focus-within:border-primary-500 focus-within:ring-2 focus-within:ring-primary-500/30 dark:border-slate-600 dark:bg-slate-950">
                        <span className="hidden items-center bg-slate-100 px-3 text-base text-slate-600 sm:flex dark:bg-slate-800 dark:text-slate-300">/storefront/</span>
                        <input
                          id="storefront-slug"
                          value={draft.slug}
                          onChange={(event) => updateDraftField('slug', event.target.value)}
                          disabled={savedSettings?.slug_editable === false}
                          maxLength={128}
                          autoCapitalize="none"
                          autoCorrect="off"
                          placeholder="jane-events"
                          className="min-w-0 flex-1 bg-transparent px-3 text-[16px] text-slate-900 outline-none placeholder:text-slate-500 disabled:cursor-not-allowed disabled:bg-slate-100 dark:text-slate-100 dark:placeholder:text-slate-400 dark:disabled:bg-slate-800"
                        />
                      </div>
                      <a
                        href={platformPreviewPath ?? platformPath}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 block min-h-11 break-all py-2 text-base font-medium text-primary-700 underline-offset-4 hover:underline dark:text-primary-300"
                      >
                        {platformPreviewPath ?? platformPath}
                      </a>
                      {savedSettings?.slug_editable === false ? (
                        <p className="text-base font-medium text-amber-800 dark:text-amber-200">The slug is locked after first publication.</p>
                      ) : null}
                    </div>
                    <div>
                      <label htmlFor="storefront-title" className="text-base font-semibold">Storefront title</label>
                      <input id="storefront-title" value={draft.title} maxLength={100} onChange={(event) => updateDraftField('title', event.target.value)} placeholder="Jane's Luxury Weddings" className={editorInputClass} />
                    </div>
                    <div>
                      <label htmlFor="storefront-description" className="text-base font-semibold">Description</label>
                      <textarea id="storefront-description" value={draft.description} maxLength={2000} rows={5} onChange={(event) => updateDraftField('description', event.target.value)} placeholder="Describe the planning experience you create." className={`${editorInputClass} py-3`} />
                    </div>
                  </section>

                  <section className="space-y-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                    <div className="flex items-center gap-2">
                      <Paintbrush className="h-5 w-5 text-slate-600 dark:text-slate-300" aria-hidden="true" />
                      <h3 className="text-[16px] font-semibold">Media and appearance</h3>
                    </div>
                    <div>
                      <label htmlFor="storefront-theme" className="text-base font-semibold">Theme color</label>
                      <div className="mt-2 flex items-center gap-3">
                        <input id="storefront-theme" type="color" value={draft.theme_color} onChange={(event) => updateDraftField('theme_color', event.target.value)} className="h-11 w-14 rounded-lg border border-slate-300 bg-white p-1 dark:border-slate-600 dark:bg-slate-950" />
                        <input aria-label="Theme color hex value" value={draft.theme_color} pattern="#[0-9A-Fa-f]{6}" onChange={(event) => updateDraftField('theme_color', event.target.value)} className={`${editorInputClass} mt-0 max-w-40 uppercase`} />
                      </div>
                    </div>
                    <StorefrontImagePicker id="storefront-hero-image" label="Hero image" hint="Wide landscape image, up to 5 MB." imageUrl={draft.hero_image_url} hasImage={Boolean(draft.hero_asset_id)} uploading={uploadingSlots.has('hero')} onFileSelect={(file) => handleImageUpload('hero', file)} onRemove={() => void handleRemoveImage('hero')} />
                    <StorefrontImagePicker id="storefront-about-image" label="About image" hint="Planner portrait or team image, up to 5 MB." imageUrl={draft.about_image_url} hasImage={Boolean(draft.about_asset_id)} uploading={uploadingSlots.has('about')} onFileSelect={(file) => handleImageUpload('about', file)} onRemove={() => void handleRemoveImage('about')} compact />
                  </section>
                </div>
              </fieldset>
            ) : null}
          </section>

          <section
            id="storefront-panel-content"
            role="tabpanel"
            aria-labelledby="storefront-tab-content"
            hidden={showLivePreview || activeTab !== 'content'}
          >
            {!showLivePreview && activeTab === 'content' && loadState !== 'ready' ? renderLoadBoundary() : null}
            {!showLivePreview && activeTab === 'content' && loadState === 'ready' ? (
              <fieldset disabled={saving} className="contents">
                <div className="mx-auto grid max-w-5xl gap-6 p-4 sm:p-6 lg:grid-cols-2">
                  <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                    <div>
                      <h3 className="text-[16px] font-semibold">Contact and publication</h3>
                      <p className="mt-1 text-base leading-6 text-slate-600 dark:text-slate-300">Control how visitors contact you and when the saved storefront becomes public.</p>
                    </div>
                    <div>
                      <label htmlFor="storefront-contact-email" className="text-base font-semibold">Contact email</label>
                      <input id="storefront-contact-email" type="email" value={draft.contact_email} onChange={(event) => updateDraftField('contact_email', event.target.value)} placeholder="hello@example.com" className={editorInputClass} />
                    </div>
                    <div>
                      <label htmlFor="storefront-contact-phone" className="text-base font-semibold">Contact phone</label>
                      <input id="storefront-contact-phone" type="tel" maxLength={40} value={draft.contact_phone} onChange={(event) => updateDraftField('contact_phone', event.target.value)} placeholder="+1 555 0100" className={editorInputClass} />
                    </div>
                    <ToggleSwitch checked={draft.is_published} onChange={(is_published) => updateDraftField('is_published', is_published)} label="Publish storefront" description="Make the saved storefront visible to public visitors." />
                  </section>

                  <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                    <div className="flex items-center gap-2">
                      <Eye className="h-5 w-5 text-slate-600 dark:text-slate-300" aria-hidden="true" />
                      <h3 className="text-[16px] font-semibold">Visible content</h3>
                    </div>
                    <p className="text-base leading-6 text-slate-600 dark:text-slate-300">Choose which current business content appears on the public storefront.</p>
                    <ToggleSwitch checked={draft.packages_enabled} onChange={(packages_enabled) => updateDraftField('packages_enabled', packages_enabled)} label="Display packages" description="Show current active, non-template packages." />
                    <ToggleSwitch checked={draft.reviews_enabled} onChange={(reviews_enabled) => updateDraftField('reviews_enabled', reviews_enabled)} label="Display reviews" description="Show currently published planner reviews." />
                  </section>
                </div>
              </fieldset>
            ) : null}
          </section>

          <section
            id="storefront-panel-domain"
            role="tabpanel"
            aria-labelledby="storefront-tab-domain"
            hidden={showLivePreview || activeTab !== 'domain'}
          >
            {!showLivePreview && activeTab === 'domain' ? (
              <div className="mx-auto max-w-[760px] p-4 sm:p-6">
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                  <p className="mb-5 rounded-lg border border-sky-200 bg-sky-50 p-3 text-base leading-6 text-sky-950 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100">
                    Custom-domain operations apply immediately. Save settings only changes storefront design and content.
                  </p>
                  <CustomDomainPanel
                    transport={transport}
                    canActivate={access.custom_domain_enabled}
                    canManageExisting={access.can_manage_existing_domain}
                    platformUrl={savedPlatformPath}
                    isPublished={savedSettings?.is_published === true}
                    attemptId={domainAttemptId}
                    onResumeHandled={onDomainResumeHandled}
                  />
                </div>
              </div>
            ) : null}
          </section>

          <section
            role="region"
            aria-label="Live preview"
            hidden={!showLivePreview}
          >
            {showLivePreview && loadState !== 'ready' ? renderLoadBoundary() : null}
            {showLivePreview && loadState === 'ready' ? (
              <div className="bg-slate-200 p-2 sm:p-5 dark:bg-slate-900">
                <div className="mx-auto max-w-5xl overflow-hidden rounded-xl bg-white shadow-xl">
                  <StorefrontView data={livePreviewData} previewMode />
                </div>
              </div>
            ) : null}
          </section>
        </div>

        {activeTab !== 'domain' || showLivePreview ? (
          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-950 sm:px-6">
            <div className="min-h-6 text-base">
              {error ? <p role="alert" className="font-medium text-red-700 dark:text-red-300">{error}</p> : null}
              {message ? <p role="status" className="font-medium text-emerald-700 dark:text-emerald-300">{message}</p> : null}
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <button type="button" onClick={() => void handleClose()} disabled={busy} className="min-h-11 rounded-lg px-4 text-base font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-700 disabled:hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800 dark:disabled:bg-slate-800 dark:disabled:text-slate-200 dark:disabled:hover:bg-slate-800">Cancel</button>
              <button type="button" onClick={() => void handleSave(false)} disabled={busy || loadState !== 'ready'} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-primary-300 bg-white px-4 text-base font-semibold text-primary-700 transition hover:bg-primary-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-200 disabled:text-slate-700 disabled:hover:bg-slate-200 dark:border-primary-800 dark:bg-slate-900 dark:text-primary-300 dark:disabled:border-slate-600 dark:disabled:bg-slate-800 dark:disabled:text-slate-200 dark:disabled:hover:bg-slate-800">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Save className="h-4 w-4" aria-hidden="true" />}
                Save settings
              </button>
              <button type="button" onClick={() => void handleSave(true)} disabled={busy || loadState !== 'ready'} className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-primary-800 px-4 text-base font-semibold text-white transition-shadow hover:bg-primary-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-700 disabled:hover:bg-slate-200 dark:disabled:bg-slate-800 dark:disabled:text-slate-200 dark:disabled:hover:bg-slate-800">
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
                Save for preview
              </button>
              {savedPreviewUrl ? (
                <a
                  href={savedPreviewUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-primary-300 bg-white px-4 text-base font-semibold text-primary-700 transition hover:bg-primary-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:border-primary-800 dark:bg-slate-900 dark:text-primary-300"
                >
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                  Open saved preview
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
              ) : null}
            </div>
          </footer>
        ) : null}
      </div>
    </div>,
    portalTarget,
  );
}
