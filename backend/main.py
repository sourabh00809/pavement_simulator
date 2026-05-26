import io
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from src.engine import (
    FatigueSN,
    PavementSimulator,
    load_weather_dataframe,
)
from src.weather_fetcher import fetch_weather_by_days

HERE = Path(__file__).resolve().parent
FRONTEND = HERE.parent / "frontend"

app = FastAPI(title="Pavement Fatigue Simulator")

# ─── Plot helpers ─────────────────────────────

COLORS = {
    "blue": "#3b82f6",
    "red": "#ef4444",
    "green": "#22c55e",
    "orange": "#f97316",
    "purple": "#a855f7",
    "teal": "#14b8a6",
    "dark": "#0f172a",
}


def _to_lists(r):
    """Convert all numpy arrays in a dict to lists for JSON serialization."""
    return {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in r.items()}


def _ts_fig(r):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    r = _to_lists(r)
    t = r["t"]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                        vertical_spacing=0.06)
    fig.add_trace(go.Scatter(x=t, y=r["T_air"], name="T_air",
                   line=dict(color=COLORS["red"], width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["T_top"], name="T_top",
                   line=dict(color=COLORS["orange"], width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["T_bottom"], name="T_bottom",
                   line=dict(color=COLORS["blue"], width=1.5)), row=1, col=1)
    fig.update_yaxes(title_text="Temp (C)", row=1, col=1)

    fig.add_trace(go.Scatter(x=t, y=r["RH"], name="RH (air)",
                   line=dict(color=COLORS["blue"], width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["M_top"], name="M_top",
                   line=dict(color=COLORS["green"], width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["M_bottom"], name="M_bottom",
                   line=dict(color=COLORS["teal"], width=1.5)), row=2, col=1)
    fig.update_yaxes(title_text="Moisture", row=2, col=1)

    fig.add_trace(go.Scatter(x=t, y=r["loads_N"], name="Load (N)",
                   line=dict(color=COLORS["purple"], width=1.5)), row=3, col=1)
    fig.update_yaxes(title_text="Load (N)", row=3, col=1)

    fig.add_trace(go.Scatter(x=t, y=r["sigma_total"], name="sigma_total",
                   line=dict(color=COLORS["dark"], width=2)), row=4, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["sigma_load_only"], name="sigma_load",
                   line=dict(color=COLORS["red"], width=1.5, dash="dash")), row=4, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["sigma_thermal"], name="sigma_thermal",
                   line=dict(color=COLORS["orange"], width=1.5, dash="dot")), row=4, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["sigma_moisture"], name="sigma_moisture",
                   line=dict(color=COLORS["green"], width=1.5, dash="dashdot")), row=4, col=1)
    fig.update_yaxes(title_text="Stress (MPa)", row=4, col=1)
    fig.update_xaxes(title_text="Time (days)", row=4, col=1)
    fig.update_layout(height=550, margin=dict(l=50, r=20, t=30, b=50),
                      hovermode="x unified",
                      template="plotly_white",
                      legend=dict(orientation="h", y=1.02, font_size=10))
    return fig


def _single_fig(r, key, title, ylabel, traces):
    import plotly.graph_objects as go

    r = _to_lists(r)
    t = r["t"]
    fig = go.Figure()
    for k, name, color, dash in traces:
        kw = dict(line=dict(color=color, width=1.5))
        if dash:
            kw["line"]["dash"] = dash
        fig.add_trace(go.Scatter(x=t, y=r[k], name=name, **kw))
    fig.update_layout(title=title, xaxis_title="Time (days)",
                      yaxis_title=ylabel, height=400,
                      margin=dict(l=50, r=20, t=40, b=50),
                      hovermode="x unified", template="plotly_white",
                      legend=dict(orientation="h", y=1.02))
    return fig


def _to_json(fig):
    return fig.to_dict()


def _build_plots(res):
    return {
        "timeSeries": _to_json(_ts_fig(res)),
        "temperature": _to_json(_single_fig(res, "T_air",
            "Temperature Time Series", "Temp (C)",
            [("T_air", "T_air", COLORS["red"], None),
             ("T_top", "T_top", COLORS["orange"], None),
             ("T_bottom", "T_bottom", COLORS["blue"], None)])),
        "moisture": _to_json(_single_fig(res, "RH",
            "Moisture / Relative Humidity", "Moisture",
            [("RH", "RH (air)", COLORS["blue"], None),
             ("M_top", "M_top", COLORS["green"], None),
             ("M_bottom", "M_bottom", COLORS["teal"], None)])),
        "load": _to_json(_single_fig(res, "loads_N",
            "Vehicle Load History", "Load (N)",
            [("loads_N", "Load (N)", COLORS["purple"], None)])),
        "stress": _to_json(_single_fig(res, "sigma_total",
            "Stress Components", "Stress (MPa)",
            [("sigma_total", "sigma_total", COLORS["dark"], None),
             ("sigma_load_only", "sigma_load", COLORS["red"], "dash"),
             ("sigma_thermal", "sigma_thermal", COLORS["orange"], "dot"),
             ("sigma_moisture", "sigma_moisture", COLORS["green"], "dashdot")])),
    }


# ─── JSON encoder for response ────────────────

class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return super().default(obj)


# ─── API ──────────────────────────────────────


@app.post("/api/simulate")
async def simulate(
    slab_length: float = Form(6.0),
    slab_width: float = Form(3.5),
    h: float = Form(0.35),
    E: float = Form(30e9),
    nu: float = Form(0.15),
    alpha: float = Form(10e-6),
    beta_shrinkage: float = Form(3e-4),
    k: float = Form(150e3),
    wheel_load: float = Form(200e3),
    contact_radius: float = Form(0.12),
    weather_mode: str = Form("synthetic"),
    lat: float = Form(28.7041),
    lon: float = Form(77.1025),
    days: int = Form(365),
    sim_days: int = Form(1095),
    daily_steps: int = Form(1),
    mean_temp: float = Form(25),
    amp_temp: float = Form(12),
    mean_RH: float = Form(0.55),
    amp_RH: float = Form(0.18),
    load_mode: str = Form("constant"),
    fatigue_A: float = Form(1e8),
    fatigue_m: float = Form(6.0),
    fatigue_sigma_ref: float = Form(1.0),
    weather_csv: Optional[UploadFile] = File(None),
    load_csv: Optional[UploadFile] = File(None),
):
    try:
        fatigue = FatigueSN(A=fatigue_A, m=fatigue_m,
                            sigma_ref=fatigue_sigma_ref)

        # Weather
        weather_df = None
        weather_path = None
        if weather_mode == "openmeteo":
            df = fetch_weather_by_days(lat, lon, days)
            weather_df = df
        elif weather_mode == "csv" and weather_csv:
            content = await weather_csv.read()
            df = pd.read_csv(io.BytesIO(content))
            weather_df = df

        # Load
        load_path = None
        wheel_loads = None
        if load_mode == "csv" and load_csv:
            content = await load_csv.read()
            fd, load_path = tempfile.mkstemp(suffix=".csv")
            os.close(fd)
            with open(load_path, "wb") as f:
                f.write(content)
        else:
            wheel_loads = [wheel_load]

        sim = PavementSimulator(
            slab_length=slab_length, slab_width=slab_width,
            h=h, E=E, nu=nu, alpha=alpha,
            beta_shrinkage=beta_shrinkage, k=k,
            wheel_loads=wheel_loads, contact_radius=contact_radius,
            sim_days=sim_days, daily_steps=daily_steps,
            mean_temp=mean_temp, amp_temp=amp_temp,
            mean_RH=mean_RH, amp_RH=amp_RH,
            fatigue_sn=fatigue,
            weather_df=weather_df,
            load_csv=load_path,
        )
        res = sim.run(verbose=False)

        # Clean up temp file
        if load_path:
            try:
                os.remove(load_path)
            except Exception:
                pass

        plots = _build_plots(res)

        cycles = [{
            "range": c["range"], "mean": c["mean"],
            "count": c["count"], "amplitude": c["sigma_amp"],
            "nf": c["Nf"], "damage": c["damage"],
        } for c in res["damage_list"]]

        summary = {
            "samples": len(res["t"]),
            "totalDamage": res["total_damage"],
            "nCycles": len(res["cycles"]),
            "maxStress": float(np.max(res["sigma_total"])),
            "minStress": float(np.min(res["sigma_total"])),
            "maxLoad": float(np.max(res["loads_N"])),
            "timeSpan": float(res["t"][-1]),
        }

        body = json.dumps({"ok": True, "plots": plots, "cycles": cycles,
                           "summary": summary}, cls=_NumpyEncoder)
        return Response(content=body, media_type="application/json")

    except Exception as e:
        import traceback
        traceback.print_exc()
        body = json.dumps({"ok": False, "error": str(e)})
        return Response(content=body, media_type="application/json")


@app.post("/api/export")
async def export(data: dict):
    cycles = data.get("cycles", [])
    buf = io.StringIO()
    buf.write("Range(MPa),Mean(MPa),Count,Amplitude(MPa),Nf,Damage\n")
    for c in cycles:
        buf.write(f"{c['range']:.6f},{c['mean']:.6f},{c['count']:.2f},"
                  f"{c['amplitude']:.6f},{c['nf']:.3e},{c['damage']:.3e}\n")
    csv_content = buf.getvalue()
    return Response(content=csv_content, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=cycles.csv"})


# ─── Static files ─────────────────────────────

if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True),
              name="frontend")
