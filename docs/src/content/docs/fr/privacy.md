---
title: "Confidentialité et sécurité sur l'ordinateur"
description: "Ce qui sort de votre ordinateur, où Notosaurus garde ses données, qui peut l'utiliser, et comment le sauvegarder."
---

Cette page concerne Notosaurus sur ordinateur. Pour l'application Android et son service, voir la
[politique de confidentialité de l'application](../app-privacy/).

Sur ordinateur, Notosaurus n'a ni compte ni serveur à lui : il tourne sur votre ordinateur. Une leçon montre
souvent l'écriture d'un enfant, parfois son nom : voici où elle va.

## Ce qui sort de votre ordinateur

- **Les photos et la consigne** vont au **service d'IA choisi dans les réglages**, pour faire et
  corriger les cartes. Le texte d'un PDF numérique part avec sa page. Avec elles partent la classe
  de l'enfant et vos instructions pour lui, **jamais son prénom**.
- **Les versos des cartes** vont au service de synthèse vocale de Microsoft, pour faire l'audio,
  quand une voix est choisie.
- **La description d'une image** va au service qui la dessine, pour « Langue : vocabulaire en images ».

- **Les mots d'une recherche d'image** (quelques mots en anglais : « dog », « Storming of the
  Bastille painting ») vont à Wikimedia Commons et Openverse, pour trouver des images libres ;
  jamais les photos.

Les pages elles-mêmes ne chargent rien d'ailleurs : leurs scripts et leurs polices viennent avec
Notosaurus (ni Google Fonts, ni CDN).

Rien d'autre : ni statistiques, ni pistage. Avec un modèle chez vous (voir
[Services d'IA](../ai-services/#un-modèle-chez-vous)), les photos ne sortent pas non plus de la
maison.

:::caution[Offres gratuites]
Les offres gratuites autorisent en général le service d'IA à utiliser ce que vous envoyez pour
améliorer ses modèles. Pour les cahiers des enfants, préférez une clé payante. Avant de prendre
la photo, vous pouvez aussi cacher un nom écrit sur la page.
:::

## Où sont les données ?

Tout est gardé sous forme de simples fichiers, dans le **dossier de données** de Notosaurus :
les leçons (photos, cartes, audio), les consignes et les réglages.

- Avec le **greffon**, il est dans le dossier du greffon, sous `user_files/data`. **Outils →
  Notosaurus → État du serveur…** indique où. Il est conservé quand le greffon est mis à jour, et
  supprimé avec lui.
- En **autonome**, c'est le dossier `data/` (ou `NOTOSAURUS_DATA`).

Les **clés d'API** sont rangées dans ce dossier, dans `settings.json`, lisible seulement par votre
compte utilisateur. Elles ne sont jamais renvoyées à un téléphone ni à un navigateur : les
réglages n'en montrent que les quatre derniers caractères.

**Pour sauvegarder Notosaurus**, copiez le dossier de données. Les cartes elles-mêmes sont dans
Anki, sauvegardées par Anki et, avec un compte, par AnkiWeb.

## Qui peut utiliser Notosaurus ?

- **Seulement les appareils associés.** Sur le Wi-Fi, seuls l'ordinateur lui-même et les
  appareils qui ont scanné le QR code (**Réglages → Téléphones**) peuvent utiliser Notosaurus :
  les autres ne peuvent ni dépenser vos crédits d'IA ni supprimer des leçons. **Déconnecter tous
  les téléphones** les dissocie tous, par exemple après la perte ou le prêt d'un téléphone.
- **Les réglages seulement sur l'ordinateur.** Avec le greffon, les réglages ne s'ouvrent que
  sur l'ordinateur lui-même : les enfants ne peuvent ni changer le service d'IA ni voir les clés
  depuis un téléphone. En autonome, ils sont protégés par un mot de passe.
- **Une leçon appartient à un profil.** Une leçon ne se modifie que depuis le profil Anki où elle
  a été faite ; un autre enfant a sa propre copie (**⧉ Copier pour…**).

## Le Wi-Fi

Notosaurus parle aux téléphones en HTTP simple, sur votre réseau local. L'association écarte les
curieux et les autres sites web, mais pas quelqu'un qui espionnerait le trafic du Wi-Fi : gardez
votre Wi-Fi protégé (WPA2 ou WPA3).

Notosaurus est fait pour la maison : les téléphones l'utilisent sur le même Wi-Fi que
l'ordinateur. **N'exposez jamais Notosaurus** (ni AnkiConnect) **sur Internet.**
