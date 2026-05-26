import os
import tempfile
import gradio as gr
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

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
.gradient-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #0f2640 100%);
    padding: 1.5rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.gradient-header h1 {
    color: #ffffff;
    font-size: 1.6rem;
    font-weight: 600;
    margin: 0 0 0.3rem 0;
    letter-spacing: -0.02em;
}
.gradient-header p {
    color: #94a3b8;
    font-size: 0.9rem;
    margin: 0;
}
.section-card {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    background: #ffffff;
    margin-bottom: 1rem;
}
.section-card .section-title {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b;
    margin: 0 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #2563eb;
}
.run-btn {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 1.05rem !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3) !important;
    transition: all 0.2s ease !important;
}
.run-btn:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.4) !important;
}
.run-btn-container {
    margin-top: 1.5rem;
}
.status-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
    margin-top: 1rem;
    min-height: 120px;
}
footer {
    text-align: center;
    color: #94a3b8;
    font-size: 0.8rem;
    padding: 1.5rem 0 0.5rem 0;
    border-top: 1px solid #e2e8f0;
    margin-top: 2rem;
}
"""

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
        # Build fatigue model
        fatigue = FatigueSN(A=fatigue_A, m=fatigue_m, sigma_ref=fatigue_sigma_ref)

        # Determine weather source
        weather_df = None
        weather_csv_path = None

        if weather_mode == "Open-Meteo API":
            df = fetch_weather_by_days(lat, lon, days)
            weather_df = df
            sim_days_actual = days
        elif weather_mode == "Upload CSV" and weather_csv is not None:
            weather_csv_path = weather_csv
            sim_days_actual = sim_days
        else:
            sim_days_actual = sim_days

        # Determine load source
        load_csv_path = None
        wheel_loads_list = None

        if load_mode == "Upload CSV" and load_csv is not None:
            load_csv_path = load_csv
        else:
            wheel_loads_list = [wheel_load]

        # Build simulator
        sim = PavementSimulator(
            slab_length=slab_length,
            slab_width=slab_width,
            h=h,
            E=E,
            nu=nu,
            alpha=alpha,
            beta_shrinkage=beta_shrinkage,
            k=k,
            wheel_loads=wheel_loads_list,
            contact_radius=contact_radius,
            sim_days=sim_days_actual,
            daily_steps=daily_steps,
            mean_temp=mean_temp,
            amp_temp=amp_temp,
            mean_RH=mean_RH,
            amp_RH=amp_RH,
            fatigue_sn=fatigue,
            weather_csv=weather_csv_path,
            weather_df=weather_df,
            load_csv=load_csv_path,
        )

        res = sim.run(verbose=False)

        # Generate plots
        fig_ts = sim.plot_time_series()
        fig_temp = sim.plot_temperature()
        fig_moist = sim.plot_moisture()
        fig_load = sim.plot_load()
        fig_stress = sim.plot_stress()

        # Build cycle dataframe
        cycles_data = []
        for c in res['damage_list']:
            cycles_data.append([
                f"{c['range']:.6f}",
                f"{c['mean']:.6f}",
                f"{c['count']:.2f}",
                f"{c['sigma_amp']:.6f}",
                f"{c['Nf']:.3e}",
                f"{c['damage']:.3e}",
            ])
        cycles_df = pd.DataFrame(
            cycles_data,
            columns=["Range (MPa)", "Mean (MPa)", "Count", "Amplitude (MPa)", "Nf", "Damage"],
        )

        # Build summary
        n_samples = len(res['t'])
        total_damage = res['total_damage']
        max_stress = float(np.max(res['sigma_total']))
        min_stress = float(np.min(res['sigma_total']))
        mean_stress = float(np.mean(res['sigma_total']))
        n_cycles = len(res['cycles'])
        max_load = float(np.max(res['loads_N']))

        summary = (
            f"**Simulation Summary**\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Samples Processed | {n_samples} |\n"
            f"| Time Span | {res['t'][-1]:.1f} days |\n"
            f"| Total Fatigue Damage | **{total_damage:.6e}** |\n"
            f"| Rainflow Cycles Detected | {n_cycles} |\n"
            f"| Max Total Stress | {max_stress:.4f} MPa |\n"
            f"| Min Total Stress | {min_stress:.4f} MPa |\n"
            f"| Mean Total Stress | {mean_stress:.4f} MPa |\n"
            f"| Max Wheel Load | {max_load:.2f} N |\n"
        )

        return (
            fig_ts, fig_temp, fig_moist, fig_load, fig_stress,
            cycles_df,
            summary,
            f"Simulation complete - {n_samples} samples, damage = {total_damage:.6e}",
            sim,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        empty_plot = plt.figure(figsize=(6, 3))
        empty_df = pd.DataFrame({"Error": [str(e)]})
        return (
            empty_plot, empty_plot, empty_plot, empty_plot, empty_plot,
            empty_df,
            f"**Error:** {str(e)}",
            f"Error: {str(e)}",
            None,
        )


def export_cycles(sim_state):
    if sim_state is None or not sim_state.results:
        return None, "No simulation data to export."
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    sim_state.export_cycles_csv(path)
    return path, f"Exported to {path}"


# ──────────────────────────────────────────────
# UI LAYOUT
# ──────────────────────────────────────────────

HEADER_HTML = """
<div class="gradient-header">
    <h1>Pavement Fatigue Simulator</h1>
    <p>Rainflow-based fatigue analysis of rigid pavements with real climate data</p>
