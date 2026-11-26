// Connection status of each live data source: 0 = waiting, 1 = connected, -1 = could not connect.
// Shown on the "satellite data" screen.
export const sourceStatus = { sst: 0, chl: 0, depth: 0, wx: 0 };

// Thai label for a source's status.
export const statusLabel = key =>
  sourceStatus[key] === 1 ? 'เชื่อมแล้ว' : sourceStatus[key] === -1 ? 'เชื่อมไม่ได้' : 'รอข้อมูล';
