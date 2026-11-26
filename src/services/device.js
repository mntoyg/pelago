// Browser/device access: localStorage lists, GPS and speech.

// Reads a JSON list from localStorage; returns [] when missing or unreadable.
export const loadList = key => {
  try { return JSON.parse(localStorage.getItem(key)) || []; } catch (e) { return []; }
};

// Stores a value as JSON; silently does nothing when storage is unavailable (e.g. private mode).
export const saveList = (key, value) => {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* storage unavailable: data stays in memory only */ }
};

// Current GPS position. Calls cb(null, coords) on success, or cb(error) on failure / no geolocation.
export const getPosition = cb => navigator.geolocation
  ? navigator.geolocation.getCurrentPosition(p => cb(null, p.coords), e => cb(e || 1), { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 })
  : cb(1);

// Reads text aloud in Thai (no-op where speech synthesis is unavailable).
export function speak(text) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'th-TH';
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  } catch (e) { /* speech synthesis unavailable */ }
}
