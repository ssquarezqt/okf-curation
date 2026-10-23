/**
 * Cliente de la API de reclamaciones (servicio-reclamaciones).
 */
const base = import.meta.env.VITE_CLAIMS_API_URL as string;

export interface NewClaim {
  booking_ref: string;
  flight_number: string;
  delay_minutes: number;
  amount: number;
}

export async function createClaim(claim: NewClaim, token: string): Promise<{ claim_id: string; status: string }> {
  const res = await fetch(`${base}/claims`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(claim),
  });
  if (res.status === 422) throw new Error('El retraso no da derecho a compensación');
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function getClaim(id: string, token: string) {
  const res = await fetch(`${base}/claims/${id}`, { headers: { Authorization: `Bearer ${token}` } });
  if (res.status === 404) return null;
  return res.json();
}
