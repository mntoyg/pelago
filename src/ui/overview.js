// Static overlays on the map: today's date chip and the (sample) time-of-day strip.
import { $ } from '../utils.js';

export function renderOverview() {
  $('#date').innerHTML = new Date().toLocaleDateString('th-TH-u-ca-buddhist', { day: 'numeric', month: 'short', year: 'numeric' }) + '<em>ข้อมูลล่าสุด</em>';
  $('#tl').innerHTML = '<b>วันนี้</b>' +
    ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00']
      .map((t, i) => `<button class="${i == 2 ? 'on' : ''}" onclick="this.parentNode.querySelectorAll('button').forEach(b=>b.classList.remove('on'));this.classList.add('on')">${t}</button>`)
      .join('') +
    '<s>ตัวอย่าง · ไม่ใช่ข้อมูลจริง</s>';
}
