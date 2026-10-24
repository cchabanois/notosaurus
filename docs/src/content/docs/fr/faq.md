---
title: "Dépannage et FAQ"
description: "Que faire quand Notosaurus ne démarre pas, que le téléphone ne se connecte pas, que l'IA échoue ou que les cartes n'arrivent pas dans Anki, et réponses aux questions fréquentes."
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

**Les cartes sont fausses ou il en manque.** Vérifiez la photo (voir
[Photos et PDF](../photos/)), précisez la consigne, ou faites-les corriger par l'IA. Claude
lit le mieux l'écriture manuscrite.

## Un PDF ne s'ajoute pas

- **« Déjà 10 pages : retirez-en avant d'ajouter un PDF. »** Une leçon tient en 10 pages :
  retirez les photos inutiles (**×**), ou faites deux leçons.
- **« … est protégé par un mot de passe »** : ouvrez le PDF, enregistrez-le sans mot de passe (ou
  imprimez-le dans un nouveau PDF), puis ajoutez-le à nouveau.
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

## Dans l'application

Voir aussi [L'application Android](../android-app/).

| Message | Que faire |
|---|---|
| « Plus de crédits ce mois-ci » | Ils reviennent au prochain renouvellement : **🔑 Abonnement**, dans les réglages, dit quand. |
| « Votre essai gratuit est terminé » | Abonnez-vous dans les Réglages (**🔑 Abonnement**) pour continuer. |
| « Votre abonnement est terminé » | Réabonnez-vous dans l'application. |
| « Paiement en attente » | Google Play n'a pas pu renouveler l'abonnement : mettez à jour votre moyen de paiement dans Google Play (**Réglages → Gérer l'abonnement**). |
| « L'essai gratuit n'est possible qu'avec l'app installée depuis Google Play, sur un vrai téléphone » | Installez l'application depuis Google Play ; l'essai n'est pas proposé sur un émulateur. |
| « Aucun abonnement trouvé sur ce compte Google » (**J'ai déjà un abonnement**) | Vérifiez que le téléphone utilise le compte Google avec lequel l'abonnement a été pris. |
| « Notosaurus n'a pas le droit d'ajouter des cartes à AnkiDroid » | **Réglages → 📥 AnkiDroid → Autoriser**, puis ajoutez à nouveau les cartes. Refusé pour de bon (Android ne demande plus) : autorisez-le dans les paramètres d'Android, **Applications → Notosaurus → Autorisations**. |
| « AnkiDroid n'est pas installé » / « AnkiDroid n'a pas pris les cartes » | Installez AnkiDroid, **ouvrez-le une fois** (il crée sa collection), puis ajoutez à nouveau les cartes. |
| « 💻 Votre ordinateur ne répond pas » | En **💻 Sur mon ordinateur** : Anki doit être ouvert avec le greffon, et le téléphone sur le même Wi-Fi. |

**✎ Notosaurus ne fait rien dans AnkiDroid** (« La carte ne peut pas lancer d'autres
applications ») : sur AnkiDroid 2.25 et avant, activez **Paramètres → Avancé → Autoriser les cartes
à lancer d'autres applications** (voir [Notosaurus dans Anki](../in-anki/#les-cartes-dans-anki)).

## Questions

**Notosaurus marche-t-il sans Anki sur ordinateur ?**
Oui, avec l'[application Android](../android-app/) : elle fait les cartes sur le téléphone et les
met dans AnkiDroid. Le greffon a besoin d'Anki sur un ordinateur ; Notosaurus peut aussi tourner
[en autonome](../install/). Le navigateur du téléphone a toujours besoin de l'ordinateur (ou d'un
serveur) où tourne Notosaurus.

**Est-ce que ça marche sur iPhone ?**
Oui, dans le navigateur, avec Notosaurus sur l'ordinateur (il n'y a pas d'application iPhone) : la page s'ouvre dans Safari et peut être ajoutée à l'écran d'accueil. Les révisions se font
dans AnkiMobile (payant, il finance le développement d'Anki).

**Plusieurs enfants peuvent-ils l'utiliser ?**
Oui : chaque enfant a sa fiche (**🧒** sur la page principale), avec sa classe, ses paquets, ses
instructions et ses leçons. Voir [Plusieurs enfants](../several-children/).

**Combien ça coûte ?**
Le greffon est gratuit : vous payez directement le service d'IA, d'une fraction de centime à
quelques centimes par leçon (voir [Services d'IA et coûts](../ai-services/)).
L'[application Android](../android-app/) seule fonctionne avec un abonnement, avec un essai
gratuit ; avec le greffon, elle est gratuite.

**Comment soutenir Notosaurus ?**
Si Notosaurus vous rend service, vous pouvez faire un don sur
[Ko-fi](https://ko-fi.com/notosaurus) : **☕ Soutenir Notosaurus** en bas de la page et des
réglages, ou **Outils → Notosaurus → Soutenir Notosaurus…** dans Anki (sur l'ordinateur : l'application n'en a pas, son
abonnement paie). Notosaurus reste gratuit, sans publicité.

**Comment le mettre à jour ?**
Voir [Nouveautés](../whats-new/#mettre-à-jour-notosaurus).

**Comment le désinstaller ?**
Dans Anki, **Outils → Greffons**, sélectionnez Notosaurus, **Supprimer**. Ses composants **et son
dossier de données (leçons, photos, réglages) sont supprimés aussi** : copiez d'abord le dossier
de données si vous voulez les garder (voir
[Confidentialité et sécurité](../privacy/#où-sont-les-données-)). Les cartes déjà envoyées restent
dans Anki.
