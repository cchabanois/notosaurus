// One block of markup written once and shown in several places: <template id="…"> holds it,
// each <… data-include="…"> gets a copy as its content before Alpine starts, so Alpine sees
// the markup as if written there (its x-for's, x-show's, the scope around it: a card's `card`).
// What differs between the places stays on the element that includes it (its class, its
// x-show). Copies inside a <template> (an x-for's) too: Alpine clones those with the copy.
// Read before vendor/alpinejs starts.
function includeBlocks(root) {
  for (const el of root.querySelectorAll("[data-include]")) {
    const block = document.getElementById(el.dataset.include);
    if (!block) throw new Error(`no <template id="${el.dataset.include}">`);
    el.append(block.content.cloneNode(true));
    el.removeAttribute("data-include");
  }
  for (const template of root.querySelectorAll("template")) {
    if (!template.id) includeBlocks(template.content);
  }
}

document.addEventListener("alpine:init", () => {
  if (typeof document.querySelectorAll === "function") includeBlocks(document);
});
