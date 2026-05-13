// =============================================================================
// firebase-config.js — REMPLIS ces valeurs avec celles de ton projet Firebase
// (console Firebase > Paramètres du projet > Tes applications > Config SDK).
// Tant que apiKey contient "VOTRE_", l'app démarre en mode local (mono-client)
// et t'invite à utiliser le simulateur.
// =============================================================================

export const firebaseConfig = {
  apiKey: "VOTRE_API_KEY",
  authDomain: "VOTRE_PROJET.firebaseapp.com",
  projectId: "VOTRE_PROJET",
  storageBucket: "VOTRE_PROJET.appspot.com",
  messagingSenderId: "VOTRE_SENDER_ID",
  appId: "VOTRE_APP_ID"
};

// Passe à true pour taper sur l'émulateur Firebase local (firebase emulators:start)
export const USE_EMULATOR = false;
