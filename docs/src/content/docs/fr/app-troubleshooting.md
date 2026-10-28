---
title: "Dépannage de l'application"
description: "Que faire quand l'application Android dit qu'il n'y a plus de crédits, que l'essai ou l'abonnement est terminé, qu'AnkiDroid ne prend pas les cartes, ou que l'ordinateur ne répond pas."
---

Les messages ci-dessous sont ceux qu'affiche l'application.

## L'abonnement

| Message | Que faire |
|---|---|
| « Plus de crédits ce mois-ci » | Ils reviennent au prochain renouvellement : **🔑 Abonnement**, dans les réglages, dit quand. |
| « Votre essai gratuit est terminé » | Abonnez-vous dans les Réglages (**🔑 Abonnement**) pour continuer. |
| « Pas de nouvel essai gratuit pour le moment… » | Les nouveaux essais gratuits sont suspendus pour l'instant : abonnez-vous dans les Réglages, ou réessayez demain. Un essai déjà commencé continue. |
| « Votre abonnement est terminé » | Réabonnez-vous dans l'application. |
| « Paiement en attente » | Google Play n'a pas pu renouveler l'abonnement : mettez à jour votre moyen de paiement dans Google Play (**Réglages → Gérer l'abonnement**). |
| « L'essai gratuit n'est possible qu'avec l'app installée depuis Google Play, sur un vrai téléphone » | Installez l'application depuis Google Play ; l'essai n'est pas proposé sur un émulateur. |
| « Aucun abonnement trouvé sur ce compte Google » (**J'ai déjà un abonnement**) | Vérifiez que le téléphone utilise le compte Google avec lequel l'abonnement a été pris. |

Voir [L'abonnement](../app-subscription/).

## AnkiDroid

| Message | Que faire |
|---|---|
| « Notosaurus n'a pas le droit d'ajouter des cartes à AnkiDroid » | **Réglages → 📥 AnkiDroid → Autoriser**, puis ajoutez à nouveau les cartes. Refusé pour de bon (Android ne demande plus) : autorisez-le dans les paramètres d'Android, **Applications → Notosaurus → Autorisations**. |
| « AnkiDroid n'est pas installé » / « AnkiDroid n'a pas pris les cartes » | Installez AnkiDroid, **ouvrez-le une fois** (il crée sa collection), puis ajoutez à nouveau les cartes. |

**✎ Notosaurus ne fait rien dans AnkiDroid** (« La carte ne peut pas lancer d'autres
applications ») : jusqu'à AnkiDroid 2.25.2, activez **Paramètres → Avancé → Autoriser les cartes
à lancer d'autres applications** dans AnkiDroid, ou mettez AnkiDroid à jour (depuis 2.25.3, le lien
passe sans ce réglage).

**Des cartes sans son** : les voix du service Notosaurus n'ont pas répondu (le téléphone a besoin
d'Internet). Les cartes sont envoyées sans leur son, et le message dit combien. Ajoutez à nouveau
la leçon à Anki plus tard : les sons qui manquent sont ajoutés.

Voir [L'application et AnkiDroid](../app-ankidroid/).

## Avec votre ordinateur

| Message | Que faire |
|---|---|
| « 💻 Votre ordinateur ne répond pas » | Anki doit être ouvert sur l'ordinateur avec le greffon, et le téléphone sur le même Wi-Fi. **Réessayer**, ou **Scanner à nouveau le QR code** si l'adresse de l'ordinateur a changé. |

Voir [Avec votre ordinateur](../app-with-computer/).

## Les cartes

**Les cartes sont fausses ou il en manque.** Vérifiez la photo (voir [Photos et PDF](../photos/)),
précisez la consigne, ou corrigez-les avec l'IA (voir [Relire les cartes](../review/)). Une carte
faite par l'IA fausse ou inadaptée : **⋯ → ⚑ Signaler** dessus.

## Un PDF ne s'ajoute pas

- **« Déjà 10 pages : retirez-en avant d'ajouter un PDF. »** Une leçon tient en 10 pages : retirez
  les photos inutiles (le bouton **Retirer cette page**, ✕, sur chacune), ou faites deux leçons.
- **« … est protégé par un mot de passe : enregistrez-le sans mot de passe, puis ajoutez-le à
  nouveau. »** Ouvrez le PDF, enregistrez-le sans mot de passe (ou imprimez-le dans un nouveau
  PDF), puis ajoutez-le à nouveau.
- **Des mots mal lus dans un PDF** : un PDF scanné ne contient que des images, lues comme des
  photos. Un PDF fait sur ordinateur donne à l'IA son texte exact.
