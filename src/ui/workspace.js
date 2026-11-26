// Screen switching (map vs workspace views), top nav / phone bottom bar, and the actions behind view buttons.
import { $ } from '../utils.js';
import { loadList, saveList, getPosition } from '../services/device.js';
import { VIEWS, renderFuelResult } from './views.js';

// Phone bottom bar: [view key, icon, label]
const BOTTOM_BAR = [['go', '🧭', 'ออกไหม'], ['survey', '🗺️', 'แผนที่'], ['sea', '🌊', 'ทะเล'], ['log', '📒', 'บันทึก'], ['sos', '🆘', 'SOS']];
// Desktop top nav: [view key, label]
const TOP_NAV = [['survey', 'สำรวจแหล่งปลา'], ['route', 'วางแผนเส้นทาง'], ['log', 'บันทึกการจับ'], ['fish', 'จำแนกปลา AI']];

let firstShow = true;

// Adds the (CSS-hidden on desktop) phone bottom bar container.
export function mountBottomBar() {
  try { document.body.insertAdjacentHTML('beforeend', '<div id=bar></div>'); } catch (e) { /* no body to attach to */ }
}

// Shows a screen by key: 'survey' = the map, anything else = a workspace view. Highlights it in both navs.
// On a phone-sized screen the very first call opens the go/no-go view instead of the map.
export function show(key) {
  if (firstShow) {
    firstShow = false;
    if (innerWidth < 820 && key === 'survey') key = 'go';
  }
  const view = $('#view');
  view.hidden = key === 'survey';
  $('#nav').innerHTML = TOP_NAV.map(([k, name]) => `<span class="${k === key ? 'on' : ''}" onclick="show('${k}')">${name}</span>`).join('');
  $('#bar').innerHTML = BOTTOM_BAR.map(b => `<button class="${b[0] === key ? 'on' : ''}" onclick="show('${b[0]}')"><b>${b[1]}</b>${b[2]}</button>`).join('');
  if (key === 'survey') return;
  view.innerHTML = VIEWS[key]();
  view.scrollTop = 0;
  if (key === 'fuel') renderFuelResult();
}

const shortDate = () => new Date().toLocaleDateString('th-TH', { day: 'numeric', month: 'short' });

// Saves a fish price report (kept on this device only). Ignores empty or out-of-range prices.
export function addPrice() {
  const price = +$('#pv2').value;
  if (!(price > 0 && price < 100000)) return;
  const reports = loadList('pr');
  reports.unshift([$('#pk').value, price, $('#pp').value || '-', shortDate()]);
  saveList('pr', reports.slice(0, 50));
  show('price');
}

// Saves the current GPS position as a private pin (kept on this device only).
export function addPin() {
  const name = $('#pn').value || 'จุดของฉัน';
  $('#pm').textContent = 'กำลังหาตำแหน่ง...';
  getPosition((err, coords) => {
    if (err) { $('#pm').textContent = 'ไม่ได้ตำแหน่ง: เปิด GPS และอนุญาตให้เว็บใช้ตำแหน่ง'; return; }
    const pins = loadList('pins');
    pins.unshift([name, coords.latitude.toFixed(5), coords.longitude.toFixed(5), shortDate()]);
    saveList('pins', pins.slice(0, 100));
    show('pins');
  });
}

export function delPin(index) {
  const pins = loadList('pins');
  pins.splice(index, 1);
  saveList('pins', pins);
  show('pins');
}

// SOS: shows the current coordinates and copies them to the clipboard. It does not message anyone.
export function doSos() {
  $('#sm').textContent = 'กำลังหาตำแหน่ง...';
  getPosition((err, coords) => {
    if (err) { $('#sm').textContent = 'ไม่ได้ตำแหน่ง: เปิด GPS และอนุญาตให้เว็บใช้ตำแหน่ง'; return; }
    const text = coords.latitude.toFixed(5) + ', ' + coords.longitude.toFixed(5);
    $('#sm').innerHTML = 'ตำแหน่งของคุณ: <b style="color:var(--tx)">' + text + '</b> (±' + Math.round(coords.accuracy) + ' ม.) คัดลอกแล้ว — ส่งต่อให้คนที่ไว้ใจหรือแจ้งหน่วยกู้ภัย';
    try { navigator.clipboard.writeText(text); } catch (e) { /* clipboard unavailable */ }
  });
}
