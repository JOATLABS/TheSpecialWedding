import { redirect } from 'next/navigation';

export default function CommunicationsIndexPage() {
  redirect('/admin/communications/inbox');
}
