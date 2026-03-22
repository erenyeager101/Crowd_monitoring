/* ============================================================
   CrowdSense Dashboard — App.js
   Wires up all backend endpoints and manages the dashboard UI.
   ============================================================ */

'use strict';

// ── Constants ────────────────────────────────────────────────
const PYTHON_API = 'http://localhost:8000';
const REFRESH_INTERVAL = 5000; // ms

const SHOP_NAMES = {
  '18.5204,73.8567': 'Zudio',
  '18.5250,73.8567': 'Phoenix Mall',
  '18.5369,73.8567': 'Kaka Halwai',
  '18.5650,73.8567': 'Shaniwar Peth',
  '18.5850,73.8567': 'Starbucks',
};

function shopName(lat, lng) {
  const key4 = `${parseFloat(lat).toFixed(4)},${parseFloat(lng).toFixed(4)}`;
  const key  = `${lat},${lng}`;
  return SHOP_NAMES[key4] || SHOP_NAMES[key] || `${lat}, ${lng}`;
}

// ── Chart.js defaults ────────────────────────────────────────
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#2e3347';
Chart.defaults.font.family = 'Inter, sans-serif';
Chart.defaults.plugins.legend.display = false;

function lineDataset(label, color) {
  return {
    label,
    data: [],
    borderColor: color,
    backgroundColor: color + '22',
    fill: true,
    tension: 0.35,
    pointRadius: 3,
    pointHoverRadius: 5,
  };
}

function makeChart(id, datasets, yLabel) {
  const ctx = document.getElementById(id);
  if (!ctx) return null;
  return new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      scales: {
        x: { title: { display: false }, ticks: { maxTicksLimit: 8 } },
        y: { beginAtZero: true, title: { display: !!yLabel, text: yLabel || '' } },
      },
      plugins: { legend: { display: datasets.length > 1 } },
    },
  });
}

function pushToChart(chart, label, values) {
  if (!chart) return;
  chart.data.labels.push(label);
  values.forEach((v, i) => chart.data.datasets[i].data.push(v));
  if (chart.data.labels.length > 20) {
    chart.data.labels.shift();
    chart.data.datasets.forEach(d => d.data.shift());
  }
  chart.update('none');
}

// ── Navigation ───────────────────────────────────────────────
const SECTION_TITLES = {
  'overview':  'Overview',
  'live-map':  'Live Map',
  'shops':     'Shops & Locations',
  'analytics': 'Trends & Charts',
  'top-shops': 'Top Locations',
  'heatmap':   'Heatmap Data',
  'history':   'History',
  'health':    'System Health',
};

let currentSection = 'overview';

function navigate(section) {
  document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const sec = document.getElementById('sec-' + section);
  if (sec) sec.classList.add('active');
  const nav = document.querySelector(`.nav-item[data-section="${section}"]`);
  if (nav) nav.classList.add('active');
  document.getElementById('topbarTitle').textContent = SECTION_TITLES[section] || section;
  currentSection = section;
  closeSidebar();
  // Lazy load section data
  if (section === 'shops')     loadShops();
  if (section === 'top-shops') loadTopShops();
  if (section === 'heatmap')   loadHeatmap();
  if (section === 'health')    loadHealth();
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('open');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('open');
}
document.getElementById('sidebarOverlay').addEventListener('click', closeSidebar);

// ── Fetch helpers ────────────────────────────────────────────
async function apiFetch(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
  return response.json();
}

// ── Overview + Map charts (shared) ──────────────────────────
let ovPeakChart, ovAvgChart, ovForecastChart;
let anPeakChart, anAvgChart, anForecastChart;
let recentData = [];
let leafletMap, mapMarkers = {}, mapCircles = {};

