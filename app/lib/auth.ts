import { cookies } from 'next/headers';

/**
 * Server-side function to check if user is authenticated
 * This runs on the server and has access to httpOnly cookies
 */
export async function getSession() {
  const cookieStore = await cookies();
  const token = cookieStore.get('admin_token');

  if (!token) {
    return null;
  }

  // Token exists, return session info (not the actual token)
  return {
    isAuthenticated: true,
    // We don't expose the actual token to the client
  };
}

/**
 * Server-side function to verify session validity
 * Can be extended to validate token with backend
 */
export async function verifySession() {
  const session = await getSession();

  if (!session) {
    return { isValid: false };
  }

  // In production, you might want to verify the token with your backend
  // For now, we just check if it exists
  return {
    isValid: true,
    isAuthenticated: true
  };
}