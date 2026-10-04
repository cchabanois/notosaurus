---
title: "Confidentialité et sécurité"
description: "Ce qui sort de ton ordinateur, où Notosaurus garde ses données, qui peut l'utiliser, et comment le sauvegarder."
---

Notosaurus n'a ni compte ni serveur à lui : il tourne sur ton ordinateur. Une leçon montre
souvent l'écriture d'un enfant, parfois son nom : voici où elle va.

## Ce qui sort de ton ordinateur

- **Les photos et la consigne** vont au **service d'IA choisi dans les réglages**, pour faire et
  corriger les cartes. Le texte d'un PDF numérique part avec sa page.
- **Les versos des cartes** vont au service de synthèse vocale de Microsoft, pour faire l'audio,
  quand une voix est choisie.
- **La description d'une image** va au service qui la dessine, pour « Mots en images ».

Rien d'autre : ni statistiques, ni pistage. Avec un modèle chez toi (voir
[Services d'IA](../ai-services/#un-modèle-chez-toi)), les photos ne sortent pas non plus de la
maison.

:::caution[Offres gratuites]
Les offres gratuites autorisent en général le service d'IA à utiliser ce que tu envoies pour
améliorer ses modèles. Pour les cahiers des enfants, préfère une clé payante. Avant de prendre
la photo, tu peux aussi cacher un nom écrit sur la page.
:::

## Où sont les données ?

Tout est gardé sous forme de simples fichiers, dans le **dossier de données** de Notosaurus :
les leçons (photos, cartes, audio), les consignes et les réglages.

- Avec le **greffon**, il est dans le dossier du greffon, sous `user_files/data`. **Outils →
  Notosaurus → État du serveur…** indique où. Il est conservé quand le greffon est mis à jour, et
  supprimé avec lui.
- En **autonome**, c'est le dossier `data/` (ou `NOTOSAURUS_DATA`).

Les **clés d'API** sont rangées dans ce dossier, dans `settings.json`, lisible seulement par ton
compte utilisateur. Elles ne sont jamais renvoyées à un téléphone ni à un navigateur : les
réglages n'en montrent que les quatre derniers caractères.

**Pour sauvegarder Notosaurus**, copie le dossier de données. Les cartes elles-mêmes sont dans
Anki, sauvegardées par Anki et, avec un compte, par AnkiWeb.

## Qui peut utiliser Notosaurus ?

- **Seulement les appareils associés.** Sur le Wi-Fi, seuls l'ordinateur lui-même et les
  appareils qui ont scanné le QR code (**Réglages → Téléphones**) peuvent utiliser Notosaurus :
  les autres ne peuvent ni dépenser tes crédits d'IA ni supprimer des leçons. **Déconnecter tous
  les téléphones** les dissocie tous, par exemple après la perte ou le prêt d'un téléphone.
- **Les réglages seulement sur l'ordinateur.** Avec le greffon, les réglages ne s'ouvrent que
  sur l'ordinateur lui-même : les enfants ne peuvent ni changer le service d'IA ni voir les clés
  depuis un téléphone. En autonome, ils sont protégés par un mot de passe.
- **Une leçon appartient à un profil.** Seul le profil qui a créé une leçon peut la modifier ;
  une leçon partagée est en lecture seule pour les autres.

## Le Wi-Fi

Notosaurus parle aux téléphones en HTTP simple, sur ton réseau local. L'association écarte les
curieux et les autres sites web, mais pas quelqu'un qui espionnerait le trafic du Wi-Fi : garde
ton Wi-Fi protégé (WPA2 ou WPA3).

Notosaurus est fait pour la maison : les téléphones l'utilisent sur le même Wi-Fi que
l'ordinateur. **N'expose jamais Notosaurus** (ni AnkiConnect) **sur Internet.**
