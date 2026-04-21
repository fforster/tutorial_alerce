// Stamp FITS pipeline.
//
// Both LSST and ZTF stamp endpoints serve gzip-compressed FITS. The browser
// fetches the bytes, gunzips them via DecompressionStream, parses the FITS
// header in 2880-byte blocks, reads the pixel array honoring BITPIX/BZERO/
// BSCALE, applies an asinh stretch over z-scale percentiles, and rotates the
// result so North points up using the CD (or PC+CDELT) matrix.
//
// The template emits one <canvas class="stamp-canvas" data-stamp-url="..."
// data-stamp-type="..."> per stamp; we hook htmx:afterSwap to (re)render each
// one, and rely on the compass / scale overlays painted on the canvas itself
// rather than separate DOM elements.

(function () {
  const rendered = new WeakSet();
  // Cached pre-stretched image per canvas. Lets the zoom controls re-blit
  // without re-fetching / re-parsing FITS on every click.
  const cache = new WeakMap();

  const ZOOM_MIN = 0.25;
  const ZOOM_MAX = 8;

  function getPanelZoom(panel) {
    if (!panel) return 1;
    const z = parseFloat(panel.dataset.zoom || "1");
    return isFinite(z) && z > 0 ? z : 1;
  }

  function setPanelZoom(panel, z) {
    panel.dataset.zoom = String(z);
    const label = panel.querySelector(".stamps-zoom-reset");
    if (label) label.textContent = `${z.toFixed(2)}×`;
  }

  async function loadAndRenderFitsStamp(canvas, url) {
    const card = canvas.closest(".tw-relative") || canvas.parentElement;
    const loadingEl = card?.querySelector(".stamp-loading");
    const compassEl = card?.querySelector(".stamp-compass");

    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      let fitsBuf = await resp.arrayBuffer();

      const magic = new Uint8Array(fitsBuf, 0, 2);
      if (magic[0] === 0x1f && magic[1] === 0x8b) {
        fitsBuf = await gunzip(fitsBuf);
      }

      let fits = parseFitsHeader(fitsBuf, 0);
      if (!fits.naxis1 || !fits.naxis2) {
        if (fits.headerEndByte < fitsBuf.byteLength) {
          fits = parseFitsHeader(fitsBuf, fits.headerEndByte);
        }
      }
      if (!fits.naxis1 || !fits.naxis2) throw new Error("Invalid FITS: no image data");

      const pixels = readFitsImageData(fitsBuf, fits);
      const northAngle = computeNorthAngle(fits.header);
      // Stretch once; cache the resulting source canvas so zoom is cheap.
      const srcCanvas = buildStretchedSrcCanvas(pixels, fits.naxis1, fits.naxis2, fits.header);
      cache.set(canvas, {
        srcCanvas,
        nx: fits.naxis1,
        ny: fits.naxis2,
        northAngle,
        header: fits.header,
      });
      redrawStamp(canvas);

      if (compassEl) {
        compassEl.textContent = Math.abs(northAngle) > 0.001
          ? `N↑ E← (rot ${(-northAngle * 180 / Math.PI).toFixed(1)}°)`
          : "N↑ E←";
      }
      if (loadingEl) loadingEl.style.display = "none";
    } catch (e) {
      console.error("FITS stamp error:", e, url);
      if (loadingEl) loadingEl.textContent = "stamp error";
      if (compassEl) compassEl.textContent = "";
    }
  }

  function redrawStamp(canvas) {
    const cached = cache.get(canvas);
    if (!cached) return;
    const panel = canvas.closest("#stamps-panel");
    const zoom = getPanelZoom(panel);
    blitStampCanvas(canvas, cached, zoom);
  }

  function redrawPanelStamps(panel) {
    if (!panel) return;
    panel.querySelectorAll("canvas.stamp-canvas").forEach(redrawStamp);
  }

  async function gunzip(buffer) {
    const ds = new DecompressionStream("gzip");
    const writer = ds.writable.getWriter();
    writer.write(new Uint8Array(buffer));
    writer.close();
    const reader = ds.readable.getReader();
    const chunks = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
    }
    const total = chunks.reduce((s, c) => s + c.length, 0);
    const out = new Uint8Array(total);
    let offset = 0;
    for (const c of chunks) { out.set(c, offset); offset += c.length; }
    return out.buffer;
  }

  function parseFitsHeader(buffer, startOffset) {
    const bytes = new Uint8Array(buffer);
    const decoder = new TextDecoder("ascii");
    const header = {};
    let headerEndByte = 0;

    for (let block = 0; block < 100; block++) {
      const blockStart = startOffset + block * 2880;
      if (blockStart >= bytes.length) break;
      let foundEnd = false;
      for (let i = 0; i < 36; i++) {
        const recStart = blockStart + i * 80;
        if (recStart + 80 > bytes.length) break;
        const record = decoder.decode(bytes.slice(recStart, recStart + 80));
        const keyword = record.substring(0, 8).trim();

        if (keyword === "END") {
          headerEndByte = startOffset + (block + 1) * 2880;
          foundEnd = true;
          break;
        }

        if (record.charAt(8) === "=" && record.charAt(9) === " ") {
          let valStr = record.substring(10).split("/")[0].trim();
          if (valStr.startsWith("'")) {
            header[keyword] = valStr.replace(/'/g, "").trim();
          } else if (valStr === "T") {
            header[keyword] = true;
          } else if (valStr === "F") {
            header[keyword] = false;
          } else if (valStr !== "") {
            const num = parseFloat(valStr);
            if (!isNaN(num)) header[keyword] = num;
          }
        }
      }
      if (foundEnd) break;
    }

    return {
      header,
      naxis1: header.NAXIS1 || 0,
      naxis2: header.NAXIS2 || 0,
      bitpix: header.BITPIX || -32,
      headerEndByte,
    };
  }

  function readFitsImageData(buffer, fits) {
    const { naxis1, naxis2, bitpix, headerEndByte, header } = fits;
    const npix = naxis1 * naxis2;
    const dv = new DataView(buffer, headerEndByte);
    const pixels = new Float64Array(npix);
    const bpp = Math.abs(bitpix) / 8;

    for (let i = 0; i < npix; i++) {
      const off = i * bpp;
      if (off + bpp > dv.byteLength) break;
      if (bitpix === -32) pixels[i] = dv.getFloat32(off, false);
      else if (bitpix === -64) pixels[i] = dv.getFloat64(off, false);
      else if (bitpix === 16) pixels[i] = dv.getInt16(off, false);
      else if (bitpix === 32) pixels[i] = dv.getInt32(off, false);
      else if (bitpix === 8) pixels[i] = dv.getUint8(off);
    }

    const bzero = header.BZERO || 0;
    const bscale = header.BSCALE || 1;
    if (bzero !== 0 || bscale !== 1) {
      for (let i = 0; i < npix; i++) pixels[i] = pixels[i] * bscale + bzero;
    }
    return pixels;
  }

  function computeNorthAngle(header) {
    let cd11 = header.CD1_1;
    let cd12 = header.CD1_2;
    let cd21 = header.CD2_1;
    let cd22 = header.CD2_2;

    if (cd11 == null || cd22 == null) {
      const pc11 = header.PC1_1 ?? header.PC001001;
      const pc12 = header.PC1_2 ?? header.PC001002;
      const pc21 = header.PC2_1 ?? header.PC002001;
      const pc22 = header.PC2_2 ?? header.PC002002;
      const cdelt1 = header.CDELT1;
      const cdelt2 = header.CDELT2;
      if (pc11 != null && pc22 != null && cdelt1 != null && cdelt2 != null) {
        cd11 = pc11 * cdelt1;
        cd12 = (pc12 || 0) * cdelt2;
        cd21 = (pc21 || 0) * cdelt1;
        cd22 = pc22 * cdelt2;
      } else if (cdelt1 != null && cdelt2 != null) {
        const crota2 = (header.CROTA2 || 0) * Math.PI / 180;
        cd11 = cdelt1 * Math.cos(crota2);
        cd12 = -cdelt2 * Math.sin(crota2);
        cd21 = cdelt1 * Math.sin(crota2);
        cd22 = cdelt2 * Math.cos(crota2);
      } else {
        return 0;
      }
    }
    if (cd12 == null) cd12 = 0;
    if (cd21 == null) cd21 = 0;

    const det = cd11 * cd22 - cd12 * cd21;
    if (Math.abs(det) < 1e-20) return 0;
    const dpx = -cd12 / det;
    const dpy = cd11 / det;
    return Math.atan2(dpx, dpy);
  }

  function zscaleStretch(pixels) {
    const valid = [];
    for (let i = 0; i < pixels.length; i++) {
      if (isFinite(pixels[i])) valid.push(pixels[i]);
    }
    if (!valid.length) return { vmin: 0, vmax: 1 };
    valid.sort((a, b) => a - b);
    const n = valid.length;
    const vmin = valid[Math.floor(n * 0.01)];
    let vmax = valid[Math.floor(n * 0.995)];
    if (vmax === vmin) vmax = vmin + 1;
    return { vmin, vmax };
  }

  function buildStretchedSrcCanvas(pixels, nx, ny, header) {
    const { vmin, vmax } = zscaleStretch(pixels);
    const cdelt2 = header.CD2_2 || header.CDELT2;
    const flipY = (cdelt2 != null && cdelt2 > 0);

    const srcCanvas = document.createElement("canvas");
    srcCanvas.width = nx;
    srcCanvas.height = ny;
    const srcCtx = srcCanvas.getContext("2d");
    const imgData = srcCtx.createImageData(nx, ny);
    const a = 10;

    for (let row = 0; row < ny; row++) {
      for (let col = 0; col < nx; col++) {
        const fitsIdx = row * nx + col;
        const canvasRow = flipY ? (ny - 1 - row) : row;
        const canvasIdx = (canvasRow * nx + col) * 4;
        let val = pixels[fitsIdx];
        if (!isFinite(val)) val = vmin;
        let norm = (vmax !== vmin) ? (val - vmin) / (vmax - vmin) : 0.5;
        norm = Math.max(0, Math.min(1, norm));
        norm = Math.asinh(norm * a) / Math.asinh(a);
        const byte = Math.round(norm * 255);
        imgData.data[canvasIdx] = byte;
        imgData.data[canvasIdx + 1] = byte;
        imgData.data[canvasIdx + 2] = byte;
        imgData.data[canvasIdx + 3] = 255;
      }
    }
    srcCtx.putImageData(imgData, 0, 0);
    return srcCanvas;
  }

  function blitStampCanvas(canvas, cached, zoom) {
    const { srcCanvas, nx, ny, northAngle, header } = cached;
    const outSize = canvas.width;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, outSize, outSize);

    // Fit-to-canvas baseline × user zoom. Because the transform scales about
    // the canvas centre (translate then scale), the object — which sits at
    // the cutout centre — stays anchored while the field of view shrinks.
    const baseScale = outSize / Math.max(nx, ny);
    const scale = baseScale * (zoom || 1);

    ctx.save();
    ctx.translate(outSize / 2, outSize / 2);
    ctx.rotate(-northAngle);
    ctx.scale(scale, scale);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(srcCanvas, -nx / 2, -ny / 2, nx, ny);
    ctx.restore();
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    drawCompass(ctx, outSize);
    drawScaleBar(ctx, outSize, scale, header);
  }

  function drawCompass(ctx, size) {
    const cx = size - 20;
    const cy = 20;
    const len = 14;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.strokeStyle = "#58a6ff";
    ctx.fillStyle = "#58a6ff";
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -len); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, -len); ctx.lineTo(-3, -len + 5); ctx.lineTo(3, -len + 5);
    ctx.closePath(); ctx.fill();
    ctx.font = "9px IBM Plex Mono";
    ctx.textAlign = "center";
    ctx.fillText("N", 0, -len - 4);

    ctx.strokeStyle = "#f85149";
    ctx.fillStyle = "#f85149";
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-len, 0); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-len, 0); ctx.lineTo(-len + 5, -3); ctx.lineTo(-len + 5, 3);
    ctx.closePath(); ctx.fill();
    ctx.fillText("E", -len - 4, 3);
    ctx.restore();
  }

  function drawScaleBar(ctx, canvasSize, imageScale, header) {
    let pixScaleArcsec = 0;
    const cd11 = header.CD1_1;
    const cd12 = header.CD1_2 || 0;
    const cd21 = header.CD2_1 || 0;
    const cd22 = header.CD2_2;
    if (cd11 != null && cd22 != null) {
      const det = Math.abs(cd11 * cd22 - cd12 * cd21);
      const arcsec = Math.sqrt(det) * 3600;
      if (arcsec > 0 && arcsec < 10) pixScaleArcsec = arcsec;
    }
    if (!pixScaleArcsec) {
      const cdelt1 = header.CDELT1;
      const cdelt2 = header.CDELT2;
      if (cdelt1 != null && cdelt2 != null) {
        const arcsec = Math.sqrt(Math.abs(cdelt1 * cdelt2)) * 3600;
        if (arcsec > 0 && arcsec < 10) pixScaleArcsec = arcsec;
      }
    }
    if (!pixScaleArcsec) pixScaleArcsec = 1.0;  // ZTF ~1"/px, LSST ~0.2"/px; 1" is a sane fallback

    const pxPerArcsec = imageScale / pixScaleArcsec;
    let barArcsec = 1;
    let barPx = pxPerArcsec * barArcsec;
    if (barPx < 15) { barArcsec = 5; barPx = pxPerArcsec * 5; }
    if (barPx < 15) { barArcsec = 10; barPx = pxPerArcsec * 10; }
    if (barPx > canvasSize * 0.5) { barArcsec = 0.5; barPx = pxPerArcsec * 0.5; }
    if (barPx > canvasSize * 0.5) { barArcsec = 0.2; barPx = pxPerArcsec * 0.2; }

    const padX = 8;
    const padY = 10;
    const y = canvasSize - padY;
    const x0 = padX;
    const x1 = x0 + barPx;

    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.fillRect(x0 - 4, y - 20, barPx + 8, 26);
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(x0, y - 6); ctx.lineTo(x0, y + 4); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x1, y - 6); ctx.lineTo(x1, y + 4); ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 11px IBM Plex Mono";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(`${barArcsec}″`, (x0 + x1) / 2, y - 7);
    ctx.restore();
  }

  function initCanvas(canvas) {
    if (rendered.has(canvas)) return;
    const url = canvas.dataset.stampUrl;
    if (!url) return;
    rendered.add(canvas);
    loadAndRenderFitsStamp(canvas, url);
  }

  function initAll(root) {
    (root || document).querySelectorAll("canvas.stamp-canvas").forEach(initCanvas);
  }

  // Zero-round-trip identifier swap: the server emits stamp URL templates with
  // __IDENT__ placeholders as data attrs on #stamps-panel. We rewrite each
  // canvas's URL locally and force a re-render — no hit to our server.
  window.updateStampsForIdentifier = function (ident) {
    if (!ident) return;
    const panel = document.getElementById("stamps-panel");
    if (!panel) return;
    const canvases = panel.querySelectorAll("canvas.stamp-canvas");
    canvases.forEach((canvas) => {
      const type = canvas.dataset.stampType;
      const tpl = panel.dataset[`urlTemplate${type.charAt(0).toUpperCase() + type.slice(1)}`]
        || panel.getAttribute(`data-url-template-${type}`);
      if (!tpl) return;
      canvas.dataset.stampUrl = tpl.replace("__IDENT__", encodeURIComponent(ident));
      rendered.delete(canvas);
      cache.delete(canvas);
      const card = canvas.closest(".tw-relative") || canvas.parentElement;
      const loadingEl = card?.querySelector(".stamp-loading");
      const compassEl = card?.querySelector(".stamp-compass");
      if (loadingEl) { loadingEl.textContent = "loading…"; loadingEl.style.display = ""; }
      if (compassEl) compassEl.textContent = "";
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      initCanvas(canvas);
    });
    const picker = panel.querySelector('select[name="identifier"]');
    if (picker && picker.value !== String(ident)) picker.value = String(ident);
  };

  // Apply a zoom factor (relative multiplier, or the string "reset") to every
  // stamp in the panel containing the clicked button. Scaling happens about
  // the canvas centre in blitStampCanvas, so the object stays put.
  window.zoomStamps = function (originEl, factor) {
    const panel = originEl?.closest("#stamps-panel") || document.getElementById("stamps-panel");
    if (!panel) return;
    let z = factor === "reset" ? 1 : getPanelZoom(panel) * Number(factor);
    if (!isFinite(z) || z <= 0) return;
    z = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
    setPanelZoom(panel, z);
    redrawPanelStamps(panel);
  };

  document.addEventListener("DOMContentLoaded", () => initAll(document));
  document.addEventListener("htmx:afterSwap", (evt) => initAll(evt.detail.target));
})();
