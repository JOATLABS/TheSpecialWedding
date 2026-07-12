import React from 'react';
import { notFound } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { Star, CheckCircle, ArrowRight, ExternalLink } from 'lucide-react';

interface StorefrontSettings {
  title: string | null;
  description: string | null;
  hero_image_url: string | null;
  about_image_url: string | null;
  theme_color: string | null;
  packages_enabled: boolean;
  reviews_enabled: boolean;
  contact_email: string | null;
  contact_phone: string | null;
}

interface Planner {
  company_name: string | null;
  first_name: string | null;
  profile_image_url: string | null;
}

interface PackageService {
  name: string;
  description: string | null;
}

interface PackageItem {
  _id: string;
  name: string;
  description: string | null;
  total_amount: number;
  currency: string;
  services: PackageService[];
}

interface ReviewItem {
  _id: string;
  author_name: string;
  rating: number;
  text: string;
  source: string;
  date: string;
}

interface StorefrontData {
  slug: string;
  storefront: StorefrontSettings;
  planner: Planner;
  packages: PackageItem[];
  reviews: ReviewItem[];
}

function formatPackageAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: (currency || 'USD').toUpperCase(),
    maximumFractionDigits: 0,
  }).format(amount);
}

async function getStorefrontData(domain: string): Promise<StorefrontData | null> {
  try {
    // In production, we would use the actual domain. 
    // We pass it directly to the backend.
    const res = await fetch(`${getApiBaseUrl()}/api/storefront/${domain}`, {
      next: { revalidate: 60 } // Cache for 60 seconds
    });
    
    if (!res.ok) {
      return null;
    }
    
    return res.json();
  } catch (e) {
    console.error("Failed to fetch storefront", e);
    return null;
  }
}

