// The workspace screens (everything except the map). Each entry in VIEWS returns an HTML string.
// Handlers referenced from the markup (show, addPrice, addPin, delPin, doSos, say, fu, M) are exposed on `window`
// by main.js, because the markup uses inline onclick/oninput attributes.
import { $, fm, f1 } from '../utils.js';
import { COUNTRIES } from '../data/spots.js';
import { weekForecast } from '../services/weather.js';
import { moonText } from '../services/marine-data.js';
import { statusLabel } from '../services/source-status.js';
import { loadList } from '../services/device.js';
import { shell, pageHeader, tileMap } from './layout.js';

const TODAY = new Date().toLocaleDateString('th-TH-u-ca-buddhist', { day: 'numeric', month: 'short', year: 'numeric' });

// Trip fuel inputs edited on the fuel screen (exposed to the markup as window.M).
export const fuelInputs = { km: 80, rate: 0.35, price: 30, res: 20 };

// PORT approximate/demo, not a surveyed pier position
const PORT = [100.9, 12.66];

// Fuel needed for the trip: litres, reserve litres, total litres, cost, reserve cost, total cost.
const fuelEstimate = () => {
  const litres = fuelInputs.km * fuelInputs.rate, reserveLitres = litres * fuelInputs.res / 100;
  return {
    litres, reserveLitres, totalLitres: litres + reserveLitres,
    cost: litres * fuelInputs.price, reserveCost: reserveLitres * fuelInputs.price, totalCost: (litres + reserveLitres) * fuelInputs.price,
  };
};

// Go / caution / stay-in rating for a small boat from max wave height (m) and wind (km/h): [label, colour].
// small-boat (<10 m) thresholds from the project guide
const seaStatus = (wave, wind) =>
  wave >= 1.5 || wind >= 30 ? ['ไม่ควรออก', '#ff8a8a'] : wave >= 1 || wind >= 20 ? ['ระวัง', '#f5c451'] : ['ปกติ', '#7bf0c8'];

// SVG polyline points for a 300x100 sparkline (values scaled against `max`).
const sparkline = (values, max) => values.map((v, i) => (i * 300 / (values.length - 1)).toFixed(0) + ',' + (95 - v / max * 85).toFixed(0)).join(' ');

// Fills the fuel result card (#fr) from the current inputs. Called on every input event.
export function renderFuelResult() {
  const f = fuelEstimate(), m = fuelInputs;
  $('#fr').innerHTML = `<div class=eb>เตรียมงบค่าน้ำมัน</div><b style="font-size:38px;color:var(--ac)">฿ ${fm(f.totalCost)}</b><p>รวมสำรอง ${m.res}% · ผลคำนวณตัวอย่าง</p>` +
    `<div class=fl>น้ำมันที่ใช้ตามระยะทาง<b>${f1(f.litres)} ลิตร</b></div><div class=fl>สำรองเพิ่ม ${m.res}%<b>${f1(f.reserveLitres)} ลิตร</b></div>` +
    `<div class=fl>ควรเตรียมรวม<b>${f1(f.totalLitres)} ลิตร</b></div><div class=fl>ค่าน้ำมันก่อนสำรอง<b>฿ ${fm(f.cost)}</b></div><div class=fl>งบสำรอง<b>฿ ${fm(f.reserveCost)}</b></div>` +
    `<p class=ok>${m.km} × ${m.rate} × ${m.price} = ${fm(f.cost)} บาท<br>รวมสำรอง ${fm(f.cost)} × ${(1 + m.res / 100).toFixed(2)} = ${fm(f.totalCost)} บาท</p><button class=btn onclick="show('route')">ทบทวนเส้นทาง →</button>`;
}

// Per-country marine rescue numbers: UNSET until taken from official sources
const SOS_NUMBERS = {};

