/* Valgfritt: et ekte opplastings-endepunkt.
 *
 * GitHub Pages kan bare servere filer, det kan ikke ta imot opplastinger.
 * Trenger du en adresse telefon-appen kan sende CSV-filen til, kan du legge
 * denne på Cloudflare Workers (gratisnivået holder i massevis).
 *
 *   POST https://<navn>.workers.dev/?token=HEMMELIG   → lagrer filen
 *   GET  https://<navn>.workers.dev/?token=HEMMELIG   → leverer siste fil
 *
 * GET-adressen limer du inn i «Hent fra nettadresse» i appen.
 *
 * Oppsett:
 *   npm install -g wrangler
 *   wrangler kv namespace create TIMER
 *   (lim inn id-en i wrangler.toml)
 *   wrangler secret put TOKEN
 *   wrangler deploy
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': '*'
    };

    if (request.method === 'OPTIONS') return new Response(null, { headers: cors });

    const token = url.searchParams.get('token') || (request.headers.get('authorization') || '').replace(/^Bearer\s+/i, '');
    if (!env.TOKEN || token !== env.TOKEN) {
      return new Response('Feil eller manglende token.', { status: 401, headers: cors });
    }

    if (request.method === 'POST' || request.method === 'PUT') {
      let innhold = '';
      const type = request.headers.get('content-type') || '';
      if (type.includes('multipart/form-data') || type.includes('application/x-www-form-urlencoded')) {
        const skjema = await request.formData();
        const fil = skjema.get('file') || skjema.get('csv') || skjema.get('data');
        innhold = fil && fil.text ? await fil.text() : String(fil || '');
      } else {
        innhold = await request.text();
      }
      if (!innhold.trim()) return new Response('Tom fil.', { status: 400, headers: cors });

      await env.TIMER.put('siste', innhold);
      await env.TIMER.put('oppdatert', new Date().toISOString());
      return new Response('Lagret ' + innhold.length + ' tegn.', { headers: cors });
    }

    const data = await env.TIMER.get('siste');
    if (data === null) return new Response('Ingen fil lastet opp ennå.', { status: 404, headers: cors });
    return new Response(data, {
      headers: { ...cors, 'content-type': 'text/csv; charset=utf-8', 'cache-control': 'no-store' }
    });
  }
};
