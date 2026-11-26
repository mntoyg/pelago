// Building blocks shared by the full-screen workspace views: sidebar shell, page header, static satellite map.
import { DEG } from '../utils.js';
import { ESRI_IMAGERY_TILE_URL } from '../config.js';

// Workspace screens in sidebar order: [view key, label]. Keys match the view renderers in views.js.
const WORKSPACE_TABS = [
  ['survey', 'สำรวจแหล่งปลา'],
  ['route', 'วางแผนเส้นทาง'],
  ['sea', 'สภาพทะเลและระดับน้ำ'],
  ['fuel', 'คำนวณน้ำมัน'],
  ['log', 'สมุดบันทึกการจับ'],
  ['fish', 'จำแนกปลา AI'],
  ['data', 'ศูนย์ข้อมูลดาวเทียม'],
  ['go', 'ออกหรือไม่ออก'],
  ['price', 'ราคาปลาที่ท่า'],
  ['bloom', 'เตือนน้ำเสีย'],
  ['pins', 'จุดของฉัน'],
  ['sos', 'ปุ่ม SOS'],
];

// Wraps a view body in the workspace layout (left navigation + content). `active` is the current view key.
export const shell = (active, body) =>
  `<aside class=ws><div class=st><div class=eb>PELAGO WORKSPACE</div><h2>พร้อมสำหรับทะเล</h2><p>เครื่องมือสำหรับชาวประมง</p><div class="card pd area">พื้นที่ของคุณ<b>สัตหีบ, ชลบุรี</b>ประเทศไทย · เรือเล็ก 8 เมตร</div></div>` +
  `<div class=nv>${WORKSPACE_TABS.map(([key, name], i) => `<button class="${key === active ? 'on' : ''}" onclick="show('${key}')"><i>0${i + 1}</i>${name}</button>`).join('')}</div>` +
  `<div class=sb><div class=wn style="color:var(--ac);border-color:#1f4a45;background:#0f2e2c"><b style="font-size:12px;color:var(--ac)">ข้อมูลของคุณ เป็นของคุณ</b>จุดปักหมุดและบันทึกการจับไม่เปิดเผยต่อผู้ใช้อื่น</div><p style="color:#f5c451">● โหมดต้นแบบ ไม่มีข้อมูลพยากรณ์ระดับจริง</p></div></aside>` +
  `<div class=wb>${body}</div>`;

// Page header with an eyebrow, title, subtitle and one action button that opens another view.
export const pageHeader = (eyebrow, title, subtitle, buttonLabel, targetView) =>
  `<div class=hd><div><div class=eb>${eyebrow}</div><h1 class=vt>${title}</h1><p class=vs>${subtitle}</p></div><button class=btn onclick="show('${targetView}')">${buttonLabel}</button></div>`;

// Static satellite map made of Esri tiles (no canvas). `points` = [[lon, lat, label], ...]; `showLine` joins them.
export function tileMap(lon, lat, z, height, points, showLine) {
  const n = 2 ** z;
  const mercatorY = a => (1 - Math.log(Math.tan(Math.PI / 4 + a * DEG / 2)) / Math.PI) / 2 * n;
  const fx = (lon + 180) / 360 * n, fy = mercatorY(lat);
  const tx = Math.floor(fx), ty = Math.floor(fy);
  const toPx = p => [((p[0] + 180) / 360 * n - fx) * 256, (mercatorY(p[1]) - fy) * 256];   // offset from map centre
  let tiles = '';
  for (let j = -3; j <= 3; j++) {
    for (let i = -4; i <= 4; i++) {
      tiles += `<img alt="" loading=lazy src="${ESRI_IMAGERY_TILE_URL.replace('{z}', z).replace('{y}', ty + j).replace('{x}', tx + i)}" style="width:256px;height:256px;left:calc(50% + ${(tx + i - fx) * 256}px);top:calc(50% + ${(ty + j - fy) * 256}px)">`;
    }
  }
  const px = points.map(toPx);
  const line = showLine
    ? `<svg width=1 height=1 style="overflow:visible;position:absolute"><polyline points="${px.map(a => a.join(',')).join(' ')}" fill=none stroke=#5eead4 stroke-width=3 stroke-dasharray="8 6"/></svg>`
    : '';
  const pins = px.map((a, i) => `<span class=pin style="left:${a[0]}px;top:${a[1]}px">${points[i][2]}</span>`).join('');
  return `<div class=tm style="height:${height}px">${tiles}<div style="position:absolute;left:50%;top:50%">${line}${pins}</div></div>`;
}
