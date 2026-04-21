/* Planck-2018 flat ΛCDM cosmology (H0=67.4, Ωm=0.315, ΩΛ=0.685).
 *
 * Comoving distance is computed by 1000-step midpoint integration of
 *   dc = (c/H0) · ∫₀ᶻ dz' / E(z'),   E(z) = sqrt(Ωm·(1+z)³ + ΩΛ),
 * which is dense enough that plot-level precision is never the limit
 * (error << 1 mmag for z < 5). Luminosity distance and distance
 * modulus follow from the standard relations.
 *
 * Exposed as window.cosmology so future panels (folded LC, periodogram)
 * can reuse it without a second implementation.
 */
(function () {
  const H0 = 67.4;        // km/s/Mpc
  const Om = 0.315;
  const OL = 0.685;
  const C_KM_S = 299792.458;

  function comovingDistance(z) {
    if (!(z > 0) || !isFinite(z)) return NaN;
    const nSteps = 1000;
    const dz = z / nSteps;
    let integral = 0;
    for (let i = 0; i < nSteps; i++) {
      const zMid = (i + 0.5) * dz;
      const Ez = Math.sqrt(Om * Math.pow(1 + zMid, 3) + OL);
      integral += dz / Ez;
    }
    return (C_KM_S / H0) * integral;  // Mpc
  }

  function luminosityDistance(z) {
    const dc = comovingDistance(z);
    return isFinite(dc) ? (1 + z) * dc : NaN;
  }

  function distanceModulus(z) {
    // μ = 5·log10(d_L / 10 pc) = 5·log10(d_L_Mpc) + 25
    const dL = luminosityDistance(z);
    if (!isFinite(dL) || dL <= 0) return NaN;
    return 5 * Math.log10(dL) + 25;
  }

  window.cosmology = { comovingDistance, luminosityDistance, distanceModulus };
})();
