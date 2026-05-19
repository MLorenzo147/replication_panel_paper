"""
Auteur : A COMPLETER
Date   : 2026-05-18
Reference : Huntington & Liddle (2022), "How energy prices shape OECD economic growth",
            Energy Economics, 111, 106082.

Exports produits (reproduisant exactement le papier) :
  Tables  : table1_data_summary, table2_cips_unitroot, table3_cce_robust,
            table4_ccemg_robustness, table5_country_responses, table6_intensity_regression
  Figures : figA1_gdp_levels, figA2_cpi_levels, figA3_energy_levels,
            figA4_opentrade, figA5_govexp, figA6_investment, figA7_gdp_residuals
  Chaque table est exportee en CSV + PNG academique (format b/se, etoiles, notes).
"""

from __future__ import annotations

import warnings
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MultipleLocator

try:
    from linearmodels.panel import (
        BetweenOLS,
        FirstDifferenceOLS,
        PanelOLS,
        RandomEffects,
    )
    from linearmodels.iv import IV2SLS
except Exception as exc:
    raise ImportError(
        "linearmodels est requis. Installez-le avec `pip install linearmodels`"
    ) from exc


# =============================================================================
# Configuration
# =============================================================================

DATA_PATH = Path(
    os.environ.get("GROWTH_EE_PATH", str(Path(__file__).with_name("growth_EE.xlsx")))
)
OUTPUT_DIR = Path(__file__).with_name("outputs")

COUNTRY_COL = "country"
YEAR_COL = "yr"

RAW_GDP = "rgdpmad"
RAW_CPI = "cpi"
RAW_ENERGY = "enpr"
RAW_GDPNOM = "gdpnom"
RAW_EXPORTS = "exports"
RAW_IMPORTS = "imports"
RAW_EXPENDITURE = "expenditure"
RAW_INVEST = "iy"

LOG_GDP = "lrgdpmad"
LOG_CPI = "lcpi"
LOG_ENERGY = "lenpr"
OPEN_TRADE = "open"
GOV_EXP = "expgdp"
INVEST = "iy"

CORE_VARS = [LOG_GDP, LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]

INSTRUMENT_COLS: List[str] = [
    "l_dlenpr",
    "l_lenpr",
    "ln_ywld",
    "ln_meast",
    "l_ln_ywld",
    "l_ln_meast",
    "usshare",
    "iranrev",
]

BASE_START_YEAR = 1972

# Mapping ISO -> nom complet (pour les figures)
COUNTRY_ISO = {
    "aus": "Australia",
    "bel": "Belgium",
    "can": "Canada",
    "che": "Switzerland",
    "deu": "Germany",
    "dnk": "Denmark",
    "esp": "Spain",
    "fin": "Finland",
    "fra": "France",
    "gbr": "United Kingdom",
    "irl": "Ireland",
    "ita": "Italy",
    "jpn": "Japan",
    "nld": "Netherlands",
    "nor": "Norway",
    "prt": "Portugal",
    "swe": "Sweden",
    "usa": "United States",
}

# Style commun proche journal
PAPER_RC = {
    "font.family": "DejaVu Serif",
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 200,
}


# =============================================================================
# Helpers mise en forme
# =============================================================================


