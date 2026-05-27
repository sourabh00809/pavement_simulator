/* ─── State ──────────────────────────────────── */
let simData = null;
let isLoading = false;
let renderedTabs = {};

/* ─── DOM refs ───────────────────────────────── */
const $ = (id) => document.getElementById(id);
const runBtn = $("runBtn");
const exportBtn = $("exportBtn");
const loader = $("loader");
const statusText = $("statusText");
const samplesText = $("samplesText");
const damageText = $("damageText");
const errorBox = $("errorBox");
const tabBar = $("tabBar");

const TAB_CHART_MAP = {
  timeseries: "chart-timeseries",
  temperature: "chart-temperature",
  moisture: "chart-moisture",
  load: "chart-load",
  stress: "chart-stress",
};

/* ─── Radio pill toggle ─────────────────────── */
document.querySelectorAll(".radio-group").forEach((group) => {
  group.addEventListener("change", (e) => {
    if (e.target.type !== "radio") return;
    group.querySelectorAll(".radio-pill").forEach((pill) => {
      pill.classList.toggle("active", pill.contains(e.target));
    });
  });
});

/* ─── Weather mode toggle ───────────────────── */
document.querySelectorAll('[name="weather_mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const val = document.querySelector('[name="weather_mode"]:checked').value;
    $("weather_synthetic").classList.toggle("hidden", val !== "synthetic");
    $("weather_csv").classList.toggle("hidden", val !== "csv");
    $("weather_openmeteo").classList.toggle("hidden", val !== "openmeteo");
  });
});

/* ─── Load mode toggle ──────────────────────── */
document.querySelectorAll('[name="load_mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const val = document.querySelector('[name="load_mode"]:checked').value;
    $("load_constant").classList.toggle("hidden", val !== "constant");
    $("load_csv_section").classList.toggle("hidden", val !== "csv");
  });
});

/* ─── File upload display ────────────────────── */
$("weather_csv_input").addEventListener("change", function () {
  $("weather_csv_name").textContent = this.files[0] ? this.files[0].name : "";
});
$("load_csv_input").addEventListener("change", function () {
  $("load_csv_name").textContent = this.files[0] ? this.files[0].name : "";
});

/* ─── Tab switching ──────────────────────────── */
tabBar.addEventListener("click", (e) => {
  const tab = e.target.closest(".tab");
  if (!tab) return;

  const tabName = tab.dataset.tab;

  tabBar.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  tab.classList.add("active");

  document.querySelectorAll(".tab-content").forEach((tc) => tc.classList.remove("active"));
  const target = $("tab-" + tabName);
  if (target) target.classList.add("active");

  // Render chart lazily if not yet rendered
  const chartId = TAB_CHART_MAP[tabName];
  const chartDiv = $(chartId);
  if (chartDiv && simData && simData.plots && simData.plots[tabName]) {
    if (!renderedTabs[tabName]) {
      Plotly.newPlot(chartDiv, simData.plots[tabName].data, simData.plots[tabName].layout, {
        displaylogo: false,
        modeBarButtonsToRemove: ["lasso2d", "select2d"],
      });
      renderedTabs[tabName] = true;
    } else {
      Plotly.Plots.resize(chartDiv);
    }
  }
});

/* ─── Run Simulation ─────────────────────────── */
runBtn.addEventListener("click", async () => {
  if (isLoading) return;
  isLoading = true;
  runBtn.disabled = true;
  loader.classList.remove("hidden");
  errorBox.classList.add("hidden");
  errorBox.textContent = "";

  try {
    const formData = new FormData();

    formData.append("slab_length", $("slab_length").value);
    formData.append("slab_width", $("slab_width").value);
    formData.append("h", $("h").value);
    formData.append("contact_radius", $("contact_radius").value);

    formData.append("E", $("E").value);
    formData.append("k", $("k").value);
    formData.append("nu", $("nu").value);
    formData.append("alpha", $("alpha").value);
    formData.append("beta_shrinkage", $("beta_shrinkage").value);

    formData.append("fatigue_A", $("fatigue_A").value);
    formData.append("fatigue_m", $("fatigue_m").value);
    formData.append("fatigue_sigma_ref", $("fatigue_sigma_ref").value);

    const weatherMode = document.querySelector('[name="weather_mode"]:checked').value;
    formData.append("weather_mode", weatherMode);

    if (weatherMode === "synthetic") {
      formData.append("sim_days", $("sim_days").value);
      formData.append("daily_steps", $("daily_steps").value);
      formData.append("mean_temp", $("mean_temp").value);
      formData.append("amp_temp", $("amp_temp").value);
      formData.append("mean_RH", $("mean_RH").value);
      formData.append("amp_RH", $("amp_RH").value);
    } else if (weatherMode === "openmeteo") {
      formData.append("lat", $("lat").value);
      formData.append("lon", $("lon").value);
      formData.append("days", $("days").value);
    } else if (weatherMode === "csv") {
      const file = $("weather_csv_input").files[0];
      if (file) formData.append("weather_csv", file, file.name);
      formData.append("sim_days", $("sim_days").value);
      formData.append("daily_steps", $("daily_steps").value);
      formData.append("mean_temp", $("mean_temp").value);
      formData.append("amp_temp", $("amp_temp").value);
      formData.append("mean_RH", $("mean_RH").value);
      formData.append("amp_RH", $("amp_RH").value);
    }

    const loadMode = document.querySelector('[name="load_mode"]:checked').value;
    formData.append("load_mode", loadMode);

    if (loadMode === "constant") {
      formData.append("wheel_load", $("wheel_load").value);
    } else if (loadMode === "csv") {
      const file = $("load_csv_input").files[0];
      if (file) formData.append("load_csv", file, file.name);
      formData.append("wheel_load", $("wheel_load").value);
    }

    const res = await fetch("/api/simulate", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!data.ok) {
      throw new Error(data.error || "Simulation failed");
    }

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

/* ─── Render Results ─────────────────────────── */
function renderResults(data) {
  const { plots, cycles, summary } = data;

  renderedTabs = {};

  statusText.textContent = "Complete";
  samplesText.textContent = summary.samples.toLocaleString();
  damageText.textContent = summary.totalDamage.toExponential(4);

  // Only render the visible (timeseries) chart; rest are lazy-rendered on tab click
  const tsChart = $("chart-timeseries");
  if (tsChart && plots.timeSeries) {
    Plotly.newPlot(tsChart, plots.timeSeries.data, plots.timeSeries.layout, {
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });
    renderedTabs["timeseries"] = true;
  }

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

  // Summary cards
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

/* ─── Export CSV ────────────────────────────── */
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
