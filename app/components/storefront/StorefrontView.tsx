import { ArrowRight, CheckCircle2, Star } from 'lucide-react';
import type { ReactNode } from 'react';

import type { PublicStorefrontData } from '@/storefront/storefrontTypes';

export type StorefrontViewData = PublicStorefrontData;

interface StorefrontViewProps {
  data: StorefrontViewData;
  previewMode?: boolean;
  inquiryForm?: ReactNode;
}

function formatPackageAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: (currency || 'USD').toUpperCase(),
    maximumFractionDigits: 0,
  }).format(amount);
}

export function StorefrontView({
  data,
  previewMode = false,
  inquiryForm,
}: StorefrontViewProps) {
  const { storefront, planner, packages, reviews } = data;
  const themeColor = storefront.theme_color || '#0f172a';
  const brandName =
    storefront.title ||
    planner.company_name ||
    (planner.first_name ? `${planner.first_name}'s Weddings` : 'Wedding Planning');

  return (
    <div className="min-h-full bg-white font-sans text-slate-900 selection:bg-rose-100">
      {previewMode ? (
        <div
          role="status"
          className="bg-amber-50 px-4 py-2 text-center text-xs font-semibold text-amber-900"
        >
          Live design preview · unsaved changes are visible · inquiries are disabled
        </div>
      ) : null}

      <nav className="border-b border-slate-100 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex h-20 max-w-6xl items-center justify-between px-6">
          <div className="flex min-w-0 items-center gap-3">
            {planner.profile_image_url ? (
              // Dynamic planner images are served from a runtime-configured CDN.
              <img
                src={planner.profile_image_url}
                alt=""
                className="h-10 w-10 rounded-full object-cover"
              />
            ) : null}
            <span className="truncate text-xl font-bold tracking-tight">{brandName}</span>
          </div>
          <a
            href="#contact"
            className="rounded-full px-4 py-2 text-sm font-semibold text-white shadow-sm"
            style={{ backgroundColor: themeColor }}
          >
            Book consultation
          </a>
        </div>
      </nav>

      <section className="relative isolate overflow-hidden px-6 py-24 text-center md:py-32">
        {storefront.hero_image_url ? (
          <>
            <div className="absolute inset-0 -z-10 bg-slate-950/50" />
            <img
              src={storefront.hero_image_url}
              alt=""
              className="absolute inset-0 -z-20 h-full w-full object-cover"
            />
          </>
        ) : (
          <div className="absolute inset-0 -z-10 bg-gradient-to-br from-slate-50 to-slate-200" />
        )}
        <div className="mx-auto max-w-4xl">
          <h1
            className={`text-4xl font-extrabold tracking-tight md:text-6xl ${
              storefront.hero_image_url ? 'text-white' : 'text-slate-950'
            }`}
          >
            {storefront.title || 'Curating unforgettable weddings'}
          </h1>
          <p
            className={`mx-auto mt-6 max-w-2xl text-lg md:text-xl ${
              storefront.hero_image_url ? 'text-white/90' : 'text-slate-600'
            }`}
          >
            {storefront.description ||
              'Expert wedding planning tailored to your unique love story.'}
          </p>
          <a
            href="#contact"
            className="mt-8 inline-flex items-center gap-2 rounded-full px-6 py-3 font-semibold text-white shadow-lg"
            style={{ backgroundColor: themeColor }}
          >
            Start planning
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </a>
        </div>
      </section>

      <section id="about" className="bg-white px-6 py-20">
        <div className="mx-auto grid max-w-6xl items-center gap-12 md:grid-cols-2">
          <div className="h-80 overflow-hidden rounded-3xl bg-slate-100 md:h-[32rem]">
            {storefront.about_image_url ? (
              <img
                src={storefront.about_image_url}
                alt={planner.first_name ? `${planner.first_name}, wedding planner` : 'Wedding planner'}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full items-center justify-center px-8 text-center text-sm text-slate-400">
                Add an about image to introduce the planner.
              </div>
            )}
          </div>
          <div>
            <p
              className="text-sm font-bold uppercase tracking-[0.2em]"
              style={{ color: themeColor }}
            >
              Meet your planner
            </p>
            <h2 className="mt-4 text-4xl font-bold text-slate-950">
              {planner.first_name ? `Hi, I'm ${planner.first_name}` : brandName}
            </h2>
            <p className="mt-6 text-lg leading-8 text-slate-600">
              {storefront.description ||
                `As the team behind ${planner.company_name || brandName}, we handle every detail so couples can stay present for their celebration.`}
            </p>
          </div>
        </div>
      </section>

      {storefront.packages_enabled && packages.length > 0 ? (
        <section id="packages" className="bg-slate-50 px-6 py-20">
          <div className="mx-auto max-w-6xl">
            <div className="mb-12 text-center">
              <h2 className="text-4xl font-bold">Planning packages</h2>
              <p className="mt-3 text-slate-600">
                Choose the level of support that fits your celebration.
              </p>
            </div>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {packages.map((pkg) => (
                <article
                  key={pkg._id}
                  className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm"
                >
                  <h3 className="text-2xl font-bold">{pkg.name}</h3>
                  <p className="mt-2 text-3xl font-extrabold">
                    {formatPackageAmount(pkg.total_amount, pkg.currency)}
                  </p>
                  {pkg.description ? (
                    <p className="mt-4 text-slate-600">{pkg.description}</p>
                  ) : null}
                  <ul className="mt-6 space-y-3">
                    {pkg.services.map((service, index) => (
                      <li key={`${service.name}-${index}`} className="flex items-start gap-3">
                        <CheckCircle2
                          className="mt-0.5 h-5 w-5 shrink-0"
                          style={{ color: themeColor }}
                          aria-hidden="true"
                        />
                        <span>
                          <span className="font-medium">{service.name}</span>
                          {service.description ? (
                            <span className="block text-sm text-slate-500">
                              {service.description}
                            </span>
                          ) : null}
                        </span>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {storefront.reviews_enabled && reviews.length > 0 ? (
        <section id="reviews" className="bg-white px-6 py-20">
          <div className="mx-auto max-w-6xl">
            <h2 className="text-center text-4xl font-bold">Love from our couples</h2>
            <div className="mt-12 grid gap-6 md:grid-cols-2">
              {reviews.map((review) => {
                const rating = Math.max(0, Math.min(5, Math.round(review.rating ?? 0)));
                return (
                  <article key={review._id} className="rounded-2xl bg-slate-50 p-7">
                    <div className="flex gap-1" aria-label={`${rating} out of 5 stars`}>
                      {Array.from({ length: 5 }, (_, index) => (
                        <Star
                          key={index}
                          className={`h-5 w-5 ${
                            index < rating ? 'fill-amber-400 text-amber-400' : 'text-slate-300'
                          }`}
                          aria-hidden="true"
                        />
                      ))}
                    </div>
                    {review.text ? (
                      <p className="mt-4 text-lg italic text-slate-700">“{review.text}”</p>
                    ) : null}
                    <div className="mt-5 flex justify-between gap-4 text-sm">
                      <span className="font-bold">{review.author_name || 'Verified couple'}</span>
                      {review.source ? <span className="text-slate-500">{review.source}</span> : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>
      ) : null}

      <footer id="contact" className="bg-slate-950 px-6 py-20 text-white">
        <div className="mx-auto grid max-w-6xl gap-10 md:grid-cols-2">
          <div>
            <h2 className="text-4xl font-bold">Let&apos;s craft your perfect day.</h2>
            <p className="mt-5 text-lg text-slate-400">
              Reach out to check availability and schedule a consultation.
            </p>
            <div className="mt-8 space-y-3 text-slate-300">
              {storefront.contact_email ? (
                <p>
                  <span className="font-semibold text-white">Email:</span>{' '}
                  {storefront.contact_email}
                </p>
              ) : null}
              {storefront.contact_phone ? (
                <p>
                  <span className="font-semibold text-white">Phone:</span>{' '}
                  {storefront.contact_phone}
                </p>
              ) : null}
            </div>
          </div>
          <div className="rounded-2xl bg-slate-900 p-7">
            {previewMode ? (
              <button
                type="button"
                disabled
                className="w-full cursor-not-allowed rounded-xl px-5 py-4 font-bold text-white opacity-70"
                style={{ backgroundColor: themeColor }}
              >
                Inquiries disabled in preview
              </button>
            ) : (
              inquiryForm ?? (
                <a
                  href={storefront.contact_email ? `mailto:${storefront.contact_email}` : '#'}
                  className="block w-full rounded-xl px-5 py-4 text-center font-bold text-white"
                  style={{ backgroundColor: themeColor }}
                >
                  Contact this planner
                </a>
              )
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}
