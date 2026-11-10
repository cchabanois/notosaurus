#set page(width: auto, height: auto, margin: 6pt)
// Scratch scripts with blockst: each block drawn from its text as Scratch draws it, its
// shape, colour and width from what it says (its words measured in the figure's font),
// never drawn by hand. A block Scratch doesn't have is drawn grey and refused
// (figures_typst: the AI told which, to write it again)
#import "@preview/blockst:0.4.1": set-blockst
#import "@preview/blockst:0.4.1": scratch as _scratch
#set-blockst(font: "DejaVu Sans")
// A block of the script's own used with "call" in every language: blockst reads its French
// word only in French ("appeler"), and would write "call" on the block
#let scratch(code, language: "en", ..options) = _scratch(
  if language == "fr" { code.replace(regex("(?m)^([ \t]*)call "), m => m.captures.at(0) + "appeler ") } else { code },
  language: language,
  ..options,
)
// ---- What the AI writes, from here (the rule's example: everything above is given)
#scratch("
définir carré (côté)
stylo en position d'écriture
répéter (4) fois
  avancer de (côté) pas
  tourner ↻ de (90) degrés
fin

quand le drapeau vert est cliqué
call carré (50)
", language: "fr")
