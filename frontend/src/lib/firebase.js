import { initializeApp, getApps } from 'firebase/app';
import { 
  getAuth, 
  GoogleAuthProvider, 
  signInWithPopup, 
  signOut, 
  onAuthStateChanged 
} from 'firebase/auth';

const firebaseConfig = {
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "gdg-agents-6b59a",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:876483189679:web:52342a7d29ca11da416d5a",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "gdg-agents-6b59a.firebasestorage.app",
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyCvRFAKcjlJu_LI7K0aRHmI3OYAmWWrngI",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "gdg-agents-6b59a.firebaseapp.com",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "876483189679",
  projectNumber: import.meta.env.VITE_FIREBASE_PROJECT_NUMBER || "876483189679"
};

import { initializeAppCheck, ReCaptchaV3Provider } from 'firebase/app-check';

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
export const auth = getAuth(app);

// Initialize Firebase App Check to protect against abuse and automated scrapers
let appCheck = null;
if (typeof window !== 'undefined') {
  const recaptchaKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY || import.meta.env.VITE_FIREBASE_APP_CHECK_KEY;
  if (recaptchaKey) {
    try {
      if (import.meta.env.DEV) {
        // @ts-ignore
        self.FIREBASE_APPCHECK_DEBUG_TOKEN = true;
      }
      appCheck = initializeAppCheck(app, {
        provider: new ReCaptchaV3Provider(recaptchaKey),
        isTokenAutoRefreshEnabled: true
      });
      console.log('🛡️ [App Check] Initialized with reCAPTCHA v3 provider.');
    } catch (err) {
      console.warn('⚠️ [App Check] Initialization notice:', err);
    }
  }
}
export { appCheck };

export const googleProvider = new GoogleAuthProvider();
googleProvider.addScope('https://www.googleapis.com/auth/drive');
googleProvider.addScope('https://www.googleapis.com/auth/drive.file');
googleProvider.addScope('https://www.googleapis.com/auth/documents');
googleProvider.setCustomParameters({
  prompt: 'select_account'
});

export async function loginWithGoogle() {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const credential = GoogleAuthProvider.credentialFromResult(result);
    const token = credential?.accessToken;
    if (token && typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem('google_drive_token', token);
    }
    return {
      user: result.user,
      accessToken: token
    };
  } catch (error) {
    console.error("Firebase Google Auth Error:", error);
    throw error;
  }
}

export async function logoutUser() {
  try {
    await signOut(auth);
  } catch (error) {
    console.error("Firebase Logout Error:", error);
  }
}

export { onAuthStateChanged };
