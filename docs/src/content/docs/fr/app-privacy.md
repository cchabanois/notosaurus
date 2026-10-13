---
title: "Politique de confidentialité de l'app Android"
description: "Les données que l'app Notosaurus pour Android et son service traitent, pourquoi, où, combien de temps, et tes droits."
---

*Dernière mise à jour : 13 octobre 2026.*

Cette page concerne **l'app Notosaurus pour Android** et **le service Notosaurus** qu'elle
utilise pour lire les photos, faire les cartes et les voix. Notosaurus sur ordinateur (le
greffon Anki) fonctionne autrement : voir [Confidentialité et sécurité](../privacy/).

**Responsable du traitement** : CHABANOIS Cédric.
**Contact** : notosaurus.app@gmail.com

**Qui utilise l'app** : un **parent** (un adulte), qui prépare les révisions de ses enfants.
L'app n'est pas faite pour être utilisée par un enfant.

## En bref

- Tes **leçons restent sur ton téléphone** : photos, cartes, consignes, sons.
- Ce que l'IA doit lire (photos, consignes, dictées) **passe par le service** le temps de faire
  les cartes, **et n'y est pas gardé**.
- L'IA (**Gemini de Google**) et les voix sont **traitées dans l'Union européenne**. Google ne
  s'en sert pas pour entraîner ses modèles.
- **Ni publicité, ni statistiques, ni pistage**, et rien n'est vendu.
- Le service ne garde que ta **licence** (son empreinte, ta formule et tes crédits), et ce que
  tu **signales** avec ⚑, si tu le fais.

## Ce qui reste sur ton téléphone

Les leçons (photos des pages, cartes, consignes, images des cartes, sons), tes consignes
enregistrées et tes réglages, dont ta clé de licence, sont gardés **dans l'espace privé de
l'app** sur ton téléphone. Les autres apps n'y ont pas accès. Ils sont supprimés si tu
supprimes une leçon, ou l'app.

Les cartes envoyées dans **AnkiDroid** y sont écrites sur ton téléphone. Leur synchronisation
avec AnkiWeb dépend d'AnkiDroid et de ton compte AnkiWeb, pas de Notosaurus.

## Ce qui passe par le service Notosaurus

Quand tu le demandes, l'app envoie au service, en HTTPS :

| Quoi | Pour quoi faire |
|---|---|
| Les **photos** des pages et leur texte (PDF), la **consigne**, tes consignes permanentes, les noms de tes paquets | Faire ou compléter les cartes de la leçon |
| Les **cartes** d'une leçon et ta demande de correction | Corriger, expliquer une carte, mettre une consigne au propre |
| Un **enregistrement de ta voix** (🎤) | L'écrire en texte (dictée d'une consigne ou d'une correction) |
| Le **verso** d'une carte | Le lire à voix haute (voix des cartes) |
| La **description** d'une image, ou quelques **mots-clés** | Dessiner l'image d'une carte, ou chercher une image libre |
| Ta **clé de licence** | Vérifier ta licence et compter tes crédits |

Le service transmet ces contenus aux sous-traitants ci-dessous, renvoie le résultat à l'app,
et **ne les garde pas** : ni photo, ni carte, ni enregistrement, ni texte de leçon n'est
enregistré, ni écrit dans ses journaux. Sauf un **signalement** : voir plus bas.

Une page de cahier montre souvent le **nom de l'enfant**. Avant d'envoyer une photo, tu peux le
**cacher** : 🖍️ sur la photo, puis noircis-le du doigt. Seule la photo noircie part et reste
dans la leçon.

## Ce que le service garde

- **Ta licence** : l'empreinte de sa clé (pas la clé elle-même), ta formule, tes crédits
  restants, leur date de renouvellement, ce qui a été utilisé dans la journée, et une courte note
  pour le support (par exemple un numéro de commande). Elle est gardée tant qu'elle est valable,
  puis **12 mois** après sa fin (pour répondre à une question ou à une réclamation), puis supprimée.
- **Ce que tu signales** avec ⚑ (une carte, son explication ou son image faites par l'IA,
  choquantes ou fausses), si tu le fais : exactement ce que l'app te montre avant l'envoi, le
  motif, ton commentaire, la consigne de la leçon, la langue et un identifiant court de la
  licence. Jamais les photos de la leçon, ni le prénom de l'enfant. Lu par Notosaurus pour
  améliorer le contenu de l'IA, gardé **180 jours**, puis supprimé.
- **Tes e-mails au support**, s'il y en a : gardés **12 mois** après le dernier échange.
- **Des journaux techniques**, gardés **30 jours** pour faire fonctionner le service et repérer
  les pannes et les abus : l'heure, l'action demandée (« faire une leçon »…), sa durée, son
  résultat, le modèle d'IA et les crédits utilisés, la version de l'app, un identifiant court de
  la licence, et, comme pour tout site web, l'**adresse IP** de la requête. Jamais le contenu
  des leçons.

