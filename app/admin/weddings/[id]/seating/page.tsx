import { redirect } from 'next/navigation';

type SeatingRedirectPageProps = {
  params: Promise<{ id: string }>;
};

export default async function SeatingRedirectPage({ params }: SeatingRedirectPageProps) {
  const { id } = await params;
  redirect(`/admin/seating?weddingId=${encodeURIComponent(id)}`);
}
