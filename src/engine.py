import math
import csv
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd


# ================================
# ENGINEERING HELPERS
# ================================

def radius_rel_stiffness(E: float, h: float, k: float, nu: float = 0.15) -> float:
    l4 = (E * h**3) / (12.0 * (1.0 - nu**2) * k)
    return float(l4**0.25)


def westergaard_stresses(P: float, h: float, a: float, b: float, l: float) -> Dict[str, float]:
    g = 9.80665
    P_kg = P / g
    h_cm = h * 100.0
    a_cm = a * 100.0
    b_cm = b * 100.0
    l_cm = l * 100.0

    ratio_lb = max(l_cm / max(b_cm, 1e-9), 1e-6)

    sigma_i = 0.316 * P_kg / (h_cm**2) * (4 * math.log10(ratio_lb) + 1.069)
    sigma_e = 0.572 * P_kg / (h_cm**2) * (4 * math.log10(ratio_lb) + 0.359)
    val = (a_cm * math.sqrt(2.0) / max(l_cm, 1e-9))
    sigma_c = 3.0 * P_kg / (h_cm**2) * (1.0 - val**0.6)

    conv = 98066.5
    return {
        'sigma_i_MPa': sigma_i * conv / 1e6,
        'sigma_e_MPa': sigma_e * conv / 1e6,
        'sigma_c_MPa': sigma_c * conv / 1e6,
    }


def bradbury_C_approx(B_over_l: float) -> float:
    x = B_over_l
    if x <= 0.2:
        return 1.05 - 0.1 * x
    elif x <= 1.0:
        return 0.95 - 0.8 * ((x - 0.2) / (1.0 - 0.2))
    else:
        return max(0.1, 0.4 - 0.3 * (x - 1.0))


def thermal_warping_stress_scalar(C, E, alpha, deltaT) -> float:
    return (C * E * alpha * deltaT) / 1e6


def moisture_warping_stress_scalar(C, E, beta, deltaM) -> float:
    return (C * E * beta * deltaM) / 1e6


# ================================
# SEASONAL CLIMATE SIMULATION / CSV LOADER
# ================================

def seasonal_forcing(days, mean_temp, amp_temp, mean_RH, amp_RH,
                     noise_std_temp, noise_std_RH, daily_steps=1):
    n = int(days * daily_steps)
    t = np.linspace(0, days, n)
    omega = 2 * math.pi / 365.0

    T_air = mean_temp + amp_temp * np.sin(omega * t)
    RH = mean_RH + amp_RH * np.cos(omega * t)

    if noise_std_temp > 0:
        T_air += np.random.normal(scale=noise_std_temp, size=n)
    if noise_std_RH > 0:
        RH += np.random.normal(scale=noise_std_RH, size=n)

    RH = np.clip(RH, 0.0, 1.0)
    return t, T_air, RH


def load_weather_csv(path: str):
    df = pd.read_csv(path)

    required = ["time", "temperature_2m", "relative_humidity_2m"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col} in CSV")

    RH = df["relative_humidity_2m"].astype(float).values
    if RH.max() > 1.5:
        RH = RH / 100.0

    T_air = df["temperature_2m"].astype(float).values

    rain = df["rain"].astype(float).values if "rain" in df.columns else np.zeros_like(T_air)
    precip = df["precipitation"].astype(float).values if "precipitation" in df.columns else np.zeros_like(T_air)

    try:
        tcol = df["time"].astype(float).values
        t = tcol - tcol[0]
    except Exception:
        t = np.arange(len(df), dtype=float)

    return t, T_air, RH, rain, precip


def load_weather_dataframe(df: pd.DataFrame):
    required = ["time", "temperature_2m", "relative_humidity_2m"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col} in DataFrame")

    RH = df["relative_humidity_2m"].astype(float).values
    if RH.max() > 1.5:
        RH = RH / 100.0

    T_air = df["temperature_2m"].astype(float).values

    rain = df["rain"].astype(float).values if "rain" in df.columns else np.zeros_like(T_air)
    precip = df["precipitation"].astype(float).values if "precipitation" in df.columns else np.zeros_like(T_air)

    try:
        tcol = df["time"].astype(float).values
        t = tcol - tcol[0]
    except Exception:
        t = np.arange(len(df), dtype=float)

    return t, T_air, RH, rain, precip


def load_load_csv(path: str):
    df = pd.read_csv(path)

    if "axle_load_kN" in df.columns:
        loads_kN = df["axle_load_kN"].astype(float).values
    else:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) == 0:
            raise ValueError("No numeric columns found in load CSV.")
        if len(numeric_cols) >= 2:
            loads_kN = df[numeric_cols[1]].astype(float).values
        else:
            loads_kN = df[numeric_cols[0]].astype(float).values

    loads_N = loads_kN * 1000.0

    if "timestep" in df.columns:
        tcol = df["timestep"].astype(float).values
    elif "time" in df.columns:
        try:
            tcol = df["time"].astype(float).values - float(df["time"].astype(float).values[0])
        except Exception:
            tcol = np.arange(len(loads_N), dtype=float)
    else:
        tcol = np.arange(len(loads_N), dtype=float)

    return tcol, loads_N


