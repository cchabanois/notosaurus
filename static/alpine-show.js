// x-show as its last value says. Alpine (3.14.9) shows an element a frame later
// (requestAnimationFrame) and hides it in that frame too, through promises: a value turned
// on then off within a frame (a click, then a reply a few ms later) can run the hide first and
// the show last, the element left shown while its value is false (the bottom bar's 📤 with
// Anki out of reach). Each show or hide is done only while it is still the element's last
// value; Alpine's timing kept (a menu opened by a click isn't closed by its @click.outside).
// Read before vendor/alpinejs starts.
document.addEventListener("alpine:init", () => {
  const toggle = Element.prototype._x_toggleAndCascadeWithTransitions;
  if (typeof toggle !== "function") return;
  Element.prototype._x_toggleAndCascadeWithTransitions = function (el, value, show, hide) {
    el._x_lastShown = value;
    return toggle.call(this, el, value, () => el._x_lastShown && show(), () => !el._x_lastShown && hide());
  };
});
