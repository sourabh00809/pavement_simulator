import os
import tempfile
import gradio as gr
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.engine import (
    PavementSimulator,
    FatigueSN,
    load_weather_dataframe,
    load_weather_csv,
    load_load_csv,
)
from src.weather_fetcher import fetch_weather_by_days

# ──────────────────────────────────────────────
# THEME
# ──────────────────────────────────────────────

theme = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="slate",
    neutral_hue="stone",
    font=gr.themes.GoogleFont("Inter"),
    font_mono=gr.themes.GoogleFont("JetBrains Mono"),
    spacing_size="md",
    radius_size="md",
    text_size="md",
)

CUSTOM_CSS = """
.header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #1e3a5f 100%);
    padding: 1.5rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.15);
}
.header h1 {
    color: #f8fafc;
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0 0 0.2rem 0;
    letter-spacing: -0.02em;
}
.header p {
    color: #94a3b8;
    font-size: 0.85rem;
    margin: 0;
    font-weight: 400;
}
.section-title {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #475569;
    margin: 0 0 0.75rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid #3b82f6;
}
.run-btn {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 1.1rem !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.35) !important;
    transition: all 0.2s ease !important;
    height: 48px !important;
}
.run-btn:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(37,99,235,0.45) !important;
}
.status-panel {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-top: 0.75rem;
}
.status-panel p { margin: 0.25rem 0; }
.export-btn {
    font-size: 0.8rem !important;
}
footer {
    text-align: center;
    color: #94a3b8;
    font-size: 0.75rem;
    padding: 1.5rem 0 0.5rem 0;
    border-top: 1px solid #e2e8f0;
    margin-top: 2rem;
}
"""

# ──────────────────────────────────────────────
# PLOTLY PLOT HELPERS
# ──────────────────────────────────────────────

COLORS = {
    "blue": "#3b82f6",
    "red": "#ef4444",
    "green": "#22c55e",
    "orange": "#f97316",
    "purple": "#a855f7",
    "teal": "#14b8a6",
    "gray": "#64748b",
    "dark": "#0f172a",
}


def make_time_series_plot(r):
    t = r["t"]
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        subplot_titles=("Temperature", "Relative Humidity & Moisture", "Vehicle Load", "Stress Components"),
        vertical_spacing=0.06,
    )
    fig.add_trace(go.Scatter(x=t, y=r["T_air"], name="T_air", line=dict(color=COLORS["red"], width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["T_top"], name="T_top", line=dict(color=COLORS["orange"], width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["T_bottom"], name="T_bottom", line=dict(color=COLORS["blue"], width=1.5)), row=1, col=1)
    fig.update_yaxes(title_text="Temp (C)", row=1, col=1)

    fig.add_trace(go.Scatter(x=t, y=r["RH"], name="RH (air)", line=dict(color=COLORS["blue"], width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["M_top"], name="M_top", line=dict(color=COLORS["green"], width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["M_bottom"], name="M_bottom", line=dict(color=COLORS["teal"], width=1.5)), row=2, col=1)
    fig.update_yaxes(title_text="Moisture", row=2, col=1)

    fig.add_trace(go.Scatter(x=t, y=r["loads_N"], name="Load (N)", line=dict(color=COLORS["purple"], width=1.5)), row=3, col=1)
    fig.update_yaxes(title_text="Load (N)", row=3, col=1)

    fig.add_trace(go.Scatter(x=t, y=r["sigma_total"], name="sigma_total", line=dict(color=COLORS["dark"], width=2)), row=4, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["sigma_load_only"], name="sigma_load", line=dict(color=COLORS["red"], width=1.5, dash="dash")), row=4, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["sigma_thermal"], name="sigma_thermal", line=dict(color=COLORS["orange"], width=1.5, dash="dot")), row=4, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["sigma_moisture"], name="sigma_moisture", line=dict(color=COLORS["green"], width=1.5, dash="dashdot")), row=4, col=1)
    fig.update_yaxes(title_text="Stress (MPa)", row=4, col=1)
    fig.update_xaxes(title_text="Time (days)", row=4, col=1)

    fig.update_layout(height=700, margin=dict(l=50, r=20, t=40, b=50), hovermode="x unified", template="plotly_white", legend=dict(orientation="h", y=1.02, font_size=10))
    return fig


def make_temperature_plot(r):
    t = r["t"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=r["T_air"], name="T_air", line=dict(color=COLORS["red"], width=2)))
    fig.add_trace(go.Scatter(x=t, y=r["T_top"], name="T_top", line=dict(color=COLORS["orange"], width=2)))
    fig.add_trace(go.Scatter(x=t, y=r["T_bottom"], name="T_bottom", line=dict(color=COLORS["blue"], width=2)))
    fig.update_layout(title="Temperature Time Series", xaxis_title="Time (days)", yaxis_title="Temperature (C)", height=400, margin=dict(l=50, r=20, t=40, b=50), hovermode="x unified", template="plotly_white", legend=dict(orientation="h", y=1.02))
    return fig


