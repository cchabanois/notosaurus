---
title: "Commencer avec le greffon"
description: "Installer Notosaurus dans Anki, le configurer avec l'assistant, connecter votre téléphone et faire votre premier paquet à partir d'une photo."
---

Le greffon Anki fait tourner Notosaurus sur votre ordinateur, dans Anki, gratuitement, avec votre
propre clé d'IA. Vous l'utilisez depuis le navigateur du téléphone, ou depuis l'application
Android, sur le même Wi-Fi. Plutôt l'application toute seule ? Voir
[Quel Notosaurus ?](../which-notosaurus/).

## Ce qu'il vous faut

- **Anki** sur un ordinateur (Windows, macOS ou Linux), dans une version récente.
- **Un téléphone** sur le même Wi-Fi que l'ordinateur.
- **Une clé pour un service d'IA.** Gemini est le moins cher et a une offre gratuite pour
  essayer Notosaurus ; Claude et GPT marchent bien aussi. Une leçon coûte d'une
  fraction de centime à quelques centimes.

:::caution[Offres gratuites et confidentialité]
Les offres gratuites autorisent en général le fournisseur d'IA à utiliser ce que vous envoyez
pour améliorer ses modèles. Pour les cahiers de vos enfants, préférez une clé payante :
quelques euros durent longtemps.
:::

## 1. Installer le greffon

1. Téléchargez `notosaurus-<version>.ankiaddon` depuis la
   [dernière version](https://github.com/cchabanois/notosaurus/releases/latest).
2. Double-cliquez sur le fichier (ou dans Anki : **Outils → Greffons → Installer depuis un
   fichier**), puis redémarrez Anki.
3. Au premier démarrage, Notosaurus demande avant d'installer ses composants (environ
   300 Mo). Ça prend quelques minutes, une seule fois.

## 2. L'assistant de démarrage

Une fois les composants installés, Anki propose **« Le configurer maintenant ? »** :
l'assistant s'ouvre dans le navigateur de l'ordinateur. Deux étapes, quelques minutes. Vous le
retrouvez à tout moment dans **Outils → Notosaurus → Assistant de démarrage**, et tant qu'aucune IA n'est
configurée, la page de Notosaurus affiche **« Encore une étape »** avec un bouton pour le
lancer.

**L'IA.** Choisissez le service qui lit les leçons. **Gemini** est conseillé : le meilleur
rapport qualité/prix dans nos essais, environ 1 centime par leçon (voir
[Réglages et services d'IA](../ai-services/) pour les autres).

![L'assistant : le choix de l'IA](../../../assets/screenshots/fr/setup-start.png)

Pour Gemini, l'assistant explique comment obtenir la clé en trois étapes. Collez-la, puis
touchez **🔌 Vérifier la clé** : Notosaurus vérifie que le modèle lit une image et répond au
bon format. **Suivant** apparaît quand c'est bon.

![L'assistant : la clé Gemini, vérifiée](../../../assets/screenshots/fr/setup-ai.png)

**Le téléphone.** Scannez le QR code avec l'appareil photo du téléphone et ouvrez le lien.
L'assistant attend le téléphone, puis affiche **« ✓ Le téléphone est connecté »**. Ajoutez
ensuite la page à l'écran d'accueil : elle s'ouvre comme une appli (voir
[Sur le téléphone](../phone/) pour chaque navigateur). **Plus tard** passe cette étape : le
QR code reste dans **Outils → Notosaurus → Ouvrir sur le téléphone…** et dans les réglages.

![L'assistant : le QR code pour le téléphone](../../../assets/screenshots/fr/setup-phone.png)

**Notosaurus est prêt !** Ouvrez Notosaurus, ou tous les réglages : images des cartes, voix,
consignes par enfant… Les réglages ne s'ouvrent que sur l'ordinateur : les enfants ne peuvent
pas les changer depuis un téléphone.

![L'assistant : Notosaurus est prêt](../../../assets/screenshots/fr/setup-done.png)

:::tip
Seuls les appareils qui ont scanné ce QR code peuvent utiliser Notosaurus. Si un téléphone
est perdu ou prêté : **Réglages → Téléphones → Déconnecter tous les téléphones**.
:::

## 3. Votre première leçon

1. Dans **Photos de la leçon**, prenez la page en photo (ou plusieurs pages), ou ajoutez un PDF :
   voir [Photos et PDF](../photos/).
2. Dans **Consigne**, choisissez ce qu'il faut faire : vocabulaire, questions, texte à trous,
   schéma à compléter… **Automatique** choisit d'après la leçon. Voir [Les consignes](../instructions/).

   ![La photo de la leçon et la consigne](../../../assets/screenshots/fr/instructions.png)

3. Touchez **Générer les cartes** et attendez quelques secondes.
4. Vérifiez les cartes. Modifiez-les, supprimez-en, ou demandez à l'IA de les corriger avec
   vos mots : voir [Relire les cartes](../review/).

   ![Les cartes, prêtes à être relues](../../../assets/screenshots/fr/review.png)

   ![Demander une correction à l'IA](../../../assets/screenshots/fr/correction.png)

5. Touchez **Ajouter à Anki**.

La leçon est enregistrée : vous pouvez la rouvrir plus tard depuis la liste des leçons, la
corriger et la renvoyer. Ses cartes sont mises à jour dans Anki, pas dupliquées.

Avec la consigne **Schéma ou carte à compléter**, les légendes d'un schéma sont cachées derrière des
numéros : chaque carte en demande une.

![Un schéma avec ses légendes masquées](../../../assets/screenshots/fr/diagram.png)

## 4. Réviser sur le téléphone

Pour réviser sur le téléphone, utilisez **AnkiDroid** (Android) ou **AnkiMobile** (iPhone)
avec un compte **AnkiWeb** : Notosaurus synchronise Anki après l'envoi des cartes. Avec
plusieurs enfants, consultez [Plusieurs enfants](../several-children/).