def slab_first_order_response(series, tau_days, dt_days):
    y = np.zeros_like(series)
    if len(series) == 0:
        return y
    y[0] = series[0]
    alpha = dt_days / max(tau_days, dt_days * 1e-6)

    for i in range(1, len(series)):
        y[i] = y[i - 1] + alpha * (series[i - 1] - y[i - 1])

    return y


# ================================
# FATIGUE: S-N MODEL
# ================================

@dataclass
class FatigueSN:
    A: float = 1e8
    m: float = 6.0
    sigma_ref: float = 1.0

    def cycles_to_failure(self, sigma_amp):
        if sigma_amp <= 0:
            return float('inf')
        return float(self.A * (self.sigma_ref / sigma_amp) ** self.m)


# ================================
# RAINFLOW ALGORITHM
# ================================

def extract_turning_points(series):
    if len(series) < 3:
        return series.copy()
    tp = [series[0]]
    for i in range(1, len(series) - 1):
        p, c, n = series[i - 1], series[i], series[i + 1]
        if (c > p and c >= n) or (c < p and c <= n):
            tp.append(c)
    tp.append(series[-1])
    return np.array(tp)


def rainflow_count(series):
    tp = extract_turning_points(series)
    S = []
    cycles = []

    for x in tp:
        S.append(float(x))
        while len(S) >= 3:
            x1, x2, x3 = S[-3], S[-2], S[-1]
            r1 = abs(x2 - x1)
            r2 = abs(x3 - x2)
            if r1 <= r2:
                rng = r1
                mean = 0.5 * (x1 + x2)
                cycles.append((rng, mean, 1.0))
                del S[-2]
            else:
                break

    for i in range(len(S) - 1):
        rng = abs(S[i + 1] - S[i])
        mean = 0.5 * (S[i + 1] + S[i])
        cycles.append((rng, mean, 0.5))

    return cycles


def aggregate_cycles(cycles):
    if not cycles:
        return []

    rngs = np.array([c[0] for c in cycles])
    means = np.array([c[1] for c in cycles])
    counts = np.array([c[2] for c in cycles])

    tol = max(1e-6, 1e-3 * max(rngs.max(), 1.0))
    agg = {}

    for r, m, c in zip(rngs, means, counts):
        key = round(r / tol)
        if key in agg:
            agg[key]['rng_sum'] += r * c
            agg[key]['mean_sum'] += m * c
            agg[key]['count'] += c
        else:
            agg[key] = {'rng_sum': r * c, 'mean_sum': m * c, 'count': c}

    result = []
    for v in agg.values():
        avg_rng = v['rng_sum'] / v['count']
        avg_mean = v['mean_sum'] / v['count']
        count = v['count']
        result.append((avg_rng, avg_mean, count))

    return result


# ================================
# FULL PAVEMENT SIMULATOR
# ================================