def make_moisture_plot(r):
    t = r["t"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=r["RH"], name="RH (air)", line=dict(color=COLORS["blue"], width=2)))
    fig.add_trace(go.Scatter(x=t, y=r["M_top"], name="M_top", line=dict(color=COLORS["green"], width=2)))
    fig.add_trace(go.Scatter(x=t, y=r["M_bottom"], name="M_bottom", line=dict(color=COLORS["teal"], width=2)))
    fig.update_layout(title="Moisture / Relative Humidity", xaxis_title="Time (days)", yaxis_title="Moisture", height=400, margin=dict(l=50, r=20, t=40, b=50), hovermode="x unified", template="plotly_white", legend=dict(orientation="h", y=1.02))
    return fig


def make_load_plot(r):
    t = r["t"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=r["loads_N"], name="Vehicle Load (N)", line=dict(color=COLORS["purple"], width=2)))
    fig.update_layout(title="Vehicle Load History", xaxis_title="Time (days)", yaxis_title="Load (N)", height=400, margin=dict(l=50, r=20, t=40, b=50), hovermode="x unified", template="plotly_white")
    return fig


def make_stress_plot(r):
    t = r["t"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=r["sigma_total"], name="sigma_total", line=dict(color=COLORS["dark"], width=2.5)))
    fig.add_trace(go.Scatter(x=t, y=r["sigma_load_only"], name="sigma_load", line=dict(color=COLORS["red"], width=1.5, dash="dash")))
    fig.add_trace(go.Scatter(x=t, y=r["sigma_thermal"], name="sigma_thermal", line=dict(color=COLORS["orange"], width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=t, y=r["sigma_moisture"], name="sigma_moisture", line=dict(color=COLORS["green"], width=1.5, dash="dashdot")))
    fig.update_layout(title="Stress Components and Total Stress", xaxis_title="Time (days)", yaxis_title="Stress (MPa)", height=400, margin=dict(l=50, r=20, t=40, b=50), hovermode="x unified", template="plotly_white", legend=dict(orientation="h", y=1.02))
    return fig


def make_empty_figure():
    fig = go.Figure()
    fig.update_layout(height=300, template="plotly_white", xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


# ──────────────────────────────────────────────
# SIMULATION FUNCTION
# ──────────────────────────────────────────────

def run_simulation(
    slab_length, slab_width, h, E, nu, alpha, beta_shrinkage, k,
    wheel_load, contact_radius,
    weather_mode, weather_csv, lat, lon, days,
    sim_days, daily_steps, mean_temp, amp_temp, mean_RH, amp_RH,
    load_mode, load_csv,
    fatigue_A, fatigue_m, fatigue_sigma_ref,
):
    try:
        fatigue = FatigueSN(A=fatigue_A, m=fatigue_m, sigma_ref=fatigue_sigma_ref)

        weather_df = None
        weather_csv_path = None
        if weather_mode == "Open-Meteo API":
            df = fetch_weather_by_days(lat, lon, int(days))
            weather_df = df
            sim_days_actual = int(days)
        elif weather_mode == "Upload CSV" and weather_csv is not None:
            weather_csv_path = weather_csv
            sim_days_actual = int(sim_days)
        else:
            sim_days_actual = int(sim_days)

        load_csv_path = None
        wheel_loads_list = None
        if load_mode == "Upload CSV" and load_csv is not None:
            load_csv_path = load_csv
        else:
            wheel_loads_list = [wheel_load]

        sim = PavementSimulator(
            slab_length=slab_length,
            slab_width=slab_width,
            h=h, E=E, nu=nu, alpha=alpha,
            beta_shrinkage=beta_shrinkage, k=k,
            wheel_loads=wheel_loads_list,
            contact_radius=contact_radius,
            sim_days=sim_days_actual,
            daily_steps=int(daily_steps),
            mean_temp=mean_temp, amp_temp=amp_temp,
            mean_RH=mean_RH, amp_RH=amp_RH,
            fatigue_sn=fatigue,
            weather_csv=weather_csv_path,
            weather_df=weather_df,
            load_csv=load_csv_path,
        )

        res = sim.run(verbose=False)

        fig_ts = make_time_series_plot(res)
        fig_temp = make_temperature_plot(res)
        fig_moist = make_moisture_plot(res)
        fig_load = make_load_plot(res)
        fig_stress = make_stress_plot(res)

        cycles_data = [[
            f"{c['range']:.6f}", f"{c['mean']:.6f}",
            f"{c['count']:.2f}", f"{c['sigma_amp']:.6f}",
            f"{c['Nf']:.3e}", f"{c['damage']:.3e}",
        ] for c in res["damage_list"]]
        cycles_df = pd.DataFrame(
            cycles_data,
            columns=["Range (MPa)", "Mean (MPa)", "Count", "Amplitude (MPa)", "Nf", "Damage"],
        )

        n_samples = len(res["t"])
        total_damage = res["total_damage"]
        n_cycles = len(res["cycles"])
        max_stress = float(np.max(res["sigma_total"]))

        summary = (
            f"### Simulation Summary\n\n"
            f"| Metric | Value |\n"
            f"|---|---|\n"
            f"| Samples Processed | {n_samples} |\n"
            f"| Time Span | {res['t'][-1]:.1f} days |\n"
            f"| Total Fatigue Damage | **{total_damage:.6e}** |\n"
            f"| Rainflow Cycles Detected | {n_cycles} |\n"
            f"| Max Total Stress | {max_stress:.4f} MPa |\n"
            f"| Max Wheel Load | {float(np.max(res['loads_N'])):.2f} N |\n"
        )

        status = f"Simulation complete &mdash; {n_samples} samples processed, damage = {total_damage:.6e}"

        return (fig_ts, fig_temp, fig_moist, fig_load, fig_stress,
                cycles_df, summary, status, sim)

    except Exception as e:
        import traceback
        traceback.print_exc()
        empty = make_empty_figure()
        err_df = pd.DataFrame({"Error": [str(e)]})
        return (empty, empty, empty, empty, empty,
                err_df, f"**Error:** {str(e)}", f"Error: {str(e)}", None)


def export_cycles(sim_state):
    if sim_state is None or not sim_state.results:
        return None, "No simulation data to export."
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    sim_state.export_cycles_csv(path)
    return path, None


# ──────────────────────────────────────────────
# UI LAYOUT
# ──────────────────────────────────────────────

HEADER_HTML = """
<div class="header">
    <h1>Pavement Fatigue Simulator</h1>
    <p>Rainflow-based fatigue analysis of rigid pavements &mdash; synthetic, CSV, or live Open-Meteo climate data</p>
</div>
"""

with gr.Blocks(title="Pavement Fatigue Simulator") as demo:
    gr.HTML(HEADER_HTML)

    sim_state = gr.State(None)

    # ── ROW 1: PARAMETERS ──────────────────────
    with gr.Row(equal_height=False):
        # COL 1: Slab + Material + Fatigue
        with gr.Column(scale=2):
            with gr.Group():
                gr.HTML('<div class="section-title">Slab Geometry</div>')
                with gr.Row():
                    with gr.Column():
                        slab_length = gr.Number(label="Length (m)", value=6.0, minimum=0.1, step=0.1)
                        slab_width = gr.Number(label="Width (m)", value=3.5, minimum=0.1, step=0.1)
                        h = gr.Number(label="Thickness (m)", value=0.35, minimum=0.05, step=0.01)
                    with gr.Column():
                        contact_radius = gr.Number(label="Contact Radius (m)", value=0.12, minimum=0.01, step=0.01)
                        wheel_load = gr.Number(label="Wheel Load (N)", value=200e3, minimum=0, step=10e3)
                        E = gr.Number(label="Elastic Modulus E (Pa)", value=30e9, step=1e9)

            with gr.Group():
                gr.HTML('<div class="section-title">Material Properties</div>')
                with gr.Row():
                    with gr.Column():
                        k = gr.Number(label="Subgrade Modulus k (Pa/m)", value=150e3, step=10e3)
                        nu = gr.Number(label="Poisson Ratio", value=0.15, minimum=0.05, maximum=0.5, step=0.01)
                    with gr.Column():
                        alpha = gr.Number(label="CTE (1/C)", value=10e-6, step=1e-6)
                        beta_shrinkage = gr.Number(label="Shrinkage Coeff", value=3e-4, step=1e-5)

            with gr.Accordion("Fatigue Parameters (Advanced)", open=False):
                with gr.Row():
                    with gr.Column():
                        fatigue_A = gr.Number(label="S-N Coefficient A", value=1e8, step=1e7)
                        fatigue_m = gr.Number(label="S-N Exponent m", value=6.0, step=0.5)
                    with gr.Column():
                        fatigue_sigma_ref = gr.Number(label="Reference Stress (MPa)", value=1.0, step=0.1)

        # COL 2: Weather + Load
        with gr.Column(scale=2):
            with gr.Group():
                gr.HTML('<div class="section-title">Weather Source</div>')
                weather_mode = gr.Radio(
                    ["Synthetic", "Upload CSV", "Open-Meteo API"],
                    value="Synthetic", label="",
                )

                with gr.Group(visible=True) as synthetic_group:
                    with gr.Row():
                        sim_days = gr.Number(label="Simulation Days", value=365 * 3, minimum=30, step=30)
                        daily_steps = gr.Number(label="Samples per Day", value=1, minimum=1, step=1)
                    with gr.Row():
                        mean_temp = gr.Number(label="Mean Temp (C)", value=25.0, step=1)
                        amp_temp = gr.Number(label="Temp Amplitude", value=12.0, step=1)
                    with gr.Row():
                        mean_RH = gr.Number(label="Mean RH", value=0.55, minimum=0, maximum=1, step=0.05)
                        amp_RH = gr.Number(label="RH Amplitude", value=0.18, minimum=0, maximum=0.5, step=0.01)

                with gr.Group(visible=False) as csv_weather_group:
                    weather_csv = gr.File(label="Upload Weather CSV", file_types=[".csv"], file_count="single")

                with gr.Group(visible=False) as openmeteo_group:
                    with gr.Row():
                        lat = gr.Number(label="Latitude", value=28.7041, minimum=-90, maximum=90, step=0.01)
                        lon = gr.Number(label="Longitude", value=77.1025, minimum=-180, maximum=180, step=0.01)
                    days_input = gr.Number(label="Days", value=365, minimum=1, maximum=3650, step=30)

        # COL 3: Controls + Status
        with gr.Column(scale=2):
            with gr.Group():
                gr.HTML('<div class="section-title">Controls</div>')

                load_mode = gr.Radio(
                    ["Constant Load", "Upload CSV"],
                    value="Constant Load", label="Load Source",
                )

                with gr.Group(visible=False) as csv_load_group:
                    load_csv = gr.File(label="Upload Load CSV", file_types=[".csv"], file_count="single")

                run_btn = gr.Button("Run Simulation", variant="primary", size="lg",
                                    elem_classes="run-btn")

                with gr.Group(elem_classes="status-panel"):
                    gr.HTML("<strong>Status</strong>")
                    status_text = gr.Markdown("Ready")
                    n_samples_display = gr.Markdown("Samples: --")
                    damage_display = gr.Markdown("Total Damage: --")

            with gr.Row():
                export_btn = gr.Button("Export Cycles CSV", size="sm",
                                       elem_classes="export-btn")
                export_output = gr.File(label="", show_label=False, visible=False)

    # ── ROW 2: RESULTS ──────────────────────────
    with gr.Tabs(selected=0):
        with gr.Tab("Time Series"):
            ts_plot = gr.Plot(label="Time Series", show_label=False)
        with gr.Tab("Temperature"):
            temp_plot = gr.Plot(label="Temperature", show_label=False)
        with gr.Tab("Moisture"):
            moist_plot = gr.Plot(label="Moisture", show_label=False)
        with gr.Tab("Load"):
            load_plot = gr.Plot(label="Load", show_label=False)
        with gr.Tab("Stress"):
            stress_plot = gr.Plot(label="Stress", show_label=False)
        with gr.Tab("Cycles"):
            cycles_table = gr.Dataframe(label="Rainflow Cycles", wrap=True,
                                        column_widths=["12%", "12%", "10%", "14%", "14%", "14%"])
        with gr.Tab("Summary"):
            summary_text = gr.Markdown("Run a simulation to see results.")

    gr.HTML("<footer>Pavement Fatigue Simulator &mdash; Open source &middot; Rainflow-based analysis</footer>")

    # ──────────────────────────────────────────────
    # EVENT WIRING
    # ──────────────────────────────────────────────

    weather_mode.change(
        fn=lambda mode: (
            gr.update(visible=mode == "Synthetic"),
            gr.update(visible=mode == "Upload CSV"),
            gr.update(visible=mode == "Open-Meteo API"),
        ),
        inputs=weather_mode,
        outputs=[synthetic_group, csv_weather_group, openmeteo_group],
    )

    load_mode.change(
        fn=lambda mode: gr.update(visible=mode == "Upload CSV"),
        inputs=load_mode,
        outputs=csv_load_group,
    )

    click_result = run_btn.click(
        fn=run_simulation,
        inputs=[
            slab_length, slab_width, h, E, nu, alpha, beta_shrinkage, k,
            wheel_load, contact_radius,
            weather_mode, weather_csv, lat, lon, days_input,
            sim_days, daily_steps, mean_temp, amp_temp, mean_RH, amp_RH,
            load_mode, load_csv,
            fatigue_A, fatigue_m, fatigue_sigma_ref,
        ],
        outputs=[
            ts_plot, temp_plot, moist_plot, load_plot, stress_plot,
            cycles_table, summary_text, status_text, sim_state,
        ],
    )

    click_result.then(
        fn=lambda sim: f"Samples: {len(sim.results['t'])}" if sim and sim.results else "Samples: --",
        inputs=sim_state, outputs=n_samples_display,
    )

    click_result.then(
        fn=lambda sim: f"Total Damage: **{sim.results['total_damage']:.6e}**" if sim and sim.results else "Total Damage: --",
        inputs=sim_state, outputs=damage_display,
    )

    export_btn.click(
        fn=export_cycles,
        inputs=sim_state,
        outputs=[export_output, gr.State(None)],
    ).then(
        fn=lambda p: gr.update(value=p, visible=True) if p else gr.update(visible=False),
        inputs=export_output,
        outputs=export_output,
    )


# ──────────────────────────────────────────────
# LAUNCH
# ──────────────────────────────────────────────

if __name__ == "__main__":
    demo.launch(theme=theme, css=CUSTOM_CSS)
