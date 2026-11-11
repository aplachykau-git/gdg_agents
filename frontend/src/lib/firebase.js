import { initializeApp, getApps } from 'firebase/app';
import { 
  getAuth, 
  GoogleAuthProvider, 
  signInWithPopup, 
  signOut, 
  onAuthStateChanged 
} from 'firebase/auth';
import { initializeAppCheck, ReCaptchaV3Provider } from 'firebase/app-check';
import { rememberToken } from './google/drive.js';

const env = (typeof import.meta !== 'undefined' && import.meta.env) || {};

export const firebaseConfig = {
  projectId: env.VITE_FIREBASE_PROJECT_ID || '',
  appId: env.VITE_FIREBASE_APP_ID || '',
  storageBucket: env.VITE_FIREBASE_STORAGE_BUCKET || '',
  apiKey: env.VITE_FIREBASE_API_KEY || '',
  authDomain: env.VITE_FIREBASE_AUTH_DOMAIN || '',
  messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  projectNumber: env.VITE_FIREBASE_PROJECT_NUMBER || ''
};

const app = firebaseConfig.apiKey
  ? (getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0])
  : null;
export const auth = app ? getAuth(app) : null;

// Initialize Firebase App Check to protect against abuse and automated scrapers
let appCheck = null;
if (typeof window !== 'undefined' && app) {
  const recaptchaKey = env.VITE_RECAPTCHA_SITE_KEY || env.VITE_FIREBASE_APP_CHECK_KEY;
  if (recaptchaKey) {
    try {
      if (env.DEV) {
        // @ts-ignore
        self.FIREBASE_APPCHECK_DEBUG_TOKEN = true;
      }
      appCheck = initializeAppCheck(app, {
        provider: new ReCaptchaV3Provider(recaptchaKey),
        isTokenAutoRefreshEnabled: true
      });
      console.log('[App Check] Initialized with reCAPTCHA v3 provider.');
    } catch (err) {
      console.warn('[App Check] Initialization notice:', err);
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
  if (!auth) {
    throw new Error('Firebase is not configured. Set VITE_FIREBASE_API_KEY in frontend/.env.');
  }
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const credential = GoogleAuthProvider.credentialFromResult(result);
    const token = credential?.accessToken;
    // Google access tokens live about an hour; the expiry lets the Drive picker refresh in time.
    if (token) rememberToken(token);
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
  if (!auth) return;
  try {
    await signOut(auth);
  } catch (error) {
    console.error("Firebase Logout Error:", error);
  }
}

export { onAuthStateChanged };
