// The floating info card (#pop): a teaser for the focused spot/province, or the detail card for a chosen spot.
import { $ } from '../utils.js';
import { COUNTRIES, bestSpot } from '../data/spots.js';
import { selection, runtime, markersInScope } from '../state.js';
import { viewport } from '../map/canvas.js';
import { project } from '../map/projection.js';
import { fetchSpotSignal, moonText } from '../services/marine-data.js';

// Keeps the teaser card next to the focused marker (the detail card is pinned by CSS instead).
export function placePopup() {
  const el = $('#pop');
  if (selection.province != null || !runtime.focus) return;
  const q = project(runtime.focus.spot.coord[0], runtime.focus.spot.coord[1]);
  el.style.left = Math.min(Math.max(q[0] - 118, 12), viewport.w - 250) + 'px';
  el.style.top = Math.min(Math.max(q[1] + 26, 70), viewport.h - 260) + 'px';
}

export function setFocus(marker) {
  if (runtime.focus && runtime.focus.spot === marker.spot) return;
  runtime.focus = marker;
  renderPopup();
}

// Fetches live data for every marker at the current level, refreshing the popup as results arrive.
export function prefetchSignals() {
  if (!selection.country) return;
  markersInScope().forEach(marker => fetchSpotSignal(marker.spot).then(() => {
    if (runtime.focus && runtime.focus.spot === marker.spot || selection.spot != null) renderPopup();
  }));
}

export function renderPopup() {
  const el = $('#pop'), country = COUNTRIES[selection.country];
  const province = country && selection.province != null ? country.provinces[selection.province] : null;
  if (!runtime.focus) runtime.focus = bestSpot(markersInScope());
  const marker = selection.spot != null ? { ...runtime.focus, spot: province.spots[selection.spot], spotIndex: selection.spot } : runtime.focus;
  const spot = marker.spot;
  el.classList.toggle('det', selection.province != null);

  if (selection.province != null) {
    // Detail card. Live values win; demoMetrics (if any) fill in until the data arrives.
    const signal = spot.signal || {}, demo = spot.demoMetrics;
    const metrics = [
      signal.sst != null ? signal.sst.toFixed(1) : (demo ? demo[0] : '—'),
      signal.chl != null ? signal.chl.toFixed(2) : (demo ? demo[1] : '—'),
      signal.depth != null ? Math.round(signal.depth) : (demo ? demo[2] : '—'),
      demo ? demo[3] : '—',
    ];
    const allLive = signal.sst != null && signal.chl != null && signal.depth != null;
    el.innerHTML = `<span class=tag>จุด ${String(marker.spotIndex + 1).padStart(2, '0')} · ${COUNTRIES[marker.countryKey].name}</span>` +
      `<h3>${spot.name}</h3>` +
      `<p>${spot.coord[1].toFixed(3)}° N, ${spot.coord[0].toFixed(3)}° E</p>` +
      `<div style="margin:10px 0 4px"><span class=fsi>${spot.fsi}</span><small>/100 ดัชนี FSI</small></div>` +
      `<p style="margin-bottom:8px">ความเชื่อมั่น: ${allLive ? 'กลาง' : 'ต่ำ'} · ${spot.signal ? 'ข้อมูลจริง NOAA · ทดลอง ยังไม่ได้วัดความแม่นยำ' : 'ค่าตัวอย่าง กำลังโหลดข้อมูล'}` +
      `${spot.signal ? `<br>SST ${(signal.sstT || 'ไม่มี').slice(0, 10)} · คลอโรฟิลล์ ${signal.chlT ? signal.chlT.slice(0, 10) : 'ไม่มี (เมฆบัง)'}` : ''}</p>` +
      `<div class=mt>อุณหภูมิผิวน้ำ<b>${metrics[0]} °C</b></div>` +
      `<div class=mt>คลอโรฟิลล์-เอ<b>${metrics[1]} mg/m³</b></div>` +
      `<div class=mt>ความลึก<b>${metrics[2]} ม.</b></div>` +
      `<div class=mt>ระยะจากท่าเรือ<b>${metrics[3]} นม.</b></div>` +
      `<div class=mt>ดวงจันทร์<b>${moonText()}</b></div>` +
      `<p style="color:#f5c451;margin-top:8px">จุดสาธิต ยังไม่ได้ตรวจสอบกฎหมายและประกาศเตือนภัยทางการ ไม่ใช่คำแนะนำให้ออกเรือ</p>` +
      `<button class=btn onclick="show('route')">วางแผนเส้นทาง ↗</button>`;
    return;
  }

  // Teaser card: best signal across countries, or the province behind the focused marker.
  el.innerHTML = !selection.country
    ? `<span class=tag>พื้นที่คลอง</span><h3>${COUNTRIES[marker.countryKey].waters}</h3><p>สัญญาณดีสุดวันนี้ FSI ${spot.fsi}</p><a onclick="go('${marker.countryKey}')">สำรวจ${COUNTRIES[marker.countryKey].name} ›</a>`
    : `<span class=tag>ข้อมูลล่าสุด</span><h3>${country.provinces[marker.provinceIndex].name}</h3><p>${country.provinces[marker.provinceIndex].spots.length} จุดคาดการณ์ใกล้ชายฝั่ง</p><a onclick="go('${marker.countryKey}',${marker.provinceIndex})">ดูแหล่งปลา${country.provinces[marker.provinceIndex].name} ›</a>`;
}