@dataclass
class PavementSimulator:
    slab_length: float = 6.0
    slab_width: float = 3.5
    h: float = 0.35
    E: float = 30e9
    nu: float = 0.15
    alpha: float = 10e-6
    beta_shrinkage: float = 3e-4
    k: float = 150e3

    wheel_loads: List[float] = field(default_factory=lambda: [200e3])
    contact_radius: float = 0.12
    position: str = 'interior'

    sim_days: int = 365 * 3
    daily_steps: int = 1
    mean_temp: float = 25
    amp_temp: float = 12
    mean_RH: float = 0.55
    amp_RH: float = 0.18

    tau_temp_days_top: float = 2.0
    tau_temp_days_bottom: float = 25.0
    tau_moisture_days_top: float = 14.0
    tau_moisture_days_bottom: float = 180.0

    noise_std_temp: float = 0.0
    noise_std_RH: float = 0.0

    fatigue_sn: FatigueSN = field(default_factory=lambda: FatigueSN())

    weather_csv: Optional[str] = None
    weather_df: Optional[pd.DataFrame] = None
    load_csv: Optional[str] = None

    results: Dict = field(init=False, default_factory=dict)

    def run(self, verbose=True):
        # 1. Weather
        if self.weather_df is not None:
            t_w, T_air, RH, rain, precip = load_weather_dataframe(self.weather_df)
        elif self.weather_csv:
            t_w, T_air, RH, rain, precip = load_weather_csv(self.weather_csv)
        else:
            t_w, T_air, RH = seasonal_forcing(self.sim_days,
                                              self.mean_temp, self.amp_temp,
                                              self.mean_RH, self.amp_RH,
                                              self.noise_std_temp, self.noise_std_RH,
                                              daily_steps=self.daily_steps)
            rain = np.zeros_like(T_air)
            precip = np.zeros_like(T_air)

        dt = float(t_w[1] - t_w[0]) if len(t_w) > 1 else 1.0

        # 2. Loads
        if self.load_csv:
            t_L, loads_N = load_load_csv(self.load_csv)
            if len(loads_N) != len(t_w):
                loads_N = np.interp(t_w, t_L, loads_N, left=0.0, right=0.0)
        else:
            if isinstance(self.wheel_loads, (list, tuple)) and len(self.wheel_loads) > 0:
                P_total_const = float(sum(self.wheel_loads))
            else:
                P_total_const = float(self.wheel_loads)
            loads_N = P_total_const * np.ones_like(t_w)

        # 3. Responses
        T_top = slab_first_order_response(T_air, self.tau_temp_days_top, dt)
        T_bottom = slab_first_order_response(T_air, self.tau_temp_days_bottom, dt)

        M_air = np.array(RH, copy=True)
        if np.any(rain > 0) or np.any(precip > 0):
            max_rain = max(1e-6, float(max(rain.max(), precip.max())))
            add_top = 0.15 * (rain / max_rain) + 0.10 * (precip / max_rain)
            M_air = np.clip(M_air + add_top, 0.0, 1.0)

        M_top = slab_first_order_response(M_air, self.tau_moisture_days_top, dt)
        M_bottom = slab_first_order_response(M_air, self.tau_moisture_days_bottom, dt)

        deltaT = T_top - T_bottom
        deltaM = M_top - M_bottom

        # 4. geometry
        l = radius_rel_stiffness(self.E, self.h, self.k, self.nu)
        a = self.contact_radius
        if a < 1.724 * self.h:
            b = math.sqrt(1.6 * a * a + self.h * self.h) - 0.675 * self.h
        else:
            b = a

        C = bradbury_C_approx(min(self.slab_length, self.slab_width) / l)

        # 5. stresses over time
        n = len(t_w)
        sigma_thermal = np.zeros(n)
        sigma_moisture = np.zeros(n)
        sigma_env = np.zeros(n)
        sigma_load_only = np.zeros(n)
        sigma_total = np.zeros(n)

        use_interior = True
        for i in range(n):
            sigma_thermal[i] = thermal_warping_stress_scalar(C, self.E, self.alpha, deltaT[i])
            sigma_moisture[i] = moisture_warping_stress_scalar(C, self.E, self.beta_shrinkage, deltaM[i])
            sigma_env[i] = sigma_thermal[i] + sigma_moisture[i]

        for i in range(n):
            P = float(loads_N[i])
            if sigma_env[i] < 0:
                if P <= 0:
                    sigma_load = 0.0
                else:
                    wst = westergaard_stresses(P, self.h, a, b, l)
                    sigma_load = wst['sigma_i_MPa'] if use_interior else wst['sigma_i_MPa']
                    sigma_load = max(0.0, sigma_load)
            else:
                if P <= 0:
                    sigma_load = 0.0
                else:
                    halfP = P / 2.0
                    wstL = westergaard_stresses(halfP, self.h, a, b, l)
                    wstR = westergaard_stresses(halfP, self.h, a, b, l)
                    sigL = wstL['sigma_i_MPa'] if use_interior else wstL['sigma_i_MPa']
                    sigR = wstR['sigma_i_MPa'] if use_interior else wstR['sigma_i_MPa']
                    sigL_t = max(0.0, sigL)
                    sigR_t = max(0.0, sigR)
                    sigma_load = sigL_t + sigR_t

            sigma_load_only[i] = sigma_load
            sigma_total[i] = sigma_env[i] + sigma_load_only[i]

        # 6. rainflow & damage
        cycles_raw = rainflow_count(sigma_total)
        cycles = aggregate_cycles(cycles_raw)

        damage_list = []
        total_damage = 0.0
        for rng, mean, count in cycles:
            sigma_amp = rng / 2.0
            if sigma_amp <= 0:
                continue
            Nf = self.fatigue_sn.cycles_to_failure(sigma_amp)
            d = 0 if math.isinf(Nf) or Nf <= 0 else count / Nf
            total_damage += d
            damage_list.append({
                'range': rng,
                'mean': mean,
                'count': count,
                'sigma_amp': sigma_amp,
                'Nf': Nf,
                'damage': d
            })

        self.results = {
            't': t_w,
            'T_air': T_air,
            'RH': RH,
            'rain': rain,
            'precip': precip,
            'T_top': T_top,
            'T_bottom': T_bottom,
            'M_top': M_top,
            'M_bottom': M_bottom,
            'deltaT': deltaT,
            'deltaM': deltaM,
            'sigma_total': sigma_total,
            'sigma_thermal': sigma_thermal,
            'sigma_moisture': sigma_moisture,
            'sigma_load_only': sigma_load_only,
            'loads_N': loads_N,
            'cycles_raw': cycles_raw,
            'cycles': cycles,
            'damage_list': damage_list,
            'total_damage': total_damage,
            'westergaard': None,
            'C': C,
            'l': l,
        }

        if verbose:
            print("Simulation complete.")
            print(f"Samples = {n}")

        return self.results

    def export_cycles_csv(self, filename):
        if not self.results:
            raise RuntimeError("Run the simulation first.")

        with open(filename, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Range(MPa)", "Mean(MPa)", "Count", "Amplitude(MPa)", "Nf", "Damage"])

            for d in self.results['damage_list']:
                w.writerow([
                    d['range'], d['mean'], d['count'],
                    d['sigma_amp'], d['Nf'], d['damage']
                ])

        return filename