</div>
"""

with gr.Blocks(theme=theme, css=CUSTOM_CSS, title="Pavement Fatigue Simulator") as demo:
    gr.HTML(HEADER_HTML)

    sim_state = gr.State(None)

    # ── ROW 1: PARAMETERS ──────────────────────
    with gr.Row(equal_height=False):
        # ── COLUMN 1: Slab + Fatigue ──
        with gr.Column(scale=3):
            with gr.Group(elem_classes="section-card"):
                gr.HTML('<div class="section-title">Slab Properties</div>')
                with gr.Row():
                    with gr.Column():
                        slab_length = gr.Number(label="Slab Length (m)", value=6.0, minimum=0.1, step=0.1)
                        slab_width = gr.Number(label="Slab Width (m)", value=3.5, minimum=0.1, step=0.1)
                        h = gr.Number(label="Thickness (m)", value=0.35, minimum=0.05, step=0.01)
                        E = gr.Number(label="Elastic Modulus E (Pa)", value=30e9, step=1e9)
                    with gr.Column():
                        k = gr.Number(label="Subgrade Modulus k (Pa/m)", value=150e3, step=10e3)
                        nu = gr.Number(label="Poisson Ratio", value=0.15, minimum=0.05, maximum=0.5, step=0.01)
                        alpha = gr.Number(label="CTE alpha (1/C)", value=10e-6, step=1e-6)
                        beta_shrinkage = gr.Number(label="Shrinkage Coefficient beta", value=3e-4, step=1e-5)

            with gr.Accordion("Fatigue Parameters (Advanced)", open=False):
                with gr.Row():
                    with gr.Column():
                        fatigue_A = gr.Number(label="S-N Coefficient A", value=1e8, step=1e7)
                        fatigue_m = gr.Number(label="S-N Exponent m", value=6.0, step=0.5)
                    with gr.Column():
                        fatigue_sigma_ref = gr.Number(label="Reference Stress (MPa)", value=1.0, step=0.1)

        # ── COLUMN 2: Weather + Load ──
        with gr.Column(scale=3):
            # --- Weather Section ---
            with gr.Group(elem_classes="section-card"):
                gr.HTML('<div class="section-title">Weather Source</div>')
                weather_mode = gr.Radio(
                    ["Synthetic", "Upload CSV", "Open-Meteo API"],
                    value="Synthetic",
                    label="",
                )

                with gr.Group(visible=True) as synthetic_group:
                    with gr.Row():
                        with gr.Column():
                            sim_days = gr.Number(label="Simulation Days", value=365 * 3, minimum=30, step=30)
                            daily_steps = gr.Number(label="Samples per Day", value=1, minimum=1, step=1)
                        with gr.Column():
                            mean_temp = gr.Number(label="Mean Temperature (C)", value=25.0, step=1)
                            amp_temp = gr.Number(label="Temperature Amplitude", value=12.0, step=1)
                    with gr.Row():
                        mean_RH = gr.Number(label="Mean Relative Humidity", value=0.55, minimum=0, maximum=1, step=0.05)
                        amp_RH = gr.Number(label="RH Amplitude", value=0.18, minimum=0, maximum=0.5, step=0.01)

                with gr.Group(visible=False) as csv_weather_group:
                    weather_csv = gr.File(label="Upload Weather CSV", file_types=[".csv"], file_count="single")

                with gr.Group(visible=False) as openmeteo_group:
                    with gr.Row():
                        lat = gr.Number(label="Latitude", value=28.7041, minimum=-90, maximum=90, step=0.01)
                        lon = gr.Number(label="Longitude", value=77.1025, minimum=-180, maximum=180, step=0.01)
                    days_input = gr.Number(label="Days (forward/backward from today)", value=365, minimum=1, maximum=3650, step=30)

            # --- Load Section ---
            with gr.Group(elem_classes="section-card"):
                gr.HTML('<div class="section-title">Load Source</div>')
                load_mode = gr.Radio(
                    ["Constant Load", "Upload CSV"],
                    value="Constant Load",
                    label="",
                )

                with gr.Group(visible=True) as constant_load_group:
                    wheel_load = gr.Number(label="Wheel Load (N)", value=200e3, minimum=0, step=10e3)
                    contact_radius = gr.Number(label="Contact Radius (m)", value=0.12, minimum=0.01, step=0.01)

                with gr.Group(visible=False) as csv_load_group:
                    load_csv = gr.File(label="Upload Load CSV", file_types=[".csv"], file_count="single")

        # ── COLUMN 3: Run + Status ──
        with gr.Column(scale=2):
            with gr.Group(elem_classes="section-card"):
                gr.HTML('<div class="section-title">Simulation Controls</div>')

                run_btn = gr.Button("Run Simulation", variant="primary", size="lg", elem_classes="run-btn")

                with gr.Group(elem_classes="status-box"):
                    status_text = gr.Markdown("Status: Ready")
                    n_samples_display = gr.Markdown("Samples: --")
                    damage_display = gr.Markdown("Total Damage: --")

            with gr.Row():
                export_btn = gr.Button("Export Cycles CSV", size="sm")
                export_output = gr.File(label="Download", visible=True)
            export_status = gr.Markdown("", visible=False)

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
            cycles_table = gr.Dataframe(label="Rainflow Cycles", wrap=True)
        with gr.Tab("Summary"):
            summary_text = gr.Markdown("Run a simulation to see summary.")

    # ── FOOTER ──────────────────────────────────
    gr.HTML("<footer>Pavement Fatigue Simulator &mdash; Rainflow-based analysis</footer>")

    # ──────────────────────────────────────────────
    # EVENT WIRING
    # ──────────────────────────────────────────────

    # Weather mode visibility
    weather_mode.change(
        fn=lambda mode: (
            gr.update(visible=mode == "Synthetic"),
            gr.update(visible=mode == "Upload CSV"),
            gr.update(visible=mode == "Open-Meteo API"),
        ),
        inputs=weather_mode,
        outputs=[synthetic_group, csv_weather_group, openmeteo_group],
    )

    # Load mode visibility
    load_mode.change(
        fn=lambda mode: (
            gr.update(visible=mode == "Constant Load"),
            gr.update(visible=mode == "Upload CSV"),
        ),
        inputs=load_mode,
        outputs=[constant_load_group, csv_load_group],
    )

    # Run simulation
    run_btn.click(
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
            cycles_table,
            summary_text,
            status_text,
            sim_state,
        ],
    ).then(
        fn=lambda sim: (
            f"Samples: {len(sim.results['t'])}" if sim and sim.results else "Samples: --"
        ),
        inputs=sim_state,
        outputs=n_samples_display,
    ).then(
        fn=lambda sim: (
            f"Total Damage: **{sim.results['total_damage']:.6e}**" if sim and sim.results else "Total Damage: --"
        ),
        inputs=sim_state,
        outputs=damage_display,
    )

    # Export
    export_btn.click(
        fn=export_cycles,
        inputs=sim_state,
        outputs=[export_output, export_status],
    )

# ──────────────────────────────────────────────
# LAUNCH
# ──────────────────────────────────────────────

if __name__ == "__main__":
    demo.launch()