export default async function StorefrontPage({ params }: { params: Promise<{ domain: string }> }) {
  const resolvedParams = await params;
  const data = await getStorefrontData(resolvedParams.domain);
  
  if (!data) {
    notFound();
  }
  
  const { storefront, planner, packages, reviews } = data;
  
  // Custom theme overrides
  const themeColor = storefront.theme_color || '#0f172a'; // Default slate-900
  
  return (
    <div className="min-h-screen bg-white text-slate-900 font-sans selection:bg-rose-100">
      {/* Header Navigation */}
      <nav className="fixed w-full z-50 bg-white/80 backdrop-blur-md border-b border-gray-100 transition-all">
        <div className="max-w-6xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {planner.profile_image_url && (
              <img src={planner.profile_image_url} alt={planner.company_name || 'Logo'} className="w-10 h-10 rounded-full object-cover" />
            )}
            <span className="text-xl font-bold tracking-tight text-slate-900">
              {storefront.title || planner.company_name || `${planner.first_name}'s Weddings`}
            </span>
          </div>
          <div className="hidden md:flex gap-8 items-center text-sm font-medium text-slate-600">
            <a href="#about" className="hover:text-slate-900 transition-colors">About</a>
            {storefront.packages_enabled && packages.length > 0 && (
              <a href="#packages" className="hover:text-slate-900 transition-colors">Packages</a>
            )}
            {storefront.reviews_enabled && reviews.length > 0 && (
              <a href="#reviews" className="hover:text-slate-900 transition-colors">Reviews</a>
            )}
            <a 
              href="#contact" 
              className="px-5 py-2.5 rounded-full text-white transition-transform hover:scale-105 shadow-md"
              style={{ backgroundColor: themeColor }}
            >
              Book Consultation
            </a>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 overflow-hidden">
        <div className="absolute inset-0 z-0">
          {storefront.hero_image_url ? (
            <>
              <div className="absolute inset-0 bg-black/40 z-10 mix-blend-multiply" />
              <img 
                src={storefront.hero_image_url} 
                alt="Wedding Hero" 
                className="w-full h-full object-cover"
              />
            </>
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-slate-50 to-slate-100" />
          )}
        </div>
        
        <div className="relative z-10 max-w-6xl mx-auto px-6 text-center">
          <h1 className={`text-5xl md:text-7xl font-extrabold tracking-tight mb-6 ${storefront.hero_image_url ? 'text-white' : 'text-slate-900'}`}>
            {storefront.title || "Curating Unforgettable Weddings"}
          </h1>
          <p className={`text-xl md:text-2xl max-w-3xl mx-auto mb-10 ${storefront.hero_image_url ? 'text-white/90' : 'text-slate-600'}`}>
            {storefront.description || "Expert wedding planning tailored to your unique love story."}
          </p>
          <a 
            href="#contact" 
            className="inline-flex items-center gap-2 px-8 py-4 rounded-full text-lg font-medium text-white transition-all hover:scale-105 hover:shadow-xl"
            style={{ backgroundColor: themeColor }}
          >
            Start Planning
            <ArrowRight className="w-5 h-5" />
          </a>
        </div>
      </section>

      {/* About / Meet the Planner */}
      <section id="about" className="py-24 bg-white">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div className="order-2 md:order-1 relative h-[600px] rounded-3xl overflow-hidden shadow-2xl">
              {storefront.about_image_url ? (
                <img 
                  src={storefront.about_image_url} 
                  alt={planner.first_name || 'Planner'} 
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full bg-slate-200 flex items-center justify-center text-slate-400">
                  No Image Available
                </div>
              )}
            </div>
            <div className="order-1 md:order-2">
              <span className="text-sm font-bold tracking-widest uppercase mb-4 block" style={{ color: themeColor }}>Meet Your Planner</span>
              <h2 className="text-4xl font-bold text-slate-900 mb-6">
                Hi, I'm {planner.first_name}
              </h2>
              <div className="prose prose-lg text-slate-600">
                <p>
                  As the founder of {planner.company_name || 'this planning agency'}, I believe that your wedding day should be a flawless reflection of your personality and love story.
                </p>
                <p>
                  With meticulous attention to detail and a passion for design, my team and I handle the logistics so you can focus on what truly matters: celebrating with your loved ones.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Dynamic Packages Integration */}
      {storefront.packages_enabled && packages.length > 0 && (
        <section id="packages" className="py-24 bg-slate-50">
          <div className="max-w-6xl mx-auto px-6">
            <div className="text-center mb-16">
              <h2 className="text-4xl font-bold text-slate-900 mb-4">Our Packages</h2>
              <p className="text-xl text-slate-600 max-w-2xl mx-auto">
                Comprehensive planning services designed for every stage of your wedding journey.
              </p>
            </div>
            
            <div className="grid md:grid-cols-3 gap-8">
              {packages.map((pkg, idx) => (
                <div 
                  key={pkg._id} 
                  className={`bg-white rounded-3xl p-8 shadow-sm border ${idx === 1 ? 'border-4 transform md:-translate-y-4 shadow-xl' : 'border-gray-100'} transition-all hover:shadow-md`}
                  style={{ borderColor: idx === 1 ? themeColor : undefined }}
                >
                  <h3 className="text-2xl font-bold text-slate-900 mb-2">{pkg.name}</h3>
                  <div className="text-4xl font-extrabold text-slate-900 mb-6">
                    {formatPackageAmount(pkg.total_amount, pkg.currency)}
                  </div>
                  <p className="text-slate-600 mb-8 min-h-[60px]">
                    {pkg.description}
                  </p>
                  <ul className="space-y-4 mb-8">
                    {pkg.services.map((service, serviceIndex) => (
                      <li key={`${service.name}-${serviceIndex}`} className="flex items-start gap-3">
                        <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: themeColor }} />
                        <span className="text-slate-700">
                          <span className="font-medium">{service.name}</span>
                          {service.description && (
                            <span className="block text-sm text-slate-500">{service.description}</span>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <a 
                    href="#contact" 
                    className={`block w-full py-4 text-center rounded-xl font-medium transition-colors ${idx === 1 ? 'text-white' : 'bg-slate-100 text-slate-900 hover:bg-slate-200'}`}
                    style={{ backgroundColor: idx === 1 ? themeColor : undefined }}
                  >
                    Inquire Now
                  </a>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Review Aggregation */}
      {storefront.reviews_enabled && reviews.length > 0 && (
        <section id="reviews" className="py-24 bg-white">
          <div className="max-w-6xl mx-auto px-6">
            <h2 className="text-4xl font-bold text-slate-900 text-center mb-16">Love from our couples</h2>
            <div className="grid md:grid-cols-2 gap-8">
              {reviews.map((review) => (
                <div key={review._id} className="bg-slate-50 rounded-2xl p-8 border border-slate-100">
                  <div className="flex items-center gap-1 mb-4 text-amber-400">
                    {[...Array(5)].map((_, i) => (
                      <Star key={i} className={`w-5 h-5 ${i < review.rating ? 'fill-current' : 'text-slate-200'}`} />
                    ))}
                  </div>
                  <p className="text-lg text-slate-700 italic mb-6">"{review.text}"</p>
                  <div className="flex justify-between items-center text-sm">
                    <span className="font-bold text-slate-900">{review.author_name}</span>
                    <span className="text-slate-500">{review.source}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Vendor CPL Native Ads (Monetization Engine) */}
      <section className="py-20 bg-gradient-to-br from-indigo-50 to-blue-50 border-t border-indigo-100">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-8 bg-white/60 backdrop-blur-md rounded-3xl p-8 shadow-sm border border-white">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-bold tracking-widest text-indigo-600 uppercase">Featured Partners</span>
                <span className="w-8 h-px bg-indigo-200"></span>
              </div>
              <h3 className="text-2xl font-bold text-slate-900 mb-2">Looking for highly rated vendors?</h3>
              <p className="text-slate-600">
                Explore our curated network of premium photographers, florists, and caterers ready to make your day perfect.
              </p>
            </div>
            <a 
              href="/vendors" 
              className="shrink-0 flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-full font-medium hover:bg-indigo-700 transition-colors shadow-md shadow-indigo-200"
            >
              Browse Vendors
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>
      </section>

      {/* Footer / Contact */}
      <footer id="contact" className="bg-slate-950 text-white py-20">
        <div className="max-w-6xl mx-auto px-6 grid md:grid-cols-2 gap-16">
          <div>
            <h2 className="text-4xl font-bold mb-6">Let's craft your perfect day.</h2>
            <p className="text-slate-400 mb-8 text-lg">
              Reach out to check our availability and schedule your complimentary consultation.
            </p>
            <div className="space-y-4 text-slate-300">
              {storefront.contact_email && (
                <p className="flex items-center gap-3">
                  <span className="font-medium text-white">Email:</span> {storefront.contact_email}
                </p>
              )}
              {storefront.contact_phone && (
                <p className="flex items-center gap-3">
                  <span className="font-medium text-white">Phone:</span> {storefront.contact_phone}
                </p>
              )}
            </div>
          </div>
          <div className="bg-slate-900 rounded-2xl p-8">
            {/* Simple Contact Form */}
            <form className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">First Name</label>
                  <input type="text" className="w-full bg-slate-800 border-none rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-white/20" />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Last Name</label>
                  <input type="text" className="w-full bg-slate-800 border-none rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-white/20" />
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Email</label>
                <input type="email" className="w-full bg-slate-800 border-none rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-white/20" />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Wedding Date</label>
                <input type="date" className="w-full bg-slate-800 border-none rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-white/20" />
              </div>
              <button 
                type="button"
                className="w-full py-4 rounded-xl text-white font-bold mt-4 transition-transform hover:scale-[1.02]"
                style={{ backgroundColor: themeColor }}
              >
                Send Inquiry
              </button>
            </form>
          </div>
        </div>
      </footer>
    </div>
  );
}
