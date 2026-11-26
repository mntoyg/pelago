// DEMO DATA: FSI values and spot coordinates are illustrative placeholders, not model output. [lon, lat]
// DEMO spots: placeholder sea coordinates, not model output.
//
// Shape: COUNTRIES[code] -> { name, label, center, span, waters, provinces[] }
//   province -> { name, area, spots[] }
//   spot     -> { name, coord: [lon, lat], fsi, demoMetrics? }
// demoMetrics = [sea surface temp (°C), chlorophyll-a (mg/m³), depth (m), distance from port (nm)],
// used only until live NOAA data arrives (see services/marine-data.js).
// Runtime fields added later by marine-data.js: spot.signalPromise, spot.signal.
//
// To plug in real data later, replace this file (or fill COUNTRIES from an API) and keep this shape.

export const COUNTRIES = {
  th: {
    name: 'ประเทศไทย', label: 'THAILAND · LINE', center: [101, 13], span: 13, waters: 'อ่าวไทย',
    provinces: [
      {
        name: 'ชลบุรี', area: 'อ่าวไทยตอนบน',
        spots: [
          { name: 'นอกชายฝั่งสัตหีบ', coord: [100.924, 12.306], fsi: 86, demoMetrics: [28.4, 0.82, 32, 40] },
          { name: 'อ่าวบางเสร่', coord: [100.99, 12.78], fsi: 79 },
          { name: 'นอกชายฝั่งศรีราชา', coord: [100.88, 13.05], fsi: 72 },
        ],
      },
      {
        name: 'ระยอง', area: 'อ่าวไทยตอนกลาง',
        spots: [
          { name: 'นอกเกาะเสม็ด', coord: [101.6, 12.3], fsi: 81 },
          { name: 'หาดแม่รำพึง', coord: [101.75, 12.62], fsi: 75 },
        ],
      },
      {
        name: 'ภูเก็ต', area: 'ทะเลอันดามัน',
        spots: [
          { name: 'นอกอ่าวฉลอง', coord: [98.3, 7.72], fsi: 74 },
          { name: 'นอกเกาะราชา', coord: [98.4, 7.55], fsi: 70 },
        ],
      },
    ],
  },
  vn: {
    name: 'เวียดนาม', label: 'VIETNAM · ZALO', center: [108, 12], span: 9, waters: 'ทะเลจีนใต้ฝั่งตะวันตก',
    provinces: [
      {
        name: 'ข่านห์ฮหว่า', area: 'ชายฝั่งภาคกลาง',
        spots: [
          { name: 'นอกอ่าวกามรานห์', coord: [109.4, 11.9], fsi: 82 },
          { name: 'นอกเมืองญาจาง', coord: [109.5, 12.4], fsi: 76 },
        ],
      },
      {
        name: 'บาเรีย-หวุงเต่า', area: 'ชายฝั่งภาคใต้',
        spots: [
          { name: 'นอกแหลมหวุงเต่า', coord: [107.4, 10], fsi: 79 },
          { name: 'ปากแม่น้ำไซง่อน', coord: [107.6, 9.6], fsi: 73 },
        ],
      },
    ],
  },
  id: {
    name: 'อินโดนีเซีย', label: 'INDONESIA · WHATSAPP', center: [108, -3], span: 30, waters: 'ช่องแคบมะละกา',
    provinces: [
      {
        name: 'สุมาตราเหนือ', area: 'ช่องแคบมะละกา',
        spots: [
          { name: 'นอกชายฝั่งเมดาน', coord: [99.8, 3.6], fsi: 80 },
          { name: 'ใต้เกาะปีนัง', coord: [100.6, 2.8], fsi: 74 },
        ],
      },
      {
        name: 'ชวาตะวันออก', area: 'ทะเลชวา',
        spots: [
          { name: 'ทะเลชวาตอนเหนือ', coord: [113, -6.6], fsi: 77 },
          { name: 'ช่องแคบบาหลี', coord: [114.5, -8.3], fsi: 72 },
        ],
      },
    ],
  },
  my: {
    name: 'มาเลเซีย', label: 'MALAYSIA · WHATSAPP', center: [103, 4.5], span: 10, waters: 'ช่องแคบมะละกา',
    provinces: [
      {
        name: 'ปีนัง', area: 'ช่องแคบมะละกา',
        spots: [
          { name: 'นอกเกาะปีนัง', coord: [100.15, 5.45], fsi: 78 },
          { name: 'ช่องแคบตอนเหนือ', coord: [100, 5.9], fsi: 72 },
        ],
      },
      {
        name: 'ตรังกานู', area: 'ทะเลจีนใต้',
        spots: [
          { name: 'นอกชายฝั่งตรังกานู', coord: [103.9, 5.5], fsi: 80 },
          { name: 'นอกเกาะเรดัง', coord: [103.2, 5.9], fsi: 74 },
        ],
      },
    ],
  },
  ph: {
    name: 'ฟิลิปปินส์', label: 'PHILIPPINES · MESSENGER', center: [121, 12], span: 12, waters: 'ทะเลฟิลิปปินส์',
    provinces: [
      {
        name: 'ปาลาวัน', area: 'ทะเลจีนใต้ฝั่งตะวันตก',
        spots: [
          { name: 'นอกชายฝั่งปาลาวัน', coord: [118, 10], fsi: 79 },
          { name: 'ทางใต้ปาลาวัน', coord: [117.6, 9.2], fsi: 73 },
        ],
      },
      {
        name: 'อ่าวมะนิลา', area: 'ลูซอน',
        spots: [
          { name: 'ปากอ่าวมะนิลา', coord: [120.8, 14.4], fsi: 76 },
          { name: 'นอกบาตาอัน', coord: [120.4, 14.2], fsi: 71 },
        ],
      },
    ],
  },
  kh: {
    name: 'กัมพูชา', label: 'CAMBODIA · TELEGRAM', center: [103.6, 10.8], span: 5, waters: 'อ่าวไทย',
    provinces: [
      {
        name: 'สีหนุวิลล์', area: 'อ่าวไทยฝั่งกัมพูชา',
        spots: [
          { name: 'นอกสีหนุวิลล์', coord: [103.3, 10.4], fsi: 77 },
          { name: 'ใกล้เกาะรง', coord: [103.1, 10.6], fsi: 71 },
        ],
      },
      {
        name: 'แกบ', area: 'อ่าวไทยตอนใต้',
        spots: [
          { name: 'นอกชายฝั่งแกบ', coord: [104.1, 10.2], fsi: 75 },
        ],
      },
    ],
  },
  mm: {
    name: 'เมียนมา', label: 'MYANMAR · VIBER', center: [96.5, 16], span: 9, waters: 'อ่าวเมาตะมะ',
    provinces: [
      {
        name: 'ย่างกุ้ง', area: 'อ่าวเมาตะมะ',
        spots: [
          { name: 'ปากอ่าวเมาตะมะ', coord: [96.8, 15.8], fsi: 74 },
          { name: 'นอกปากแม่น้ำ', coord: [96.2, 15.9], fsi: 70 },
        ],
      },
      {
        name: 'ทวาย', area: 'ทะเลอันดามัน',
        spots: [
          { name: 'นอกชายฝั่งทวาย', coord: [97.9, 14], fsi: 77 },
        ],
      },
    ],
  },
  in: {
    name: 'อินเดีย', label: 'INDIA · WHATSAPP', center: [79, 12], span: 18, waters: 'อ่าวเบงกอล',
    provinces: [
      {
        name: 'ทมิลนาดู', area: 'อ่าวเบงกอล',
        spots: [
          { name: 'นอกชายฝั่งเจนนไน', coord: [80.5, 13], fsi: 81 },
          { name: 'ทางใต้เจนนไน', coord: [80.4, 12.2], fsi: 75 },
        ],
      },
      {
        name: 'เกรละ', area: 'ทะเลอารเบีย',
        spots: [
          { name: 'นอกชายฝั่งโคชิ', coord: [75.8, 9.9], fsi: 79 },
          { name: 'ทางเหนือโคชิ', coord: [75.6, 10.6], fsi: 73 },
        ],
      },
    ],
  },
  lk: {
    name: 'ศรีลังกา', label: 'SRI LANKA · WHATSAPP', center: [80.7, 7.8], span: 4, waters: 'มหาสมุทรอินเดีย',
    provinces: [
      {
        name: 'โคลัมโบ', area: 'ชายฝั่งตะวันตก',
        spots: [
          { name: 'นอกชายฝั่งโคลัมโบ', coord: [79.6, 6.9], fsi: 77 },
          { name: 'ทางใต้โคลัมโบ', coord: [79.7, 6.3], fsi: 72 },
        ],
      },
      {
        name: 'ตรินโกมาลี', area: 'ชายฝั่งตะวันออก',
        spots: [
          { name: 'นอกอ่าวตรินโกมาลี', coord: [81.4, 8.7], fsi: 78 },
        ],
      },
    ],
  },
  bd: {
    name: 'บังคลาเทศ', label: 'BANGLADESH · WHATSAPP', center: [90.8, 21.5], span: 6, waters: 'อ่าวเบงกอล',
    provinces: [
      {
        name: 'คอกซ์บาซาร์', area: 'อ่าวเบงกอลตอนใต้',
        spots: [
          { name: 'นอกชายฝั่งคอกซ์บาซาร์', coord: [91.6, 21.2], fsi: 76 },
        ],
      },
      {
        name: 'บาริซาล', area: 'ปากแม่น้ำคงคา',
        spots: [
          { name: 'นอกปากแม่น้ำ', coord: [90.6, 21.6], fsi: 73 },
        ],
      },
    ],
  },
  jp: {
    name: 'ญี่ปุ่น', label: 'JAPAN · LINE', center: [138, 36], span: 14, waters: 'แปซิฟิกตะวันตก',
    provinces: [
      {
        name: 'ชิซูโอกะ', area: 'ชายฝั่งแปซิฟิก',
        spots: [
          { name: 'นอกชายฝั่งชิซูโอกะ', coord: [138.4, 34.5], fsi: 82 },
          { name: 'อ่าวซูรุงะ', coord: [138.6, 34.7], fsi: 76 },
        ],
      },
      {
        name: 'ฮอกไกโด', area: 'ชายฝั่งใต้',
        spots: [
          { name: 'นอกชายฝั่งฮอกไกโด', coord: [143, 41.6], fsi: 78 },
        ],
      },
    ],
  },
  tw: {
    name: 'ไต้หวัน', label: 'TAIWAN · LINE', center: [121, 23.5], span: 5, waters: 'แปซิฟิกตะวันตก',
    provinces: [
      {
        name: 'ไถตง', area: 'ชายฝั่งตะวันออก',
        spots: [
          { name: 'นอกชายฝั่งไถตง', coord: [121.6, 22.7], fsi: 79 },
        ],
      },
      {
        name: 'ผิงตง', area: 'ชายฝั่งใต้',
        spots: [
          { name: 'นอกชายฝั่งผิงตง', coord: [120.2, 22.3], fsi: 74 },
        ],
      },
    ],
  },
};

// Flat list of every spot with its position in the tree, in COUNTRIES order.
// Each entry: { countryKey, provinceIndex, spotIndex, spot }
export const ALL_SPOTS = [];
for (const countryKey of Object.keys(COUNTRIES)) {
  COUNTRIES[countryKey].provinces.forEach((province, provinceIndex) => {
    province.spots.forEach((spot, spotIndex) => ALL_SPOTS.push({ countryKey, provinceIndex, spotIndex, spot }));
  });
}

// Entry with the highest FSI from a list of ALL_SPOTS-style entries (ties keep the first).
export const bestSpot = entries => entries.slice().sort((a, b) => b.spot.fsi - a.spot.fsi)[0];
