import Image from "next/image";
import Link from "next/link";
import { MARKETING_FEATURES } from "@/data/marketingFeatures";

export function FeatureShowcase() {
  const features = MARKETING_FEATURES;
  const leadFeatures = features.slice(0, 4);
  const supportingFeatures = features.slice(4);

  return (
    <div className="space-y-8">
      <div className="grid gap-6 lg:grid-cols-2">
        {leadFeatures.map((feature) => (
          <article
            key={feature.id}
            className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.045] shadow-2xl shadow-black/25"
          >
            <div className="relative aspect-[16/9] border-b border-white/10 bg-[#071020] p-2 sm:p-3">
              <Image
                src={feature.image}
                alt={`${feature.title}: ${feature.tagline}`}
                fill
                sizes="(min-width: 1280px) 604px, (min-width: 1024px) 46vw, calc(100vw - 48px)"
                className="object-contain object-top"
                loading="lazy"
              />
            </div>
            <div className="p-5 sm:p-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-wedding-rose">{feature.category}</p>
              <h3 className="mt-3 text-2xl font-semibold text-white">{feature.title}</h3>
              <p className="mt-3 text-sm font-semibold leading-6 text-slate-200">{feature.tagline}</p>
              <p className="mt-3 line-clamp-3 text-sm leading-7 text-slate-300">{feature.description}</p>
              {feature.blogSlug ? (
                <Link
                  href={`/resources/blog/${feature.blogSlug}`}
                  className="mt-4 inline-flex text-sm font-semibold text-wedding-rose transition hover:text-wedding-blush"
                >
                  Read the story
                </Link>
              ) : null}
            </div>
          </article>
        ))}
      </div>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {supportingFeatures.map((feature) => (
          <article
            key={feature.id}
            className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.035] transition hover:border-wedding-rose/40 hover:bg-white/[0.055]"
          >
            <div className="relative aspect-[16/10] border-b border-white/10 bg-[#071020] p-2">
              <Image
                src={feature.image}
                alt={`${feature.title}: ${feature.tagline}`}
                fill
                sizes="(min-width: 1280px) 389px, (min-width: 768px) 45vw, calc(100vw - 48px)"
                className="object-contain object-top"
                loading="lazy"
              />
            </div>
            <div className="p-5">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-wedding-rose">{feature.category}</p>
              <h3 className="mt-2 text-lg font-semibold text-white">{feature.title}</h3>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-300">{feature.tagline}</p>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
