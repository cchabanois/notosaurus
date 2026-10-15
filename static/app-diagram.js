// The diagram labels of the open lesson: the masks on a photo, moved and resized, and the
// diagram's frame (what Anki shows of the photo).
// Methods of the page's Alpine component (app.js), as `this`.

const diagramPart = {
  photoFor(card) {
    return this.photos[card.mask.page - 1]?.url ?? null;
  },

  hasMasks() {
    return this.cards.some((c) => c.mask);
  },

  // Every mask on the same photo: all of them are hidden on the card's image.
  masksOnPage(card) {
    return this.cards.filter((c) => c.mask && c.mask.page === card.mask.page);
  },

  // What Anki shows of the photo: the diagram's frame stretched to hold every mask
  // with a margin, so it never cuts a label (same as diagrams.crop on the server).
  // No frame: the whole photo.
  cropFor(card) {
    const frame = this.frames.find((f) => f.page === card.mask.page);
    if (!frame) return { box: [0, 0, 1, 1] };
    const m = 0.03;
    const masks = this.masksOnPage(card).map(({ mask: { box: b } }) => [b[0] - m, b[1] - m, b[2] + m, b[3] + m]);
    const boxes = [frame.box, ...masks];
    const clamp = (v) => Math.min(1, Math.max(0, v));
    return {
      box: [
        clamp(Math.min(...boxes.map((b) => b[0]))), clamp(Math.min(...boxes.map((b) => b[1]))),
        clamp(Math.max(...boxes.map((b) => b[2]))), clamp(Math.max(...boxes.map((b) => b[3]))),
      ],
    };
  },

  // Drag a corner of the frame ("nw", "ne", "sw", "se"). It starts from what is shown,
  // and can't go inside the masks: the crop stretches back to hold them.
  startCrop(event, card, corner) {
    if (this.readOnly()) return;
    event.preventDefault();
    const rect = event.currentTarget.closest(".diagram").getBoundingClientRect();
    let frame = this.frames.find((f) => f.page === card.mask.page);
    if (!frame) {
      frame = { page: card.mask.page, box: [0, 0, 1, 1] };
      this.frames.push(frame);
    }
    frame.box = [...this.cropFor(card).box];
    const start = { x: event.clientX, y: event.clientY, box: [...frame.box] };
    const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
    const move = (e) => {
      const dx = (e.clientX - start.x) / rect.width;
      const dy = (e.clientY - start.y) / rect.height;
      let [x0, y0, x1, y1] = start.box;
      if (corner.includes("w")) x0 = clamp(x0 + dx, 0, x1 - 0.05);
      if (corner.includes("e")) x1 = clamp(x1 + dx, x0 + 0.05, 1);
      if (corner.includes("n")) y0 = clamp(y0 + dy, 0, y1 - 0.05);
      if (corner.includes("s")) y1 = clamp(y1 + dy, y0 + 0.05, 1);
      frame.box = [x0, y0, x1, y1].map((v) => Math.round(v * 10000) / 10000);
    };
    const stop = () => {
      frame.box = [...this.cropFor(card).box];  // what is shown: pushed inside a mask, it stops there
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  },

  maskStyle(mask) {
    const [x0, y0, x1, y1] = mask.box.map((v) => v * 100);
    return `left: ${x0}%; top: ${y0}%; width: ${x1 - x0}%; height: ${y1 - y0}%`;
  },

  // Drag the mask (mode "move") or its corner ("resize"), with a finger or a mouse.
  // Boxes are fractions of the photo, like on the server.
  startDrag(event, card, mode) {
    if (this.readOnly()) return;
    event.preventDefault();
    const frame = event.currentTarget.closest(".diagram").getBoundingClientRect();
    const start = { x: event.clientX, y: event.clientY, box: [...card.mask.box] };
    const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
    const move = (e) => {
      const dx = (e.clientX - start.x) / frame.width;
      const dy = (e.clientY - start.y) / frame.height;
      let [x0, y0, x1, y1] = start.box;
      if (mode === "move") {
        const [w, h] = [x1 - x0, y1 - y0];
        x0 = clamp(x0 + dx, 0, 1 - w);
        y0 = clamp(y0 + dy, 0, 1 - h);
        [x1, y1] = [x0 + w, y0 + h];
      } else {
        x1 = clamp(x1 + dx, x0 + 0.02, 1);
        y1 = clamp(y1 + dy, y0 + 0.02, 1);
      }
      card.mask.box = [x0, y0, x1, y1].map((v) => Math.round(v * 10000) / 10000);
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  },
};
