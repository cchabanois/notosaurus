---
title: "Dépannage du greffon"
description: "Que faire quand le greffon ne démarre pas, que le téléphone ne se connecte pas, que l'IA échoue ou que les cartes n'arrivent pas dans Anki."
---

Les messages ci-dessous sont ceux qu'affiche Notosaurus. Quand quelque chose ne va pas dans le
greffon, **Outils → Notosaurus → Journal du serveur** montre ce qui s'est passé, et
**Redémarrer le serveur** suffit souvent.

## Notosaurus ne démarre pas

**« Notosaurus n'est pas démarré. »** Vous avez refusé l'installation de ses composants au premier
démarrage. Pour les installer : **Outils → Notosaurus → Ouvrir Notosaurus**.

**« Téléchargement de uv depuis GitHub impossible »** ou **« Installation des dépendances de
Notosaurus impossible ».** Le premier démarrage télécharge environ 300 Mo : vérifiez la connexion
Internet, puis **Outils → Notosaurus → Redémarrer le serveur**. Le journal indique ce qui a
échoué.

**Le serveur s'arrête juste après avoir démarré.** Un autre programme utilise peut-être le port
8000, par exemple Notosaurus lancé en autonome en même temps. Arrêtez-le, ou choisissez un autre port
dans la config du greffon (**Outils → Greffons → Notosaurus → Config**, `port`), puis redémarrez
Anki.

## Le téléphone n'arrive pas à ouvrir Notosaurus

Voir aussi [Sur le téléphone](../phone/).

- Le téléphone et l'ordinateur doivent être sur le **même Wi-Fi**. Un réseau « invité » isole
  souvent ses appareils : utilisez le réseau principal.
- Sous Windows, autorisez Anki (ou Python) quand le **pare-feu** le demande, la première fois.
- Si l'adresse de l'ordinateur a changé (après un redémarrage de la box), **scannez à nouveau le
  QR code** : **Outils → Notosaurus → Ouvrir sur le téléphone…**.
- **« Le serveur n'écoute que sur cet ordinateur »** : mettez `host` à `0.0.0.0` dans la config du
  greffon.
- **« Cet appareil n'est pas encore autorisé »** : le téléphone n'a pas scanné le QR code, ou tous
  les téléphones ont été déconnectés. Scannez-le à nouveau.

## Les réglages ne s'ouvrent pas sur le téléphone

**« Les réglages s'ouvrent depuis Anki, sur l'ordinateur. »** C'est voulu : avec le greffon, les
réglages (et les clés d'API) ne sont accessibles que sur l'ordinateur lui-même. Ouvrez-les avec
**Outils → Notosaurus → Réglages**.

## L'IA échoue

| Message | Que faire |
|---|---|
| « Pas de clé … » / « Clé … invalide » | Collez à nouveau la clé dans **Réglages → Accès**, puis **🔌 Tester**. |
| « … est surchargé en ce moment » | Fréquent avec Gemini : réessayez dans une minute. Les modèles de secours prennent le relais automatiquement. |
| « Quota … atteint » | La limite d'une clé gratuite est atteinte : attendez, ou activez la facturation. |
| « Réponse tronquée : trop de cartes d'un coup » | Envoyez moins de pages à la fois, ou demandez moins de cartes. |
| « Le modèle n'a pas renvoyé de cartes valides » | Réessayez ; si ça se répète, choisissez un autre modèle. |
| Le modèle « ne semble pas voir l'image » (Tester) | Le modèle ne lit pas les images : choisissez un modèle « vision ». |

## Les cartes sont fausses ou il en manque

Vérifiez la photo (voir [Photos et PDF](../photos/)), précisez la consigne, ou corrigez-les avec
l'IA (voir [Relire les cartes](../review/)). Pour l'écriture manuscrite, Claude lit le mieux :
voir [Réglages et services d'IA](../ai-services/).

## Un PDF ne s'ajoute pas

- **« Déjà 10 pages : retirez-en avant d'ajouter un PDF. »** Une leçon tient en 10 pages : retirez
  les photos inutiles (le bouton **Retirer cette page**, ✕, sur chacune), ou faites deux leçons.
- **« … est protégé par un mot de passe : enregistrez-le sans mot de passe, puis ajoutez-le à
  nouveau. »** Ouvrez le PDF, enregistrez-le sans mot de passe (ou imprimez-le dans un nouveau
  PDF), puis ajoutez-le à nouveau.
- **Des mots mal lus dans un PDF** : un PDF scanné ne contient que des images, lues comme des
  photos. Un PDF fait sur ordinateur donne à l'IA son texte exact.

## Les cartes n'arrivent pas dans Anki

- **« Anki est injoignable »** : lancez Anki sur l'ordinateur. En autonome, Anki a besoin du
  greffon AnkiConnect.
- **« Aucun profil ouvert dans Anki »** : ouvrez le profil de l'enfant, puis renvoyez.
- **Un avertissement sur un autre profil** : la leçon appartient à un autre enfant que le profil
  ouvert dans Anki. Ouvrez le bon profil, ou confirmez.
- **Les cartes n'arrivent pas sur le téléphone** : le message indique « pas de synchro AnkiWeb »
  quand le profil n'est pas connecté à AnkiWeb. Cliquez une fois sur **Synchroniser** dans Anki
  pour vous connecter, puis renvoyez. Sur le téléphone, synchronisez AnkiDroid ou AnkiMobile.
- **Des cartes sans son** : le service de voix n'a pas répondu (il a besoin d'Internet). Renvoyez
  la leçon plus tard : l'audio manquant est ajouté.

## Désinstaller le greffon

Dans Anki, **Outils → Greffons**, sélectionnez Notosaurus, **Supprimer**. Ses composants **et son
dossier de données (leçons, photos, réglages) sont supprimés aussi** : copiez d'abord le dossier
de données si vous voulez les garder (voir
[Confidentialité et sécurité sur l'ordinateur](../privacy/#où-sont-les-données-)). Les cartes déjà envoyées restent
dans Anki.