function initCharts() {
  ovPeakChart     = makeChart('ovPeakChart',     [lineDataset('Peak', '#4f8ef7')]);
  ovAvgChart      = makeChart('ovAvgChart',      [lineDataset('Avg',  '#22c55e')]);
  ovForecastChart = makeChart('ovForecastChart', [lineDataset('Forecast', '#f59e0b')]);
  anPeakChart     = makeChart('anPeakChart',     [lineDataset('Peak', '#4f8ef7')]);
  anAvgChart      = makeChart('anAvgChart',      [lineDataset('Avg',  '#22c55e')]);
  anForecastChart = makeChart('anForecastChart', [lineDataset('Forecast', '#f59e0b')]);
}

function initMap() {
  leafletMap = L.map('map').setView([18.5204, 73.8567], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(leafletMap);
}

function crowdColor(count) {
  if (count >= 6) return '#ef4444';
  if (count >= 3) return '#f59e0b';
  return '#22c55e';
}

function crowdBadgeClass(count) {
  if (count >= 6) return 'red';
  if (count >= 3) return 'amber';
  return 'green';
}

function crowdLabel(count) {
  if (count >= 6) return 'High';
  if (count >= 3) return 'Moderate';
  return 'Low';
}

function createDivIcon(color) {
  return L.divIcon({
    className: '',
    html: `<div style="width:18px;height:18px;border-radius:50%;background:${color};border:2px solid rgba(255,255,255,0.6);box-shadow:0 0 6px ${color}88"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

function updateMapMarkers(items) {
  // Remove stale circles
  Object.values(mapCircles).forEach(cs => cs.forEach(c => leafletMap.removeLayer(c)));
  mapCircles = {};

  items.forEach(item => {
    const lat = item.coordinates.latitude;
    const lng = item.coordinates.longitude;
    const key = `${lat.toFixed(4)},${lng.toFixed(4)}`;
    const name = shopName(lat, lng);
    const color = crowdColor(item.count);
    const badgeCls = crowdBadgeClass(item.count);
    const lbl = crowdLabel(item.count);

    const popup = `
      <div style="min-width:140px">
        <strong>${name}</strong><br/>
        Crowd: <b>${item.count}</b>
        <span style="margin-left:6px;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600;
          background:${color}22;color:${color}">${lbl}</span><br/>
        <span style="font-size:11px;color:#94a3b8">${lat}, ${lng}</span>
      </div>`;

    if (!mapMarkers[key]) {
      mapMarkers[key] = L.marker([lat, lng], { icon: createDivIcon(color) })
        .addTo(leafletMap)
        .bindPopup(popup);
    } else {
      mapMarkers[key].setIcon(createDivIcon(color));
      mapMarkers[key].setPopupContent(popup);
    }

    const radius = Math.max(40, item.count * 12);
    mapCircles[key] = [
      L.circle([lat, lng], { color, fillColor: color, fillOpacity: 0.18, radius, stroke: false }).addTo(leafletMap),
    ];
  });
}

// ── Main data fetch (crowd data) ─────────────────────────────
async function fetchCrowdData() {
  try {
    const data = await apiFetch('/data');
    const items = data.data || [];

    // KPIs
    let maxC = 0, minC = Infinity, minName = '—', maxName = '—';
    const uniqueLocs = new Set();
    items.forEach(item => {
      const key = `${item.coordinates.latitude.toFixed(4)},${item.coordinates.longitude.toFixed(4)}`;
      uniqueLocs.add(key);
      if (item.count > maxC) { maxC = item.count; maxName = shopName(item.coordinates.latitude, item.coordinates.longitude); }
      if (item.count < minC) { minC = item.count; minName = shopName(item.coordinates.latitude, item.coordinates.longitude); }
    });

    const peak = data.maxCrowd ?? maxC;
    const avg  = parseFloat(data.averageCrowd) || 0;
    const forecast = (peak * 1.1).toFixed(1);
    const now = new Date().toLocaleTimeString();

    // Update KPI cards
    document.getElementById('kpiPeak').textContent      = peak;
    document.getElementById('kpiAvg').textContent       = avg;
    document.getElementById('kpiLocations').textContent = uniqueLocs.size;
    document.getElementById('kpiPreferred').textContent = minC < Infinity ? `${minName} (${minC})` : '—';
    document.getElementById('kpiBusiest').textContent   = maxC > 0        ? `${maxName} (${maxC})`  : '—';

    // Map stats
    document.getElementById('mapPeak').textContent = peak;
    document.getElementById('mapAvg').textContent  = avg;
    document.getElementById('mapBest').textContent = minC < Infinity ? `${minName} (${minC})` : '—';

    // Charts
    pushToChart(ovPeakChart,     now, [peak]);
    pushToChart(ovAvgChart,      now, [avg]);
    pushToChart(ovForecastChart, now, [forecast]);
    pushToChart(anPeakChart,     now, [peak]);
    pushToChart(anAvgChart,      now, [avg]);
    pushToChart(anForecastChart, now, [forecast]);

    // Map markers
    if (leafletMap) updateMapMarkers(items);

    // Recent table
    recentData = items;
    renderRecentTable(items);

    // System badge
    setBadge('ok');
  } catch (err) {
    console.error('fetchCrowdData error:', err);
    setBadge('error');
  }
}

function setBadge(status) {
  const badge = document.getElementById('systemBadge');
  const text  = document.getElementById('systemBadgeText');
  badge.className = 'topbar-badge';
  if (status === 'ok') {
    badge.classList.add('topbar-badge');
    text.textContent = 'Live';
  } else {
    badge.classList.add('warning');
    text.textContent = 'Degraded';
  }
}

// ── Recent table ─────────────────────────────────────────────
function renderRecentTable(items) {
  const el = document.getElementById('recentTableContainer');
  if (!items || items.length === 0) {
    el.innerHTML = `<div class="state-box"><i class="fas fa-database"></i><p>No records found.</p></div>`;
    return;
  }
  el.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Location</th>
          <th>Coordinates</th>
          <th>Count</th>
          <th>Status</th>
          <th>Timestamp</th>
        </tr>
      </thead>
      <tbody>
        ${items.map(item => {
          const lat = item.coordinates.latitude;
          const lng = item.coordinates.longitude;
          const ts  = item.timestamp ? new Date(item.timestamp).toLocaleString() : '—';
          const bc  = crowdBadgeClass(item.count);
          const bl  = crowdLabel(item.count);
          return `<tr>
            <td><strong>${shopName(lat, lng)}</strong></td>
            <td style="font-size:12px;color:var(--muted)">${lat.toFixed(4)}, ${lng.toFixed(4)}</td>
            <td><strong>${item.count}</strong></td>
            <td><span class="badge ${bc}">${bl}</span></td>
            <td style="font-size:12px;color:var(--muted)">${ts}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

function filterRecentTable() {
  const q = document.getElementById('recentSearch').value.trim().toLowerCase();
  if (!q) { renderRecentTable(recentData); return; }
  renderRecentTable(recentData.filter(item => {
    const name = shopName(item.coordinates.latitude, item.coordinates.longitude).toLowerCase();
    return name.includes(q) ||
      String(item.coordinates.latitude).includes(q) ||
      String(item.coordinates.longitude).includes(q);
  }));
}

// ── Map search ───────────────────────────────────────────────
function searchOnMap() {
  const q = document.getElementById('mapSearchInput').value.trim().toLowerCase();
  const resultEl = document.getElementById('mapSearchResult');
  if (!q) { resultEl.textContent = 'Please enter a shop name.'; return; }

  for (const [coords, name] of Object.entries(SHOP_NAMES)) {
    if (name.toLowerCase().includes(q)) {
      const [lat, lng] = coords.split(',').map(Number);
      leafletMap.setView([lat, lng], 16);
      const key = `${lat.toFixed(4)},${lng.toFixed(4)}`;
      if (mapMarkers[key]) mapMarkers[key].openPopup();
      resultEl.textContent = `Found: ${name} at ${lat}, ${lng}`;
      return;
    }
  }
  resultEl.textContent = 'No shop found with that name.';
}

// ── Shops section ────────────────────────────────────────────
let shopsData = [];

async function loadShops() {
  const el = document.getElementById('shopsTableContainer');
  el.innerHTML = `<div class="state-box"><div class="spinner"></div><p>Loading shops…</p></div>`;
  try {
    const shops = await apiFetch('/shops');
    shopsData = shops;

    // Merge current crowd data for status
    let crowdMap = {};
    try {
      const cd = await apiFetch('/data');
      (cd.data || []).forEach(item => {
        const key = `${item.coordinates.latitude.toFixed(4)},${item.coordinates.longitude.toFixed(4)}`;
        if (!crowdMap[key] || item.count > crowdMap[key]) crowdMap[key] = item.count;
      });
    } catch (_) {}

    renderShopsTable(shops, crowdMap);
  } catch (err) {
    console.error('loadShops error:', err);
    el.innerHTML = `<div class="state-box"><i class="fas fa-circle-exclamation"></i><p>Failed to load shops. Is the server running?</p></div>`;
  }
}

function renderShopsTable(shops, crowdMap) {
  const el = document.getElementById('shopsTableContainer');
  if (!shops || shops.length === 0) {
    el.innerHTML = `<div class="state-box"><i class="fas fa-store-slash"></i><p>No shops registered yet.</p></div>`;
    return;
  }
  el.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Shop Name</th>
          <th>Coordinates</th>
          <th>Video Feed</th>
          <th>Live Crowd</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${shops.map(shop => {
          // Try to match crowd count
          let count = '—';
          let bc = 'muted';
          let bl = 'Unknown';
          if (shop.coordinates) {
            const parts = shop.coordinates.split(',');
            if (parts.length >= 2) {
              const key = `${parseFloat(parts[0]).toFixed(4)},${parseFloat(parts[1]).toFixed(4)}`;
              if (crowdMap[key] !== undefined) {
                count = crowdMap[key];
                bc = crowdBadgeClass(count);
                bl = crowdLabel(count);
              }
            }
          }
          return `<tr>
            <td><strong>${shop.shopName || '—'}</strong></td>
            <td style="font-size:12px;color:var(--muted)">${shop.coordinates || '—'}</td>
            <td style="font-size:12px;color:var(--muted)">${shop.videoFeed ? `<a href="${shop.videoFeed}" target="_blank">View Feed</a>` : '—'}</td>
            <td><strong>${count}</strong></td>
            <td><span class="badge ${bc}">${bl}</span></td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

function filterShopsTable() {
  const q = document.getElementById('shopSearch').value.trim().toLowerCase();
  if (!q) { renderShopsTable(shopsData, {}); return; }
  const filtered = shopsData.filter(s =>
    (s.shopName || '').toLowerCase().includes(q) ||
    (s.coordinates || '').toLowerCase().includes(q)
  );
  renderShopsTable(filtered, {});
}

// ── Top Shops ────────────────────────────────────────────────
let topShopsChart = null;

async function loadTopShops() {
  const el = document.getElementById('topShopsTableContainer');
  el.innerHTML = `<div class="state-box"><div class="spinner"></div><p>Loading…</p></div>`;
  try {
    const data = await apiFetch('/api/top-shops');
    renderTopShops(data);
  } catch (err) {
    console.error('loadTopShops error:', err);
    el.innerHTML = `<div class="state-box"><i class="fas fa-circle-exclamation"></i><p>Failed to load top shops data.</p></div>`;
  }
}

function renderTopShops(data) {
  const el = document.getElementById('topShopsTableContainer');
  if (!data || data.length === 0) {
    el.innerHTML = `<div class="state-box"><i class="fas fa-database"></i><p>No data available.</p></div>`;
    return;
  }

  const labels = data.map((d, i) => {
    if (d._id && d._id.latitude && d._id.longitude) {
      return shopName(d._id.latitude, d._id.longitude);
    }
    return `Location ${i + 1}`;
  });
  const values = data.map(d => d.totalCrowd || 0);

  // Chart
  if (topShopsChart) topShopsChart.destroy();
  const ctx = document.getElementById('topShopsChart');
  if (ctx) {
    topShopsChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Total Crowd',
          data: values,
          backgroundColor: ['#4f8ef7', '#22c55e', '#f59e0b', '#ef4444', '#7c5cbf'],
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  // Table
  el.innerHTML = `
    <table>
      <thead>
        <tr><th>#</th><th>Location</th><th>Total Crowd</th><th>Share</th></tr>
      </thead>
      <tbody>
        ${data.map((d, i) => {
          const name = (d._id && d._id.latitude) ? shopName(d._id.latitude, d._id.longitude) : `Location ${i + 1}`;
          const total = values.reduce((a, b) => a + b, 0);
          const pct = total > 0 ? ((d.totalCrowd / total) * 100).toFixed(1) : 0;
          return `<tr>
            <td><strong>#${i + 1}</strong></td>
            <td>${name}</td>
            <td><strong>${d.totalCrowd || 0}</strong></td>
            <td style="min-width:120px">
              <div style="display:flex;align-items:center;gap:8px">
                <div style="flex:1;height:6px;border-radius:3px;background:var(--border)">
                  <div style="width:${pct}%;height:100%;border-radius:3px;background:var(--accent)"></div>
                </div>
                <span style="font-size:12px;color:var(--muted)">${pct}%</span>
              </div>
            </td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

// ── Heatmap ──────────────────────────────────────────────────
async function loadHeatmap() {
  const el = document.getElementById('heatmapContainer');
  el.innerHTML = `<div class="state-box"><div class="spinner"></div><p>Loading heatmap data…</p></div>`;
  try {
    const data = await apiFetch('/api/heatmap');
    if (!data || data.length === 0) {
      el.innerHTML = `<div class="state-box"><i class="fas fa-fire"></i><p>No heatmap data available.</p></div>`;
      return;
    }
    const maxCount = Math.max(...data.map(d => d.count || 0), 1);
    el.innerHTML = `<div class="heatmap-list">
      ${data.map(item => {
        const lat = item.coordinates ? item.coordinates.latitude : '—';
        const lng = item.coordinates ? item.coordinates.longitude : '—';
        const count = item.count || 0;
        const pct   = ((count / maxCount) * 100).toFixed(0);
        const color = crowdColor(count);
        const name  = (lat !== '—') ? shopName(lat, lng) : '—';
        return `<div class="heatmap-item">
          <div class="coord">${lat}, ${lng}</div>
          <div style="font-weight:600;margin-bottom:4px;font-size:13px">${name}</div>
          <div class="count" style="color:${color}">${count}</div>
          <div style="height:6px;border-radius:3px;background:var(--border);margin-top:8px;overflow:hidden">
            <div style="width:${pct}%;height:100%;border-radius:3px;background:${color}"></div>
          </div>
          <div style="font-size:11px;color:var(--muted);margin-top:4px">${pct}% of peak</div>
        </div>`;
      }).join('')}
    </div>`;
  } catch (err) {
    console.error('loadHeatmap error:', err);
    el.innerHTML = `<div class="state-box"><i class="fas fa-circle-exclamation"></i><p>Failed to load heatmap data.</p></div>`;
  }
}

// ── History ──────────────────────────────────────────────────
let histChart = null;

async function loadHistory() {
  const shop = document.getElementById('histShop').value;
  const time = document.getElementById('histTime').value;
  const tableEl = document.getElementById('histTableContainer');
  tableEl.innerHTML = `<div class="state-box"><div class="spinner"></div><p>Fetching history…</p></div>`;

  try {
    const data = await apiFetch(`/history?shop=${encodeURIComponent(shop)}&time=${time}`);
    renderHistoryTable(data, shop);
  } catch (err) {
    console.error('loadHistory error:', err);
    tableEl.innerHTML = `<div class="state-box"><i class="fas fa-circle-exclamation"></i><p>Failed to fetch history.</p></div>`;
    document.getElementById('histChartWrap').style.display = 'none';
  }
}

function renderHistoryTable(data, shop) {
  const tableEl = document.getElementById('histTableContainer');
  const chartWrap = document.getElementById('histChartWrap');

  // Handle API returning object with message
  if (!Array.isArray(data)) {
    const msg = data.message || data.error || 'No data returned.';
    tableEl.innerHTML = `<div class="state-box"><i class="fas fa-inbox"></i><p>${msg}</p></div>`;
    chartWrap.style.display = 'none';
    return;
  }

  if (data.length === 0) {
    tableEl.innerHTML = `<div class="state-box"><i class="fas fa-inbox"></i><p>No records found for this time range.</p></div>`;
    chartWrap.style.display = 'none';
    return;
  }

  // Chart
  chartWrap.style.display = 'block';
  document.getElementById('histChartTitle').textContent = `Crowd History — ${shop}`;
  if (histChart) histChart.destroy();
  const ctx = document.getElementById('histChart');
  if (ctx) {
    const labels = data.map(d => new Date(d.timestamp).toLocaleTimeString());
    const counts = data.map(d => d.count);
    histChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Crowd Count',
          data: counts,
          borderColor: '#4f8ef7',
          backgroundColor: '#4f8ef722',
          fill: true,
          tension: 0.35,
          pointRadius: 3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { beginAtZero: true } },
        plugins: { legend: { display: false } },
      },
    });
  }

  // Table
  tableEl.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Crowd Count</th>
          <th>Latitude</th>
          <th>Longitude</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${data.map(item => {
          const ts  = item.timestamp ? new Date(item.timestamp).toLocaleString() : '—';
          const bc  = crowdBadgeClass(item.count);
          const bl  = crowdLabel(item.count);
          const lat = item.coordinates ? item.coordinates.latitude : '—';
          const lng = item.coordinates ? item.coordinates.longitude : '—';
          return `<tr>
            <td style="font-size:12px">${ts}</td>
            <td><strong>${item.count}</strong></td>
            <td style="font-size:12px;color:var(--muted)">${lat}</td>
            <td style="font-size:12px;color:var(--muted)">${lng}</td>
            <td><span class="badge ${bc}">${bl}</span></td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

// ── Analytics — Shop Comparison ──────────────────────────────
let compareChart = null;

async function loadCompareChart() {
  const shop1 = document.getElementById('compareShop1').value;
  const shop2 = document.getElementById('compareShop2').value;

  const [lat1, lng1] = shop1.split(',');
  const [lat2, lng2] = shop2.split(',');

  const name1 = shopName(lat1, lng1);
  const name2 = shopName(lat2, lng2);

  try {
    const [d1, d2] = await Promise.all([
      apiFetch(`/api/historical-data?latitude=${lat1}&longitude=${lng1}`),
      apiFetch(`/api/historical-data?latitude=${lat2}&longitude=${lng2}`),
    ]);

    const labels = [...new Set([
      ...(d1.map ? d1.map(d => new Date(d.timestamp).toLocaleTimeString()) : []),
      ...(d2.map ? d2.map(d => new Date(d.timestamp).toLocaleTimeString()) : []),
    ])].slice(0, 30);

    const counts1 = d1.map ? d1.slice(0, 30).map(d => d.count) : [];
    const counts2 = d2.map ? d2.slice(0, 30).map(d => d.count) : [];

    if (compareChart) compareChart.destroy();
    const ctx = document.getElementById('anCompareChart');
    if (ctx) {
      compareChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            { label: name1, data: counts1, borderColor: '#4f8ef7', backgroundColor: '#4f8ef722', fill: true, tension: 0.35, pointRadius: 3 },
            { label: name2, data: counts2, borderColor: '#22c55e', backgroundColor: '#22c55e22', fill: true, tension: 0.35, pointRadius: 3 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { y: { beginAtZero: true } },
          plugins: { legend: { display: true, labels: { color: '#e2e8f0' } } },
        },
      });
    }
  } catch (err) {
    console.error('loadCompareChart error:', err);
  }
}

// ── Health ───────────────────────────────────────────────────
async function loadHealth() {
  await Promise.allSettled([loadNodeHealth(), loadPyHealth(), loadOrchHealth()]);
}

async function loadNodeHealth() {
  const badge = document.getElementById('nodeHealthBadge');
  const body  = document.getElementById('nodeHealthBody');
  try {
    const data = await apiFetch('/health');
    badge.className = 'badge green';
    badge.textContent = data.status === 'ok' ? 'OK' : 'Degraded';
    body.innerHTML = renderHealthRows({
      Status:    data.status,
      Version:   data.version || '—',
      Service:   data.service || '—',
      Timestamp: data.timestamp ? new Date(data.timestamp).toLocaleString() : '—',
    });
  } catch (err) {
    badge.className = 'badge red';
    badge.textContent = 'Unreachable';
    body.innerHTML = `<div class="state-box" style="padding:20px"><i class="fas fa-circle-xmark"></i><p>Could not reach /health</p></div>`;
  }
}

async function loadPyHealth() {
  const badge = document.getElementById('pyHealthBadge');
  const body  = document.getElementById('pyHealthBody');
  try {
    const data = await apiFetch(`${PYTHON_API}/health`);
    const overall = data.status || 'unknown';
    badge.className = overall === 'ok' ? 'badge green' : 'badge amber';
    badge.textContent = overall === 'ok' ? 'OK' : 'Degraded';
    const rows = { 'Overall Status': overall };
    if (data.providers && typeof data.providers === 'object') {
      Object.entries(data.providers).forEach(([k, v]) => {
        rows[k] = typeof v === 'object' ? (v.status || JSON.stringify(v)) : v;
      });
    }
    body.innerHTML = renderHealthRows(rows);
  } catch (err) {
    badge.className = 'badge muted';
    badge.textContent = 'Offline';
    body.innerHTML = `<div class="state-box" style="padding:20px"><i class="fas fa-plug-circle-xmark"></i><p>Python API not reachable (port 8000).<br/>Start with: <code style="font-size:11px">uvicorn api_server:app --port 8000</code></p></div>`;
  }
}

async function loadOrchHealth() {
  const badge = document.getElementById('orchHealthBadge');
  const body  = document.getElementById('orchHealthBody');
  try {
    const data = await apiFetch(`${PYTHON_API}/api/v1/orchestrator/health`);
    badge.className = 'badge blue';
    badge.textContent = 'Active';
    const rows = {};
    if (data.success_rate  !== undefined) rows['Success Rate']  = `${(data.success_rate * 100).toFixed(1)}%`;
    if (data.fallback_rate !== undefined) rows['Fallback Rate'] = `${(data.fallback_rate * 100).toFixed(1)}%`;
    if (data.total_calls   !== undefined) rows['Total Calls']   = data.total_calls;
    if (data.providers && typeof data.providers === 'object') {
      Object.entries(data.providers).forEach(([k, v]) => {
        rows[`Provider: ${k}`] = typeof v === 'object' ? (v.state || JSON.stringify(v)) : v;
      });
    }
    body.innerHTML = Object.keys(rows).length ? renderHealthRows(rows) :
      `<div class="state-box" style="padding:20px"><i class="fas fa-check-circle"></i><p>Orchestrator active</p></div>`;
  } catch (err) {
    badge.className = 'badge muted';
    badge.textContent = 'Offline';
    body.innerHTML = `<div class="state-box" style="padding:20px"><i class="fas fa-plug-circle-xmark"></i><p>Orchestrator API not reachable (port 8000).</p></div>`;
  }
}

function renderHealthRows(rows) {
  return Object.entries(rows).map(([k, v]) => `
    <div class="health-row">
      <span class="health-key">${k}</span>
      <span class="health-val">${v}</span>
    </div>`).join('');
}

// ── Global refresh ───────────────────────────────────────────
function refreshAll() {
  fetchCrowdData();
  if (currentSection === 'shops')     loadShops();
  if (currentSection === 'top-shops') loadTopShops();
  if (currentSection === 'heatmap')   loadHeatmap();
  if (currentSection === 'health')    loadHealth();
}

// ── Initialise ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  initMap();
  fetchCrowdData();
  setInterval(fetchCrowdData, REFRESH_INTERVAL);
});
