const DEFAULT_SITE_ORIGIN = 'https://thespecialwedding.io';

function isSupportedPublicOrigin(value: string | undefined): value is string {
  if (!value) {
    return false;
  }

  try {
    const url = new URL(value);
    const isHttpOrigin = url.protocol === 'https:' || url.protocol === 'http:';
    const hostname = url.hostname.toLowerCase();
    const isInvalidTld = hostname === 'invalid' || hostname.endsWith('.invalid');

    return isHttpOrigin && !isInvalidTld;
  } catch {
    return false;
  }
}

export function getBreadcrumbSchemaOrigin() {
  const configuredOrigins = [process.env.FRONTEND_URL, process.env.NEXT_PUBLIC_SITE_URL];

  for (const configuredOrigin of configuredOrigins) {
    const candidateOrigin = configuredOrigin?.trim();
    if (isSupportedPublicOrigin(candidateOrigin)) {
      return new URL(candidateOrigin).origin;
    }
  }

  return DEFAULT_SITE_ORIGIN;
}

type BreadcrumbItem = {
  name: string;
  href: string;
};

export default function BreadcrumbSchema({ items }: { items: BreadcrumbItem[] }) {
  if (items.length < 2) {
    return null;
  }

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: new URL(item.href, getBreadcrumbSchemaOrigin()).toString(),
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}
