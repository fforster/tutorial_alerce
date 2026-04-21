/* Milky-Way E(B-V) lookup for the Fitzpatrick (1999) extinction correction.
 *
 * Source: a Cloudflare-Worker proxy in front of IRSA's dust service. The
 * proxy returns { ebv_sf11, ebv_sfd98, ... }; we prefer SF11 and fall back
 * to SFD98. Results are cached in-memory, keyed by (ra, dec) rounded to
 * 0.01° (~36 arcsec) — dust maps are smooth on that scale, so the same
 * E(B-V) serves nearby objects without a refetch.
 *
 * At low Galactic latitude (|b| < 5°) the dust columns can over-correct
 * and we log a warning; the value is still returned because the user may
 * have reasons to use it anyway (or override via manual input).
 *
 * Exposed as window.dust.{fetchEBV, galacticLatitude}.
 */
(function () {
  const DUST_PROXY_URL = "https://dust-proxy.francisco-forster.workers.dev/";
  const REQUEST_TIMEOUT_MS = 15000;
  const cache = Object.create(null);

  // J2000 → Galactic conversion (Reid & Brunthaler 2004 pole/node).
  // Only |b| is used downstream, so l is discarded.
  function galacticLatitude(raDeg, decDeg) {
    const toRad = Math.PI / 180;
    const ra = raDeg * toRad;
    const dec = decDeg * toRad;
    const decNGP = 27.12825 * toRad;
    const raNGP  = 192.85948 * toRad;
    const sinB = Math.sin(dec) * Math.sin(decNGP)
               + Math.cos(dec) * Math.cos(decNGP) * Math.cos(ra - raNGP);
    return Math.asin(sinB) / toRad;
  }

  function cacheKey(ra, dec) {
    return `${ra.toFixed(2)}_${dec.toFixed(2)}`;
  }

  // Returns { ebv, source, ebv_sf11, ebv_sfd98 } on success or null on failure.
  // Silent on network/HTTP/timeout — callers keep working with manual E(B-V).
  async function fetchEBV(ra, dec) {
    if (!isFinite(ra) || !isFinite(dec)) return null;
    const key = cacheKey(ra, dec);
    if (cache[key] !== undefined) return cache[key];

    try {
      const url = `${DUST_PROXY_URL}?ra=${ra}&dec=${dec}`;
      const resp = await fetch(url, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
      if (!resp.ok) { cache[key] = null; return null; }
      const data = await resp.json();
      const sf11 = typeof data.ebv_sf11 === "number" ? data.ebv_sf11 : null;
      const sfd98 = typeof data.ebv_sfd98 === "number" ? data.ebv_sfd98 : null;
      const ebv = sf11 != null ? sf11 : sfd98;
      if (ebv == null || !isFinite(ebv) || ebv < 0) {
        cache[key] = null;
        return null;
      }
      const out = {
        ebv,
        source: sf11 != null ? "SF11" : "SFD98",
        ebv_sf11: sf11,
        ebv_sfd98: sfd98,
      };
      cache[key] = out;
      const b = galacticLatitude(ra, dec);
      if (Math.abs(b) < 5) {
        console.warn(`E(B-V) = ${ebv.toFixed(4)} at low |b| = ${Math.abs(b).toFixed(1)}° — may over-correct`);
      }
      return out;
    } catch (e) {
      console.warn("E(B-V) fetch failed:", e.message);
      cache[key] = null;
      return null;
    }
  }

  window.dust = { fetchEBV, galacticLatitude };
})();
