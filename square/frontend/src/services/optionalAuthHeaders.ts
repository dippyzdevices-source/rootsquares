import { supabase } from './supabaseClient'

// For otherwise-public GETs where a signed-in admin additionally receives hidden/draft items
// (tagged `published: false`) so they can preview them before going live. It only ever decides
// what the response includes, never whether the request succeeds: no session, an expired token
// or a non-admin role all behave exactly like an anonymous visitor, so this swallows any error.
export async function optionalAuthHeaders(): Promise<HeadersInit> {
  try {
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}
