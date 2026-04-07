const SITE_ORIGIN =
  process.env.FRONTEND_URL ||
  process.env.NEXT_PUBLIC_SITE_URL ||
  'https://thespecialwedding.io';

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
      item: new URL(item.href, SITE_ORIGIN).toString(),
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}
