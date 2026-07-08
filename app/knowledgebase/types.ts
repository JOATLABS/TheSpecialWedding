export type PublicKBArticle = {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  content?: string;
  category: string;
  tags: string[];
  is_official: boolean;
  featured: boolean;
  author_name: string;
  view_count: number;
  helpful_count: number;
  card_image?: string | null;
  og_image?: string | null;
  estimated_read_minutes: number;
  created_at?: string;
  updated_at?: string;
};

export type PublicKBCategory = {
  category: string;
  display_name: string;
  article_count: number;
};

export type PublicKBArticlesResponse = {
  articles: PublicKBArticle[];
  total: number;
  page: number;
  pages: number;
  limit: number;
};

export type PublicKBCategoriesResponse = {
  categories: PublicKBCategory[];
  total_articles: number;
};
