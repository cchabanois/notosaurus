---
title: "Sur le téléphone"
description: "Ouvrir Notosaurus sur le téléphone avec le QR code, et l'ajouter à l'écran d'accueil sur Android et iPhone."
---

Notosaurus est une page web, pas une appli d'un magasin d'applications : le téléphone l'ouvre dans
son navigateur. Ajoutée à l'écran d'accueil, elle s'ouvre ensuite d'un geste, comme une appli.

## 1. Ouvrir Notosaurus

Dans Anki sur l'ordinateur, **Outils → Notosaurus → Ouvrir sur le téléphone…** affiche un QR code.
Avec le téléphone sur le **même Wi-Fi** que l'ordinateur, scanne-le avec l'appareil photo du
téléphone et ouvre le lien.

Scanner le QR code **autorise aussi ce téléphone** à utiliser Notosaurus : les autres appareils du
Wi-Fi ne le peuvent pas (voir
[Confidentialité et sécurité](../privacy/#qui-peut-utiliser-notosaurus-)).

## 2. L'ajouter à l'écran d'accueil

Fais-le **juste après avoir scanné le QR code**, depuis la page qui s'est ouverte : l'icône garde
l'autorisation du téléphone.

### Android

- **Chrome** : le menu **⋮** (en haut à droite) → **Ajouter à l'écran d'accueil** (ou **Installer
  l'application**) → **Ajouter**.
- **Samsung Internet** : le menu **≡** → **Ajouter la page à** → **Écran d'accueil**.
- **Firefox** : le menu **⋮** → **Ajouter à l'écran d'accueil** (ou **Installer**).

### iPhone et iPad

Dans **Safari** : le bouton **Partager** (le carré avec une flèche) → **Sur l'écran d'accueil** →
**Ajouter**. Sur un iPhone, l'icône ne partage pas la mémoire de Safari : c'est en l'ajoutant juste
après avoir scanné le QR code qu'elle est autorisée.

L'icône **Notosaurus**, avec son dinosaure, apparaît alors parmi les applis.

## Bon à savoir

- **Le téléphone doit être sur le même Wi-Fi** que l'ordinateur, et Anki doit être ouvert sur
  l'ordinateur (avec le greffon). Loin de la maison, voir [Tailscale](../privacy/#le-wi-fi).
- **Si tous les téléphones ont été déconnectés** (Réglages → Téléphones) ou si l'adresse de
  l'ordinateur a changé (après un redémarrage de la box), l'icône n'ouvre plus Notosaurus : scanne à
  nouveau le QR code, puis ajoute de nouveau la page à l'écran d'accueil (et supprime l'ancienne
  icône).
- Sur Android, en HTTP simple sur le réseau local, l'icône ouvre la page dans le navigateur. Avec le
  HTTPS (Tailscale), Chrome peut **installer** Notosaurus : il s'ouvre alors en plein écran, comme
  une appli.
- Les photos marchent dans tous les cas : **Prendre une photo** ouvre l'appareil photo du téléphone.
