export interface PublicStorefrontSettings {
  title: string | null;
  description: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  hero_image_url: string | null;
  about_image_url: string | null;
  theme_color: string;
  packages_enabled: boolean;
  reviews_enabled: boolean;
}

export interface PublicStorefrontPlanner {
  company_name: string | null;
  first_name: string | null;
  profile_image_url: string | null;
}

export interface PublicStorefrontPackageService {
  name: string;
  description: string | null;
}

export interface PublicStorefrontPackage {
  _id: string;
  name: string;
  description: string | null;
  total_amount: number;
  currency: string;
  services: PublicStorefrontPackageService[];
}

export interface PublicStorefrontReview {
  _id: string;
  author_name: string | null;
  rating: number | null;
  text: string | null;
  source: string | null;
  date: string | null;
}

export interface PublicStorefrontData {
  slug: string;
  storefront: PublicStorefrontSettings;
  planner: PublicStorefrontPlanner;
  packages: PublicStorefrontPackage[];
  reviews: PublicStorefrontReview[];
}

export interface StorefrontInquiryPayload {
  name: string;
  email: string;
  phone?: string;
  wedding_date?: string;
  message: string;
}

export interface StorefrontInquiryResult {
  success: boolean;
  inquiry_id: string;
  message: string;
}

