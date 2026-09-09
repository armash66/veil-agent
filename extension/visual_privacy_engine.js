/**
 * WebVeil — Visual Privacy Engine (In-Browser Canvas Redactor)
 * 
 * Strict Egress Invariant:
 * Raw pixels remain in local memory ONLY.
 * Passwords and sensitive PII are blacked out with solid #000000 fill.
 * Faces and profile avatars are permanently blurred via Gaussian convolution (12px blur).
 * Only the sanitized canvas is exported for egress audit or remote transmission.
 */

class VisualPrivacyEngine {
  constructor(options = {}) {
    this.defaultBlurRadius = options.blurRadius || 14;
    this.blackoutColor = options.blackoutColor || '#000000';
    this.labelColor = options.labelColor || '#6366f1';
  }

  /**
   * Redact visual screenshot according to detected PII, passwords, and face/avatar regions.
   *
   * @param {Object} params
   * @param {string|HTMLImageElement|ImageBitmap} params.screenshot - Base64 Data URL or Image
   * @param {Array<{bbox: number[], label?: string, type?: string}>} params.passwordRegions - [x, y, w, h]
   * @param {Array<{bbox: number[], label?: string, type?: string}>} params.piiRegions - [x, y, w, h]
   * @param {Array<{bbox: number[], label?: string, type?: string}>} params.faceRegions - [x, y, w, h]
   * @param {number} [params.devicePixelRatio=1] - DPR for coordinate scaling
   * @returns {Promise<{sanitizedImage: string, redactions: Array, dimensions: {width: number, height: number}}>}
   */
  async redact({
    screenshot,
    passwordRegions = [],
    piiRegions = [],
    faceRegions = [],
    devicePixelRatio = 1,
    viewport = null,
  }) {
    if (!screenshot) {
      throw new Error('[VisualPrivacyEngine] No screenshot provided for redaction.');
    }

    // 1. Load image onto an offscreen HTML5 canvas
    const img = await this._loadImage(screenshot);
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });

    if (!ctx) {
      throw new Error('[VisualPrivacyEngine] Failed to acquire 2D canvas context.');
    }

    // Draw initial raw frame into offscreen memory
    ctx.drawImage(img, 0, 0);

    // Calculate scale factor between viewport CSS pixels and captured image pixels
    const dpr = devicePixelRatio || window.devicePixelRatio || 1;
    let scaleX = dpr;
    let scaleY = dpr;

    if (viewport && viewport.width && viewport.height) {
      scaleX = canvas.width / viewport.width;
      scaleY = canvas.height / viewport.height;
    }

    const appliedRedactions = [];

    // Helper to scale bounding box [x, y, w, h]
    const scaleBbox = (b) => {
      const x = Math.max(0, Math.floor(b[0] * scaleX));
      const y = Math.max(0, Math.floor(b[1] * scaleY));
      const w = Math.min(canvas.width - x, Math.ceil(b[2] * scaleX));
      const h = Math.min(canvas.height - y, Math.ceil(b[3] * scaleY));
      return [x, y, w, h];
    };

    // ── PHASE C: FACE & AVATAR BLURRING ──
    // Applies 12-14px Gaussian blur over detected face and profile avatar boxes
    for (const region of faceRegions) {
      const bbox = region.bbox || region;
      if (!bbox || bbox.length < 4) continue;
      const [x, y, w, h] = scaleBbox(bbox);
      if (w <= 0 || h <= 0) continue;

      this._applyGaussianBlur(ctx, canvas, x, y, w, h, this.defaultBlurRadius);

      // Subtle indicator border on blurred region
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.4)';
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      appliedRedactions.push({
        type: 'FACE_AVATAR',
        action: 'blur',
        bbox: [x, y, w, h],
        label: region.label || '[BLURRED_FACE]'
      });
    }

    // ── PHASE A: PASSWORD BLACKOUT ──
    // Solid, irreversible #000000 fill over password boxes
    for (const region of passwordRegions) {
      const bbox = region.bbox || region;
      if (!bbox || bbox.length < 4) continue;
      const [x, y, w, h] = scaleBbox(bbox);
      if (w <= 0 || h <= 0) continue;

      ctx.fillStyle = this.blackoutColor;
      ctx.fillRect(x, y, w, h);

      // Add clean monospace token label
      ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
      ctx.font = 'bold 11px monospace';
      const labelText = region.label || '[REDACTED_PASSWORD]';
      ctx.fillText(labelText, x + 4, y + Math.min(h - 4, 14));

      appliedRedactions.push({
        type: 'PASSWORD',
        action: 'blackout',
        bbox: [x, y, w, h],
        label: labelText
      });
    }

    // ── PHASE A: PII SENSITIVE TEXT BLACKOUT ──
    // Solid #000000 fill over detected Aadhaar, Emails, Phones, Credit Cards
    for (const region of piiRegions) {
      const bbox = region.bbox || region;
      if (!bbox || bbox.length < 4) continue;
      const [x, y, w, h] = scaleBbox(bbox);
      if (w <= 0 || h <= 0) continue;

      ctx.fillStyle = this.blackoutColor;
      ctx.fillRect(x, y, w, h);

      ctx.fillStyle = 'rgba(99, 102, 241, 0.95)';
      ctx.font = 'bold 10px monospace';
      const tokenText = region.label || region.replacement || '[REDACTED_PII]';
      ctx.fillText(tokenText, x + 3, y + Math.min(h - 3, 12));

      appliedRedactions.push({
        type: region.type || 'PII',
        action: 'blackout',
        bbox: [x, y, w, h],
        label: tokenText
      });
    }

    // Export sanitized image as WebP (or PNG fallback)
    const sanitizedImage = canvas.toDataURL('image/webp', 0.88);
    const dimensions = { width: canvas.width, height: canvas.height };

    // Explicitly wipe the canvas context to free memory & uphold invariant
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    canvas.width = 1;
    canvas.height = 1;

    return {
      sanitizedImage,
      redactions: appliedRedactions,
      dimensions,
    };
  }

  /**
   * Apply Gaussian blur to a specific sub-rectangle of the canvas.
   */
  _applyGaussianBlur(ctx, sourceCanvas, x, y, w, h, blurRadius) {
    // 1. Create small temporary canvas for the patch
    const patchCanvas = document.createElement('canvas');
    patchCanvas.width = w;
    patchCanvas.height = h;
    const patchCtx = patchCanvas.getContext('2d');
    if (!patchCtx) return;

    // 2. Draw original patch into temp canvas
    patchCtx.drawImage(sourceCanvas, x, y, w, h, 0, 0, w, h);

    // 3. Draw back onto main canvas with Gaussian blur filter
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();
    ctx.filter = `blur(${blurRadius}px)`;
    // Draw enlarged to prevent edge bleed
    ctx.drawImage(patchCanvas, 0, 0, w, h, x - 4, y - 4, w + 8, h + 8);
    ctx.restore();
    ctx.filter = 'none';

    // Cleanup
    patchCanvas.width = 1;
    patchCanvas.height = 1;
  }

  /**
   * Helper to load screenshot data into an HTMLImageElement.
   */
  _loadImage(src) {
    return new Promise((resolve, reject) => {
      if (typeof ImageBitmap !== 'undefined' && src instanceof ImageBitmap) {
        resolve(src);
        return;
      }
      if (src instanceof HTMLImageElement && src.complete) {
        resolve(src);
        return;
      }

      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => resolve(img);
      img.onerror = (e) => reject(new Error(`Failed to load screenshot into canvas: ${e}`));
      img.src = typeof src === 'string' ? src : URL.createObjectURL(src);
    });
  }
}

// Export for extension and browser test environments
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { VisualPrivacyEngine };
}
if (typeof window !== 'undefined') {
  window.VisualPrivacyEngine = VisualPrivacyEngine;
}
