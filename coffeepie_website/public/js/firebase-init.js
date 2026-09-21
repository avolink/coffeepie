/* 
  Firebase Initialization with App Check
  Configured for Coffee Pie Project
*/
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app-check.js";

const firebaseConfig = {
    apiKey: "YOUR_FIREBASE_API_KEY", // IMPORTANT: Inject this via environment variables or CI/CD
    authDomain: "coffeepie-firebase.firebaseapp.com",
    projectId: "coffeepie-firebase",
    storageBucket: "coffeepie-firebase.firebasestorage.app",
    messagingSenderId: "194088927708",
    appId: "1:194088927708:web:7f6d34ea76aa4694b7c7128f" // IMPORTANT: Verify this App ID in Firebase Console
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize App Check
// The user requested reCAPTCHA Enterprise or Play Integrity.
// We implement reCAPTCHA Enterprise as it is standard for Web.
const appCheck = initializeAppCheck(app, {
    provider: new ReCaptchaEnterpriseProvider('6Ld_RECAPTCHA_ENTERPRISE_SITE_KEY'), // Replace with your actual site key
    isTokenAutoRefreshEnabled: true
});

console.log("Firebase App Check initialized with reCAPTCHA Enterprise.");
