/*
Renders the analytics charts on the dashboard by calling this app's own
JSON API (fetch, same-origin, so the session cookie is sent automatically -
no API key needed here). This is the same /api/stats and /api/links/{id}/stats
endpoints documented in docs/API.md - the dashboard is just another API
consumer, same as an external app would be.

Expects a global `LS_STATS_URL` to be set by the template (either
"/api/stats" for the main dashboard or "/api/links/{id}/stats" for a
single link's page) before this script runs.
*/

const PALETTE = {
  primary: "#5b5ff0",
  primaryLight: "rgba(91, 95, 240, 0.15)",
  accent: "#22c3a6",
  slate: "#8a8fa3",
  categories: ["#5b5ff0", "#22c3a6", "#f5a623", "#ef476f", "#118ab2", "#8a8fa3"],
};

async function loadStats() {
  const res = await fetch(LS_STATS_URL, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    console.error("Failed to load stats:", res.status);
    return null;
  }
  return res.json();
}

function renderDailyChart(canvas, daily) {
  new Chart(canvas, {
    type: "line",
    data: {
      labels: daily.map((d) => d.day.slice(5)),
      datasets: [
        {
          label: "Clicks",
          data: daily.map((d) => d.count),
          borderColor: PALETTE.primary,
          backgroundColor: PALETTE.primaryLight,
          fill: true,
          tension: 0.35,
          pointRadius: 2,
          pointHoverRadius: 5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } },
        x: { grid: { display: false } },
      },
    },
  });
}

function renderDoughnut(canvas, rows, labelKey) {
  if (!rows.length) return;
  new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: rows.map((r) => r[labelKey]),
      datasets: [
        {
          data: rows.map((r) => r.count),
          backgroundColor: PALETTE.categories,
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } } },
      cutout: "60%",
    },
  });
}

function renderHorizontalBar(canvas, rows, labelKey) {
  if (!rows.length) return;
  new Chart(canvas, {
    type: "bar",
    data: {
      labels: rows.map((r) => {
        const v = r[labelKey] || "";
        return v.length > 28 ? v.slice(0, 28) + "…" : v;
      }),
      datasets: [
        {
          data: rows.map((r) => r.count),
          backgroundColor: PALETTE.accent,
          borderRadius: 4,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { precision: 0 } },
      },
    },
  });
}

function renderSummary(stats) {
  const totalEl = document.getElementById("stat-total");
  const last24El = document.getElementById("stat-last24");
  if (totalEl) totalEl.textContent = stats.summary.total;
  if (last24El) last24El.textContent = stats.summary.last_24h;
}

async function initDashboardCharts() {
  const stats = await loadStats();
  if (!stats) return;

  renderSummary(stats);

  const dailyCanvas = document.getElementById("chart-daily");
  if (dailyCanvas) renderDailyChart(dailyCanvas, stats.daily);

  const devicesCanvas = document.getElementById("chart-devices");
  if (devicesCanvas) renderDoughnut(devicesCanvas, stats.devices, "device_type");

  const countriesCanvas = document.getElementById("chart-countries");
  if (countriesCanvas) renderHorizontalBar(countriesCanvas, stats.top_countries, "country");

  const referrersCanvas = document.getElementById("chart-referrers");
  if (referrersCanvas) renderHorizontalBar(referrersCanvas, stats.top_referrers, "referrer");
}

document.addEventListener("DOMContentLoaded", initDashboardCharts);
