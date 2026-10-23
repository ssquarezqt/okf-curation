import { createClaim } from '../services/api';

export function NewClaimPage({ token }: { token: string }) {
  async function submit(form: FormData) {
    const r = await createClaim({
      booking_ref: String(form.get('booking_ref')),
      flight_number: String(form.get('flight_number')),
      delay_minutes: Number(form.get('delay_minutes')),
      amount: Number(form.get('amount')),
    }, token);
    alert(r.status === 'APPROVED' ? 'Aprobada' : 'Enviada a revisión');
  }
  return <form action={submit}>...</form>;
}
