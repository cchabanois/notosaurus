---
title: "Politique de confidentialité de l'app Android"
description: "Les données que l'app Notosaurus pour Android et son service traitent, pourquoi, où, combien de temps, et tes droits."
---

*Dernière mise à jour : 11 octobre 2026.*

Cette page concerne **l'app Notosaurus pour Android** et **le service Notosaurus** qu'elle
utilise pour lire les photos, faire les cartes et les voix. Notosaurus sur ordinateur (le
greffon Anki) fonctionne autrement : voir [Confidentialité et sécurité](../privacy/).

**Responsable du traitement** : [à compléter : nom et adresse de l'éditeur].
**Contact** : notosaurus.app@gmail.com

## En bref

- Tes **leçons restent sur ton téléphone** : photos, cartes, consignes, sons.
- Ce que l'IA doit lire (photos, consignes, dictées) **passe par le service** le temps de faire
  les cartes, **et n'y est pas gardé**.
- L'IA (**Gemini de Google**) et les voix sont **traitées dans l'Union européenne**. Google ne
  s'en sert pas pour entraîner ses modèles.
- **Ni publicité, ni statistiques, ni pistage**, et rien n'est vendu.
- Le service ne garde que ta **licence** : son empreinte, ta formule et tes crédits.

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
enregistré, ni écrit dans ses journaux.

Une page de cahier montre souvent le **nom de l'enfant**. Avant d'envoyer une photo, tu peux le
**cacher** : 🖍️ sur la photo, puis noircis-le du doigt. Seule la photo noircie part et reste
dans la leçon.

## Ce que le service garde

- **Ta licence** : l'empreinte de sa clé (pas la clé elle-même), ta formule, tes crédits
  restants, leur date de renouvellement et ce qui a été utilisé dans la journée. Elle est gardée
  tant que la licence existe, puis supprimée sur demande.
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
données pour entraîner ses modèles.

## Les autorisations de l'app

- **Internet** : pour joindre le service.
- **Micro**, demandé la première fois que tu touches 🎤, et utilisé seulement pendant la dictée.
- **AnkiDroid**, pour y ajouter les cartes, demandé au premier envoi.
- Les photos sont prises par l'appareil photo du téléphone ou choisies dans la galerie, au
  moment où tu le fais. L'app n'a pas besoin d'accéder à toutes tes photos.

## Les enfants

Notosaurus est fait pour **les parents** qui préparent les révisions de leurs enfants. Les
photos de cahiers peuvent contenir des données d'enfant (nom, écriture) : cache le nom avec 🖍️
avant l'envoi, et ne mets rien de personnel dans les consignes.

## Tes droits

Tu peux demander l'accès à tes données, leur rectification ou leur suppression, en écrivant à
**notosaurus.app@gmail.com**. Les leçons, elles, sont sur ton téléphone : tu les supprimes
toi-même dans l'app. Tu peux aussi saisir la **CNIL** (cnil.fr).

## Sécurité

Tous les échanges avec le service passent en **HTTPS**. Seule l'empreinte de ta clé de licence
est gardée côté service. Sur ton téléphone, la clé reste dans l'espace privé de l'app, et les
réglages n'en montrent que les derniers caractères.

## Changements

Si cette politique change, la date en haut de la page change aussi.
