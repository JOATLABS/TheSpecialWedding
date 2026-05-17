import { MetadataRoute } from 'next';
import {
  ROBOTS_ALLOWED_PATHS,
  ROBOTS_DISALLOWED_PATHS,
} from '@/seo/crawlPolicy';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: [...ROBOTS_ALLOWED_PATHS],
        disallow: [...ROBOTS_DISALLOWED_PATHS],
      },
    ],
    sitemap: 'https://thespecialwedding.io/sitemap.xml',
  };
}
