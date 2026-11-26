// Static map geometry for the globe. All coordinates are [lon, lat] in degrees.
// Pure data: no DOM access, so it can be imported from anywhere (including Node checks).

// Hand-simplified coastlines (coarse, illustrative). Replace with Natural Earth GeoJSON for production.
// Each polygon is a "lon,lat lon,lat ..." string, parsed and densified below.
const LAND_SOURCE = [
  // Asian mainland + Indian subcontinent + Siberia (one coarse outline)
  '30,45 36,41 30,36 36,36 35,33 35,29 39,22 43,13 52,16 59.5,22.5 56.5,26 51,24.5 50,26.5 48,30 56.5,27 61,25 66.5,25 68,23.5 72.5,21 73,16 76,9 77.5,8 80,10 80,15.5 84,19 87,21.5 89,22 91,22.5 92.5,20.5 94.5,16 97.5,16.5 98,13 98.5,8 100,6.5 101,3 103.5,1.5 104.2,1.5 103.4,4 102.2,6.3 100.5,7.2 99.8,9.5 99.2,10.5 100,12.5 100.9,13.5 101.5,12.7 102.4,12 103.5,10.6 105,8.8 106.7,9.8 108,11 109.3,12.5 109.2,15 108,16.2 106.5,18.5 105.7,19.6 106.8,20.7 108,21.5 110,21 111.5,21.5 114,22.3 117,23.5 119.5,25.5 121.5,28.5 122,31 120.5,34 119,37 122.5,37 121,38.8 122,40.5 124.5,40 126,37.5 126.5,34.5 129,35.5 129.5,37 129.5,41 132,43 135,43.5 140,48 141,52 136,54 138,56 143,59 150,59.5 156,61 162,62 163,59.5 156,57 156,51 160,53 162,56 164,60 170,60 178,64 180,66 180,69 170,70 160,69.5 150,71 140,72.5 130,71 115,73.5 105,77 95,76 80,73 70,73 68,69 60,69 50,68 40,66 30,60',
  // Hainan
  '108.7,19.2 110,20 111,19.8 110.5,18.5 109.5,18.2',
  // Taiwan
  '120.2,23 121,25.2 121.9,24.5 120.9,22',
  // Honshu + Shikoku
  '130.9,34 133,35.5 136,36 137,37.5 139.5,38.5 140,41 141.5,41.3 141.8,39 140.8,36 139.8,35 137,34.6 135.2,33.6 133,34',
  // Hokkaido
  '140,42 141.5,45.4 145.5,43.5 143,42',
  // Kyushu
  '129.7,33.2 131.8,33.7 131.2,31 130.2,31.2',
  // Sumatra
  '95.3,5.6 98,4 100.5,2 103.8,-1 106,-3 105.8,-5.8 104.5,-5.8 102,-4 100.5,-1.5 98.5,1.5 97,3.5',
  // Java
  '105.2,-6.8 108,-6.3 110.5,-6.9 113,-6.9 114.5,-7.7 114.3,-8.7 110,-8.2 106.5,-7.4',
  // Borneo
  '109,1.5 111,1.8 113,3.2 115,5 117,7 119,5.2 117.7,4 118.5,1 117.5,-0.5 116.5,-3.5 114.5,-4 111.5,-3.3 110,-1.8 109,-0.5',
  // Sulawesi
  '119.5,-5.5 120.5,-2.8 119.8,0.5 121,1.4 124.8,1.7 123,0.5 121.5,-0.8 123,-1.2 122,-4.8 121,-3 120.5,-5.5',
  // Luzon
  '120.5,18.5 122.2,18.5 122.3,16.2 124,13.5 122,13.8 120.6,14.2 120,16',
  // Mindanao
  '122,7 123.5,8.5 125.5,9.8 126.5,7.5 125.5,5.8 124,6.5',
  // Sri Lanka
  '79.8,9.5 81.5,7.5 81.2,6 80,6.2 79.8,8',
];

// Simplified Thailand outline (drawn only when zoomed far in with the satellite layer off).
const THAILAND_SOURCE = '97.8,19.5 99,20.4 100.1,20.3 101.2,19.5 100.5,18 101.2,17.5 102.5,18.2 103.5,18.4 104.5,17.4 105.4,16 105,14.3 103,14.3 102.5,14.2 102.9,12.7 102.3,12.2 101,12.7 100.9,13.4 100,13.4 99.9,12.2 99.2,10.5 99.9,9.5 100.5,7.2 101.4,6.8 102,6.2 101.2,5.8 100.2,6.5 99.5,7.2 98.3,8.3 98.6,10 98.5,12 98.7,13.5 99,15 98.2,16.5 97.6,18';

const parsePolygon = text => text.trim().split(/\s+/).map(pair => pair.split(',').map(Number));

// Horizon-clipped drawing needs short edges, so insert points at most ~3 degrees apart.
// (This fixes spikes/wedges at the globe limb.)
const densify = points => {
  const out = [];
  for (let i = 0; i < points.length; i++) {
    const a = points[i], b = points[(i + 1) % points.length];
    const n = Math.max(1, Math.ceil(Math.max(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])) / 3));
    for (let j = 0; j < n; j++) out.push([a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n]);
  }
  return out;
};

export const LAND_POLYGONS = LAND_SOURCE.map(parsePolygon).map(densify);
export const THAILAND_OUTLINE = densify(parsePolygon(THAILAND_SOURCE));

// Country name labels on the globe: [text, lon, lat]
export const COUNTRY_LABELS = [
  ['CHINA', 104, 34],
  ['INDIA', 78, 22],
  ['JAPAN', 138, 37],
  ['MYANMAR', 96.5, 21],
  ['THAILAND', 101, 16],
  ['VIETNAM', 107, 16],
  ['CAMBODIA', 104.8, 12.6],
  ['INDONESIA', 113, -1],
  ['PHILIPPINES', 122, 12],
  ['MALAYSIA', 102, 4.3],
];

// Sea / ocean name labels on the globe: [text, lon, lat]
export const SEA_LABELS = [
  ['อ่าวไทย', 101.4, 10.2],
  ['ทะเลอันดามัน', 95, 9],
  ['ทะเลจีนใต้', 112, 13],
  ['อ่าวเบงกอล', 88, 14],
  ['มหาสมุทรอินเดีย', 82, -4],
  ['แปซิฟิกตะวันตก', 134, 20],
  ['ช่องแคบมะละกา', 99.5, 3.8],
];

// Deterministic pseudo-random star field: [x 0..1, y 0..1, base alpha, size px]
export const STARS = Array.from({ length: 150 }, (_, i) => {
  const rand = n => { const v = Math.sin(i * 127.1 + n * 311.7) * 43758.5; return v - Math.floor(v); };
  return [rand(1), rand(2), 0.25 + rand(3) * 0.6, rand(4) > 0.9 ? 2 : 1];
});
