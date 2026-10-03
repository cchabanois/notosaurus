---
title: "Dépannage et FAQ"
description: "Que faire quand Notosaurus ne démarre pas, que le téléphone ne se connecte pas, que l'IA échoue ou que les cartes n'arrivent pas dans Anki, et réponses aux questions fréquentes."
---

Les messages ci-dessous sont ceux qu'affiche Notosaurus. Quand quelque chose ne va pas dans le
greffon, **Outils → Notosaurus → Journal du serveur** montre ce qui s'est passé, et
**Redémarrer le serveur** suffit souvent.

## Notosaurus ne démarre pas

**« Notosaurus n'est pas démarré. »** Tu as refusé l'installation de ses composants au premier
démarrage. Pour les installer : **Outils → Notosaurus → Ouvrir Notosaurus**.

**« Téléchargement de uv depuis GitHub impossible »** ou **« Installation des dépendances de
Notosaurus impossible ».** Le premier démarrage télécharge environ 300 Mo : vérifie la connexion
Internet, puis **Outils → Notosaurus → Redémarrer le serveur**. Le journal indique ce qui a
échoué.

**Le serveur s'arrête juste après avoir démarré.** Un autre programme utilise peut-être le port
8000, par exemple Notosaurus lancé en autonome en même temps. Arrête-le, ou choisis un autre port
dans la config du greffon (**Outils → Greffons → Notosaurus → Config**, `port`), puis redémarre
Anki.

## Le téléphone n'arrive pas à ouvrir Notosaurus

- Le téléphone et l'ordinateur doivent être sur le **même Wi-Fi**. Un réseau « invité » isole
  souvent ses appareils : utilise le réseau principal.
- Sous Windows, autorise Anki (ou Python) quand le **pare-feu** le demande, la première fois.
- Si l'adresse de l'ordinateur a changé (après un redémarrage de la box), **scanne à nouveau le
  QR code** : **Outils → Notosaurus → Ouvrir sur le téléphone…**.
- **« Le serveur n'écoute que sur cet ordinateur »** : mets `host` à `0.0.0.0` dans la config du
  greffon.
- **« Cet appareil n'est pas encore autorisé »** : le téléphone n'a pas scanné le QR code, ou tous
  les téléphones ont été déconnectés. Scanne-le à nouveau.

## Les réglages ne s'ouvrent pas sur le téléphone

**« Les réglages s'ouvrent depuis Anki, sur l'ordinateur. »** C'est voulu : avec le greffon, les
réglages (et les clés d'API) ne sont accessibles que sur l'ordinateur lui-même. Ouvre-les avec
**Outils → Notosaurus → Réglages**.

## L'IA échoue

| Message | Que faire |
|---|---|
| « Pas de clé … » / « Clé … invalide » | Colle à nouveau la clé dans **Réglages → Accès**, puis **🔌 Tester**. |
| « … est surchargé en ce moment » | Fréquent avec Gemini : réessaie dans une minute. Les modèles de secours prennent le relais automatiquement. |
| « Quota … atteint » | La limite d'une clé gratuite est atteinte : attends, ou active la facturation. |
| « Réponse tronquée : trop de cartes d'un coup » | Envoie moins de pages à la fois, ou demande moins de cartes. |
| « Le modèle n'a pas renvoyé de cartes valides » | Réessaie ; si ça se répète, choisis un autre modèle. |
| Le modèle « ne semble pas voir l'image » (Tester) | Le modèle ne lit pas les images : choisis un modèle « vision ». |

**Les cartes sont fausses ou il en manque.** Vérifie la photo (voir
[Bien prendre la photo](../photos/)), précise la consigne, ou fais-les corriger par l'IA. Claude
lit le mieux l'écriture manuscrite.

## Les cartes n'arrivent pas dans Anki

- **« Anki est injoignable »** : lance Anki sur l'ordinateur. En autonome, Anki a besoin du
  greffon AnkiConnect.
- **« Aucun profil ouvert dans Anki »** : ouvre le profil de l'enfant, puis renvoie.
- **Un avertissement sur un autre profil** : la leçon appartient à un autre enfant que le profil
  ouvert dans Anki. Ouvre le bon profil, ou confirme.
- **Les cartes n'arrivent pas sur le téléphone** : le message indique « pas de synchro AnkiWeb »
  quand le profil n'est pas connecté à AnkiWeb. Clique une fois sur **Synchroniser** dans Anki
  pour te connecter, puis renvoie. Sur le téléphone, synchronise AnkiDroid ou AnkiMobile.
- **Des cartes sans son** : le service de voix n'a pas répondu (il a besoin d'Internet). Renvoie
  la leçon plus tard : l'audio manquant est ajouté.

## Questions

**Notosaurus marche-t-il sans Anki sur ordinateur ?**
Le greffon a besoin d'Anki sur un ordinateur. Notosaurus peut aussi tourner
[en autonome](../install/), et le fichier `.apkg` s'ouvre dans AnkiDroid sans ordinateur. Mais la
page du téléphone a toujours besoin de l'ordinateur (ou d'un serveur) où tourne Notosaurus.

**Est-ce que ça marche sur iPhone ?**
Oui : la page s'ouvre dans Safari et peut être ajoutée à l'écran d'accueil. Les révisions se font
dans AnkiMobile (payant, il finance le développement d'Anki).

**Plusieurs enfants peuvent-ils l'utiliser ?**
Oui, avec un profil Anki chacun : voir [Plusieurs enfants](../several-children/).

**Combien ça coûte ?**
Notosaurus est gratuit. Le service d'IA coûte d'une fraction de centime à quelques centimes par
leçon : voir [Services d'IA et coûts](../ai-services/).

**Comment le désinstaller ?**
Dans Anki, **Outils → Greffons**, sélectionne Notosaurus, **Supprimer**. Ses composants **et son
dossier de données (leçons, photos, réglages) sont supprimés aussi** : copie d'abord le dossier
de données si tu veux les garder (voir
[Confidentialité et sécurité](../privacy/#où-sont-les-données-)). Les cartes déjà envoyées restent
dans Anki.
