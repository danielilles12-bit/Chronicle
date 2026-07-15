// Pinch/pan/double-tap zoom for a block element, applied as a CSS transform
// (origin 0 0, so all maths live in the element's layout space — which a
// transform never moves). Built for the Face Value / Relic frame:
// single-finger taps pass through to the scrap buttons beneath, panning
// engages only while zoomed in, pinching below 1x snaps home. Double-tap
// toggles 1x ⇄ 2.5x around the tapped point.
//
// attachPinchZoom(el, { maxScale, onZoomChange }) -> { reset }
export function attachPinchZoom(el, opts = {}) {
  const MAX = opts.maxScale || 4;
  const DOUBLE_TAP_MS = 350;
  const DOUBLE_TAP_SLOP = 30;   // px between the two taps
  const TAP_SLOP = 10;          // px of movement that still counts as a tap

  let scale = 1, tx = 0, ty = 0;
  const pointers = new Map();   // pointerId -> {x, y}
  let pinch0 = null;            // pinch-start snapshot
  let pan0 = null;              // single-finger pan-start snapshot
  let tap0 = null;              // pointer-down spot for tap detection
  let lastTap = null;           // {t, x, y} of the previous completed tap

  el.style.touchAction = 'none';

  // Top-left of the element's LAYOUT box in viewport coords: the rendered
  // rect minus the current translation (origin 0 0 keeps layout.left fixed).
  function layoutOrigin() {
    const r = el.getBoundingClientRect();
    return [r.left - tx, r.top - ty];
  }

  function apply(animated) {
    if (animated) {
      el.style.transition = 'transform .25s ease';
      setTimeout(() => { el.style.transition = ''; }, 260);
    }
    el.style.transformOrigin = '0 0';
    el.style.transform = scale === 1 && !tx && !ty
      ? '' : `translate(${tx.toFixed(1)}px, ${ty.toFixed(1)}px) scale(${scale.toFixed(3)})`;
    if (opts.onZoomChange) opts.onZoomChange(scale);
  }

  // Keep the layout box covered: scaled content spans [tx, tx + w*scale].
  function clamp() {
    const w = el.offsetWidth, h = el.offsetHeight;
    tx = Math.min(0, Math.max(w * (1 - scale), tx));
    ty = Math.min(0, Math.max(h * (1 - scale), ty));
  }

  function setScaleAbout(px, py, newScale, animated) {
    // (px, py) in layout space; the content point under it stays put.
    const cx = (px - tx) / scale, cy = (py - ty) / scale;
    scale = Math.min(MAX, Math.max(1, newScale));
    tx = px - cx * scale;
    ty = py - cy * scale;
    if (scale === 1) { tx = 0; ty = 0; }
    clamp();
    apply(animated);
  }

  el.addEventListener('pointerdown', (e) => {
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const [ox, oy] = layoutOrigin();
      const mx = (a.x + b.x) / 2 - ox, my = (a.y + b.y) / 2 - oy;
      pinch0 = {
        d: Math.hypot(a.x - b.x, a.y - b.y) || 1,
        scale,
        ox, oy,
        // content point under the start midpoint — the pinch's anchor
        cx: (mx - tx) / scale, cy: (my - ty) / scale,
      };
      pan0 = null;
      tap0 = null;
    } else if (pointers.size === 1) {
      tap0 = { x: e.clientX, y: e.clientY, moved: false };
      if (scale > 1) pan0 = { x: e.clientX, y: e.clientY, tx, ty };
    }
  });

  el.addEventListener('pointermove', (e) => {
    const p = pointers.get(e.pointerId);
    if (!p) return;
    p.x = e.clientX; p.y = e.clientY;
    if (tap0 && Math.hypot(e.clientX - tap0.x, e.clientY - tap0.y) > TAP_SLOP) {
      tap0.moved = true;
    }
    if (pointers.size === 2 && pinch0) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      const mx = (a.x + b.x) / 2 - pinch0.ox, my = (a.y + b.y) / 2 - pinch0.oy;
      // zoom by the distance ratio, keep the anchor under the moving midpoint
      scale = Math.min(MAX, Math.max(1, pinch0.scale * (d / pinch0.d)));
      tx = mx - pinch0.cx * scale;
      ty = my - pinch0.cy * scale;
      if (scale === 1) { tx = 0; ty = 0; }
      clamp();
      apply(false);
    } else if (pointers.size === 1 && pan0 && scale > 1) {
      tx = pan0.tx + (e.clientX - pan0.x);
      ty = pan0.ty + (e.clientY - pan0.y);
      clamp();
      apply(false);
    }
  });

  function pointerEnd(e) {
    const wasTap = tap0 && !tap0.moved && pointers.size === 1 && e.type === 'pointerup';
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch0 = null;
    if (pointers.size === 0) pan0 = null;
    if (!wasTap) { if (pointers.size === 0) tap0 = null; return; }
    const now = performance.now();
    if (lastTap && now - lastTap.t < DOUBLE_TAP_MS
        && Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) < DOUBLE_TAP_SLOP) {
      lastTap = null;
      const [ox, oy] = layoutOrigin();
      setScaleAbout(e.clientX - ox, e.clientY - oy, scale > 1.2 ? 1 : 2.5, true);
    } else {
      lastTap = { t: now, x: e.clientX, y: e.clientY };
    }
    tap0 = null;
  }
  el.addEventListener('pointerup', pointerEnd);
  el.addEventListener('pointercancel', pointerEnd);

  return {
    reset() {
      pointers.clear(); pinch0 = null; pan0 = null; tap0 = null;
      scale = 1; tx = 0; ty = 0;
      apply(false);
    },
  };
}
