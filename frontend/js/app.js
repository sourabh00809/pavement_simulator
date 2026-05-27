let simData = null;
let isLoading = false;
let chartInstances = {};

const $ = (id) => document.getElementById(id);
const runBtn = $("runBtn");
const exportBtn = $("exportBtn");
const loader = $("loader");
const statusText = $("statusText");
const samplesText = $("samplesText");
const damageText = $("damageText");
const errorBox = $("errorBox");
const tabBar = $("tabBar");

const TAB_IDS = ["timeseries", "temperature", "moisture", "load", "stress", "cycles", "summary"];

// Subplot chart IDs for the time series tab
const TS_CHARTS = { temperature: "chart-ts-temp", moisture: "chart-ts-moist", load: "chart-ts-load", stress: "chart-ts-stress" };

document.querySelectorAll(".radio-group").forEach((group) => {
  group.addEventListener("change", (e) => {
    if (e.target.type !== "radio") return;
    group.querySelectorAll(".radio-pill").forEach((pill) => {
      pill.classList.toggle("active", pill.contains(e.target));
    });
  });
});

document.querySelectorAll('[name="weather_mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const val = document.querySelector('[name="weather_mode"]:checked').value;
    $("weather_synthetic").classList.toggle("hidden", val !== "synthetic");
    $("weather_csv").classList.toggle("hidden", val !== "csv");
    $("weather_openmeteo").classList.toggle("hidden", val !== "openmeteo");
  });
});

document.querySelectorAll('[name="load_mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const val = document.querySelector('[name="load_mode"]:checked').value;
    $("load_constant").classList.toggle("hidden", val !== "constant");
    $("load_csv_section").classList.toggle("hidden", val !== "csv");
  });
});

$("weather_csv_input").addEventListener("change", function () {
  $("weather_csv_name").textContent = this.files[0] ? this.files[0].name : "";
});
$("load_csv_input").addEventListener("change", function () {
  $("load_csv_name").textContent = this.files[0] ? this.files[0].name : "";
});

tabBar.addEventListener("click", (e) => {
  const tab = e.target.closest(".tab");
  if (!tab) return;

  const tabName = tab.dataset.tab;

  tabBar.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  tab.classList.add("active");

  document.querySelectorAll(".tab-content").forEach((tc) => tc.classList.remove("active"));
  const target = $("tab-" + tabName);
  if (target) target.classList.add("active");

  if (tabName === "timeseries" && simData) {
    renderTSSubplots(simData.charts.timeSeries);
  } else if (["temperature", "moisture", "load", "stress"].includes(tabName) && simData) {
    renderSingleChart(tabName, simData.charts[tabName]);
  }
});

function chartOpts(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "nearest", axis: "x", intersect: false },
    plugins: {
      legend: { position: "top", labels: { boxWidth: 12, padding: 8, font: { size: 11 } } },
      zoom: {
        zoom: { wheel: { enabled: true }, pinch: { enabled: true }, drag: { enabled: true } },
        pan: { enabled: true, mode: "x" },
      },
    },
    scales: {
      x: { title: { display: true, text: "Time (days)", font: { size: 11 } }, tick: { font: { size: 10 } } },
      y: { title: { display: true, text: yLabel, font: { size: 11 } }, tick: { font: { size: 10 } } },
    },
  };
}

function destroyChart(id) {
  if (chartInstances[id]) {
    chartInstances[id].destroy();
    delete chartInstances[id];
  }
}

function createChart(canvasId, data, yLabel) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  chartInstances[canvasId] = new Chart(ctx, {
    type: "line",
    data: data,
    options: chartOpts(yLabel),
  });
}

function renderTSSubplots(subplots) {
  if (!subplots) return;
  const labels = {
    temperature: "Temp (C)",
    moisture: "Moisture",
    load: "Load (N)",
    stress: "Stress (MPa)",
  };
  Object.keys(subplots).forEach((key) => {
    const id = TS_CHARTS[key];
    if (id) createChart(id, subplots[key], labels[key]);
  });
}

function renderSingleChart(tabName, data) {
  const labels = {
    temperature: "Temp (C)",
    moisture: "Moisture",
    load: "Load (N)",
    stress: "Stress (MPa)",
  };
  const id = "chart-" + tabName;
  createChart(id, data, labels[tabName] || "");
}