export const VIEWS = {
  route() {
    const S = COUNTRIES.th.provinces[0].spots;
    return shell('route', pageHeader('TRIP PLANNER', 'วางแผนทริปให้คุ้มทุกไมล์', 'เลือกจุดหมาย จัดลำดับเส้นทาง และเทียบทะเลก่อนออกเดินทาง', 'คำนวณค่าน้ำมัน →', 'fuel') +
      `<div class="g g2"><div class="card pd">${tileMap(100.95, 12.5, 10, 380, [[PORT[0], PORT[1], 'ท่าเรือ'], [S[1].coord[0], S[1].coord[1], '02'], [S[0].coord[0], S[0].coord[1], '01']], 1)}` +
      `<p style="margin-top:8px">เส้นทางประกอบการออกแบบเท่านั้น ไม่ใช่เส้นทางเดินเรือที่ผ่านการตรวจสอบ</p></div>` +
      `<div class="card pd"><h3>ทริปของคุณ</h3><p>${TODAY} · ออกเรือ 06:00</p><div class=fl>A ท่าเรือสัตหีบ<span>จุดเริ่มต้น</span></div><div class=fl>01 ${S[0].name}<span>FSI 86</span></div>` +
      `<div class=fl>02 จุดสำรองใกล้เส้นทาง<span>FSI 79</span></div><div class=fl>เรือที่ใช้<span>เรือเล็ก 8 ม.</span></div><div class=fl>ความเร็วสมมติ<span>25 กม./ชม.</span></div>` +
      `<div class=wn>ยังไม่ตรวจพื้นที่ห้ามและประกาศเตือนภัย ต้องตรวจสอบก่อนนำไปใช้จริง</div><button class=btn onclick="show('sea')">ดูคลื่นลมและระดับน้ำ →</button></div></div>` +
      `<div class="g g3"><div class="card pd">ระยะทางรวม ไป-กลับ<b>80 กม.</b>ใช้เป็นฐานคำนวณต้นทุน</div><div class="card pd">เวลาเดินเรือโดยประมาณ<b>3 ชม. 12 นาที</b>ที่ความเร็ว 25 กม./ชม.</div><div class="card pd">น้ำมันก่อนสำรอง<b>฿840</b>28 ลิตร × 30 บาท/ลิตร</div></div>`);
  },

  sea() {
    const days = [...Array(7)].map((_, i) => new Date(Date.now() + i * 864e5).toLocaleDateString('th-TH', { weekday: 'short', day: 'numeric' }));
    const wave = weekForecast ? weekForecast.wave : [0.6, 0.8, 1.1, 1.6, 1.2, 0.8, 0.6];
    const wind = weekForecast ? weekForecast.wind : [12, 16, 22, 32, 24, 18, 12];
    return shell('sea', pageHeader('MARINE FORECAST', 'รู้ทันทะเล ก่อนออกเรือ', 'คลื่น ลม ฝน และระดับน้ำในมุมมองเดียว · สัตหีบ ชลบุรี', 'ดูแผนการเดินเรือ →', 'route') +
      `<div class="g g4"><div class="card pd">ความสูงคลื่น<b>0.6 ม.</b>ช่วงเช้า · ตัวอย่าง</div><div class="card pd">ความเร็วลม<b>12 กม./ชม.</b>ทิศตะวันออกเฉียงเหนือ</div><div class="card pd">โอกาสฝน<b>20%</b>ค่าตัวอย่าง</div><div class="card pd">อุณหภูมิผิวน้ำ<b>28.4 °C</b>ค่าตัวอย่าง</div></div>` +
      `<div class="g g2"><div class="card pd"><h3>คลื่นรายชั่วโมง</h3><svg viewBox="0 0 300 100" style="width:100%"><polyline points="${sparkline([0.5, 0.6, 0.7, 1.1, 0.9, 0.8, 0.6, 0.5], 1.6)}" fill=none stroke=#5eead4 stroke-width=2 /></svg><p>ตัวอย่างแนวโน้ม · ความสูงคลื่นเป็นเมตร</p></div>` +
      `<div class="card pd"><h3>น้ำขึ้น–น้ำลง</h3><svg viewBox="0 0 300 100" style="width:100%"><polyline points="${sparkline([1.2, 0.9, 0.5, 1, 1.8, 2.1, 1.5, 0.8], 2.5)}" fill=none stroke=#7fb6e8 stroke-width=2 /></svg><div class=fl>น้ำขึ้น<span>14:20 · 2.1 ม.</span></div><div class=fl>น้ำลง<span>08:10 · 0.4 ม.</span></div></div></div>` +
      `<div class="card pd"><h3>วางแผนล่วงหน้า 7 วัน</h3><div class="g g7">${days.map((t, i) => { const s = seaStatus(wave[i], wind[i]); return `<div class=card style="padding:10px">${t}<b style="font-size:18px">${wave[i]} ม.</b>ลม ${wind[i]} กม./ชม.<br><span style="color:${s[1]}">${s[0]}</span></div>`; }).join('')}</div>` +
      `<p>${weekForecast ? 'ค่าคลื่น/ลม 7 วันจาก Open-Meteo (ข้อมูลจริง ฟรีเฉพาะไม่ใช่เชิงพาณิชย์) · ' : 'ตัวอย่าง · '}ไม่ใช่ประกาศทางการ โปรดติดตามประกาศจากหน่วยงานทางการก่อนออกเรือ</p></div>`);
  },

  fuel() {
    const m = fuelInputs;
    return shell('fuel', pageHeader('FUEL & COST', 'คำนวณก่อนออก คุ้มกว่าที่คิด', 'ประเมินน้ำมันและงบประมาณตามเรือของคุณ · ทริปสัตหีบ', 'กลับไปดูเส้นทาง →', 'route') +
      `<div class="g g2"><div class="card pd"><h3>ตั้งค่าสำหรับทริปนี้</h3><p>ปรับตามเรือและราคาน้ำมันในพื้นที่ของคุณ</p><div class=fl>เรือของฉัน<select><option>เรือเล็ก 8 เมตร</option></select></div>` +
      `<div class=fl>ระยะทางรวม ไป-กลับ (กิโลเมตร)<input type=number inputmode=decimal value=${m.km} oninput="M.km=+this.value||0;fu()"></div>` +
      `<div class=fl>อัตราสิ้นเปลือง (ลิตร/กิโลเมตร)<input type=number inputmode=decimal step=.01 value=${m.rate} oninput="M.rate=+this.value||0;fu()"></div>` +
      `<div class=fl>ราคาน้ำมันสมมติ (บาท/ลิตร)<input type=number inputmode=decimal value=${m.price} oninput="M.price=+this.value||0;fu()"></div>` +
      `<div class=fl>น้ำมันสำรอง (เปอร์เซ็นต์)<input type=number inputmode=numeric value=${m.res} oninput="M.res=+this.value||0;fu()"></div></div><div class="card pd" id=fr style="border-color:#1f6a4b"></div></div>` +
      `<div class="g g2" style="grid-template-columns:1fr 1fr"><div class="card pd"><h3>อะไรทำให้ใช้น้ำมันเพิ่ม?</h3>คลื่น ลม น้ำหนักบรรทุก และสภาพเครื่องยนต์อาจทำให้ใช้น้ำมันมากกว่าที่คำนวณ</div><div class="card pd"><h3>ก่อนออกเรือทุกครั้ง</h3>ตรวจปริมาณน้ำมันจริง สภาพอากาศ และระยะกลับฝั่ง ตัวเลขนี้เป็นเพียงตัวอย่างประกอบการวางแผน</div></div>`);
  },

  log() {
    // DEMO DATA: sample trips, not the user's records (the form below does not save anything).
    const rows = [['23 พ.ย. 69', 'สัตหีบ · ปลาทู', 18], ['21 พ.ย. 69', 'สัตหีบ · ปลาหลัง', 26], ['19 พ.ย. 69', 'บางเสร่ · ปลาทู', 32], ['17 พ.ย. 69', 'สัตหีบ · ปลาทู', 24], ['15 พ.ย. 69', 'บางเสร่ · ปลาโอ', 30], ['12 พ.ย. 69', 'บางเสร่ · ปลาทู', 26]];
    const kg = rows.reduce((a, r) => a + r[2], 0), fuelCost = rows.length * 840;
    return shell('log', pageHeader('YOUR CATCH JOURNAL', 'ทุกทริป คือข้อมูลที่มีค่า', 'เก็บน้ำหนักปลา ปริมาณ และต้นทุนไว้กับตัวเอง · ข้อมูลของคุณเป็นส่วนตัว', 'ดูแบบฟอร์มทริปตัวอย่าง', 'log') +
      `<div class="g g4"><div class="card pd">ทริปเดือนนี้<b>${rows.length} ทริป</b>ตัวอย่างข้อมูลสมมติ</div><div class="card pd">น้ำหนักรวม<b>${kg} กก.</b>เฉลี่ย ${Math.round(kg / rows.length)} กก./ทริป</div>` +
      `<div class="card pd">ค่าน้ำมันรวม<b>฿ ${fm(fuelCost)}</b>ก่อนรวมค่าใช้จ่ายอื่น</div><div class="card pd">น้ำมันต่อกก. ที่จับ<b>฿ ${f1(fuelCost / kg).replace(/\.(\d)$/, '.$10')}/กก.</b>${fm(fuelCost)} ÷ ${kg}</div></div>` +
      `<div class="g g2"><div class="card pd"><h3>บันทึกการออกเรือ</h3><table><tr><th>วันที่ออกเรือ<th>พื้นที่ / ชนิดปลา<th>น้ำหนัก<th>น้ำมัน<th>สถานะ</tr>${rows.map(r => `<tr><td>${r[0]}<td>${r[1]}<td>${r[2]} กก.<td>฿840<td class=ok>บันทึกแล้ว`).join('')}</table><p>ข้อมูลตัวอย่าง 6 รายการ · จุดส่วนตัวไม่แสดงบนแผนที่สาธารณะ</p></div>` +
      `<div class="card pd"><h3>บันทึกทริปใหม่</h3><p style="color:#f5c451">ตัวอย่างแบบฟอร์ม</p><div class=fl>วันที่ออกเรือ<span>${TODAY}</span></div><div class=fl>พื้นที่<span>นอกชายฝั่งสัตหีบ</span></div><div class=fl>ชนิดปลา<span>ปลาทู</span></div><div class=fl>ปริมาณที่จับได้<span>18 กก.</span></div><div class=fl>ค่าน้ำมันจริง<span>840 บาท</span></div>` +
      `<button class=btn onclick="show('fish')">เพิ่มภาพปลา / จำแนกชนิด ↗</button><p style="color:#f5c451;margin-top:8px">ต้นแบบนี้ไม่เก็บข้อมูลจริง</p></div></div>`);
  },

  fish() {
    return shell('fish', pageHeader('FISH ID STUDIO', 'รู้จักปลาที่คุณจับได้', 'ตัวอย่างขั้นตอนจำแนกปลาและยืนยันผลก่อนบันทึก', 'บันทึกผลในสมุดการจับ →', 'log') +
      `<div class="g g2"><div class="card pd"><h3>ภาพตัวอย่างของคุณ</h3><div class=tm style="height:300px;display:grid;place-items:center">ภาพตัวอย่าง (ยังไม่มีรูปในต้นแบบ)</div><p style="margin-top:8px">ยังไม่รองรับการอัปโหลดจริงในต้นแบบนี้</p></div>` +
      `<div class="card pd"><p style="color:#f5c451">ผลตัวอย่าง · ยังไม่ได้วิเคราะห์ด้วย AI จริง</p><h1 class=vt>ปลาทู</h1><p><i>Rastrelliger brachysoma</i></p>` +
      `<div class=wn style="color:var(--ac);border-color:#1f6a4b;background:#0f2e2c"><b style="font-size:12px;color:var(--ac)">รอคุณยืนยันชนิดปลา</b>ตรวจสอบก่อนบันทึกในสมุดการจับ</div>` +
      `<h3>สิ่งที่ควรถ่ายให้เห็น</h3><div class=fl>01 ลำตัวเต็มตัวและครบริม</div><div class=fl>02 ด้านข้างในแสงธรรมชาติ</div><div class=fl>03 วัตถุเทียบขนาดอยู่ข้างปลา</div><button class=btn onclick="show('log')">ยืนยันปลาและไปหน้าบันทึก →</button></div></div>` +
      `<div class="g g3"><div class="card pd"><h3>ถ่ายให้ชัด</h3>ใช้ภาพปลาเดี่ยว ไม่ทับซ้อน หลีกเลี่ยงเงาและแสงสะท้อนจากพื้น</div><div class="card pd"><h3>AI เป็นผู้ช่วย ไม่ใช่ตัวตัดสิน</h3>ควรให้ผู้รู้ชนิดปลายืนยันก่อนบันทึกทุกครั้ง</div><div class="card pd"><h3>เชื่อมต่อสมุดบันทึก</h3>ผลที่ยืนยันแล้วเข้าสมุดการจับของคุณเท่านั้น</div></div>`);
  },

  data() {
    const rows = [['ภาพพื้นหลัง', 'Esri World Imagery', 'ภาพอ้างอิง'], ['ภาพโลก', 'NASA Blue Marble', 'ภาพอ้างอิง'], ['อุณหภูมิผิวน้ำ', 'NOAA ERDDAP · MUR SST', statusLabel('sst')],
      ['คลอโรฟิลล์-เอ', 'NOAA ERDDAP · VIIRS', statusLabel('chl')], ['ความลึกทะเล', 'NOAA ETOPO 2022 (แทน GEBCO)', statusLabel('depth')], ['คลื่น ลม (7 วัน)', 'Open-Meteo', statusLabel('wx')],
      ['ข้างขึ้น-ข้างแรม', 'คำนวณในเครื่อง', 'เชื่อมแล้ว'], ['ประกาศและพยากรณ์', 'หน่วยงานอุตุนิยมวิทยา', 'ยังไม่เชื่อม']];
    return shell('data', pageHeader('SATELLITE EXPLORER', 'มองทะเล ผ่านสายตาดาวเทียม', 'ดูแหล่งภาพ ชั้นข้อมูล และสิ่งที่พร้อมใช้งานจริง', 'กลับสู่แผนที่ ↗', 'survey') +
      `<div class="g g2"><div class="card pd"><h3>อ่าวไทยตอนบน</h3>${tileMap(100.9, 13, 8, 330, [], 0)}<p style="margin-top:8px">Esri, Maxar, Earthstar Geographics · ภาพถ่ายตามช่วงเวลา ไม่ใช่ภาพสด</p><button class=btn style="width:auto" onclick="show('survey')">เปิดภาพบนแผนที่ ↗</button></div>` +
      `<div class="card pd"><h3>สถานะแหล่งข้อมูล</h3><p>สิ่งที่มีอยู่ กับสิ่งที่ยังต้องเชื่อมต่อ</p>${rows.map(a => `<div class=fl>${a[0]}<span style="color:var(--mu)">${a[1]}</span><span class="${/ภาพอ้างอิง|เชื่อมแล้ว/.test(a[2]) ? 'ok' : ''}" style="color:${/ภาพอ้างอิง|เชื่อมแล้ว/.test(a[2]) ? '' : '#f5c451'}">${a[2]}</span></div>`).join('')}` +
      `<div class=wn>ภาพพื้นหลังเป็นภาพจริง แต่ความหมายสีของ FSI และพยากรณ์เป็นข้อมูลตัวอย่าง</div></div></div>` +
      `<h3 style="margin:8px 0">จากอวกาศ สู่การตัดสินใจที่เข้าใจง่าย</h3><div class="g g4">${[['รับข้อมูลดาวเทียม', 'อุณหภูมิ คลอโรฟิลล์ ความลึก และสถานะผิวทะเล'], ['ประเมินด้วย AI', 'รวมหลายปัจจัยเป็น FSI พร้อมระดับความเชื่อมั่น'], ['แสดงแผนที่เป้าหมาย', 'จำแนกพื้นที่ที่เหมาะ โดยให้เห็นระยะและความเสี่ยง'], ['เรียนรู้จากผลจับ', 'ใช้ข้อมูลรวมกลุ่มเพื่อปรับปรุงรายพื้นที่']].map((a, i) => `<div class="card pd"><span class=eb>0${i + 1}</span><h3>${a[0]}</h3>${a[1]}</div>`).join('')}</div>`);
  },

  go() {
    const wave = weekForecast ? weekForecast.wave[0] : 0.6, wind = weekForecast ? weekForecast.wind[0] : 12;
    const s = seaStatus(wave, wind), red = s[0] === 'ไม่ควรออก', f = fuelEstimate();
    const head = red ? 'ไม่ควรออก' : s[0] === 'ปกติ' ? 'ทะเลปกติ' : 'ระวัง';
    const spoken = red ? 'วันนี้ไม่ควรออกเรือ คลื่นหรือลมแรงเกินเกณฑ์เรือเล็ก'
      : `ทะเล${s[0] === 'ปกติ' ? 'ปกติ' : 'ต้องระวัง'} คลื่น ${wave} เมตร ลม ${wind} กิโลเมตรต่อชั่วโมง ค่าน้ำมันประมาณ ${fm(f.totalCost)} บาท ยังประมาณกำไรไม่ได้`;
    return shell('go', pageHeader('GO / NO-GO', 'วันนี้ออกเรือไหม', 'ตอบสั้น ๆ ก่อนดูแผนที่ · ความปลอดภัยมาก่อนเสมอ', 'ดูจุดปลาบนแผนที่ →', 'survey') +
      `<div class="card pd" style="border-color:${s[1]};text-align:center;padding:26px"><div style="font-size:44px;font-weight:700;color:${s[1]}">${head}</div><p style="font-size:14px;margin-top:6px">คลื่น ${wave} ม. · ลม ${wind} กม./ชม. · ${weekForecast ? 'ข้อมูลจริง Open-Meteo' : 'ค่าตัวอย่าง'}</p></div>` +
      `${red ? '' : `<div class="g g3" style="margin-top:12px"><div class="card pd">ระยะไป-กลับ<b>${fuelInputs.km} กม.</b></div><div class="card pd">ค่าน้ำมันโดยประมาณ<b>฿${fm(f.totalCost)}</b></div><div class="card pd">กำไรที่คาด<b style="font-size:16px">ยังประมาณไม่ได้</b>พื้นที่นี้อยู่ขั้น “ทดลอง”</div></div>`}` +
      `${s[0] === 'ระวัง' ? '<div class=wn>ทะเลอยู่ระดับระวัง ผลดีที่สุดได้แค่ “ลุ้น” ตรวจประกาศเตือนภัยก่อนออกเรือ</div>' : ''}` +
      `<div class="card pd" style="margin-top:12px">ดวงจันทร์วันนี้<b style="font-size:16px">${moonText()}</b></div>` +
      `<button class=btn style="margin-top:12px;font-size:16px" onclick="say(this.dataset.t)" data-t="${spoken}">🔊 ฟังคำแนะนำ</button>` +
      `<div class=wn>จุดแนะนำเป็นการประมาณจากดาวเทียม ไม่ใช่เส้นเขตแดนทางกฎหมาย และไม่แทนประกาศของหน่วยงานรัฐ</div>`);
  },

  price() {
    const reports = loadList('pr');
    return shell('price', pageHeader('FISH PRICE', 'ราคาปลาที่ท่าวันนี้', 'ผู้ใช้ช่วยกันรายงานราคาขายจริง', 'ไปสมุดบันทึก →', 'log') +
      `<div class="card pd"><h3>ราคากลางรายท่า</h3><p>ยังไม่มีราคาที่ยืนยัน · ต้องมีอย่างน้อย 3 รายงานจาก 2 คน ภายใน 48 ชม. (ยังไม่มีเซิร์ฟเวอร์รวมรายงาน)</p></div>` +
      `<div class="card pd" style="margin-top:12px"><h3>รายงานราคาของฉัน (เก็บในเครื่องนี้)</h3><div class=fl>ชนิด<select id=pk><option>ปลาทู<option>ปลาหมึก<option>ปลากะพง<option>ปูม้า</select></div>` +
      `<div class=fl>ราคา (บาท/กก.)<input id=pv2 type=number inputmode=decimal></div><div class=fl>ท่า / ตลาด<input id=pp placeholder="เช่น ท่าเรือสัตหีบ"></div><button class=btn onclick="addPr()">บันทึกราคา</button>` +
      `<table>${reports.map(r => `<tr><td>${r[0]}<td>${r[1]} บาท/กก.<td>${r[2]}<td>${r[3]}`).join('')}</table></div>`);
  },

  bloom() {
    return shell('bloom', pageHeader('BLOOM ALERT', 'เตือนแพลงก์ตอนบลูมและน้ำเสีย', 'ให้ชาวประมงและฟาร์มชายฝั่งรู้ก่อนน้ำเสียหนัก', 'ดูข้อมูลดาวเทียม →', 'data') +
      `<div class="card pd" style="border-color:#f5c451"><h3>สถานะวันนี้: ยังไม่มีข้อมูลเตือน</h3><p>ยังไม่ได้เชื่อมข้อมูลคลอโรฟิลล์ จึงยังประเมินบลูมไม่ได้ — ไม่ได้แปลว่าน้ำปลอดภัย</p></div>` +
      `<div class="g g3" style="margin-top:12px">${[['เฝ้าระวัง', 'R ≥ 2 ติดกัน 2 วัน หรือมีรายงาน 1 ราย', 'ฟาร์มในรัศมี 10 กม.'], ['เตือน', 'R ≥ 4 และพื้นที่ขยาย หรือรายงาน ≥ 3 ราย', 'ฟาร์มและชาวประมงในพื้นที่'], ['วิกฤต', 'ปลาตายหลายราย หรือหน่วยงานรัฐประกาศ', 'ทุกคนในพื้นที่']].map((a, i) => `<div class="card pd" style="border-color:${['#f5c451', '#ff9f5a', '#ff8a8a'][i]}"><h3>${a[0]}</h3>${a[1]}<br><span style="color:var(--tx)">ส่งให้: ${a[2]}</span></div>`).join('')}</div>` +
      `<div class=wn>ดาวเทียมบอกไม่ได้ว่าแพลงก์ตอนมีสารพิษหรือไม่ และบอกไม่ได้ว่าหอยหรือสัตว์น้ำปลอดภัยต่อการกิน ต้องอ้างประกาศหน่วยงานรัฐเท่านั้น · เกณฑ์เป็นค่าตั้งต้นจากคู่มือ ต้องปรับกับเหตุการณ์จริง</div>` +
      `<button class=btn onclick="show('pins')">เห็นน้ำผิดปกติ? บันทึกตำแหน่ง →</button>`);
  },

  pins() {
    const pins = loadList('pins');
    return shell('pins', pageHeader('MY SPOTS', 'จุดของฉัน', 'จุดปลาลับเก็บเฉพาะในเครื่องนี้ ไม่แสดงให้ผู้ใช้อื่น', 'ไปสมุดบันทึก →', 'log') +
      `<div class="card pd"><div class=fl>ชื่อจุด<input id=pn placeholder="เช่น แหล่งปลาทู"></div><button class=btn onclick="addPin()">📍 บันทึกตำแหน่งปัจจุบัน</button><p id=pm></p>` +
      `<table>${pins.map((r, i) => `<tr><td>${r[0]}<td>${r[1]}, ${r[2]}<td>${r[3]}<td><button class=bd onclick="delPin(${i})" style="color:#ff8a8a;background:none;padding:10px">ลบ</button>`).join('')}</table></div>`);
  },

  sos() {
    return shell('sos', pageHeader('SOS', 'ปุ่ม SOS', 'ขอตำแหน่งล่าสุดและคัดลอกพิกัดเพื่อส่งต่อ', 'วันนี้ออกไหม →', 'go') +
      `<div class=wn style="font-size:13px"><b>ปุ่มนี้ไม่แทนวิทยุสื่อสารหรืออุปกรณ์กู้ภัยทางทะเล</b> ใช้ได้เมื่อมีสัญญาณมือถือเท่านั้น ซึ่งมักหายเมื่ออยู่ห่างฝั่ง · ตอนนี้ยังไม่ส่งข้อความหาใครให้อัตโนมัติ ทำได้แค่คัดลอกพิกัด</div>` +
      `<button class=btn style="background:#ff6b6b;font-size:20px;padding:22px" onclick="doSos()">🆘 ขอตำแหน่งและคัดลอกพิกัด</button><p id=sm class=vs style="margin-top:12px"></p>` +
      `<div class="card pd"><h3>เบอร์กู้ภัยทางทะเล</h3>${SOS_NUMBERS.th || 'ยังไม่ได้ตั้งค่า — ต้องใส่เบอร์จากหน่วยงานทางการของประเทศนั้นก่อนใช้จริง'}</div>`);
  },
};
