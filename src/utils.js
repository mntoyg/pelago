// Small shared helpers.

export const DEG = Math.PI / 180;

// Shorthand for document.querySelector.
export const $ = selector => document.querySelector(selector);

// Whole number with Thai-locale digit grouping (used for baht and litres).
export const fm = n => Math.round(n).toLocaleString('th-TH');

// One decimal place.
export const f1 = n => n.toFixed(1);