runBtn.addEventListener("click", async () => {
  if (isLoading) return;
  isLoading = true;
  runBtn.disabled = true;
  loader.classList.remove("hidden");
  errorBox.classList.add("hidden");
  errorBox.textContent = "";

  try {
    const fd = new FormData();

    fd.append("slab_length", $("slab_length").value);
    fd.append("slab_width", $("slab_width").value);
    fd.append("h", $("h").value);
    fd.append("contact_radius", $("contact_radius").value);

    fd.append("E", $("E").value);
    fd.append("k", $("k").value);
    fd.append("nu", $("nu").value);
    fd.append("alpha", $("alpha").value);
    fd.append("beta_shrinkage", $("beta_shrinkage").value);

    fd.append("fatigue_A", $("fatigue_A").value);
    fd.append("fatigue_m", $("fatigue_m").value);
    fd.append("fatigue_sigma_ref", $("fatigue_sigma_ref").value);

    const weatherMode = document.querySelector('[name="weather_mode"]:checked').value;
    fd.append("weather_mode", weatherMode);

    if (weatherMode === "synthetic") {
      fd.append("sim_days", $("sim_days").value);
      fd.append("daily_steps", $("daily_steps").value);
      fd.append("mean_temp", $("mean_temp").value);
      fd.append("amp_temp", $("amp_temp").value);
      fd.append("mean_RH", $("mean_RH").value);
      fd.append("amp_RH", $("amp_RH").value);
    } else if (weatherMode === "openmeteo") {
      fd.append("lat", $("lat").value);
      fd.append("lon", $("lon").value);
      fd.append("days", $("days").value);
    } else if (weatherMode === "csv") {
      const file = $("weather_csv_input").files[0];
      if (file) fd.append("weather_csv", file, file.name);
      fd.append("sim_days", $("sim_days").value);
      fd.append("daily_steps", $("daily_steps").value);
      fd.append("mean_temp", $("mean_temp").value);
      fd.append("amp_temp", $("amp_temp").value);
      fd.append("mean_RH", $("mean_RH").value);
      fd.append("amp_RH", $("amp_RH").value);
    }

    const loadMode = document.querySelector('[name="load_mode"]:checked').value;
    fd.append("load_mode", loadMode);

    if (loadMode === "constant") {
      fd.append("wheel_load", $("wheel_load").value);
    } else if (loadMode === "csv") {
      const file = $("load_csv_input").files[0];
      if (file) fd.append("load_csv", file, file.name);
      fd.append("wheel_load", $("wheel_load").value);
    }

    const res = await fetch("/api/simulate", { method: "POST", body: fd });
    const data = await res.json();

    if (!data.ok) throw new Error(data.error || "Simulation failed");

    simData = data;
    renderResults(data);

  } catch (err) {
    errorBox.textContent = err.message || "An error occurred";
    errorBox.classList.remove("hidden");
    statusText.textContent = "Error";
  } finally {
    isLoading = false;
    runBtn.disabled = false;
    loader.classList.add("hidden");
  }
});

function renderResults(data) {
  const { charts, cycles, summary } = data;

  // Destroy any existing chart instances
  Object.keys(chartInstances).forEach((k) => {
    try { chartInstances[k].destroy(); } catch (e) {}
  });
  chartInstances = {};

  statusText.textContent = "Complete";
  samplesText.textContent = summary.samples.toLocaleString();
  damageText.textContent = summary.totalDamage.toExponential(4);

  // Render visible timeseries subplots immediately
  renderTSSubplots(charts.timeSeries);

  // Cycles table
  const tbody = $("cyclesBody");
  if (cycles.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">No cycles detected.</td></tr>';
  } else {
    tbody.innerHTML = cycles.map((c) => `
      <tr>
        <td>${Number(c.range).toFixed(6)}</td>
        <td>${Number(c.mean).toFixed(6)}</td>
        <td>${Number(c.count).toFixed(2)}</td>
        <td>${Number(c.amplitude).toFixed(6)}</td>
        <td>${Number(c.nf).toExponential(3)}</td>
        <td>${Number(c.damage).toExponential(3)}</td>
      </tr>
    `).join("");
  }

  const grid = $("summaryGrid");
  grid.innerHTML = `
    <div class="summary-card accent">
      <div class="value">${summary.totalDamage.toExponential(4)}</div>
      <div class="label">Total Damage</div>
    </div>
    <div class="summary-card">
      <div class="value">${summary.samples.toLocaleString()}</div>
      <div class="label">Samples</div>
    </div>
    <div class="summary-card">
      <div class="value">${summary.nCycles}</div>
      <div class="label">Rainflow Cycles</div>
    </div>
    <div class="summary-card">
      <div class="value">${summary.maxStress.toFixed(4)}</div>
      <div class="label">Max Stress (MPa)</div>
    </div>
    <div class="summary-card">
      <div class="value">${summary.minStress.toFixed(4)}</div>
      <div class="label">Min Stress (MPa)</div>
    </div>
    <div class="summary-card">
      <div class="value">${summary.timeSpan.toFixed(0)}</div>
      <div class="label">Time Span (days)</div>
    </div>
  `;

  exportBtn.disabled = false;
}

exportBtn.addEventListener("click", async () => {
  if (!simData || !simData.cycles || simData.cycles.length === 0) return;

  try {
    const res = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cycles: simData.cycles }),
    });

    if (!res.ok) throw new Error("Export failed");

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cycles.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    errorBox.textContent = "Export failed: " + err.message;
    errorBox.classList.remove("hidden");
  }
});