## Les sous-traitants

| Service | Ce qu'il reçoit | Où |
|---|---|---|
| **Google Cloud** : Vertex AI (Gemini) | Photos, consignes, cartes, dictées, descriptions d'images | Union européenne |
| **Google Cloud** : Cloud Run, Firestore, journaux | Le service lui-même, les licences, les journaux | Belgique (europe-west1) |
| **Google Cloud** : Text-to-Speech | Le texte à lire (le verso d'une carte) | Union européenne |
| **Wikimedia Commons**, **Openverse**, **Pixabay** | Quelques mots-clés en anglais (« dog »), jamais une photo | Leurs serveurs |
| **GitHub** (GitHub Pages) | Au démarrage, l'app y lit l'adresse du service : GitHub voit ton adresse IP | Ses serveurs |

Google agit comme sous-traitant, sous les conditions de Google Cloud, et n'utilise pas ces
données pour entraîner ses modèles. Pour détecter les abus, Google peut toutefois garder les
requêtes envoyées à Gemini **jusqu'à 90 jours**, selon ses conditions, sans s'en servir à
d'autres fins.

### Transferts hors de l'Union européenne

Les traitements ont lieu dans l'Union européenne, mais Google, GitHub, la Wikimedia
Foundation et Openverse sont des organisations américaines, qui peuvent y accéder. Ces
transferts sont encadrés par les **clauses contractuelles types** de la Commission européenne
et, pour les sociétés certifiées comme Google, par le **cadre de protection des données
UE–États-Unis**. Pixabay est une société de l'Union européenne.

## Pourquoi : les bases légales

| Traitement | Base légale |
|---|---|
| Faire, compléter, corriger et expliquer les cartes ; dictée ; voix ; images | L'**exécution du service** que tu demandes |
| Vérifier ta licence et compter tes crédits | L'**exécution du contrat** (ta licence) |
| Journaux techniques, sécurité, lutte contre les abus | L'**intérêt légitime** à faire fonctionner un service sûr |
| Tes signalements du contenu de l'IA | Ta **demande**, et l'intérêt légitime à une IA qui fait un contenu adapté |
| Le micro | Ton **consentement**, demandé à la première dictée et retirable dans les réglages du téléphone |
| Répondre à tes e-mails | Ta **demande** |

Notosaurus ne prend **aucune décision automatisée** te concernant et ne fait **aucun profilage**.
Sans ta licence, le service ne peut pas être fourni ; tout le reste n'est envoyé que quand tu le
demandes.

## Le mode « Avec mon ordinateur »

Quand l'app ouvre Notosaurus sur ton ordinateur (le greffon Anki), le téléphone parle
directement à l'ordinateur, sur le Wi-Fi de la maison : rien ne passe alors par le service
Notosaurus. C'est la page [Confidentialité et sécurité](../privacy/) qui s'applique.

## Les autorisations de l'app

- **Internet** : pour joindre le service.
- **Micro**, demandé la première fois que tu touches 🎤, et utilisé seulement pendant la dictée.
- **AnkiDroid**, pour y ajouter les cartes, demandé au premier envoi.
- Les photos sont prises par l'appareil photo du téléphone ou choisies dans la galerie, au
  moment où tu le fais. L'app n'a pas besoin d'accéder à toutes tes photos.

## Les enfants

L'app est utilisée par **un parent**, pas par l'enfant. Mais les photos de cahiers peuvent
contenir des données de l'enfant (son nom, son écriture) : cache le nom avec 🖍️ avant l'envoi,
et ne mets rien de personnel dans les consignes.

## Tes droits

Tu peux, en écrivant à **notosaurus.app@gmail.com** :

- **accéder** à tes données et en obtenir une copie (**portabilité**) ;
- les faire **rectifier** ou **effacer** ;
- en **limiter** le traitement, ou t'**opposer** à celui fondé sur l'intérêt légitime ;
- **retirer ton consentement** (le micro) à tout moment, sans effet sur ce qui a été fait avant.

Les leçons, elles, sont sur ton téléphone : tu les supprimes toi-même dans l'app. Une réponse
est donnée sous un mois. Tu peux aussi adresser une réclamation à la **CNIL** (cnil.fr).

## Sécurité

Tous les échanges avec le service passent en **HTTPS**. Seule l'empreinte de ta clé de licence
est gardée côté service. Sur ton téléphone, la clé reste dans l'espace privé de l'app, et les
réglages n'en montrent que les derniers caractères.

## Changements

Si cette politique change, la date en haut de la page change aussi.
