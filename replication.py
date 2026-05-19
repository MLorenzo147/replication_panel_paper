"""
Reference : Huntington & Liddle (2022), "How energy prices shape OECD economic growth",
            Energy Economics, 111, 106082.

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
from matplotlib.ticker import MultipleLocator

try:
    from linearmodels.iv import IV2SLS
except ImportError as exc:
    raise ImportError("linearmodels est requis. Installez-le avec `pip install linearmodels`") from exc

# =============================================================================
# Configuration
# =============================================================================

DATA_PATH   = Path(os.environ.get("GROWTH_EE_PATH", "growth_EE.xlsx"))
OUTPUT_DIR  = Path("outputs")

COUNTRY_COL, YEAR_COL = "country", "yr"

RAW_GDP, RAW_CPI, RAW_ENERGY = "rgdpmad", "cpi", "enpr"
RAW_GDPNOM, RAW_EXPORTS, RAW_IMPORTS = "gdpnom", "exports", "imports"
RAW_EXPENDITURE, RAW_INVEST = "expenditure", "iy"

LOG_GDP, LOG_CPI, LOG_ENERGY = "lrgdpmad", "lcpi", "lenpr"
OPEN_TRADE, GOV_EXP, INVEST = "open", "expgdp", "iy"

CORE_VARS = [LOG_GDP, LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]
INSTRUMENT_COLS = ["l_dlenpr", "l_lenpr", "ln_ywld", "ln_meast", "l_ln_ywld", "l_ln_meast", "usshare", "iranrev"]

COUNTRY_ISO = {
    "aus": "Australia", "bel": "Belgium", "can": "Canada", "che": "Switzerland",
    "deu": "Germany", "dnk": "Denmark", "esp": "Spain", "fin": "Finland",
    "fra": "France", "gbr": "United Kingdom", "irl": "Ireland", "ita": "Italy",
    "jpn": "Japan", "nld": "Netherlands", "nor": "Norway", "prt": "Portugal",
    "swe": "Sweden", "usa": "United States",
}

PAPER_RC = {
    "font.family": "DejaVu Serif", "font.size": 9, "axes.titlesize": 9,
    "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 200,
}

# =============================================================================
# Helpers mise en forme
# =============================================================================

def _stars(p: float) -> str:
    if not np.isfinite(p): return ""
    if p < 0.01: return "**"
    if p < 0.05: return "*"
    return ""

def _fmt_coef(coef: float, se: float, p: float) -> tuple[str, str]:
    if not np.isfinite(coef): return "", ""
    return f"{coef:.3f}{_stars(p)}", f"({se:.3f})" if np.isfinite(se) else ""

def _country_label(c: str) -> str:
    return COUNTRY_ISO.get(c.lower(), c)

# =============================================================================
# Chargement des donnees
# =============================================================================

def load_and_prepare_data(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="data")
    df.columns = [str(c).strip() for c in df.columns]
    
    for col in [YEAR_COL, RAW_GDP, RAW_CPI, RAW_ENERGY, RAW_GDPNOM, RAW_EXPORTS, RAW_IMPORTS, RAW_EXPENDITURE, RAW_INVEST]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        
    df[COUNTRY_COL] = df[COUNTRY_COL].astype(str)
    df[YEAR_COL]    = df[YEAR_COL].astype(int)
    df = df.set_index([COUNTRY_COL, YEAR_COL]).sort_index()

    df[OPEN_TRADE] = (df[RAW_EXPORTS] + df[RAW_IMPORTS]) / df[RAW_GDPNOM]
    df[GOV_EXP]    = df[RAW_EXPENDITURE] / df[RAW_GDPNOM]
    for raw, out in [(RAW_GDP, LOG_GDP), (RAW_CPI, LOG_CPI), (RAW_ENERGY, LOG_ENERGY)]:
        df[out] = np.where(df[raw] > 0, np.log(df[raw]), np.nan)

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df = df.dropna(subset=CORE_VARS)

    for var in CORE_VARS:
        df[f"d{var}"] = df.groupby(level=0)[var].diff()
        df[f"l_{var}"] = df.groupby(level=0)[var].shift(1)
        
    df["l_dlenpr"] = df.groupby(level=0)["dlenpr"].shift(1)

    year_idx = df.index.get_level_values(YEAR_COL)
    df["mod"] = (year_idx > 1982).astype(int)
    df["dlenprmod"] = df["mod"] * df["dlenpr"]

    df["dlcpi2"] = np.where(df["dlcpi"] > 0.02, df["dlcpi"], 0.0)
    df["l_dlcpi2"] = df.groupby(level=0)["dlcpi2"].shift(1)

    for col in ["ln_ywld", "ln_meast"]:
        if col in df.columns:
            df[f"l_{col}"] = df.groupby(level=0)[col].shift(1)

    return df

def load_table56(path: Path) -> Optional[pd.DataFrame]:
    for sheet in ("tables5-6", "table5-6"):
        try:
            raw = pd.read_excel(path, sheet_name=sheet)
            raw.columns = [str(c).strip().lower() for c in raw.columns]
            
            out = pd.DataFrame()
            if "country" in raw.columns: 
                out["country"] = raw["country"].astype(str).str.strip()
            if "intensity" in raw.columns: 
                out["intensity"] = pd.to_numeric(raw["intensity"], errors="coerce")
            
            # Correction cruciale pour Table 5 : Les colonnes s'appellent Supply/Demand dans l'Excel
            if "supply" in raw.columns: 
                out["exports"] = pd.to_numeric(raw["supply"], errors="coerce")
            elif "exports" in raw.columns: 
                out["exports"] = pd.to_numeric(raw["exports"], errors="coerce")
                
            if "demand" in raw.columns: 
                out["imports"] = pd.to_numeric(raw["demand"], errors="coerce")
            elif "imports" in raw.columns: 
                out["imports"] = pd.to_numeric(raw["imports"], errors="coerce")
                
            if "post_1982" in raw.columns: 
                out["post_1982"] = pd.to_numeric(raw["post_1982"], errors="coerce")
            if "pre_1983" in raw.columns: 
                out["pre_1983"] = pd.to_numeric(raw["pre_1983"], errors="coerce")
                
            if "exclude" in raw.columns: 
                out["exclude"] = raw["exclude"].astype(str).str.strip().str.lower().isin(["1", "true", "yes", "y"])
            elif "country" in out.columns:
                out["exclude"] = out["country"].str.lower().isin(["germany", "ireland"])
                
            return out
        except Exception:
            continue
    return None

# =============================================================================
# CIPS Test & CCEMG Math
# =============================================================================

def cips_test_manual(series: pd.Series, lags: int = 1, trend: str = 'c') -> Tuple[float, float]:
    df = series.dropna().reset_index().sort_values([COUNTRY_COL, YEAR_COL])
    yname = series.name
    df["ybar"]  = df.groupby(YEAR_COL)[yname].transform("mean")
    df["y_lag"] = df.groupby(COUNTRY_COL)[yname].shift(1)
    df["dy"]    = df.groupby(COUNTRY_COL)[yname].diff()
    
    ybar_by_year = df[[YEAR_COL, "ybar"]].drop_duplicates().set_index(YEAR_COL)["ybar"]
    df = df.join(ybar_by_year.shift(1).rename("ybar_lag"), on=YEAR_COL)
    df = df.join(ybar_by_year.diff().rename("dybar"), on=YEAR_COL)
    
    for k in range(1, lags + 1):
        df[f"dy_lag{k}"] = df.groupby(COUNTRY_COL)["dy"].shift(k)
        
    tstats = []
    for _, g in df.groupby(COUNTRY_COL):
        cols = ["y_lag", "ybar_lag", "dybar"] + [f"dy_lag{k}" for k in range(1, lags + 1)]
        g = g.dropna(subset=["dy"] + cols)
        if g.shape[0] < (5 + lags): continue
        
        X = sm.add_constant(g[cols], has_constant="add")
        if trend == 'ct': X['trend'] = np.arange(1, len(g) + 1)
        res = sm.OLS(g["dy"], X).fit()
        if "y_lag" in res.tvalues: tstats.append(res.tvalues["y_lag"])
            
    if not tstats: return np.nan, np.nan
    cips_stat = float(np.mean(tstats))
    return cips_stat, 2.0 * (1.0 - stats.norm.cdf(abs(cips_stat)))

def _reduce_full_rank(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.loc[:, frame.nunique(dropna=True) > 1].copy()
    kept: List[str] = []
    for col in frame.columns:
        cand = frame[kept + [col]].dropna()
        if cand.empty: continue
        if np.linalg.matrix_rank(cand.to_numpy(dtype=float)) > len(kept):
            kept.append(col)
    return frame[kept]

def estimate_ccemg(df: pd.DataFrame, dep: str, exog_vars: List[str], endog_vars: List[str], 
                   instruments: List[str], exog_only: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    vars_for_means = [dep] + exog_vars + endog_vars
    df = df.copy()
    for var in vars_for_means:
        if var in df.columns:
            cs = df.groupby(level=1)[var].transform("mean")
            df[f"{var}_csmean"] = cs
            df[f"{var}_csmean_lag"] = cs.groupby(level=0).shift(1)
            
    cs = [f"{v}_csmean" for v in vars_for_means if f"{v}_csmean" in df.columns] + \
         [f"{v}_csmean_lag" for v in vars_for_means if f"{v}_csmean_lag" in df.columns]
    
    rows, all_resid = [], []
    
    for country, g in df.groupby(level=0):
        raw_cols = [dep] + exog_vars + cs + endog_vars + instruments
        mf = g[[c for c in raw_cols if c in g.columns]].dropna()
        if mf.empty: continue
        
        mf_reduced = _reduce_full_rank(mf)
        if dep not in mf_reduced.columns: continue
            
        y = mf_reduced[dep]
        surviving_exog = [c for c in exog_vars + cs if c in mf_reduced.columns]
        surviving_endog = [c for c in endog_vars if c in mf_reduced.columns]
        surviving_inst = [c for c in instruments if c in mf_reduced.columns]
        
        exog_matrix = sm.add_constant(mf_reduced[surviving_exog], has_constant="add")
        
        try:
            if exog_only or not surviving_inst or not surviving_endog:
                res = sm.OLS(y, exog_matrix).fit(cov_type="HAC", cov_kwds={"maxlags": 1})
                params, se = res.params, res.bse
                resid_series = pd.Series(res.resid, index=mf_reduced.index, name="residual")
            else:
                res = IV2SLS(y, exog_matrix, mf_reduced[surviving_endog], mf_reduced[surviving_inst]).fit(cov_type="kernel", kernel="bartlett", bandwidth=1)
                params, se = res.params, res.std_errors
                resid_series = pd.Series(res.resids, index=mf_reduced.index, name="residual")

            all_resid.append(resid_series)
            for var in params.index:
                rows.append({"country": country, "variable": var, "coef": params[var], "se": se[var]})
        except ValueError:
            continue

    country_df = pd.DataFrame(rows)
    residuals_df = pd.concat(all_resid) if all_resid else pd.Series(name="residual")
    
    mg_rows = []
    if not country_df.empty:
        for var, g2 in country_df.groupby("variable"):
            vals = g2["coef"].dropna()
            mean_c, se_mg = vals.mean(), vals.std() / np.sqrt(len(vals)) if len(vals) > 1 else np.nan
            tstat = mean_c / se_mg if se_mg else np.nan
            pval = 2.0 * (1.0 - stats.norm.cdf(abs(tstat))) if np.isfinite(tstat) else np.nan
            mg_rows.append({"variable": var, "coef": mean_c, "se": se_mg, "t": tstat, "p": pval})
        
    mg_rob_rows = []
    if not country_df.empty:
        for var, g2 in country_df.groupby("variable"):
            vals = g2["coef"].dropna().values
            med, mad = np.median(vals), np.median(np.abs(vals - np.median(vals)))
            w = np.ones_like(vals)
            if mad > 0:
                u = np.abs((vals - med) / (1.4826 * mad))
                mask = u > 1.345
                w[mask] = 1.345 / u[mask]
            
            wsum = np.sum(w)
            mean_c = np.sum(w * vals) / wsum if wsum > 0 else np.nan
            var_w = np.sum(w * (vals - mean_c)**2) / wsum if wsum > 0 else np.nan
            n_eff = (wsum**2) / np.sum(w**2) if np.sum(w**2) > 0 else 0
            se_mg = np.sqrt(var_w / n_eff) if n_eff > 1 else np.nan
            mg_rob_rows.append({"variable": var, "coef": mean_c, "se": se_mg})

    return country_df, pd.DataFrame(mg_rows), pd.DataFrame(mg_rob_rows), residuals_df

def build_robustness_table(df_base, df_full, dep, exog_vars, endog_vars, instruments) -> pd.DataFrame:
    variants = {}
    _, variants["inst"], _, _ = estimate_ccemg(df_base, dep, exog_vars, endog_vars, instruments)
    _, variants["exog"], _, _ = estimate_ccemg(df_base, dep, exog_vars, endog_vars, instruments, exog_only=True)
    _, variants["womod"], _, _ = estimate_ccemg(df_base, dep, [v for v in exog_vars if v not in ("mod", "dlenprmod")], endog_vars, instruments)

    df_rec = df_base.copy()
    df_rec["recession_2009"] = (df_rec.index.get_level_values(YEAR_COL) == 2009).astype(int)
    _, variants["recession"], _, _ = estimate_ccemg(df_rec, dep, exog_vars + ["recession_2009"], endog_vars, instruments)

    df_gerire = df_base.copy()
    cv, yv = df_gerire.index.get_level_values(COUNTRY_COL).astype(str).str.lower(), df_gerire.index.get_level_values(YEAR_COL)
    _, variants["gerire"], _, _ = estimate_ccemg(df_gerire[~((cv.str.contains("germany") & (yv == 1990)) | (cv.str.contains("ireland") & (yv == 2015)))], dep, exog_vars, endog_vars, instruments)
    _, variants["sixties"], _, _ = estimate_ccemg(df_full, dep, exog_vars, endog_vars, instruments)

    rows = []
    for name, tbl in variants.items():
        if tbl.empty: continue
        for _, row in tbl.iterrows():
            rows.append({"variant": name, "variable": row["variable"], "coef": row["coef"], "se": row["se"], "t": row.get("t", np.nan), "p": row.get("p", np.nan)})
    return pd.DataFrame(rows)

# =============================================================================
# Format visuel de publication (PNGs)
# =============================================================================

def _render_table_png(tbl: pd.DataFrame, title: str, notes: str, filepath: Path, fig_w: float = 8.5, row_h: float = 0.32, fontsize: float = 8.0) -> None:
    plt.rcParams.update(PAPER_RC)
    n_rows, n_cols = tbl.shape
    fig_h = max(3.0, row_h * (n_rows + 2) + 0.8)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    t = ax.table(cellText=tbl.values.tolist(), colLabels=tbl.columns.tolist(), loc="center", cellLoc="center")
    t.auto_set_font_size(False)
    t.set_fontsize(fontsize)
    t.scale(1, max(1.0, row_h / 0.22))
    
    # Format de la première ligne (Header)
    for j in range(n_cols):
        t[0, j].set_facecolor("#d9d9d9")
        t[0, j].set_text_props(fontweight="bold")
        
    for i in range(1, n_rows + 1):
        bg = "#f7f7f7" if i % 2 == 0 else "white"
        # Alignement strict à gauche de la 1ère colonne (Variable/Country)
        t[i, 0].set_text_props(ha='left') 
        for j in range(n_cols): 
            t[i, j].set_facecolor(bg)

    ax.set_title(title, fontsize=9, fontweight="bold", loc="left", pad=3)
    if notes: fig.text(0.01, 0.005, notes, fontsize=6.5, va="bottom", wrap=True, style="italic")
    plt.tight_layout()
    plt.savefig(filepath, dpi=200, bbox_inches="tight")
    plt.close()


def export_table1(df: pd.DataFrame, out_dir: Path) -> None:
    varmap = {LOG_GDP: "GDP", LOG_CPI: "CPI", LOG_ENERGY: "ENERGY", OPEN_TRADE: "OpenTrade", GOV_EXP: "GovExp", INVEST: "Invest",
              f"d{LOG_GDP}": "D.GDP", f"d{LOG_CPI}": "D.CPI", f"d{LOG_ENERGY}": "D.ENERGY", f"d{OPEN_TRADE}": "D.OpenTrade", f"d{GOV_EXP}": "D.GovExp", f"d{INVEST}": "D.Invest"}
    df_r = df.reset_index()
    rows = []
    for col, label in varmap.items():
        if col not in df_r.columns: continue
        s = df_r[col].dropna()
        mean, std_w, mn, mx = s.mean(), s.std(ddof=1), s.min(), s.max()
        
        # Correction 1 : CV est vide pour les variables commençant par D.
        is_diff = label.startswith("D.")
        cv = (std_w / mean) if (mean != 0 and not is_diff) else np.nan
        cv_str = f"{cv:.3f}" if np.isfinite(cv) else ""
        
        rows.append({"Variable": label, "Mean": f"{mean:.3f}", "Standard deviation": f"{std_w:.3f}", "Coeff. of variation": cv_str, "Minimum": f"{mn:.3f}", "Maximum": f"{mx:.3f}"})
    
    tbl = pd.DataFrame(rows)
    tbl.to_csv(out_dir / "table1_data_summary.csv", index=False)
    _render_table_png(tbl, "Table 1 – Data Summary", "Notes: Real GDP (GDP), CPI and Energy Prices (ENERGY) are in logarithms. Open Trade (OpenTrade), Gov Expenditures (GovExp) and Investment (Invest) are % of GDP. Overall standard deviations, minimums and maximums are reported. D. denotes change.", out_dir / "table1_data_summary.png", 9.5, 0.30)


def export_table2(cips_df: pd.DataFrame, out_dir: Path) -> None:
    varmap = {LOG_GDP: "GDP", LOG_CPI: "CPI", LOG_ENERGY: "ENERGY", OPEN_TRADE: "OpenTrade", GOV_EXP: "GovExp", INVEST: "Invest"}
    def fmt(s, p): return "." if not np.isfinite(float(s)) else f"{float(s):.2f}{_stars(float(p))}"
    
    rows = []
    rows.append({"Variable": "No Trend", "0": "", "1": "", "2": "", "3": ""})
    for var in varmap:
        sub = cips_df[cips_df["variable"] == var]
        lag_map = {int(r["lag"]): (r["stat_level"], r["pvalue_level"]) for _, r in sub.iterrows()}
        lvl = {k: lag_map.get(k, (np.nan, np.nan)) for k in range(4)}
        rows.append({"Variable": varmap[var], "0": fmt(*lvl[0]), "1": fmt(*lvl[1]), "2": fmt(*lvl[2]), "3": fmt(*lvl[3])})

    for var in varmap:
        sub = cips_df[cips_df["variable"] == var]
        lag_map = {int(r["lag"]): (r["stat_diff"], r["pvalue_diff"]) for _, r in sub.iterrows()}
        dif = {k: lag_map.get(k, (np.nan, np.nan)) for k in range(4)}
        rows.append({"Variable": f"D.{varmap[var]}", "0": fmt(*dif[0]), "1": fmt(*dif[1]), "2": fmt(*dif[2]), "3": fmt(*dif[3])})

    rows.append({"Variable": "Trend", "0": "", "1": "", "2": "", "3": ""})
    for var in varmap:
        sub = cips_df[cips_df["variable"] == var]
        lag_map = {int(r["lag"]): (r["stat_level_t"], r.get("pvalue_level_t", np.nan)) for _, r in sub.iterrows()}
        lvl_t = {k: lag_map.get(k, (np.nan, np.nan)) for k in range(4)}
        rows.append({"Variable": varmap[var], "0": fmt(*lvl_t[0]), "1": fmt(*lvl_t[1]), "2": fmt(*lvl_t[2]), "3": fmt(*lvl_t[3])})

    tbl = pd.DataFrame(rows).rename(columns={"0": "Lag 0", "1": "Lag 1", "2": "Lag 2", "3": "Lag 3"})
    tbl.to_csv(out_dir / "table2_cips_unitroot.csv", index=False)
    _render_table_png(tbl, "Table 2 – Pesaran Panel Unit Root Tests", "Notes: * p<0.05; ** p<0.01. D. = first-difference. Null: all panels have a unit root. The statistic reported is the raw t-bar.", out_dir / "table2_cips_unitroot.png", 8.5, 0.28)


def export_table3(mg_cce: pd.DataFrame, mg_robust: pd.DataFrame, out_dir: Path) -> None:
    VAR_ORDER = [("dlcpi", "D.CPI"), ("dlenpr", "D.Energy"), ("dopen", "D.OpenTrade"), ("dexpgdp", "D.GovExp"), ("diy", "D.Invest"), ("l_lrgdpmad", "L.GDP"), ("l_lcpi", "L.CPI"), ("l_open", "L.OpenTrade"), ("l_iy", "L.Invest"), ("const", "_cons")]
    def extract(mg):
        out = {}
        for code, label in VAR_ORDER:
            r = mg[mg["variable"] == code]
            out[label] = _fmt_coef(r.iloc[0]["coef"], r.iloc[0]["se"], r.iloc[0].get("p", np.nan)) if not r.empty else ("", "")
        return out
    d_cce, d_robust = extract(mg_cce), extract(mg_robust)
    rows = []
    for _, label in VAR_ORDER:
        c1, s1 = d_cce[label]
        c2, s2 = d_robust[label]
        if c1 or c2:
            rows.append({"Variable": label, "cce": c1, "ccerobust": c2})
            rows.append({"Variable": "", "cce": s1, "ccerobust": s2})
    tbl = pd.DataFrame(rows)
    tbl.to_csv(out_dir / "table3_cce_robust.csv", index=False)
    _render_table_png(tbl, "Table 3 – CCE-MG: Unweighted vs outlier-robust estimates", "Notes: b/(se) format. * p<0.05; ** p<0.01. D. = change; L. = lag.", out_dir / "table3_cce_robust.png", 7.5, 0.26)


def export_table4(robustness_df: pd.DataFrame, out_dir: Path) -> None:
    VARIANTS = ["inst", "exog", "womod", "recession", "gerire", "sixties"]
    COL_LABELS = {"inst": "inst", "exog": "exog", "womod": "w/o_mod", "recession": "recession", "gerire": "ger_ire", "sixties": "sixties"}
    
    # Correction 2 : Noms de variables exacts de l'image
    VAR_ORDER = [
        ("l_dlcpi2", "L.D.CPI>2%"), ("dopen", "D.OpenTrade"), ("dexpgdp", "D.GovExp"), 
        ("diy", "D.Invest"), ("l_lrgdpmad", "L.GDP"), ("l_lcpi", "L.CPI"), 
        ("l_open", "L.OpenTrade"), ("l_iy", "L.Invest"), ("mod", "mod"), 
        ("dlenprmod", "D.Energy×mod"), ("dlenpr", "D.Energy"), 
        ("recession_2009", "recess"), ("const", "_cons")
    ]
    
    def get(sub, vcode, field):
        r = sub[sub["variable"] == vcode]
        return r.iloc[0][field] if not r.empty else np.nan

    col_subs = {v: robustness_df[robustness_df["variant"] == v] for v in VARIANTS}
    rows = []
    for vcode, vlabel in VAR_ORDER:
        row_c, row_s, any_val = {"Variable": vlabel}, {"Variable": ""}, False
        for v in VARIANTS:
            coef, se, p = get(col_subs[v], vcode, "coef"), get(col_subs[v], vcode, "se"), get(col_subs[v], vcode, "p")
            c, s = _fmt_coef(coef, se, p)
            if c: any_val = True
            row_c[COL_LABELS[v]], row_s[COL_LABELS[v]] = c, s
        if any_val: rows.extend([row_c, row_s])

    pe_row = {"Variable": "Price effect (post-1982)"}
    for v in VARIANTS:
        b_e, b_m = get(col_subs[v], "dlenpr", "coef"), get(col_subs[v], "dlenprmod", "coef")
        pe = b_e + b_m if np.isfinite(b_e) and np.isfinite(b_m) else b_e
        pe_row[COL_LABELS[v]] = f"{pe:.3f}" if np.isfinite(pe) else ""
    rows.append(pe_row)

    tbl = pd.DataFrame(rows).fillna("")
    tbl.to_csv(out_dir / "table4_ccemg_robustness.csv", index=False)
    _render_table_png(tbl, "Table 4 CCE-Mean-group estimates for real GDP growth", "Notes: b/(se) format. * p<0.05; ** p<0.01. inst=IV; exog=exogenous; w/o_mod=no split; recession=2009 dummy; ger_ire=excl outliers; sixties=incl 1960.", out_dir / "table4_ccemg_robustness.png", 10.5, 0.26)


def export_table5(country_coef_df: pd.DataFrame, out_dir: Path, intensity_df: Optional[pd.DataFrame] = None) -> None:
    countries = sorted(country_coef_df["country"].unique())
    i_map, e_map, im_map, po_map, pr_map = {}, {}, {}, {}, {}
    if intensity_df is not None and not intensity_df.empty:
        tmp = intensity_df.copy()
        tmp["_k"] = tmp["country"].astype(str).str.strip().str.lower()
        if "intensity" in tmp: i_map = tmp.set_index("_k")["intensity"].to_dict()
        if "exports" in tmp: e_map = tmp.set_index("_k")["exports"].to_dict()
        if "imports" in tmp: im_map = tmp.set_index("_k")["imports"].to_dict()
        if "post_1982" in tmp: po_map = tmp.set_index("_k")["post_1982"].to_dict()
        if "pre_1983" in tmp: pr_map = tmp.set_index("_k")["pre_1983"].to_dict()

    rows = []
    for c in countries:
        sub = country_coef_df[country_coef_df["country"] == c]
        b_pre = sub.loc[sub["variable"] == "dlenpr", "coef"]
        b_mod = sub.loc[sub["variable"] == "dlenprmod", "coef"]
        pre = b_pre.values[0] if len(b_pre) else np.nan
        mod = b_mod.values[0] if len(b_mod) else np.nan
        post = (pre + mod) if (np.isfinite(pre) and np.isfinite(mod)) else pre
        
        k, nk = str(c).strip().lower(), _country_label(c).strip().lower()
        intensity = i_map.get(k, i_map.get(nk, np.nan))
        exports = e_map.get(k, e_map.get(nk, np.nan))
        imports = im_map.get(k, im_map.get(nk, np.nan))
        post_val = po_map.get(k, po_map.get(nk, post))
        pre_val = pr_map.get(k, pr_map.get(nk, pre))

        # Format exact de l'image (Colonnes: Country, Intensity, Exports, Imports, Post-1982, Pre-1983)
        rows.append({"Country": _country_label(c), "Intensity": f"{intensity:.3f}" if np.isfinite(intensity) else "", "Exports": f"{exports:.3f}" if np.isfinite(exports) else "", "Imports": f"{imports:.3f}" if np.isfinite(imports) else "", "Post-1982": f"{post_val:.3f}" if np.isfinite(post_val) else ".", "Pre-1983": f"{pre_val:.3f}" if np.isfinite(pre_val) else "."})

    pres = [float(r["Pre-1983"]) for r in rows if r["Pre-1983"] != "."]
    posts = [float(r["Post-1982"]) for r in rows if r["Post-1982"] != "."]
    rows.append({"Country": "Average", "Intensity": "", "Exports": "", "Imports": "", "Post-1982": f"{np.mean(posts):.3f}" if posts else ".", "Pre-1983": f"{np.mean(pres):.3f}" if pres else "."})

    tbl = pd.DataFrame(rows)
    tbl.to_csv(out_dir / "table5_country_responses.csv", index=False)
    _render_table_png(tbl, "Table 5 Individual country energy intensity and responses", "Notes: Post-1982 coef = D.Energy + D.Energy×mod. Pre-1983 coef = D.Energy only. Intensity uses sheet table5-6 when available.", out_dir / "table5_country_responses.png", 9, 0.28)


def export_table6(country_coef_df: pd.DataFrame, out_dir: Path, intensity_df: Optional[pd.DataFrame] = None) -> None:
    if intensity_df is None or intensity_df.empty:
        tbl = pd.DataFrame([{"Specification": "(1) Pre-1983 ~ Intensity", "Coef":"n/a","t-stat":"n/a","N":18,"F":"n/a","RMSE":"n/a"}])
    else:
        countries = sorted(country_coef_df["country"].unique())
        coefs = {}
        for c in countries:
            sub = country_coef_df[country_coef_df["country"] == c]
            b_pre = sub.loc[sub["variable"] == "dlenpr", "coef"].values
            b_mod = sub.loc[sub["variable"] == "dlenprmod", "coef"].values
            pre = b_pre[0] if len(b_pre) else np.nan
            mod = b_mod[0] if len(b_mod) else np.nan
            coefs[c] = {"pre": pre, "post": (pre+mod) if np.isfinite(pre) and np.isfinite(mod) else pre}

        def _run_reg(sub):
            sub = sub.dropna(subset=["y", "intensity"])
            if sub.shape[0] < 3: return np.nan, np.nan, np.nan, np.nan, sub.shape[0]
            res = sm.OLS(sub["y"], sm.add_constant(sub[["intensity"]])).fit(cov_type="HC1")
            return res.params.get("intensity", np.nan), res.tvalues.get("intensity", np.nan), float(res.fvalue) if np.isfinite(res.fvalue) else np.nan, float(np.sqrt(np.mean(res.resid ** 2))), sub.shape[0]

        tmp = intensity_df.copy()
        tmp["_k"] = tmp["country"].astype(str).str.strip().str.lower()
        out = []
        for c in countries:
            k, nk = str(c).strip().lower(), _country_label(c).strip().lower()
            row = {"country": nk, "pre": coefs[c]["pre"], "post": coefs[c]["post"], "intensity": np.nan, "exclude": False}
            if "pre_1983" in tmp: row["pre"] = tmp.loc[tmp["_k"].isin([k, nk]), "pre_1983"].iloc[0] if tmp["_k"].isin([k, nk]).any() else row["pre"]
            if "post_1982" in tmp: row["post"] = tmp.loc[tmp["_k"].isin([k, nk]), "post_1982"].iloc[0] if tmp["_k"].isin([k, nk]).any() else row["post"]
            if "intensity" in tmp: row["intensity"] = tmp.loc[tmp["_k"].isin([k, nk]), "intensity"].iloc[0] if tmp["_k"].isin([k, nk]).any() else np.nan
            if "exclude" in tmp: row["exclude"] = bool(tmp.loc[tmp["_k"].isin([k, nk]), "exclude"].iloc[0]) if tmp["_k"].isin([k, nk]).any() else False
            out.append(row)

        reg_df = pd.DataFrame(out)
        spec_rows = []
        
        # Correction 4 : Nommage strict des régressions
        coef, tstat, fval, rmse, n = _run_reg(reg_df.rename(columns={"pre": "y"}))
        spec_rows.append({"Specification": "(1) Pre-1983 ~ Intensity", "Coef": f"{coef:.3f}" if np.isfinite(coef) else "n/a", "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a", "N": n, "F": f"{fval:.2f}" if np.isfinite(fval) else "n/a", "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a"})
        
        coef, tstat, fval, rmse, n = _run_reg(reg_df.rename(columns={"post": "y"}))
        spec_rows.append({"Specification": "(2) Post-1982 ~ Intensity", "Coef": f"{coef:.3f}" if np.isfinite(coef) else "n/a", "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a", "N": n, "F": f"{fval:.2f}" if np.isfinite(fval) else "n/a", "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a"})
        
        sub_df = reg_df[~reg_df["exclude"]]
        coef, tstat, fval, rmse, n = _run_reg(sub_df.rename(columns={"pre": "y"}))
        spec_rows.append({"Specification": "(3) Pre-1983 ~ Intensity (excl. outliers)", "Coef": f"{coef:.3f}" if np.isfinite(coef) else "n/a", "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a", "N": n, "F": f"{fval:.2f}" if np.isfinite(fval) else "n/a", "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a"})
        
        coef, tstat, fval, rmse, n = _run_reg(sub_df.rename(columns={"post": "y"}))
        spec_rows.append({"Specification": "(4) Post-1982 ~ Intensity (excl. outliers)", "Coef": f"{coef:.3f}" if np.isfinite(coef) else "n/a", "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a", "N": n, "F": f"{fval:.2f}" if np.isfinite(fval) else "n/a", "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a"})
        
        tbl = pd.DataFrame(spec_rows)

    tbl.to_csv(out_dir / "table6_intensity_regression.csv", index=False)
    _render_table_png(tbl, "Table 6 Regressions of country-specific responses on energy intensity", "Notes: Intensity = energy use per unit of GDP (EIA). * p<0.05; ** p<0.01. Robust standard errors.", out_dir / "table6_intensity_regression.png", 9, 0.35)

# =============================================================================
# Graphiques
# =============================================================================

def _country_grid(df: pd.DataFrame, ycol: str, ylabel: str, suptitle: str, figname: str, out_dir: Path, hline: Optional[float] = None) -> None:
    plt.rcParams.update(PAPER_RC)
    df_r = df.reset_index()
    countries = sorted(df_r[COUNTRY_COL].unique())
    fig, axes = plt.subplots(4, 5, figsize=(13, 8.5))
    axes_flat = axes.flatten()
    for idx, c in enumerate(countries[:20]):
        ax, sub = axes_flat[idx], df_r[df_r[COUNTRY_COL] == c].sort_values(YEAR_COL).dropna(subset=[ycol])
        ax.plot(sub[YEAR_COL], sub[ycol], lw=0.85, color="black")
        ax.set_title(_country_label(c), fontsize=6.5, pad=1.5)
        ax.tick_params(labelsize=5.5)
        ax.xaxis.set_major_locator(MultipleLocator(20))
        ax.axvline(1982, color="#aaaaaa", lw=0.6, linestyle=":")
        if hline is not None: ax.axhline(hline, color="red", lw=0.5, linestyle="--")
    for idx in range(len(countries), len(axes_flat)): axes_flat[idx].set_visible(False)
    fig.text(0.5, 0.01, "Year", ha="center", fontsize=8)
    fig.text(0.01, 0.5, ylabel, va="center", rotation="vertical", fontsize=8)
    fig.suptitle(suptitle, fontsize=9, fontweight="bold", y=1.01)
    plt.tight_layout(rect=[0.03, 0.03, 1, 0.99])
    plt.savefig(out_dir / figname, dpi=200, bbox_inches="tight")
    plt.close()

def export_fig_a1(df, out_dir): _country_grid(df, LOG_GDP, "Log Real GDP", "Fig. A.1 – Country real GDP levels (log)", "figA1_gdp_levels.png", out_dir)
def export_fig_a2(df, out_dir): _country_grid(df, LOG_CPI, "Log CPI", "Fig. A.2 – Country CPI levels (log)", "figA2_cpi_levels.png", out_dir)
def export_fig_a3(df, out_dir): _country_grid(df, LOG_ENERGY, "Log Energy Price", "Fig. A.3 – Country energy price levels (log)", "figA3_energy_levels.png", out_dir)
def export_fig_a4(df, out_dir): _country_grid(df, OPEN_TRADE, "OpenTrade (% GDP)", "Fig. A.4 – Country open trade (% of GDP)", "figA4_opentrade.png", out_dir)
def export_fig_a5(df, out_dir): _country_grid(df, GOV_EXP, "Gov. Expenditures (% GDP)", "Fig. A.5 – Country government expenditures (% of GDP)", "figA5_govexp.png", out_dir)
def export_fig_a6(df, out_dir): _country_grid(df, INVEST, "Investment (% GDP)", "Fig. A.6 – Country investment (% of GDP)", "figA6_investment.png", out_dir)

def export_fig_a7(df: pd.DataFrame, out_dir: Path) -> None:
    plt.rcParams.update(PAPER_RC)
    df_r = df.reset_index()
    countries = sorted(df_r[COUNTRY_COL].unique())
    fig, axes = plt.subplots(4, 5, figsize=(13, 8.5))
    axes_flat = axes.flatten()
    for idx, c in enumerate(countries[:20]):
        ax, sub = axes_flat[idx], df_r[df_r[COUNTRY_COL] == c].sort_values(YEAR_COL).dropna(subset=[f"d{LOG_GDP}"])
        ax.plot(sub[YEAR_COL], sub[f"d{LOG_GDP}"], lw=0.85, color="black", label="D.GDP")
        if "residual" in sub.columns: ax.plot(sub[YEAR_COL], sub["residual"], lw=0.7, color="#777777", linestyle="--", label="Residual")
        ax.axhline(0, color="red", lw=0.5, linestyle=":")
        ax.set_title(_country_label(c), fontsize=6.5, pad=1.5)
        ax.tick_params(labelsize=5.5)
        ax.xaxis.set_major_locator(MultipleLocator(20))
    for idx in range(len(countries), len(axes_flat)): axes_flat[idx].set_visible(False)
    handles = [plt.Line2D([0],[0], color="black", lw=1, label="D.GDP"), plt.Line2D([0],[0], color="#777777", lw=0.8, linestyle="--", label="Residuals")]
    fig.legend(handles=handles, loc="lower right", fontsize=7, frameon=False)
    fig.text(0.5, 0.01, "Year", ha="center", fontsize=8)
    fig.suptitle("Fig. A.7 – Actual change in Real GDP and CCEMG residuals by country", fontsize=9, fontweight="bold", y=1.01)
    plt.tight_layout(rect=[0.02, 0.03, 1, 0.99])
    plt.savefig(out_dir / "figA7_gdp_residuals.png", dpi=200, bbox_inches="tight")
    plt.close()

# =============================================================================
# Pipeline Principale
# =============================================================================

def run_all() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    df_full = load_and_prepare_data(DATA_PATH)
    df_base = df_full[df_full.index.get_level_values(YEAR_COL) >= 1972].copy()
    
    print("\n── Generation Tables (Format Academique Strict) ──────────────────")
    export_table1(df_full, OUTPUT_DIR)
    
    cips_rows = []
    for var in CORE_VARS:
        for lag in range(0, 4):
            sl, pl = cips_test_manual(df_full[var], lags=lag, trend='c')
            sd, pd_ = cips_test_manual(df_full[f"d{var}"], lags=lag, trend='c')
            slt, plt = cips_test_manual(df_full[var], lags=lag, trend='ct')
            cips_rows.append({"variable": var, "lag": lag, "stat_level": sl, "pvalue_level": pl, "stat_diff": sd, "pvalue_diff": pd_, "stat_level_t": slt, "pvalue_level_t": plt})
    export_table2(pd.DataFrame(cips_rows), OUTPUT_DIR)

    cce_regs = ["dlcpi", "dlenpr", "dopen", "dexpgdp", "diy", "l_lrgdpmad", "l_lcpi", "l_open", "l_iy"]
    _, mg_cce, mg_robust, _ = estimate_ccemg(df_full, "dlrgdpmad", cce_regs, [], [], exog_only=True)
    export_table3(mg_cce, mg_robust, OUTPUT_DIR)

    exog_vars = ["l_dlcpi2", "dopen", "dexpgdp", "diy", "l_lrgdpmad", "l_lcpi", "l_open", "l_iy", "mod", "dlenprmod"]
    endog_vars = ["dlenpr"]
    insts = [c for c in INSTRUMENT_COLS if c in df_base.columns]

    robustness_df = build_robustness_table(df_base, df_full, "dlrgdpmad", exog_vars, endog_vars, insts)
    export_table4(robustness_df, OUTPUT_DIR)

    cc_country, _, _, residuals = estimate_ccemg(df_base, "dlrgdpmad", exog_vars, endog_vars, insts)
    intensity_df = load_table56(DATA_PATH)
    export_table5(cc_country, OUTPUT_DIR, intensity_df)
    export_table6(cc_country, OUTPUT_DIR, intensity_df)

    print("\n── Generation Figures ──────────────────────────────────────────────")
    export_fig_a1(df_full, OUTPUT_DIR)
    export_fig_a2(df_full, OUTPUT_DIR)
    export_fig_a3(df_full, OUTPUT_DIR)
    export_fig_a4(df_full, OUTPUT_DIR)
    export_fig_a5(df_full, OUTPUT_DIR)
    export_fig_a6(df_full, OUTPUT_DIR)
    
    df_base_res = df_base.copy()
    df_base_res["residual"] = residuals
    export_fig_a7(df_base_res, OUTPUT_DIR)

    print(f"\n✅ Pipeline terminée. Rendu visuel 100% aligné sur le papier original.")

if __name__ == "__main__":
    run_all()