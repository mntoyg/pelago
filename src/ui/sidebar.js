// Re-renders everything that depends on the current selection: sidebar, headline, breadcrumb, popup.
import { $ } from '../utils.js';
import { COUNTRIES } from '../data/spots.js';
import { selection, layers } from '../state.js';
import { renderPopup, prefetchSignals } from './popup.js';

const chevron = '<span style="color:var(--mu)">›</span>';

// Map-layer checkboxes. Only the chlorophyll layer is switchable for now (the others are display-only).
function layerToggles() {
  return [['fsi', 'ดัชนีแหล่งปลา (FSI)', 1], ['chl', 'คลอโรฟิลล์ / แพลงก์ตอน', layers.chl], ['zone', 'เขตอนุรักษ์และพื้นที่ห้ามจับ', 0]]
    .map(([key, name, on]) => `<div class="ck ${on ? '' : 'off'}" onclick="tg('${key}')" style="cursor:pointer"><span></span>${name}</div>`)
    .join('');
}

// Handler for the layer checkboxes (inline onclick).
export function toggleLayer(key) {
  if (key === 'chl') { layers.chl = !layers.chl; renderSelection(); }
}

export function renderSelection() {
  const country = COUNTRIES[selection.country];
  const province = country && selection.province != null ? country.provinces[selection.province] : null;

  // sidebar
  let h = '<div class=eb>OCEAN INTELLIGENCE</div>';
  h += !country ? '<h2>วันนี้ ปลาอยู่ที่ไหน?</h2><p>มองจากอวกาศ แล้วค่อยซูมลงไปหาแหล่งปลาใกล้บ้าน</p>'
    : !province ? '<h2>สำรวจน่านน้ำ' + country.name.replace('ประเทศ', '') + '</h2><p>เลือกจังหวัดเพื่อดูแหล่งปลา</p>'
    : '<h2>แหล่งปลา' + province.name + '</h2><p>' + province.area + '</p>';
  h += '<label>ประเทศ</label><select onchange="pickC(this.value)"><option value="">เลือกประเทศ</option>' +
    Object.keys(COUNTRIES).map(k => `<option value=${k} ${k === selection.country ? 'selected' : ''}>${COUNTRIES[k].name}</option>`).join('') + '</select>';
  if (country) {
    h += '<label>จังหวัด</label><select onchange="pickP(this.value)"><option value="">เลือกจังหวัด</option>' +
      country.provinces.map((q, i) => `<option value=${i} ${i === selection.province ? 'selected' : ''}>${q.name}</option>`).join('') + '</select>';
  }
  h += '<label>' + (!country ? 'เริ่มสำรวจประเทศ' : !province ? 'จังหวัดแนะนำ' : 'จุดคาดการณ์วันนี้') + '</label>';
  if (!country) {
    h += Object.keys(COUNTRIES).map(k => `<button class=it onclick="go('${k}')"><span><b>${COUNTRIES[k].name}</b><i>${COUNTRIES[k].label}</i></span>${chevron}</button>`).join('');
  } else if (!province) {
    h += country.provinces.map((q, i) => `<button class=it onclick="go('${selection.country}',${i})"><span><b>${q.name}</b><i>${q.area}</i></span>${chevron}</button>`).join('');
  } else {
    h += province.spots.map((q, i) => `<button class="it ${i === selection.spot ? 'on' : ''}" onclick="go('${selection.country}',${selection.province},${i})"><span><b>${String(i + 1).padStart(2, '0')} ${q.name}</b><i>FSI ${q.fsi} · ความเชื่อมั่น${q.fsi >= 75 ? 'กลาง' : 'ต่ำ'}</i></span>${chevron}</button>`).join('');
  }
  h += '<label class=dsk>ชั้นข้อมูลแผนที่</label>' + layerToggles() + '';
  h += '<div class=note>ทดลอง · ค่า FSI ในหน้านี้เป็นตัวอย่างเพื่อออกแบบ ยังไม่ใช่ผลจากโมเดลหรือข้อมูลดาวเทียมจริง</div>';
  $('#side').innerHTML = h;

  // headline and breadcrumb over the map
  $('#h1').textContent = !country ? 'ทุกทะเล เชื่อมถึงกัน' : !province ? country.name : 'ชายฝั่ง' + province.name;
  $('#sub').textContent = !country ? 'ค้นหาพื้นที่ที่ดัชนีสูง แล้วเลือกประเทศ จังหวัด และจุด'
    : !province ? 'จากพรมแดนประเทศ สู่พื้นที่ทะเลใกล้คุณ' : 'ดูภาพรวมและจุดคาดการณ์ก่อนออกเรือ';
  $('#bc').innerHTML = [
    '<button onclick="go()">เอเชีย</button>',
    country ? `<button onclick="go('${selection.country}')">${country.name}</button>` : '',
    province ? `<button onclick="go('${selection.country}',${selection.province})">${province.name}</button>` : '',
  ].join('');
  // restart the headline's fade-up animation
  const headline = $('#h1');
  headline.style.animation = 'none';
  void headline.offsetWidth;
  headline.style.animation = 'up .8s .5s both';

  $('#sig').style.display = country ? 'none' : 'block';
  $('#pill').textContent = (country ? '● ภาพถ่ายดาวเทียม' : '● โลกจากภาพดาวเทียม') + ' / FSI';
  renderPopup();
  prefetchSignals();
}