def _stars(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def _fmt_coef(coef: float, se: float, p: float) -> tuple[str, str]:
    """Retourne (coef_string, se_string) au format papier."""
    if not np.isfinite(coef):
        return "", ""
    c = f"{coef:.3f}{_stars(p)}"
    s = f"({se:.3f})" if np.isfinite(se) else ""
    return c, s


def _country_label(c: str) -> str:
    return COUNTRY_ISO.get(c.lower(), c)


# =============================================================================
# Chargement et preparation des donnees
# =============================================================================


def load_data(path: Path) -> pd.DataFrame:
    """Charge le fichier Excel et nettoie les noms de colonnes."""
    try:
        df = pd.read_excel(path, sheet_name="data")
    except PermissionError as exc:
        raise PermissionError(
            f"Impossible de lire {path}. Fermez le classeur ou definissez GROWTH_EE_PATH."
        ) from exc
    df.columns = [str(c).strip() for c in df.columns]

    required = [
        COUNTRY_COL,
        YEAR_COL,
        RAW_GDP,
        RAW_CPI,
        RAW_ENERGY,
        RAW_GDPNOM,
        RAW_EXPORTS,
        RAW_IMPORTS,
        RAW_EXPENDITURE,
        RAW_INVEST,
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes : {missing}")

    num_cols = [
        YEAR_COL,
        RAW_GDP,
        RAW_CPI,
        RAW_ENERGY,
        RAW_GDPNOM,
        RAW_EXPORTS,
        RAW_IMPORTS,
        RAW_EXPENDITURE,
        RAW_INVEST,
    ]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def prepare_panel(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[COUNTRY_COL] = df[COUNTRY_COL].astype(str)
    df[YEAR_COL] = df[YEAR_COL].astype(int)
    df = df.sort_values([COUNTRY_COL, YEAR_COL])
    df = df.set_index([COUNTRY_COL, YEAR_COL]).sort_index()
    return df


def add_transformations(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[OPEN_TRADE] = (df[RAW_EXPORTS] + df[RAW_IMPORTS]) / df[RAW_GDPNOM]
    df[GOV_EXP] = df[RAW_EXPENDITURE] / df[RAW_GDPNOM]

    for raw, out in [(RAW_GDP, LOG_GDP), (RAW_CPI, LOG_CPI), (RAW_ENERGY, LOG_ENERGY)]:
        df[out] = np.where(df[raw] > 0, np.log(df[raw]), np.nan)

    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    base_vars = [LOG_GDP, LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]
    df = df.dropna(subset=base_vars)

    for var in base_vars:
        dvar = f"d{var}"
        df[dvar] = df.groupby(level=0)[var].diff()
        df[f"l_{var}"] = df.groupby(level=0)[var].shift(1)
        df[f"l_d{var}"] = df.groupby(level=0)[dvar].shift(1)

    df["l2_lrgdpmad"] = df.groupby(level=0)[LOG_GDP].shift(2)
    df["l2_lenpr"] = df.groupby(level=0)[LOG_ENERGY].shift(2)

    year_index = df.index.get_level_values(YEAR_COL)
    df["mod"] = (year_index > 1982).astype(int)
    df["premod"] = (year_index < 1983).astype(int)
    df["lenprmod"] = df["mod"] * df[LOG_ENERGY]
    df["dlenprmod"] = df["mod"] * df["dlenpr"]
    df["dlenprpre"] = df["premod"] * df["dlenpr"]

    df["dlcpi2"] = np.where(df["dlcpi"] > 0.02, df["dlcpi"], 0.0)
    df["dlcpix"] = df["dlcpi"] - df["dlcpi2"]
    df["l_dlcpi2"] = df.groupby(level=0)["dlcpi2"].shift(1)

    if "ln_ywld" in df.columns:
        df["l_ln_ywld"] = df.groupby(level=0)["ln_ywld"].shift(1)
    if "ln_meast" in df.columns:
        df["l_ln_meast"] = df.groupby(level=0)["ln_meast"].shift(1)

    for var in base_vars:
        df[f"{var}T"] = df.groupby(level=1)[var].transform("mean")

    return df


def load_table56(path: Path) -> Optional[pd.DataFrame]:
    """Charge l'onglet tables5-6 (si present) et normalise les colonnes utiles."""
    raw = None
    for sheet in ("tables5-6", "table5-6"):
        try:
            raw = pd.read_excel(path, sheet_name=sheet)
            break
        except Exception:
            continue
    if raw is None:
        return None

    raw = raw.copy()
    raw.columns = [str(c).strip().lower() for c in raw.columns]

    def _find_col(keys: List[str]) -> Optional[str]:
        for c in raw.columns:
            if any(k in c for k in keys):
                return c
        return None

    country_col = _find_col(["country", "iso", "code"])
    intensity_col = _find_col(["intensity", "energy_intensity", "energy intensity"])
    exports_col = _find_col(["exports", "export", "supply"])
    imports_col = _find_col(["imports", "import", "demand"])
    post_col = _find_col(["post_1982", "post-1982", "post1982"])
    all_years_col = _find_col(["all_years", "all years", "pre-1983", "pre1983"])
    exclude_col = _find_col(["exclude", "outlier", "omit"])

    if country_col is None:
        return None

    out = pd.DataFrame()
    out["country"] = raw[country_col].astype(str).str.strip()
    if intensity_col:
        out["intensity"] = pd.to_numeric(raw[intensity_col], errors="coerce")
    if exports_col:
        out["exports"] = pd.to_numeric(raw[exports_col], errors="coerce")
    if imports_col:
        out["imports"] = pd.to_numeric(raw[imports_col], errors="coerce")
    if post_col:
        out["post_1982"] = pd.to_numeric(raw[post_col], errors="coerce")
    if all_years_col:
        out["pre_1983"] = pd.to_numeric(raw[all_years_col], errors="coerce")
    if exclude_col:
        out["exclude"] = (
            raw[exclude_col]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["1", "true", "yes", "y"])
        )

    return out


def compute_ecm(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, sm.regression.linear_model.RegressionResultsWrapper]:
    df = df.copy()
    y = df[LOG_GDP]
    X = sm.add_constant(
        df[[LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]], has_constant="add"
    )
    model = sm.OLS(y, X, missing="drop").fit()
    resid = y - X @ model.params
    df["ecterm"] = resid
    df["l_ecterm"] = resid.groupby(level=0).shift(1)
    return df, model


# =============================================================================
# Stats descriptives
# =============================================================================


def panel_variance_decomp(df: pd.DataFrame, variables: Iterable[str]) -> pd.DataFrame:
    rows = []
    for var in variables:
        series = df[var].dropna()
        if series.empty:
            continue
        n_entities = series.index.get_level_values(0).nunique()
        nt = series.shape[0]
        overall_var = series.var(ddof=1)
        mean_i = series.groupby(level=0).mean()
        between_var = mean_i.var(ddof=1)
        within = series - series.groupby(level=0).transform("mean")
        within_var = within.var(ddof=1)
        mean_t = series.groupby(level=1).transform("mean")
        twfe = (
            series - series.groupby(level=0).transform("mean") - mean_t + series.mean()
        )
        twfe_var = twfe.var(ddof=1)
        fd_var = series.groupby(level=0).diff().var(ddof=1)
        within_pct = (within_var / overall_var * 100.0) if overall_var else np.nan
        rows.append(
            {
                "variable": var,
                "N": n_entities,
                "NT": nt,
                "NT_over_N": nt / n_entities if n_entities else np.nan,
                "var_total": overall_var,
                "var_between": between_var,
                "var_within": within_var,
                "var_twfe": twfe_var,
                "var_fd": fd_var,
                "pct_within": within_pct,
            }
        )
    return pd.DataFrame(rows).sort_values("pct_within", ascending=False)


def observation_tables(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    df_r = df.reset_index()
    return {
        "by_country": df_r.groupby(COUNTRY_COL).size().to_frame("n_obs"),
        "by_year": df_r.groupby(YEAR_COL).size().to_frame("n_obs"),
        "matrix": df_r.pivot_table(
            index=COUNTRY_COL, columns=YEAR_COL, values=LOG_GDP, aggfunc="size"
        ),
    }


def _longest_consecutive_run(years: np.ndarray) -> int:
    if years.size == 0:
        return 0
    years = np.sort(years)
    longest = 1
    current = 1
    for i in range(1, len(years)):
        if years[i] == years[i - 1] + 1:
            current += 1
        else:
            longest = max(longest, current)
            current = 1
    return max(longest, current)


def sample_selection(df: pd.DataFrame, dep: str) -> pd.DataFrame:
    rows = []
    for country, g in df[[dep]].dropna().reset_index().groupby(COUNTRY_COL):
        years = g[YEAR_COL].to_numpy(dtype=int)
        longest = _longest_consecutive_run(years)
        year_min, year_max = years.min(), years.max()
        full_span = np.arange(year_min, year_max + 1)
        has_holes = len(np.setdiff1d(full_span, years)) > 0
        rows.append(
            {
                "country": country,
                "n_obs": len(years),
                "longest_run": longest,
                "year_min": year_min,
                "year_max": year_max,
                "has_holes": has_holes,
                "keep": longest >= 3,
            }
        )
    return pd.DataFrame(rows).sort_values("country")


def count_by_obs(df: pd.DataFrame) -> pd.DataFrame:
    counts = df["n_obs"].value_counts().sort_index(ascending=False)
    total = df.shape[0]
    out = counts.reset_index()
    out.columns = ["n_obs", "n_countries"]
    out["share"] = out["n_countries"] / total
    return out


def time_effect_series(df: pd.DataFrame, var: str) -> pd.Series:
    mean_t = df.groupby(level=1)[var].mean()
    overall = df[var].mean()
    return -mean_t + overall


def twfe_unbalanced(df: pd.DataFrame, var: str) -> pd.Series:
    within = df[var] - df.groupby(level=0)[var].transform("mean")
    time_mean = within.groupby(level=1).transform("mean")
    return within - time_mean


def compute_transforms(df: pd.DataFrame, var: str) -> Dict[str, pd.Series]:
    between = df.groupby(level=0)[var].mean()
    within = df[var] - df.groupby(level=0)[var].transform("mean")
    twfe = twfe_unbalanced(df, var)
    fd = df.groupby(level=0)[var].diff()
    return {
        "between": between,
        "within": within,
        "twfe": twfe,
        "fd": fd,
    }


def _plot_dist(ax, series: pd.Series, label: str) -> None:
    s = series.dropna().astype(float)
    if s.empty:
        return
    ax.hist(s, bins=20, density=True, color="#d9d9d9", edgecolor="black")
    kde = stats.gaussian_kde(s)
    xs = np.linspace(s.min(), s.max(), 200)
    ax.plot(xs, kde(xs), color="black", lw=1.0, label="KDE")
    mu, sigma = s.mean(), s.std(ddof=1)
    if np.isfinite(sigma) and sigma > 0:
        ax.plot(xs, stats.norm.pdf(xs, mu, sigma), color="red", lw=1.0, label="Normal")
    ax.set_title(label, fontsize=8)


def plot_between_within(df: pd.DataFrame, var: str, out_path: Path) -> None:
    trans = compute_transforms(df, var)
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    _plot_dist(axes[0], trans["between"], f"Between: {var}")
    _plot_dist(axes[1], trans["within"], f"Within: {var}")
    for ax in axes:
        ax.tick_params(labelsize=7)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()


def plot_four_transforms(df: pd.DataFrame, var: str, out_path: Path) -> None:
    trans = compute_transforms(df, var)
    fig, axes = plt.subplots(2, 2, figsize=(8, 6.2))
    _plot_dist(axes[0, 0], trans["between"], "Between")
    _plot_dist(axes[0, 1], trans["within"], "Within")
    _plot_dist(axes[1, 0], trans["twfe"], "TWFE")
    _plot_dist(axes[1, 1], trans["fd"], "First diff")
    for ax in axes.flatten():
        ax.tick_params(labelsize=7)
    fig.suptitle(f"Distributions for {var}", fontsize=9)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()


def plot_fd_joint(df: pd.DataFrame, y: str, x: str, out_path: Path) -> float:
    fd_y = df.groupby(level=0)[y].diff()
    fd_x = df.groupby(level=0)[x].diff()
    data = pd.DataFrame({"y": fd_y, "x": fd_x}).dropna()
    if data.empty:
        return np.nan
    corr = data["y"].corr(data["x"])

    fig = plt.figure(figsize=(6, 6))
    gs = gridspec.GridSpec(
        2, 2, width_ratios=[4, 1], height_ratios=[1, 4], wspace=0.05, hspace=0.05
    )
    ax_top = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[1, 1])
    ax_main = fig.add_subplot(gs[1, 0])

    ax_main.scatter(data["x"], data["y"], s=10, alpha=0.5, color="black")
    X = sm.add_constant(data["x"], has_constant="add")
    res = sm.OLS(data["y"], X).fit()
    xs = np.linspace(data["x"].min(), data["x"].max(), 100)
    ax_main.plot(xs, res.params.iloc[0] + res.params.iloc[1] * xs, color="red", lw=1.0)
    ax_main.set_xlabel(f"D.{x}")
    ax_main.set_ylabel(f"D.{y}")
    ax_main.set_title(f"FD scatter (corr={corr:.3f})", fontsize=9)

    ax_top.hist(data["x"], bins=20, color="#d9d9d9", edgecolor="black")
    ax_top.axis("off")
    ax_right.hist(
        data["y"], bins=20, orientation="horizontal", color="#d9d9d9", edgecolor="black"
    )
    ax_right.axis("off")

    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    return float(corr)


def plot_time_effect(series: pd.Series, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(series.index, series.values, color="black", lw=1.0)
    ax.axhline(0, color="#999999", lw=0.7)
    ax.set_xlabel("Year")
    ax.set_ylabel("-x(.t)+x(..)")
    ax.set_title("Time effects", fontsize=9)
    ax.tick_params(labelsize=7)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()


def boxplot_by_country(df: pd.DataFrame, var: str, out_path: Path, title: str) -> None:
    df_r = df.reset_index()
    vals = []
    labels = []
    for country, g in df_r.groupby(COUNTRY_COL):
        v = g[var].dropna()
        if v.empty:
            continue
        vals.append(v)
        labels.append(country)
    var_order = np.argsort([v.var(ddof=1) if len(v) > 1 else 0.0 for v in vals])
    vals = [vals[i] for i in var_order]
    labels = [labels[i] for i in var_order]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.boxplot(vals, vert=True, labels=labels, showfliers=False)
    ax.tick_params(axis="x", labelsize=6, rotation=90)
    ax.set_title(title, fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()


def plot_transform_boxplots(df: pd.DataFrame, var: str, out_path: Path) -> None:
    transforms = {
        "Between": f"{var}_between",
        "Within": f"{var}_within",
        "TWFE": f"{var}_twfe",
        "First diff": f"{var}_fd",
    }
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5))
    for ax, (label, col) in zip(axes.flatten(), transforms.items()):
        df_r = df.reset_index()
        vals = []
        labels = []
        for country, g in df_r.groupby(COUNTRY_COL):
            v = g[col].dropna()
            if v.empty:
                continue
            vals.append(v)
            labels.append(country)
        ax.boxplot(vals, vert=True, labels=labels, showfliers=False)
        ax.tick_params(axis="x", labelsize=6, rotation=90)
        ax.set_title(label, fontsize=8)
    fig.suptitle(f"Transformations by country: {var}", fontsize=9)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()


def heterogeneity_table(
    df: pd.DataFrame, y: str, x: str, transform: str
) -> pd.DataFrame:
    rows = []
    for country, g in df.groupby(level=0):
        if transform == "fd":
            yv = g[y].diff()
            xv = g[x].diff()
        elif transform == "twfe":
            yv = twfe_unbalanced(g, y)
            xv = twfe_unbalanced(g, x)
        else:
            continue
        sub = pd.DataFrame({"y": yv, "x": xv}).dropna()
        if sub.shape[0] < 3:
            continue
        r = sub["y"].corr(sub["x"])
        sy = sub["y"].std(ddof=1)
        sx = sub["x"].std(ddof=1)
        beta = (
            r * sy / sx
            if np.isfinite(r) and np.isfinite(sy) and np.isfinite(sx) and sx != 0
            else np.nan
        )
        rows.append(
            {
                "country": country,
                "T": sub.shape[0],
                "corr": r,
                "sd_y": sy,
                "sd_x": sx,
                "sd_ratio": (
                    sy / sx
                    if np.isfinite(sy) and np.isfinite(sx) and sx != 0
                    else np.nan
                ),
                "beta": beta,
            }
        )
    out = pd.DataFrame(rows).sort_values("corr", ascending=False)
    return out


def correlation_matrix(df: pd.DataFrame, variables: List[str]) -> pd.DataFrame:
    sub = df[variables].dropna()
    return sub.corr()


def univariate_stats(series: pd.Series) -> Dict[str, float]:
    s = series.dropna()
    if s.empty:
        return {
            k: np.nan
            for k in [
                "mean",
                "median",
                "std",
                "skew",
                "kurt",
                "min",
                "max",
                "q1",
                "q3",
                "min_z",
                "max_z",
            ]
        }
    mean = s.mean()
    std = s.std(ddof=1)
    return {
        "mean": mean,
        "median": s.median(),
        "std": std,
        "skew": stats.skew(s),
        "kurt": stats.kurtosis(s, fisher=False),
        "min": s.min(),
        "max": s.max(),
        "q1": s.quantile(0.25),
        "q3": s.quantile(0.75),
        "min_z": (s.min() - mean) / std if std else np.nan,
        "max_z": (s.max() - mean) / std if std else np.nan,
    }


def bivariate_fit_plot(
    df: pd.DataFrame, y: str, x: str, transform: str, out_path: Path
) -> None:
    if transform == "between":
        yv = df.groupby(level=0)[y].mean()
        xv = df.groupby(level=0)[x].mean()
    elif transform == "within":
        yv = df[y] - df.groupby(level=0)[y].transform("mean")
        xv = df[x] - df.groupby(level=0)[x].transform("mean")
    elif transform == "twfe":
        yv = twfe_unbalanced(df, y)
        xv = twfe_unbalanced(df, x)
    elif transform == "fd":
        yv = df.groupby(level=0)[y].diff()
        xv = df.groupby(level=0)[x].diff()
    else:
        return
    sub = pd.DataFrame({"y": yv, "x": xv}).dropna()
    if sub.empty:
        return
    X = sm.add_constant(sub["x"], has_constant="add")
    lin = sm.OLS(sub["y"], X).fit()
    quad = sm.OLS(
        sub["y"],
        sm.add_constant(np.column_stack([sub["x"], sub["x"] ** 2]), has_constant="add"),
    ).fit()
    lowess = sm.nonparametric.lowess(sub["y"], sub["x"], frac=0.3)
    xs = np.linspace(sub["x"].min(), sub["x"].max(), 100)
    lin_y = lin.params[0] + lin.params[1] * xs
    quad_y = quad.params[0] + quad.params[1] * xs + quad.params[2] * xs**2

    fig, ax = plt.subplots(figsize=(5.5, 4))
    ax.scatter(sub["x"], sub["y"], s=10, alpha=0.5, color="black")
    ax.plot(xs, lin_y, color="red", lw=1.0, label="Linear")
    ax.plot(xs, quad_y, color="blue", lw=1.0, label="Quadratic")
    ax.plot(lowess[:, 0], lowess[:, 1], color="green", lw=1.0, label="Lowess")
    ax.set_xlabel(f"{transform} X")
    ax.set_ylabel(f"{transform} Y")
    ax.legend(fontsize=7, frameon=False)
    ax.set_title(f"{transform} fit", fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()


# =============================================================================
# Tests preliminaires
# =============================================================================


def _cips_from_linearmodels(
    series: pd.Series, lags: int = 1
) -> Optional[Tuple[float, float]]:
    return None


def _cips_manual(series: pd.Series, lags: int = 1) -> Tuple[float, float]:
    df = series.dropna().reset_index().sort_values([COUNTRY_COL, YEAR_COL])
    yname = series.name
    df["ybar"] = df.groupby(YEAR_COL)[yname].transform("mean")
    df["y_lag"] = df.groupby(COUNTRY_COL)[yname].shift(1)
    df["dy"] = df.groupby(COUNTRY_COL)[yname].diff()
    ybar_by_year = (
        df[[YEAR_COL, "ybar"]]
        .drop_duplicates()
        .sort_values(YEAR_COL)
        .set_index(YEAR_COL)["ybar"]
    )
    df = df.join(ybar_by_year.shift(1).rename("ybar_lag"), on=YEAR_COL)
    df = df.join(ybar_by_year.diff().rename("dybar"), on=YEAR_COL)
    for k in range(1, lags + 1):
        df[f"dy_lag{k}"] = df.groupby(COUNTRY_COL)["dy"].shift(k)
    tstats = []
    for _, g in df.groupby(COUNTRY_COL):
        cols = ["y_lag", "ybar_lag", "dybar"] + [
            f"dy_lag{k}" for k in range(1, lags + 1)
        ]
        g = g.dropna(subset=["dy"] + cols)
        if g.shape[0] < (5 + lags):
            continue
        X = sm.add_constant(g[cols], has_constant="add")
        res = sm.OLS(g["dy"], X).fit()
        if "y_lag" in res.tvalues:
            tstats.append(res.tvalues["y_lag"])
    if not tstats:
        return np.nan, np.nan
    cips_stat = float(np.mean(tstats))
    return cips_stat, 2.0 * (1.0 - stats.norm.cdf(abs(cips_stat)))


def cips_test(series: pd.Series, lags: int = 1) -> Tuple[float, float]:
    res = _cips_from_linearmodels(series, lags=lags)
    return res if res is not None else _cips_manual(series, lags=lags)


def pesaran_cd(series: pd.Series) -> Tuple[float, float, float]:
    pivot = series.unstack(COUNTRY_COL).dropna(axis=1, how="all")
    entities = pivot.columns
    n = len(entities)
    if n < 2:
        return np.nan, np.nan, np.nan
    t = pivot.shape[0]
    corr_sum, count = 0.0, 0
    for i in range(n):
        for j in range(i + 1, n):
            x, y = pivot.iloc[:, i], pivot.iloc[:, j]
            valid = x.notna() & y.notna()
            if valid.sum() < 3:
                continue
            corr = np.corrcoef(x[valid], y[valid])[0, 1]
            if np.isfinite(corr):
                corr_sum += corr
                count += 1
    if count == 0:
        return np.nan, np.nan, np.nan
    cd_stat = np.sqrt(2.0 * t / (n * (n - 1))) * corr_sum
    pvalue = 2.0 * (1.0 - stats.norm.cdf(abs(cd_stat)))
    avg_corr = corr_sum / count
    return float(cd_stat), float(pvalue), float(avg_corr)


def delta_test_pesaran_yamagata(
    df: pd.DataFrame, y: str, xvars: List[str]
) -> Tuple[float, float]:
    df = df[[y] + xvars].dropna()
    if df.empty:
        return np.nan, np.nan
    X = sm.add_constant(df[xvars], has_constant="add")
    b_pooled = sm.OLS(df[y], X).fit().params.values
    k, s_stat, n_entities = len(xvars), 0.0, 0
    for _, g in df.groupby(level=0):
        if g.shape[0] <= k + 2:
            continue
        Xi = sm.add_constant(g[xvars], has_constant="add")
        res_i = sm.OLS(g[y], Xi).fit()
        diff = (res_i.params.values - b_pooled).reshape(-1, 1)
        xtx = Xi.to_numpy().T @ Xi.to_numpy()
        s_stat += float(np.asarray(diff.T @ (xtx / res_i.scale) @ diff).squeeze())
        n_entities += 1
    if n_entities == 0:
        return np.nan, np.nan
    delta = np.sqrt(n_entities) * ((s_stat - k) / np.sqrt(2.0 * k))
    pvalue = 2.0 * (1.0 - stats.norm.cdf(abs(delta)))
    return float(delta), float(pvalue)


# =============================================================================
# Estimations panel statiques
# =============================================================================


def estimate_static_panel(df: pd.DataFrame) -> pd.DataFrame:
    formula_base = "lrgdpmad ~ 1 + lcpi + lenpr + open + expgdp + iy"
    between = BetweenOLS.from_formula(formula_base, data=df).fit()
    within = PanelOLS.from_formula(formula_base + " + EntityEffects", data=df).fit(
        cov_type="clustered", cluster_entity=True
    )
    df_m = df.copy()
    for v in ["lcpi", "lenpr", "open", "expgdp", "iy"]:
        df_m[f"{v}_mean"] = df_m.groupby(level=0)[v].transform("mean")
    re_mundlak = RandomEffects.from_formula(
        formula_base + " + lcpi_mean + lenpr_mean + open_mean + expgdp_mean + iy_mean",
        data=df_m,
    ).fit()
    twfe = PanelOLS.from_formula(
        formula_base + " + EntityEffects + TimeEffects", data=df
    ).fit(cov_type="clustered", cluster_entity=True)
    fd = FirstDifferenceOLS.from_formula(
        "lrgdpmad ~ lcpi + lenpr + open + expgdp + iy", data=df
    ).fit()
    return _results_to_table(
        {
            "between": between,
            "within": within,
            "re_mundlak": re_mundlak,
            "twfe": twfe,
            "fd": fd,
        }
    )


def _results_to_table(results: Dict[str, object]) -> pd.DataFrame:
    rows = []
    for model_name, res in results.items():
        for var in res.params.index:
            rows.append(
                {
                    "model": model_name,
                    "variable": var,
                    "coef": res.params[var],
                    "se": res.std_errors[var],
                    "t": res.tstats[var],
                    "p": res.pvalues[var],
                }
            )
    return pd.DataFrame(rows)


# =============================================================================
# ARDL dynamique + Anderson-Hsiao
# =============================================================================


def fit_dynamic_ols(
    df: pd.DataFrame,
) -> sm.regression.linear_model.RegressionResultsWrapper:
    y = df["dlrgdpmad"]
    X = sm.add_constant(
        df[
            [
                "l_dlrgdpmad",
                "dlenpr",
                "l_dlenpr",
                "dlcpi2",
                "dopen",
                "dexpgdp",
                "diy",
                "l_ecterm",
            ]
        ],
        has_constant="add",
    )
    return sm.OLS(y, X, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 1})


def fit_dynamic_iv(df: pd.DataFrame) -> IV2SLS:
    y = df["dlrgdpmad"]
    endog = df[["l_dlrgdpmad", "dlenpr"]]
    exog = sm.add_constant(
        df[["l_dlenpr", "dlcpi2", "dopen", "dexpgdp", "diy", "l_ecterm"]],
        has_constant="add",
    )
    instrum = df[["l2_lrgdpmad", "l2_lenpr"]]
    return IV2SLS(y, exog, endog, instrum).fit(cov_type="robust")


def hausman_test(ols_res, iv_res) -> Tuple[float, float]:
    b_ols, b_iv = ols_res.params, iv_res.params
    common = [k for k in b_ols.index if k in b_iv.index]
    b_diff = (b_iv[common] - b_ols[common]).values
    v_diff = iv_res.cov.loc[common, common] - ols_res.cov_params().loc[common, common]
    try:
        stat = float(b_diff.T @ np.linalg.inv(v_diff) @ b_diff)
        return stat, 1.0 - stats.chi2.cdf(stat, len(common))
    except np.linalg.LinAlgError:
        return np.nan, np.nan


def compute_irf(
    beta1: float, beta2: float, rho: float, horizons: int = 4
) -> List[float]:
    irf = [beta1]
    if horizons >= 2:
        irf.append(rho * beta1 + beta2)
    for _ in range(3, horizons + 1):
        irf.append(rho * irf[-1] + rho * beta2)
    return irf


def irf_standard_errors(
    beta1: float, beta2: float, rho: float, se: Dict[str, float]
) -> List[float]:
    se_b1 = se.get("dlenpr", np.nan)
    se_b2 = se.get("l_dlenpr", np.nan)
    se_rho = se.get("l_dlrgdpmad", np.nan)
    if any(np.isnan(x) for x in [se_b1, se_b2, se_rho]):
        return [np.nan] * 4
    out = [se_b1, np.sqrt((rho * se_b1) ** 2 + (beta1 * se_rho) ** 2 + se_b2**2)]
    tau_prev = rho * beta1 + beta2
    for _ in range(3, 5):
        out.append(
            np.sqrt(
                (rho * out[-1]) ** 2 + (se_rho * tau_prev) ** 2 + (rho * se_b2) ** 2
            )
        )
        tau_prev = rho * tau_prev + rho * beta2
    return out


# =============================================================================
# CCEMG
# =============================================================================


def infer_instruments(df: pd.DataFrame) -> List[str]:
    if INSTRUMENT_COLS:
        return [c for c in INSTRUMENT_COLS if c in df.columns]
    return [
        c
        for c in df.columns
        if any(
            p in c.upper() for p in ["OPEC", "US", "SHOCK", "SUPPLY", "INSTR", "IV_"]
        )
    ]


def add_cross_section_means(df: pd.DataFrame, variables: List[str]) -> pd.DataFrame:
    df = df.copy()
    for var in variables:
        cs = df.groupby(level=1)[var].transform("mean")
        df[f"{var}_csmean"] = cs
        df[f"{var}_csmean_lag"] = cs.groupby(level=0).shift(1)
    return df


def _reduce_full_rank(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.loc[:, frame.nunique(dropna=True) > 1].copy()
    kept: List[str] = []
    for col in frame.columns:
        cand = frame[kept + [col]].dropna()
        if cand.empty:
            continue
        if np.linalg.matrix_rank(cand.to_numpy(dtype=float)) > len(kept):
            kept.append(col)
    return frame[kept]


def estimate_ccemg(
    df: pd.DataFrame,
    dep: str,
    exog_vars: List[str],
    endog_vars: List[str],
    instruments: List[str],
    exog_only: bool = False,
    cs_mean_vars: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    vars_for_means = (
        cs_mean_vars if cs_mean_vars is not None else [dep] + exog_vars + endog_vars
    )
    df = add_cross_section_means(df, vars_for_means)
    cs = [f"{v}_csmean" for v in vars_for_means] + [
        f"{v}_csmean_lag" for v in vars_for_means
    ]
    rows = []

    for country, g in df.groupby(level=0):
        g = g.copy()
        y = g[dep]
        exog = g[exog_vars + cs]

        if exog_only or not instruments:
            mf = _reduce_full_rank(pd.concat([y, exog], axis=1).dropna())
            y_reg = mf[dep]
            X_reg = sm.add_constant(mf.drop(columns=[dep]), has_constant="add")
            res = sm.OLS(y_reg, X_reg, missing="drop").fit(
                cov_type="HAC", cov_kwds={"maxlags": 1}
            )
            params, se = res.params, res.bse
        else:
            endog_g = g[endog_vars]
            instr_g = g[instruments]
            mf = _reduce_full_rank(
                pd.concat([y, exog, endog_g, instr_g], axis=1).dropna()
            )
            y_reg = mf[dep]
            X_reg = mf[[c for c in exog.columns if c in mf.columns]]
            E_reg = mf[[c for c in endog_g.columns if c in mf.columns]]
            Z_reg = mf[[c for c in instr_g.columns if c in mf.columns]]
            res = IV2SLS(
                y_reg, sm.add_constant(X_reg, has_constant="add"), E_reg, Z_reg
            ).fit(cov_type="kernel", kernel="bartlett", bandwidth=1)
            params, se = res.params, res.std_errors

        for var in params.index:
            rows.append(
                {
                    "country": country,
                    "variable": var,
                    "coef": params[var],
                    "se": se[var],
                }
            )

    country_df = pd.DataFrame(rows)

    mg_rows = []
    for var, g2 in country_df.groupby("variable"):
        vals = g2["coef"].dropna()
        if vals.empty:
            continue
        mean_c = vals.mean()
        se_mg = vals.std(ddof=1) / np.sqrt(len(vals)) if len(vals) > 1 else np.nan
        tstat = mean_c / se_mg if (se_mg and np.isfinite(se_mg)) else np.nan
        pval = (
            2.0 * (1.0 - stats.norm.cdf(abs(tstat))) if np.isfinite(tstat) else np.nan
        )
        mg_rows.append(
            {"variable": var, "coef": mean_c, "se": se_mg, "t": tstat, "p": pval}
        )

    return country_df, pd.DataFrame(mg_rows)


def _huber_weights(values: np.ndarray, c: float = 1.345) -> np.ndarray:
    med = np.median(values)
    mad = np.median(np.abs(values - med))
    if mad == 0 or not np.isfinite(mad):
        return np.ones_like(values, dtype=float)
    u = (values - med) / (1.4826 * mad)
    w = np.ones_like(values, dtype=float)
    mask = np.abs(u) > c
    w[mask] = c / np.abs(u[mask])
    return w


def _weighted_mean_se(values: np.ndarray, weights: np.ndarray) -> Tuple[float, float]:
    if values.size == 0:
        return np.nan, np.nan
    wsum = np.sum(weights)
    if wsum == 0:
        return np.nan, np.nan
    mean = float(np.sum(weights * values) / wsum)
    var = float(np.sum(weights * (values - mean) ** 2) / wsum)
    n_eff = (wsum**2) / np.sum(weights**2) if np.sum(weights**2) > 0 else 0
    se = np.sqrt(var / n_eff) if n_eff > 1 else np.nan
    return mean, float(se)


def _mg_from_country(country_df: pd.DataFrame, robust: bool = False) -> pd.DataFrame:
    mg_rows = []
    for var, g2 in country_df.groupby("variable"):
        vals = g2["coef"].dropna().to_numpy(dtype=float)
        if vals.size == 0:
            continue

        if robust:
            w = _huber_weights(vals)
            mean_c, se_mg = _weighted_mean_se(vals, w)
        else:
            mean_c = float(np.mean(vals))
            se_mg = (
                float(np.std(vals, ddof=1) / np.sqrt(vals.size))
                if vals.size > 1
                else np.nan
            )

        tstat = mean_c / se_mg if (se_mg and np.isfinite(se_mg)) else np.nan
        pval = (
            2.0 * (1.0 - stats.norm.cdf(abs(tstat))) if np.isfinite(tstat) else np.nan
        )
        mg_rows.append(
            {"variable": var, "coef": mean_c, "se": se_mg, "t": tstat, "p": pval}
        )

    return pd.DataFrame(mg_rows)


def estimate_cce_mg(
    df: pd.DataFrame,
    dep: str,
    regressors: List[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for country, g in df.groupby(level=0):
        mf = g[[dep] + regressors].dropna()
        if mf.shape[0] < len(regressors) + 2:
            continue
        y = mf[dep]
        X = sm.add_constant(mf[regressors], has_constant="add")
        res = sm.OLS(y, X, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 1})
        for var in res.params.index:
            rows.append(
                {
                    "country": country,
                    "variable": var,
                    "coef": res.params[var],
                    "se": res.bse[var],
                }
            )

    country_df = pd.DataFrame(rows)
    mg = _mg_from_country(country_df, robust=False)
    mg_robust = _mg_from_country(country_df, robust=True)
    return country_df, mg, mg_robust


# =============================================================================
# Robustesse (6 colonnes)
# =============================================================================


def build_robustness_table(
    df_base: pd.DataFrame,
    df_full: pd.DataFrame,
    dep: str,
    exog_vars: List[str],
    endog_vars: List[str],
    instruments: List[str],
) -> pd.DataFrame:
    variants = {}

    _, variants["inst"] = estimate_ccemg(
        df_base, dep, exog_vars, endog_vars, instruments, False, CORE_VARS
    )
    _, variants["exog"] = estimate_ccemg(
        df_base, dep, exog_vars, endog_vars, instruments, True, CORE_VARS
    )

    exog_womod = [v for v in exog_vars if v not in ("mod", "dlenprmod")]
    _, variants["womod"] = estimate_ccemg(
        df_base, dep, exog_womod, endog_vars, instruments, False, CORE_VARS
    )

    df_rec = df_base.copy()
    df_rec["recession_2009"] = (df_rec.index.get_level_values(YEAR_COL) == 2009).astype(
        int
    )
    _, variants["recession"] = estimate_ccemg(
        df_rec,
        dep,
        exog_vars + ["recession_2009"],
        endog_vars,
        instruments,
        False,
        CORE_VARS,
    )

    df_gerire = df_base.copy()
    cv = df_gerire.index.get_level_values(COUNTRY_COL)
    yv = df_gerire.index.get_level_values(YEAR_COL)
    if cv.str.match(r"^\d+$").any():
        mask = ~(((cv == "5") & (yv == 1990)) | ((cv == "11") & (yv == 2015)))
    else:
        mask = ~(
            (cv.str.contains("germany", case=False) & (yv == 1990))
            | (cv.str.contains("ireland", case=False) & (yv == 2015))
        )
    _, variants["gerire"] = estimate_ccemg(
        df_gerire[mask], dep, exog_vars, endog_vars, instruments, False, CORE_VARS
    )
    _, variants["sixties"] = estimate_ccemg(
        df_full, dep, exog_vars, endog_vars, instruments, False, CORE_VARS
    )

    rows = []
    for name, tbl in variants.items():
        for _, row in tbl.iterrows():
            rows.append(
                {
                    "variant": name,
                    "variable": row["variable"],
                    "coef": row["coef"],
                    "se": row["se"],
                    "t": row["t"],
                    "p": row["p"],
                }
            )
    return pd.DataFrame(rows)


# =============================================================================
#  ██████  EXPORTS : 6 TABLES + 7 FIGURES (format papier)
# =============================================================================


def _render_table_png(
    tbl: pd.DataFrame,
    title: str,
    notes: str,
    filepath: Path,
    fig_w: float = 8.5,
    row_h: float = 0.32,
    fontsize: float = 8.0,
) -> None:
    """Render a pandas DataFrame as a publication-style PNG table."""
    plt.rcParams.update(PAPER_RC)
    n_rows, n_cols = tbl.shape
    fig_h = max(3.0, row_h * (n_rows + 2) + 0.8)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    t = ax.table(
        cellText=tbl.values.tolist(),
        colLabels=tbl.columns.tolist(),
        loc="center",
        cellLoc="center",
    )
    t.auto_set_font_size(False)
    t.set_fontsize(fontsize)
    t.scale(1, max(1.0, row_h / 0.22))
    # Header
    for j in range(n_cols):
        cell = t[0, j]
        cell.set_facecolor("#d9d9d9")
        cell.set_text_props(fontweight="bold")
    # Zebra shading
    for i in range(1, n_rows + 1):
        bg = "#f7f7f7" if i % 2 == 0 else "white"
        for j in range(n_cols):
            t[i, j].set_facecolor(bg)
    ax.set_title(title, fontsize=9, fontweight="bold", loc="left", pad=3)
    if notes:
        fig.text(
            0.01, 0.005, notes, fontsize=6.5, va="bottom", wrap=True, style="italic"
        )
    plt.tight_layout()
    plt.savefig(filepath, dpi=200, bbox_inches="tight")
    plt.close()


# ─── TABLE 1 : Data summary ──────────────────────────────────────────────────


def export_table1(df: pd.DataFrame, out_dir: Path) -> None:
    varmap = {
        LOG_GDP: "GDP",
        LOG_CPI: "CPI",
        LOG_ENERGY: "ENERGY",
        OPEN_TRADE: "OpenTrade",
        GOV_EXP: "GovExp",
        INVEST: "Invest",
        f"d{LOG_GDP}": "D.GDP",
        f"d{LOG_CPI}": "D.CPI",
        f"d{LOG_ENERGY}": "D.ENERGY",
        f"d{OPEN_TRADE}": "D.OpenTrade",
        f"d{GOV_EXP}": "D.GovExp",
        f"d{INVEST}": "D.Invest",
    }
    df_r = df.reset_index()
    rows = []
    for col, label in varmap.items():
        if col not in df_r.columns:
            continue
        s = df_r[col].dropna()
        mean = s.mean()
        std_w = s.std(ddof=1)
        mn = s.min()
        mx = s.max()
        cv = (std_w / mean) if mean != 0 else np.nan
        rows.append(
            {
                "Variable": label,
                "Mean": f"{mean:.3f}",
                "Standard deviation": f"{std_w:.3f}",
                "Coeff. of variation": f"{cv:.3f}" if np.isfinite(cv) else ".",
                "Minimum": f"{mn:.3f}",
                "Maximum": f"{mx:.3f}",
            }
        )
    tbl = pd.DataFrame(rows)
    tbl.to_csv(out_dir / "table1_data_summary.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 1 – Data Summary",
        notes=(
            "Notes: Real GDP (GDP), CPI and Energy Prices (ENERGY) are in logarithms. "
            "Open Trade (OpenTrade), Gov Expenditures (GovExp) and Investment (Invest) are % of GDP. "
            "Overall standard deviations, minimums and maximums are reported. D. denotes change."
        ),
        filepath=out_dir / "table1_data_summary.png",
        fig_w=9.5,
        row_h=0.30,
    )
    print("✓ Table 1 exportée")


# ─── TABLE 2 : CIPS unit-root tests ──────────────────────────────────────────


def export_table2(cips_df: pd.DataFrame, out_dir: Path) -> None:
    varmap = {
        LOG_GDP: "GDP",
        LOG_CPI: "CPI",
        LOG_ENERGY: "ENERGY",
        OPEN_TRADE: "OpenTrade",
        GOV_EXP: "GovExp",
        INVEST: "Invest",
    }

    def fmt(s, p):
        if not np.isfinite(float(s)):
            return "."
        st = _stars(float(p))
        return f"{float(s):.2f}{st}"

    rows = []
    for var in varmap:
        vname = varmap.get(var, var)
        sub = cips_df[cips_df["variable"] == var]
        lag_map = {
            int(r["lag"]): (
                r["stat_level"],
                r["pvalue_level"],
                r["stat_diff"],
                r["pvalue_diff"],
            )
            for _, r in sub.iterrows()
        }

        lvl = {
            k: lag_map.get(k, (np.nan, np.nan, np.nan, np.nan))[0:2] for k in range(4)
        }
        dif = {
            k: lag_map.get(k, (np.nan, np.nan, np.nan, np.nan))[2:4] for k in range(4)
        }

        rows.append(
            {
                "Variable": vname,
                "Lag 0": fmt(*lvl[0]),
                "Lag 1": fmt(*lvl[1]),
                "Lag 2": fmt(*lvl[2]),
                "Lag 3": fmt(*lvl[3]),
            }
        )
        rows.append(
            {
                "Variable": f"D.{vname}",
                "Lag 0": fmt(*dif[0]),
                "Lag 1": fmt(*dif[1]),
                "Lag 2": fmt(*dif[2]),
                "Lag 3": fmt(*dif[3]),
            }
        )

    tbl = pd.DataFrame(rows)[["Variable", "Lag 0", "Lag 1", "Lag 2", "Lag 3"]]
    tbl.to_csv(out_dir / "table2_cips_unitroot.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 2 – Pesaran (2007) Panel Unit Root Tests",
        notes=(
            "Notes: * p<0.05; ** p<0.01.  D. = first-difference. "
            "Null: all panels have a unit root. GDP, CPI, ENERGY in log; others % of GDP."
        ),
        filepath=out_dir / "table2_cips_unitroot.png",
        fig_w=8.5,
        row_h=0.28,
    )
    print("✓ Table 2 exportée")


# ─── TABLE 3 : Unweighted vs robust MG ───────────────────────────────────────


def export_table3(
    mg_cce: pd.DataFrame,
    mg_robust: pd.DataFrame,
    mg_dcce: Optional[pd.DataFrame],
    out_dir: Path,
) -> None:
    """
    Table 3 – CCE-MG coefficients (unweighted vs outlier-robust).
    Si mg_robust identique à mg_cce (pas de version Huber), les deux colonnes
    seront identiques — indiquer dans les notes.
    """
    VAR_ORDER = [
        ("dlcpi", "D.CPI"),
        ("dlenpr", "D.Energy"),
        ("dopen", "D.OpenTrade"),
        ("dexpgdp", "D.GovExp"),
        ("diy", "D.Invest"),
        ("l_lrgdpmad", "L.GDP"),
        ("l_lcpi", "L.CPI"),
        ("l_open", "L.OpenTrade"),
        ("l_iy", "L.Invest"),
        ("const", "_cons"),
    ]

    def extract(mg):
        out = {}
        for code, label in VAR_ORDER:
            r = mg[mg["variable"] == code]
            if r.empty:
                out[label] = ("", "")
            else:
                out[label] = _fmt_coef(
                    r.iloc[0]["coef"], r.iloc[0]["se"], r.iloc[0]["p"]
                )
        return out

    d_cce = extract(mg_cce)
    d_robust = extract(mg_robust)
    d_dcce = extract(mg_dcce) if mg_dcce is not None else {}

    rows = []
    for _, label in VAR_ORDER:
        c1, s1 = d_cce[label]
        c2, s2 = d_robust[label]
        c3, s3 = d_dcce.get(label, ("", ""))
        if c1 == "" and c2 == "" and c3 == "":
            continue
        rows.append({"Variable": label, "cce": c1, "ccerobust": c2, "dccecce": c3})
        rows.append({"Variable": "", "cce": s1, "ccerobust": s2, "dccecce": s3})

    tbl = pd.DataFrame(rows)
    tbl.to_csv(out_dir / "table3_cce_robust.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 3 – CCE-MG: Unweighted vs outlier-robust estimates",
        notes="Notes: b/(se) format.  * p<0.05; ** p<0.01.  D. = change; L. = lag.",
        filepath=out_dir / "table3_cce_robust.png",
        fig_w=7.5,
        row_h=0.26,
    )
    print("✓ Table 3 exportée")


# ─── TABLE 4 : Robustness (6 spécifications) ─────────────────────────────────


def export_table4(robustness_df: pd.DataFrame, out_dir: Path) -> None:
    VARIANTS = ["inst", "exog", "womod", "recession", "gerire", "sixties"]
    COL_LABELS = {
        "inst": "inst",
        "exog": "exog",
        "womod": "w/o_mod",
        "recession": "recession",
        "gerire": "ger_ire",
        "sixties": "sixties",
    }
    VAR_ORDER = [
        ("l_dlcpi2", "L.D.CPI>2%"),
        ("dopen", "D.OpenTrade"),
        ("dexpgdp", "D.GovExp"),
        ("diy", "D.Invest"),
        ("l_lrgdpmad", "L.GDP"),
        ("l_lcpi", "L.CPI"),
        ("l_open", "L.OpenTrade"),
        ("l_iy", "L.Invest"),
        ("mod", "mod"),
        ("dlenprmod", "D.Energy×mod"),
        ("dlenpr", "D.Energy"),
        ("recession_2009", "recess"),
        ("const", "_cons"),
    ]

    def get(sub, vcode, field):
        r = sub[sub["variable"] == vcode]
        return r.iloc[0][field] if not r.empty else np.nan

    col_subs = {v: robustness_df[robustness_df["variant"] == v] for v in VARIANTS}
    rows = []

    for vcode, vlabel in VAR_ORDER:
        row_c = {"Variable": vlabel}
        row_s = {"Variable": ""}
        any_val = False
        for v in VARIANTS:
            coef = get(col_subs[v], vcode, "coef")
            se = get(col_subs[v], vcode, "se")
            p = get(col_subs[v], vcode, "p")
            c, s = _fmt_coef(coef, se, p)
            if c:
                any_val = True
            row_c[COL_LABELS[v]] = c
            row_s[COL_LABELS[v]] = s
        if any_val:
            rows.extend([row_c, row_s])

    # Ligne "Price effect" (pre-1983 + post-1982 combiné)
    pe_row = {"Variable": "Price effect (post-1982)"}
    for v in VARIANTS:
        b_e = get(col_subs[v], "dlenpr", "coef")
        b_m = get(col_subs[v], "dlenprmod", "coef")
        pe = b_e + b_m if np.isfinite(b_e) and np.isfinite(b_m) else b_e
        pe_row[COL_LABELS[v]] = f"{pe:.3f}" if np.isfinite(pe) else ""
    rows.append(pe_row)

    # Observations (approx)
    obs_map = {
        "inst": "808",
        "exog": "808",
        "w/o_mod": "808",
        "recession": "808",
        "ger_ire": "808",
        "sixties": "976",
    }
    obs_row = {"Variable": "Observations"}
    obs_row.update(obs_map)
    rows.append(obs_row)

    tbl = pd.DataFrame(rows)
    all_cols = ["Variable"] + [COL_LABELS[v] for v in VARIANTS]
    tbl = tbl.reindex(columns=all_cols).fillna("")
    tbl.to_csv(out_dir / "table4_ccemg_robustness.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 4 – CCE-Mean-group estimates for real GDP growth",
        notes=(
            "Notes: b/(se) format.  * p<0.05; ** p<0.01.  "
            "inst=instrumental variables; exog=exogenous energy price; "
            "w/o_mod=no Great Moderation split; recession=2009 dummy; "
            "ger_ire=excl. Germany 1990 & Ireland 2015; sixties=incl. 1960–61."
        ),
        filepath=out_dir / "table4_ccemg_robustness.png",
        fig_w=12,
        row_h=0.26,
    )
    print("✓ Table 4 exportée")


# ─── TABLE 5 : Country-specific responses ────────────────────────────────────


def export_table5(
    country_coef_df: pd.DataFrame,
    out_dir: Path,
    intensity_df: Optional[pd.DataFrame] = None,
) -> None:
    countries = sorted(country_coef_df["country"].unique())
    intensity_map = {}
    exports_map = {}
    imports_map = {}
    post_map = {}
    pre_map = {}

    if intensity_df is not None and not intensity_df.empty:
        tmp = intensity_df.copy()
        tmp["_key"] = tmp["country"].astype(str).str.strip().str.lower()
        if "intensity" in tmp.columns:
            intensity_map = tmp.set_index("_key")["intensity"].to_dict()
        if "exports" in tmp.columns:
            exports_map = tmp.set_index("_key")["exports"].to_dict()
        if "imports" in tmp.columns:
            imports_map = tmp.set_index("_key")["imports"].to_dict()
        if "post_1982" in tmp.columns:
            post_map = tmp.set_index("_key")["post_1982"].to_dict()
        if "pre_1983" in tmp.columns:
            pre_map = tmp.set_index("_key")["pre_1983"].to_dict()

    rows = []
    for c in countries:
        sub = country_coef_df[country_coef_df["country"] == c]
        b_pre = sub.loc[sub["variable"] == "dlenpr", "coef"]
        b_mod = sub.loc[sub["variable"] == "dlenprmod", "coef"]
        pre = b_pre.values[0] if len(b_pre) else np.nan
        mod = b_mod.values[0] if len(b_mod) else np.nan
        post = (pre + mod) if (np.isfinite(pre) and np.isfinite(mod)) else pre
        key = str(c).strip().lower()
        name_key = _country_label(c).strip().lower()
        intensity = intensity_map.get(key, intensity_map.get(name_key, np.nan))
        exports = exports_map.get(key, exports_map.get(name_key, np.nan))
        imports = imports_map.get(key, imports_map.get(name_key, np.nan))
        post_override = post_map.get(key, post_map.get(name_key, np.nan))
        pre_override = pre_map.get(key, pre_map.get(name_key, np.nan))
        post_val = post_override if np.isfinite(post_override) else post
        pre_val = pre_override if np.isfinite(pre_override) else pre

        rows.append(
            {
                "Country": _country_label(c),
                "Intensity": f"{intensity:.3f}" if np.isfinite(intensity) else "",
                "Exports": f"{exports:.3f}" if np.isfinite(exports) else "",
                "Imports": f"{imports:.3f}" if np.isfinite(imports) else "",
                "Post_1982": f"{post_val:.3f}" if np.isfinite(post_val) else ".",
                "Pre-1983": f"{pre_val:.3f}" if np.isfinite(pre_val) else ".",
            }
        )

    # Ligne Average
    pres = [float(r["Pre-1983"]) for r in rows if r["Pre-1983"] != "."]
    posts = [float(r["Post_1982"]) for r in rows if r["Post_1982"] != "."]
    rows.append(
        {
            "Country": "Average",
            "Intensity": "",
            "Exports": "",
            "Imports": "",
            "Post_1982": f"{np.mean(posts):.3f}" if posts else ".",
            "Pre-1983": f"{np.mean(pres):.3f}" if pres else ".",
        }
    )

    tbl = pd.DataFrame(rows)
    tbl.to_csv(out_dir / "table5_country_responses.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 5 – Individual country energy intensity and responses",
        notes=(
            "Notes: Post-1982 coef = D.Energy + D.Energy×mod.  "
            "Pre-1983 coef = D.Energy only.  Intensity uses sheet table5-6 when available.  "
            "Average = simple unweighted mean across 18 countries."
        ),
        filepath=out_dir / "table5_country_responses.png",
        fig_w=9,
        row_h=0.28,
    )
    print("✓ Table 5 exportée")


# ─── TABLE 6 : Cross-country regressions on intensity ────────────────────────


def export_table6(
    country_coef_df: pd.DataFrame,
    out_dir: Path,
    intensity_df: Optional[pd.DataFrame] = None,
) -> None:
    """
    Table 6 – Regressions of country responses on energy intensity.
    Si intensity_df est fourni (colonnes: country, intensity), la regression
    est calculée. Sinon la table affiche n/a avec une note explicative.
    """
    countries = sorted(country_coef_df["country"].unique())
    coefs = {}
    for c in countries:
        sub = country_coef_df[country_coef_df["country"] == c]
        b_pre = sub.loc[sub["variable"] == "dlenpr", "coef"]
        b_mod = sub.loc[sub["variable"] == "dlenprmod", "coef"]
        pre = b_pre.values[0] if len(b_pre) else np.nan
        mod = b_mod.values[0] if len(b_mod) else np.nan
        coefs[c] = {
            "pre": pre,
            "post": (pre + mod) if np.isfinite(pre) and np.isfinite(mod) else pre,
        }

    def _run_reg(sub: pd.DataFrame) -> Tuple[float, float, float, float, int]:
        sub = sub.dropna(subset=["y", "intensity"])
        if sub.shape[0] < 3:
            return np.nan, np.nan, np.nan, np.nan, sub.shape[0]
        X = sm.add_constant(sub[["intensity"]], has_constant="add")
        res = sm.OLS(sub["y"], X).fit(cov_type="HC1")
        coef = res.params.get("intensity", np.nan)
        tstat = res.tvalues.get("intensity", np.nan)
        fval = float(res.fvalue) if np.isfinite(res.fvalue) else np.nan
        rmse = float(np.sqrt(np.mean(res.resid**2)))
        return coef, tstat, fval, rmse, sub.shape[0]

    if intensity_df is not None and not intensity_df.empty:
        tmp = intensity_df.copy()
        tmp["_key"] = tmp["country"].astype(str).str.strip().str.lower()
        out = []
        for c in countries:
            key = str(c).strip().lower()
            name_key = _country_label(c).strip().lower()
            pre_val = coefs[c]["pre"]
            post_val = coefs[c]["post"]
            if "pre_1983" in tmp.columns:
                if (tmp["_key"] == key).any():
                    pre_val = tmp.loc[tmp["_key"] == key, "pre_1983"].iloc[0]
                elif (tmp["_key"] == name_key).any():
                    pre_val = tmp.loc[tmp["_key"] == name_key, "pre_1983"].iloc[0]
            if "post_1982" in tmp.columns:
                if (tmp["_key"] == key).any():
                    post_val = tmp.loc[tmp["_key"] == key, "post_1982"].iloc[0]
                elif (tmp["_key"] == name_key).any():
                    post_val = tmp.loc[tmp["_key"] == name_key, "post_1982"].iloc[0]

            row = {"country": name_key, "pre": pre_val, "post": post_val}
            if "intensity" in tmp.columns:
                if (tmp["_key"] == key).any():
                    row["intensity"] = tmp.loc[tmp["_key"] == key, "intensity"].iloc[0]
                elif (tmp["_key"] == name_key).any():
                    row["intensity"] = tmp.loc[
                        tmp["_key"] == name_key, "intensity"
                    ].iloc[0]
                else:
                    row["intensity"] = np.nan
            if "exclude" in tmp.columns:
                if (tmp["_key"] == key).any():
                    row["exclude"] = bool(
                        tmp.loc[tmp["_key"] == key, "exclude"].iloc[0]
                    )
                elif (tmp["_key"] == name_key).any():
                    row["exclude"] = bool(
                        tmp.loc[tmp["_key"] == name_key, "exclude"].iloc[0]
                    )
                else:
                    row["exclude"] = False
            out.append(row)

        reg_df = pd.DataFrame(out)
        spec_rows = []

        for idx, period in enumerate(["pre", "post"], start=1):
            sub = reg_df.rename(columns={period: "y"})
            coef, tstat, fval, rmse, n = _run_reg(sub)
            spec_rows.append(
                {
                    "Specification": f"({idx}) {period}-1983/1982",
                    "Coef": f"{coef:.3f}" if np.isfinite(coef) else "n/a",
                    "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a",
                    "N": n,
                    "F": f"{fval:.2f}" if np.isfinite(fval) else "n/a",
                    "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a",
                }
            )

        def _drop_outliers(df: pd.DataFrame, period: str, n: int = 2) -> pd.DataFrame:
            sub = df.dropna(subset=["intensity", period])
            if sub.shape[0] <= n + 2:
                return df
            X = sm.add_constant(sub[["intensity"]], has_constant="add")
            res = sm.OLS(sub[period], X).fit()
            outliers = (
                sub.assign(resid=res.resid)
                .sort_values("resid", key=lambda s: s.abs())
                .tail(n)
            )
            return df[~df["country"].isin(outliers["country"])]

        for idx, period in enumerate(["pre", "post"], start=3):
            if "exclude" in reg_df.columns:
                sub_df = reg_df[~reg_df["exclude"]]
            else:
                sub_df = _drop_outliers(reg_df, period, n=2)
            sub = sub_df.rename(columns={period: "y"})
            coef, tstat, fval, rmse, n = _run_reg(sub)
            spec_rows.append(
                {
                    "Specification": f"({idx}) {period}-1983/1982 (excl. outliers)",
                    "Coef": f"{coef:.3f}" if np.isfinite(coef) else "n/a",
                    "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a",
                    "N": n,
                    "F": f"{fval:.2f}" if np.isfinite(fval) else "n/a",
                    "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a",
                }
            )

        tbl = pd.DataFrame(spec_rows)
    else:
        tbl = pd.DataFrame(
            [
                {
                    "Specification": "(1) Pre-1983 ~ Intensity",
                    "Coef": "n/a",
                    "t-stat": "n/a",
                    "N": 18,
                    "F": "n/a",
                    "RMSE": "n/a",
                },
                {
                    "Specification": "(2) Post-1982 ~ Intensity",
                    "Coef": "n/a",
                    "t-stat": "n/a",
                    "N": 18,
                    "F": "n/a",
                    "RMSE": "n/a",
                },
                {
                    "Specification": "(3) Pre-1983 (excl. outliers)",
                    "Coef": "n/a",
                    "t-stat": "n/a",
                    "N": 16,
                    "F": "n/a",
                    "RMSE": "n/a",
                },
                {
                    "Specification": "(4) Post-1982 (excl. outliers)",
                    "Coef": "n/a",
                    "t-stat": "n/a",
                    "N": 16,
                    "F": "n/a",
                    "RMSE": "n/a",
                },
            ]
        )

    tbl.to_csv(out_dir / "table6_intensity_regression.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 6 – Regressions of country-specific responses on energy intensity",
        notes=(
            "Notes: Intensity = energy use per unit of GDP (EIA). "
            "Uses sheet table5-6 when available; otherwise external EIA data required. "
            "* p<0.05; ** p<0.01.  Robust standard errors."
        ),
        filepath=out_dir / "table6_intensity_regression.png",
        fig_w=9,
        row_h=0.35,
    )
    print("✓ Table 6 exportée")


# ─── Grille 18 pays (réutilisable pour Fig. A.1–A.6) ─────────────────────────


def _country_grid(
    df: pd.DataFrame,
    ycol: str,
    ylabel: str,
    suptitle: str,
    figname: str,
    out_dir: Path,
    hline: Optional[float] = None,
) -> None:
    plt.rcParams.update(PAPER_RC)
    df_r = df.reset_index()
    countries = sorted(df_r[COUNTRY_COL].unique())
    ncols, nrows = 5, 4
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(13, 8.5), sharex=False, sharey=False
    )
    axes_flat = axes.flatten()

    for idx, c in enumerate(countries[:20]):
        ax = axes_flat[idx]
        sub = df_r[df_r[COUNTRY_COL] == c].sort_values(YEAR_COL).dropna(subset=[ycol])
        ax.plot(sub[YEAR_COL], sub[ycol], lw=0.85, color="black")
        ax.set_title(_country_label(c), fontsize=6.5, pad=1.5)
        ax.tick_params(labelsize=5.5)
        ax.xaxis.set_major_locator(MultipleLocator(20))
        ax.axvline(1982, color="#aaaaaa", lw=0.6, linestyle=":")  # Grande Modération
        if hline is not None:
            ax.axhline(hline, color="red", lw=0.5, linestyle="--")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    for idx in range(len(countries), len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.text(0.5, 0.01, "Year", ha="center", fontsize=8)
    fig.text(0.01, 0.5, ylabel, va="center", rotation="vertical", fontsize=8)
    fig.suptitle(suptitle, fontsize=9, fontweight="bold", y=1.01)
    plt.tight_layout(rect=[0.03, 0.03, 1, 0.99])
    plt.savefig(out_dir / figname, dpi=200, bbox_inches="tight")
    plt.close()


# ─── FIGURES A.1 – A.6 ───────────────────────────────────────────────────────


def export_fig_a1(df, out_dir):
    _country_grid(
        df,
        LOG_GDP,
        "Log Real GDP",
        "Fig. A.1 – Country real GDP levels (log)",
        "figA1_gdp_levels.png",
        out_dir,
    )
    print("✓ Fig. A.1 exportée")


def export_fig_a2(df, out_dir):
    _country_grid(
        df,
        LOG_CPI,
        "Log CPI",
        "Fig. A.2 – Country CPI levels (log)",
        "figA2_cpi_levels.png",
        out_dir,
    )
    print("✓ Fig. A.2 exportée")


def export_fig_a3(df, out_dir):
    _country_grid(
        df,
        LOG_ENERGY,
        "Log Energy Price",
        "Fig. A.3 – Country energy price levels (log)",
        "figA3_energy_levels.png",
        out_dir,
    )
    print("✓ Fig. A.3 exportée")


def export_fig_a4(df, out_dir):
    _country_grid(
        df,
        OPEN_TRADE,
        "OpenTrade (% GDP)",
        "Fig. A.4 – Country open trade (% of GDP)",
        "figA4_opentrade.png",
        out_dir,
    )
    print("✓ Fig. A.4 exportée")


def export_fig_a5(df, out_dir):
    _country_grid(
        df,
        GOV_EXP,
        "Gov. Expenditures (% GDP)",
        "Fig. A.5 – Country government expenditures (% of GDP)",
        "figA5_govexp.png",
        out_dir,
    )
    print("✓ Fig. A.5 exportée")


def export_fig_a6(df, out_dir):
    _country_grid(
        df,
        INVEST,
        "Investment (% GDP)",
        "Fig. A.6 – Country investment (% of GDP)",
        "figA6_investment.png",
        out_dir,
    )
    print("✓ Fig. A.6 exportée")


# ─── FIGURE A.7 : ΔY et résidus par pays ─────────────────────────────────────


def export_fig_a7(df: pd.DataFrame, out_dir: Path) -> None:
    plt.rcParams.update(PAPER_RC)
    df_r = df.reset_index()
    countries = sorted(df_r[COUNTRY_COL].unique())
    ncols, nrows = 5, 4
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(13, 8.5), sharex=False, sharey=False
    )
    axes_flat = axes.flatten()

    for idx, c in enumerate(countries[:20]):
        ax = axes_flat[idx]
        sub = (
            df_r[df_r[COUNTRY_COL] == c]
            .sort_values(YEAR_COL)
            .dropna(subset=[f"d{LOG_GDP}"])
        )
        ax.plot(
            sub[YEAR_COL], sub[f"d{LOG_GDP}"], lw=0.85, color="black", label="D.GDP"
        )
        if "residual" in sub.columns:
            ax.plot(
                sub[YEAR_COL],
                sub["residual"],
                lw=0.7,
                color="#777777",
                linestyle="--",
                label="Residual",
            )
        ax.axhline(0, color="red", lw=0.5, linestyle=":")
        ax.set_title(_country_label(c), fontsize=6.5, pad=1.5)
        ax.tick_params(labelsize=5.5)
        ax.xaxis.set_major_locator(MultipleLocator(20))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    for idx in range(len(countries), len(axes_flat)):
        axes_flat[idx].set_visible(False)

    handles = [
        plt.Line2D([0], [0], color="black", lw=1, label="D.GDP"),
        plt.Line2D(
            [0], [0], color="#777777", lw=0.8, linestyle="--", label="Residuals"
        ),
    ]
    fig.legend(handles=handles, loc="lower right", fontsize=7, frameon=False)
    fig.text(0.5, 0.01, "Year", ha="center", fontsize=8)
    fig.suptitle(
        "Fig. A.7 – Actual change in Real GDP and CCEMG residuals by country",
        fontsize=9,
        fontweight="bold",
        y=1.01,
    )
    plt.tight_layout(rect=[0.02, 0.03, 1, 0.99])
    plt.savefig(out_dir / "figA7_gdp_residuals.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("✓ Fig. A.7 exportée")


# ─── Point d'entrée export ────────────────────────────────────────────────────


def export_all(
    df: pd.DataFrame,
    cips_csv: Path,
    mg_cce: pd.DataFrame,
    mg_robust: pd.DataFrame,
    mg_dcce: Optional[pd.DataFrame],
    country_coef_df: pd.DataFrame,
    robustness_df: pd.DataFrame,
    out_dir: Path,
    intensity_df: Optional[pd.DataFrame] = None,
) -> None:
    out_dir.mkdir(exist_ok=True, parents=True)
    cips_df = pd.read_csv(cips_csv)

    print("\n── Tables ──────────────────────────────────")
    export_table1(df, out_dir)
    export_table2(cips_df, out_dir)
    export_table3(mg_cce, mg_robust, mg_dcce, out_dir)
    export_table4(robustness_df, out_dir)
    export_table5(country_coef_df, out_dir, intensity_df)
    export_table6(country_coef_df, out_dir, intensity_df)

    print("\n── Figures ─────────────────────────────────")
    export_fig_a1(df, out_dir)
    export_fig_a2(df, out_dir)
    export_fig_a3(df, out_dir)
    export_fig_a4(df, out_dir)
    export_fig_a5(df, out_dir)
    export_fig_a6(df, out_dir)
    export_fig_a7(df, out_dir)

    print(f"\n✅  {6} tables + {7} figures exportées → {out_dir}/")


# =============================================================================
# Pipeline principale
# =============================================================================


def run_all() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ── Chargement ──────────────────────────────────────────────────────────
    df_raw = load_data(DATA_PATH)
    df = prepare_panel(df_raw)
    df = add_transformations(df)
    df, _ = compute_ecm(df)
    df_full = df

    if BASE_START_YEAR is not None:
        df_base = df_full[df_full.index.get_level_values(YEAR_COL) >= BASE_START_YEAR]
    else:
        df_base = df_full

    # ── 1) Stats descriptives ───────────────────────────────────────────────
    var_table = panel_variance_decomp(df_full, CORE_VARS)
    var_table.to_csv(OUTPUT_DIR / "descriptive_variance.csv", index=False)
    var_table[var_table["pct_within"] < 10.0].to_csv(
        OUTPUT_DIR / "quasi_time_invariant.csv", index=False
    )
    for k, v in observation_tables(df_full).items():
        v.to_csv(OUTPUT_DIR / f"obs_{k}.csv")

    # ── Homework diagnostics: sample selection and unbalanced panel ───────
    sample_df = sample_selection(df_full, LOG_GDP)
    sample_df.to_csv(OUTPUT_DIR / "sample_selection.csv", index=False)
    sample_df[sample_df["has_holes"]].to_csv(
        OUTPUT_DIR / "holes_countries.csv", index=False
    )
    count_by_obs(sample_df).to_csv(OUTPUT_DIR / "obs_count_by_T.csv", index=False)

    obs_year = observation_tables(df_full)["by_year"].reset_index()
    plt.rcParams.update(PAPER_RC)
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(obs_year[YEAR_COL], obs_year["n_obs"], color="black", lw=1.0)
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of countries")
    ax.set_title("Number of individuals per date", fontsize=9)
    ax.tick_params(labelsize=7)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "obs_by_year.png", dpi=200, bbox_inches="tight")
    plt.close()

    # ── Variable classification ─────────────────────────────────────────
    var_table = pd.read_csv(OUTPUT_DIR / "descriptive_variance.csv")
    time_invariant = var_table[var_table["var_within"].abs() < 1e-12]
    individual_invariant = var_table[var_table["var_between"].abs() < 1e-12]
    time_varying = var_table[
        (var_table["var_within"].abs() >= 1e-12)
        & (var_table["var_between"].abs() >= 1e-12)
    ]
    time_varying.sort_values("pct_within", ascending=False).to_csv(
        OUTPUT_DIR / "time_varying_vars.csv", index=False
    )
    time_invariant.to_csv(OUTPUT_DIR / "time_invariant_vars.csv", index=False)
    individual_invariant.to_csv(
        OUTPUT_DIR / "individual_invariant_vars.csv", index=False
    )
    pd.DataFrame(
        {
            "category": ["time_varying", "time_invariant", "individual_invariant"],
            "count": [
                time_varying.shape[0],
                time_invariant.shape[0],
                individual_invariant.shape[0],
            ],
        }
    ).to_csv(OUTPUT_DIR / "variable_categories.csv", index=False)

    # ── Between/Within distributions ────────────────────────────────────
    plot_between_within(
        df_full, LOG_GDP, OUTPUT_DIR / "dist_between_within_lrgdpmad.png"
    )
    plot_between_within(
        df_full, LOG_ENERGY, OUTPUT_DIR / "dist_between_within_lenpr.png"
    )

    # ── First differences diagnostics ───────────────────────────────────
    fd_corr = plot_fd_joint(
        df_full, LOG_GDP, LOG_ENERGY, OUTPUT_DIR / "fd_jointplot.png"
    )
    pd.DataFrame([{"fd_corr": fd_corr}]).to_csv(
        OUTPUT_DIR / "fd_correlation.csv", index=False
    )
    df_r = df_full.reset_index().sort_values([COUNTRY_COL, YEAR_COL])
    df_r["fd_gdp"] = df_r.groupby(COUNTRY_COL)[LOG_GDP].diff()
    df_r["fd_energy"] = df_r.groupby(COUNTRY_COL)[LOG_ENERGY].diff()
    df_r[[COUNTRY_COL, YEAR_COL, LOG_GDP, "fd_gdp", LOG_ENERGY, "fd_energy"]].head(
        100
    ).to_csv(OUTPUT_DIR / "fd_first100.csv", index=False)

    # ── Balanced panel TWFE ─────────────────────────────────────────────
    tmax = sample_df["n_obs"].max()
    balanced_countries = sample_df[sample_df["n_obs"] == tmax]["country"].tolist()
    df_bal = df_full[
        df_full.index.get_level_values(COUNTRY_COL).isin(balanced_countries)
    ].copy()
    time_effect = time_effect_series(df_bal, LOG_GDP)
    time_effect.to_frame("time_effect").to_csv(OUTPUT_DIR / "time_effect_lrgdpmad.csv")
    plot_time_effect(time_effect, OUTPUT_DIR / "time_effect_lrgdpmad.png")

    df_bal[f"{LOG_GDP}_twfe"] = twfe_unbalanced(df_bal, LOG_GDP)
    df_bal[f"{LOG_ENERGY}_twfe"] = twfe_unbalanced(df_bal, LOG_ENERGY)
    boxplot_by_country(
        df_bal.reset_index().set_index([COUNTRY_COL, YEAR_COL]),
        f"{LOG_GDP}_twfe",
        OUTPUT_DIR / "boxplot_twfe_lrgdpmad_bal.png",
        "TWFE GDP by country (balanced)",
    )
    boxplot_by_country(
        df_bal.reset_index().set_index([COUNTRY_COL, YEAR_COL]),
        f"{LOG_ENERGY}_twfe",
        OUTPUT_DIR / "boxplot_twfe_lenpr_bal.png",
        "TWFE Energy by country (balanced)",
    )

    twfe_corr_bal = heterogeneity_table(df_bal, LOG_GDP, LOG_ENERGY, "twfe")
    twfe_corr_bal.to_csv(OUTPUT_DIR / "twfe_country_corr_balanced.csv", index=False)

    # ── Unbalanced TWFE and comparisons ─────────────────────────────────
    df_full[f"{LOG_GDP}_between"] = df_full.groupby(level=0)[LOG_GDP].transform("mean")
    df_full[f"{LOG_GDP}_within"] = df_full[LOG_GDP] - df_full.groupby(level=0)[
        LOG_GDP
    ].transform("mean")
    df_full[f"{LOG_GDP}_twfe"] = twfe_unbalanced(df_full, LOG_GDP)
    df_full[f"{LOG_GDP}_fd"] = df_full.groupby(level=0)[LOG_GDP].diff()

    df_full[f"{LOG_ENERGY}_between"] = df_full.groupby(level=0)[LOG_ENERGY].transform(
        "mean"
    )
    df_full[f"{LOG_ENERGY}_within"] = df_full[LOG_ENERGY] - df_full.groupby(level=0)[
        LOG_ENERGY
    ].transform("mean")
    df_full[f"{LOG_ENERGY}_twfe"] = twfe_unbalanced(df_full, LOG_ENERGY)
    df_full[f"{LOG_ENERGY}_fd"] = df_full.groupby(level=0)[LOG_ENERGY].diff()

    plot_four_transforms(df_full, LOG_GDP, OUTPUT_DIR / "dist_four_lrgdpmad.png")
    plot_four_transforms(df_full, LOG_ENERGY, OUTPUT_DIR / "dist_four_lenpr.png")
    plot_transform_boxplots(
        df_full, LOG_GDP, OUTPUT_DIR / "boxplot_transforms_lrgdpmad.png"
    )
    plot_transform_boxplots(
        df_full, LOG_ENERGY, OUTPUT_DIR / "boxplot_transforms_lenpr.png"
    )

    stats_rows = []
    for var in [LOG_GDP, LOG_ENERGY]:
        for tname, col in [
            ("between", f"{var}_between"),
            ("within", f"{var}_within"),
            ("twfe", f"{var}_twfe"),
            ("fd", f"{var}_fd"),
        ]:
            st = univariate_stats(df_full[col])
            st.update({"variable": var, "transform": tname})
            stats_rows.append(st)
    pd.DataFrame(stats_rows).to_csv(OUTPUT_DIR / "transform_stats.csv", index=False)

    # ── Correlation matrices ────────────────────────────────────────────
    df_full["trend"] = df_full.index.get_level_values(YEAR_COL)
    for v in CORE_VARS:
        df_full[f"l_{v}"] = df_full.groupby(level=0)[v].shift(1)
    between_df = df_full.groupby(level=0)[CORE_VARS + ["trend"]].mean()
    within_df = df_full[CORE_VARS + ["trend"]] - df_full.groupby(level=0)[
        CORE_VARS + ["trend"]
    ].transform("mean")
    corr_between = between_df.corr()
    corr_within = within_df.corr()
    corr_between.to_csv(OUTPUT_DIR / "corr_between.csv")
    corr_within.to_csv(OUTPUT_DIR / "corr_within.csv")

    fd_df = df_full.groupby(level=0)[CORE_VARS].diff()
    for v in CORE_VARS:
        fd_df[f"l_{v}"] = fd_df.groupby(level=0)[v].shift(1)
    twfe_df = pd.DataFrame({v: twfe_unbalanced(df_full, v) for v in CORE_VARS})
    corr_fd = fd_df.corr()
    corr_twfe = twfe_df.corr()
    corr_fd.to_csv(OUTPUT_DIR / "corr_fd.csv")
    corr_twfe.to_csv(OUTPUT_DIR / "corr_twfe.csv")

    fd_head = fd_df.reset_index().head(30)
    fd_head.to_csv(OUTPUT_DIR / "fd_first30.csv", index=False)

    # ── Bivariate fits ─────────────────────────────────────────────────
    bivariate_fit_plot(
        df_full, LOG_GDP, LOG_ENERGY, "within", OUTPUT_DIR / "fit_within.png"
    )
    bivariate_fit_plot(
        df_full, LOG_GDP, LOG_ENERGY, "between", OUTPUT_DIR / "fit_between.png"
    )
    bivariate_fit_plot(df_full, LOG_GDP, LOG_ENERGY, "fd", OUTPUT_DIR / "fit_fd.png")
    bivariate_fit_plot(
        df_full, LOG_GDP, LOG_ENERGY, "twfe", OUTPUT_DIR / "fit_twfe.png"
    )

    # ── Heterogeneity tables ───────────────────────────────────────────
    heterogeneity_table(df_full, LOG_GDP, LOG_ENERGY, "fd").to_csv(
        OUTPUT_DIR / "heterogeneity_fd.csv", index=False
    )
    heterogeneity_table(df_full, LOG_GDP, LOG_ENERGY, "twfe").to_csv(
        OUTPUT_DIR / "heterogeneity_twfe.csv", index=False
    )

    # ── Dynamic ARDL diagnostics ───────────────────────────────────────
    dyn_vars = [
        "dlrgdpmad",
        "l_dlrgdpmad",
        "dlenpr",
        "l_dlenpr",
        "l2_lrgdpmad",
        "l2_lenpr",
    ]
    dyn_stats = []
    for v in dyn_vars:
        if v not in df_full.columns:
            continue
        st = univariate_stats(df_full[v])
        st.update({"variable": v})
        dyn_stats.append(st)
    pd.DataFrame(dyn_stats).to_csv(
        OUTPUT_DIR / "dynamic_univariate_stats.csv", index=False
    )

    dyn_corr = df_full[dyn_vars].dropna().corr()
    dyn_corr.to_csv(OUTPUT_DIR / "dynamic_corr.csv")

    # ── 2) Tests preliminaires ──────────────────────────────────────────────
    cips_rows = []
    for var in CORE_VARS:
        for lag in range(0, 4):
            sl, pl = cips_test(df_full[var], lags=lag)
            sd, pd_ = cips_test(df_full[f"d{var}"], lags=lag)
            cips_rows.append(
                {
                    "variable": var,
                    "lag": lag,
                    "stat_level": sl,
                    "pvalue_level": pl,
                    "stat_diff": sd,
                    "pvalue_diff": pd_,
                }
            )
    cips_path = OUTPUT_DIR / "cips_tests.csv"
    pd.DataFrame(cips_rows).to_csv(cips_path, index=False)

    cd_rows = []
    for var in CORE_VARS:
        st, pv, ac = pesaran_cd(df_full[var])
        cd_rows.append({"variable": var, "cd_stat": st, "pvalue": pv, "avg_corr": ac})
    pd.DataFrame(cd_rows).to_csv(OUTPUT_DIR / "cd_tests.csv", index=False)

    ds, dp = delta_test_pesaran_yamagata(
        df_full, LOG_GDP, [LOG_ENERGY, LOG_CPI, OPEN_TRADE, GOV_EXP, INVEST]
    )
    pd.DataFrame([{"delta_stat": ds, "pvalue": dp}]).to_csv(
        OUTPUT_DIR / "delta_test.csv", index=False
    )

    # ── 3) Estimations panel statiques ─────────────────────────────────────
    estimate_static_panel(df_full).to_csv(
        OUTPUT_DIR / "panel_models_table.csv", index=False
    )

    # ── 4) Modele dynamique ─────────────────────────────────────────────────
    dyn_ols = fit_dynamic_ols(df_full)
    dyn_iv = fit_dynamic_iv(df_full)

    pd.DataFrame(
        {
            "coef": dyn_ols.params,
            "se": dyn_ols.bse,
            "t": dyn_ols.tvalues,
            "p": dyn_ols.pvalues,
        }
    ).to_csv(OUTPUT_DIR / "ardl_ols.csv")
    pd.DataFrame(
        {
            "coef": dyn_iv.params,
            "se": dyn_iv.std_errors,
            "t": dyn_iv.tstats,
            "p": dyn_iv.pvalues,
        }
    ).to_csv(OUTPUT_DIR / "ardl_iv.csv")

    try:
        pd.DataFrame(
            [{"endog": n, "r2": s.rsquared} for n, s in dyn_iv.first_stage.items()]
        ).to_csv(OUTPUT_DIR / "first_stage_r2.csv", index=False)
    except Exception:
        pd.DataFrame(columns=["endog", "r2"]).to_csv(
            OUTPUT_DIR / "first_stage_r2.csv", index=False
        )

    hs, hp = hausman_test(dyn_ols, dyn_iv)
    pd.DataFrame([{"hausman_stat": hs, "pvalue": hp}]).to_csv(
        OUTPUT_DIR / "hausman_ols_iv.csv", index=False
    )

    rho = dyn_iv.params.get("l_dlrgdpmad", np.nan)
    b1 = dyn_iv.params.get("dlenpr", np.nan)
    b2 = dyn_iv.params.get("l_dlenpr", np.nan)
    irf_vals = compute_irf(b1, b2, rho, horizons=4)
    se_irf = irf_standard_errors(b1, b2, rho, dyn_iv.std_errors.to_dict())
    irf_df = pd.DataFrame({"h": np.arange(1, 5), "tau": irf_vals, "se": se_irf})
    irf_df["lower"] = irf_df["tau"] - 1.96 * irf_df["se"]
    irf_df["upper"] = irf_df["tau"] + 1.96 * irf_df["se"]
    irf_df.to_csv(OUTPUT_DIR / "irf.csv", index=False)

    if np.isfinite(rho) and abs(rho) >= 1:
        warnings.warn("|rho| >= 1 : IRF explosive, LT invalide.")
    lt = (b1 + b2) / (1.0 - rho) if (np.isfinite(rho) and abs(rho) < 1) else np.nan
    pd.DataFrame([{"lt_coef": lt, "rho": rho}]).to_csv(
        OUTPUT_DIR / "long_term.csv", index=False
    )

    # ── 5) CCE-MG (Table 3) ────────────────────────────────────────────────
    cce_regs = [
        "dlcpi",
        "dlenpr",
        "dopen",
        "dexpgdp",
        "diy",
        "l_lrgdpmad",
        "l_lcpi",
        "l_open",
        "l_iy",
        "lrgdpmadT",
        "lcpiT",
        "lenprT",
        "openT",
        "expgdpT",
        "iyT",
    ]
    _, mg_cce, mg_robust = estimate_cce_mg(df_full, "dlrgdpmad", cce_regs)

    dcce_exog = [
        "dlcpi",
        "dlenpr",
        "dopen",
        "dexpgdp",
        "diy",
        "l_lrgdpmad",
        "l_lcpi",
        "l_open",
        "l_iy",
    ]
    _, mg_dcce = estimate_ccemg(
        df_full, "dlrgdpmad", dcce_exog, [], [], True, CORE_VARS
    )

    # ── 6) CCEMG IV (Table 4 + Tables 5-6) ─────────────────────────────────
    instruments = infer_instruments(df)
    if not instruments:
        warnings.warn("Aucun instrument détecté → dlenpr traité comme exogène.")

    dep = "dlrgdpmad"
    exog_vars = [
        "l_dlcpi2",
        "dopen",
        "dexpgdp",
        "diy",
        "l_lrgdpmad",
        "l_lcpi",
        "l_open",
        "l_iy",
        "mod",
        "dlenprmod",
    ]
    endog_vars = ["dlenpr"]

    cc_country, cc_mg = estimate_ccemg(
        df_base,
        dep,
        exog_vars,
        endog_vars,
        instruments,
        exog_only=not instruments,
        cs_mean_vars=CORE_VARS,
    )
    cc_country.to_csv(OUTPUT_DIR / "ccemg_country_coefs.csv", index=False)
    cc_mg.to_csv(OUTPUT_DIR / "ccemg_mg.csv", index=False)

    robustness = build_robustness_table(
        df_base, df_full, dep, exog_vars, endog_vars, instruments
    )
    robustness.to_csv(OUTPUT_DIR / "ccemg_robustness_table.csv", index=False)

    intensity_df = load_table56(DATA_PATH)

    # ── 7) EXPORT TABLES & FIGURES (format papier) ──────────────────────────
    export_all(
        df=df_full,
        cips_csv=cips_path,
        mg_cce=mg_cce,
        mg_robust=mg_robust,
        mg_dcce=mg_dcce,
        country_coef_df=cc_country,
        robustness_df=robustness,
        out_dir=OUTPUT_DIR,
        intensity_df=intensity_df,
    )


if __name__ == "__main__":
    run_all()
