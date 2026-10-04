---
title: Plusieurs enfants
description: "Un profil Anki et un compte AnkiWeb par enfant, chacun avec ses leçons et ses cartes ; ou, sur une tablette partagée, un paquet par enfant."
---

Chaque enfant a son propre **profil Anki** : ses cartes, sa progression. Notosaurus suit le
profil ouvert dans Anki. Des enfants qui partagent un téléphone ou une tablette : voir
[Une seule tablette pour plusieurs enfants](#une-seule-tablette-pour-plusieurs-enfants).

## Un profil par enfant

1. Dans Anki, **Fichier → Changer de profil → Ajouter**, et crée un profil par enfant
   (Léa, Paul…).
2. Pour chaque profil, crée un **compte AnkiWeb** et connecte-le dans ce profil
   (**Outils → Préférences → Synchronisation**). Un compte AnkiWeb contient une seule
   collection : chaque enfant a besoin du sien.
3. Sur le téléphone de chaque enfant, connecte **AnkiDroid** ou **AnkiMobile** au compte
   AnkiWeb de cet enfant.

:::tip[Pas besoin d'une boîte mail par enfant]
Beaucoup de messageries acceptent les alias avec un `+` : `parent+lea@exemple.fr` et
`parent+paul@exemple.fr` arrivent dans ta propre boîte, mais comptent comme deux adresses.
:::

## Les leçons appartiennent à un profil

- Une leçon appartient au profil **ouvert dans Anki au moment où elle est créée**. La liste
  des leçons montre celles de ce profil.
- Pour faire une leçon pour Paul, **ouvre d'abord le profil de Paul dans Anki**, puis prends
  la photo.
- Si tu envoies une leçon alors que le profil d'un autre enfant est ouvert, Notosaurus te
  prévient avant de l'écrire dans la mauvaise collection.
- Une leçon peut être **partagée avec les autres profils** (l'interrupteur dans la
  relecture), par exemple quand deux enfants ont la même leçon.

![Les leçons du profil ouvert](../../../assets/screenshots/fr/lessons.png)

## Des instructions pour chaque enfant

Dans **Réglages → Instructions pour l'IA**, tu peux ajouter des instructions pour tous les
profils (« espagnol d'Espagne ») et pour chaque enfant (« en 5ᵉ ; réponses courtes »). Elles
s'ajoutent à chaque leçon de cet enfant.

![Réglages : les instructions pour tous les profils et pour chaque enfant](../../../assets/screenshots/fr/settings-instructions.png)

## Faire arriver les cartes sur le téléphone

Après **Ajouter à Anki**, Notosaurus synchronise le profil ouvert avec AnkiWeb. Les cartes
arrivent sur le téléphone de l'enfant à sa prochaine synchronisation.

## Une seule tablette pour plusieurs enfants

**AnkiDroid n'a pas de profils** : une installation contient une seule collection, connectée à
un seul compte AnkiWeb. AnkiMobile non plus ne passe pas d'un compte à l'autre sans se
déconnecter. Si les enfants partagent un téléphone ou une tablette, le plus simple est donc
**un seul profil Anki, avec un paquet par enfant** :

1. Garde un seul profil dans Anki, connecté à un seul compte AnkiWeb, et connecte AnkiDroid à
   ce compte.
2. Commence le nom du paquet de chaque leçon par le prénom de l'enfant :
   `Léa::Espagnol::Unité 3`, `Paul::Maths::Les fractions`. Dans la relecture, corrige le
   **Paquet** avant d'envoyer.
3. Pour réviser, chaque enfant ouvre **son** paquet (Léa, Paul) : Anki ne prend alors que ses
   cartes. Pas le bouton qui révise tout.

:::tip[Le prénom tout seul]
Pour ne pas taper le prénom à chaque fois, duplique tes consignes pour chaque enfant
(« Espagnol – Léa ») et mets son prénom dans le **nom de paquet proposé** :
`Léa::{matière}::{titre de la leçon}`. Tu peux y ajouter ce qui lui est propre (« en 5ᵉ ;
réponses courtes »). Voir [Les consignes](../instructions/).
:::

Ce qu'on perd par rapport à un profil par enfant :

- chaque enfant voit les paquets des autres, et les statistiques d'Anki sont communes ;
- Notosaurus range les leçons par le premier niveau du paquet : la liste des leçons les
  regroupe donc par enfant, plus par matière ;
- les instructions « pour chaque enfant » des réglages sont en fait par profil : avec un seul
  profil, elles valent pour tous. Utilise plutôt des consignes par enfant, comme ci-dessus.

Si chaque enfant a son propre appareil, préfère **un profil par enfant** (en haut de cette
page). Pour les plus à l'aise : AnkiDroid peut être installé en plusieurs exemplaires sur le
même appareil, un par enfant, chacun avec son compte AnkiWeb (les « parallel builds », voir la
[FAQ d'AnkiDroid](https://github.com/ankidroid/Anki-Android/wiki/FAQ), en anglais).
