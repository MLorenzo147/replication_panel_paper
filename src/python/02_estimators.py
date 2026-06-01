"""
02_estimators.py — Algorithmes économétriques (CIPS, CCEMG, Huber)
==================================================================
Référence : Huntington & Liddle (2022), "How energy prices shape OECD
            economic growth", Energy Economics, 111, 106082.

Ce module implémente les estimateurs nécessaires à la réplication :
  - Test CIPS de Pesaran (2007) : CADF manuel, reporte le t-bar brut
  - Estimateur CCEMG (Pesaran, 2006) avec IV optionnel
  - Moyennes transversales (CSA) dynamiques
  - Filtre de colinéarité _reduce_full_rank (décomposition matricielle)
  - Poids de Huber pour l'estimateur robust Mean Group (c = 1.345)
  - Table de robustesse (6 variantes du papier)

⚠ La logique mathématique est portée verbatim depuis le code validé.
  Ne pas remplacer par des packages standards qui échoueraient.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

try:
    from linearmodels.iv import IV2SLS
except ImportError as exc:
    raise ImportError(
        "linearmodels est requis. Installez-le avec `pip install linearmodels`"
    ) from exc

# ── Constantes partagées (identiques à 01_data_prep.py) ─────────────────────
COUNTRY_COL = "country"
YEAR_COL    = "yr"
CORE_VARS   = ["lrgdpmad", "lcpi", "lenpr", "open", "expgdp", "iy"]
INSTRUMENT_COLS = [
    "l_dlenpr", "l_lenpr", "ln_ywld", "ln_meast",
    "l_ln_ywld", "l_ln_meast", "usshare", "iranrev",
]


# ═════════════════════════════════════════════════════════════════════════════
# Test CIPS de Pesaran (2007)
# ═════════════════════════════════════════════════════════════════════════════

def cips_test_manual(
    series: pd.Series,
    lags: int = 1,
    trend: str = "c",
) -> Tuple[float, float]:
    """
    Calcule le test CIPS manuellement via régressions CADF par pays.

    Retourne le **t-bar brut** (moyenne des t-stats individuels sur y_lag),
    et NON le Z standardisé. C'est la convention du papier (Table 2).

    Parameters
    ----------
    series : pd.Series avec multi-index (country, yr)
    lags : nombre de retards des différences augmentées
    trend : 'c' (constante) ou 'ct' (constante + tendance)

    Returns
    -------
    (cips_stat, pvalue) : float, float
    """
    df = series.dropna().reset_index().sort_values([COUNTRY_COL, YEAR_COL])
    yname = series.name

    # Moyennes transversales par année
    df["ybar"]  = df.groupby(YEAR_COL)[yname].transform("mean")
    df["y_lag"] = df.groupby(COUNTRY_COL)[yname].shift(1)
    df["dy"]    = df.groupby(COUNTRY_COL)[yname].diff()

    ybar_by_year = (df[[YEAR_COL, "ybar"]]
                    .drop_duplicates()
                    .set_index(YEAR_COL)["ybar"])
    df = df.join(ybar_by_year.shift(1).rename("ybar_lag"), on=YEAR_COL)
    df = df.join(ybar_by_year.diff().rename("dybar"),       on=YEAR_COL)

    for k in range(1, lags + 1):
        df[f"dy_lag{k}"] = df.groupby(COUNTRY_COL)["dy"].shift(k)

    # ── Régressions CADF par pays ───────────────────────────────────────
    tstats = []
    for _, g in df.groupby(COUNTRY_COL):
        cols = (["y_lag", "ybar_lag", "dybar"] +
                [f"dy_lag{k}" for k in range(1, lags + 1)])
        g = g.dropna(subset=["dy"] + cols)
        if g.shape[0] < (5 + lags):
            continue

        X = sm.add_constant(g[cols], has_constant="add")
        if trend == "ct":
            X["trend"] = np.arange(1, len(g) + 1)
        res = sm.OLS(g["dy"], X).fit()
        if "y_lag" in res.tvalues:
            tstats.append(res.tvalues["y_lag"])

    if not tstats:
        return np.nan, np.nan

    cips_stat = float(np.mean(tstats))
    pvalue = 2.0 * (1.0 - stats.norm.cdf(abs(cips_stat)))
    return cips_stat, pvalue


# ═════════════════════════════════════════════════════════════════════════════
# Filtre de colinéarité (rang complet de la matrice)
# ═════════════════════════════════════════════════════════════════════════════

def _reduce_full_rank(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Élimine les colonnes constantes puis celles qui n'augmentent pas le
    rang de la matrice (colinéarité parfaite). Indispensable pour les
    petits échantillons pays où ``mod`` est constante à 0 ou 1.
    """
    # Supprimer les colonnes constantes
    frame = frame.loc[:, frame.nunique(dropna=True) > 1].copy()

    kept: List[str] = []
    for col in frame.columns:
        cand = frame[kept + [col]].dropna()
        if cand.empty:
            continue
        if np.linalg.matrix_rank(cand.to_numpy(dtype=float)) > len(kept):
            kept.append(col)

    return frame[kept]


# ═════════════════════════════════════════════════════════════════════════════
# CCEMG (Common Correlated Effects Mean Group)
# ═════════════════════════════════════════════════════════════════════════════

def estimate_ccemg(
    df: pd.DataFrame,
    dep: str,
    exog_vars: List[str],
    endog_vars: List[str],
    instruments: List[str],
    exog_only: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    Estimateur CCEMG : boucle sur les pays avec régressions OLS ou IV
    augmentées des moyennes transversales (CSA).

    Returns
    -------
    country_df : coefficients individuels par pays
    mg_df : Mean Group (moyenne simple)
    mg_robust_df : Robust MG (poids de Huber, c = 1.345)
    residuals : résidus concaténés (pour Fig. A7)
    """
    vars_for_means = [dep] + exog_vars + endog_vars

    # ── Calcul des CSA ──────────────────────────────────────────────────
    df = df.copy()
    for var in vars_for_means:
        if var in df.columns:
            cs = df.groupby(level=1)[var].transform("mean")
            df[f"{var}_csmean"]     = cs
            df[f"{var}_csmean_lag"] = cs.groupby(level=0).shift(1)

    cs_cols = ([f"{v}_csmean"     for v in vars_for_means
                if f"{v}_csmean" in df.columns] +
               [f"{v}_csmean_lag" for v in vars_for_means
                if f"{v}_csmean_lag" in df.columns])

    rows = []
    all_resid = []

    # ── Boucle pays par pays ────────────────────────────────────────────
    for country, g in df.groupby(level=0):
        raw_cols = ([dep] + exog_vars + cs_cols + endog_vars + instruments)
        mf = g[[c for c in raw_cols if c in g.columns]].dropna()
        if mf.empty:
            continue

        # Filtre de rang complet (élimine mod constant, etc.)
        mf_reduced = _reduce_full_rank(mf)
        if dep not in mf_reduced.columns:
            continue

        y = mf_reduced[dep]
        surviving_exog  = [c for c in exog_vars + cs_cols
                           if c in mf_reduced.columns]
        surviving_endog = [c for c in endog_vars
                           if c in mf_reduced.columns]
        surviving_inst  = [c for c in instruments
                           if c in mf_reduced.columns]

        exog_matrix = sm.add_constant(mf_reduced[surviving_exog],
                                      has_constant="add")

        try:
            if exog_only or not surviving_inst or not surviving_endog:
                # ── OLS + HAC ───────────────────────────────────────────
                res = sm.OLS(y, exog_matrix).fit(
                    cov_type="HAC", cov_kwds={"maxlags": 1})
                params, se = res.params, res.bse
                resid_series = pd.Series(res.resid,
                                         index=mf_reduced.index,
                                         name="residual")
            else:
                # ── IV/2SLS + kernel HAC ────────────────────────────────
                res = IV2SLS(
                    y, exog_matrix,
                    mf_reduced[surviving_endog],
                    mf_reduced[surviving_inst],
                ).fit(cov_type="kernel", kernel="bartlett", bandwidth=1)
                params, se = res.params, res.std_errors
                resid_series = pd.Series(res.resids,
                                         index=mf_reduced.index,
                                         name="residual")

            all_resid.append(resid_series)
            for var in params.index:
                rows.append({
                    "country":  country,
                    "variable": var,
                    "coef":     params[var],
                    "se":       se[var],
                })
        except ValueError:
            continue

    country_df = pd.DataFrame(rows)
    residuals  = (pd.concat(all_resid) if all_resid
                  else pd.Series(name="residual"))

    # ── Mean Group (simple) ─────────────────────────────────────────────
    mg_rows = []
    if not country_df.empty:
        for var, g2 in country_df.groupby("variable"):
            vals = g2["coef"].dropna()
            if vals.empty:
                continue
            mean_c = vals.mean()
            se_mg = (vals.std(ddof=1) / np.sqrt(len(vals))
                     if len(vals) > 1 else np.nan)
            tstat = mean_c / se_mg if se_mg else np.nan
            pval = (2.0 * (1.0 - stats.norm.cdf(abs(tstat)))
                    if np.isfinite(tstat) else np.nan)
            mg_rows.append({
                "variable": var, "coef": mean_c,
                "se": se_mg, "t": tstat, "p": pval,
            })

    # ── Robust Mean Group (Huber, c = 1.345) ────────────────────────────
    mg_rob_rows = []
    if not country_df.empty:
        for var, g2 in country_df.groupby("variable"):
            vals = g2["coef"].dropna().values
            if vals.size == 0:
                continue

            med = np.median(vals)
            mad = np.median(np.abs(vals - med))
            w = np.ones_like(vals, dtype=float)
            if mad > 0:
                u = np.abs((vals - med) / (1.4826 * mad))
                mask = u > 1.345
                w[mask] = 1.345 / u[mask]

            wsum = np.sum(w)
            mean_c = np.sum(w * vals) / wsum if wsum > 0 else np.nan
            var_w = (np.sum(w * (vals - mean_c) ** 2) / wsum
                     if wsum > 0 else np.nan)
            n_eff = (wsum ** 2) / np.sum(w ** 2) if np.sum(w ** 2) > 0 else 0
            se_mg = np.sqrt(var_w / n_eff) if n_eff > 1 else np.nan
            tstat = mean_c / se_mg if (se_mg and np.isfinite(se_mg)) else np.nan
            pval = (2.0 * (1.0 - stats.norm.cdf(abs(tstat)))
                    if np.isfinite(tstat) else np.nan)
            mg_rob_rows.append({
                "variable": var, "coef": mean_c,
                "se": se_mg, "t": tstat, "p": pval,
            })

    return (country_df,
            pd.DataFrame(mg_rows),
            pd.DataFrame(mg_rob_rows),
            residuals)


# ═════════════════════════════════════════════════════════════════════════════
# Table de robustesse (6 variantes, Table 4)
# ═════════════════════════════════════════════════════════════════════════════

def build_robustness_table(
    df_base: pd.DataFrame,
    df_full: pd.DataFrame,
    dep: str,
    exog_vars: List[str],
    endog_vars: List[str],
    instruments: List[str],
) -> pd.DataFrame:
    """
    Construit la Table 4 avec 6 spécifications de robustesse :
    inst, exog, womod, recession, gerire, sixties.
    """
    variants = {}

    # (1) IV (instrumental)
    _, variants["inst"], _, _ = estimate_ccemg(
        df_base, dep, exog_vars, endog_vars, instruments)

    # (2) Exogène
    _, variants["exog"], _, _ = estimate_ccemg(
        df_base, dep, exog_vars, endog_vars, instruments, exog_only=True)

    # (3) Sans mod
    exog_womod = [v for v in exog_vars if v not in ("mod", "dlenprmod")]
    _, variants["womod"], _, _ = estimate_ccemg(
        df_base, dep, exog_womod, endog_vars, instruments)

    # (4) Dummy récession 2009
    df_rec = df_base.copy()
    df_rec["recession_2009"] = (
        df_rec.index.get_level_values(YEAR_COL) == 2009
    ).astype(int)
    _, variants["recession"], _, _ = estimate_ccemg(
        df_rec, dep, exog_vars + ["recession_2009"],
        endog_vars, instruments)

    # (5) Exclusion Germany 1990 + Ireland 2015
    df_gerire = df_base.copy()
    cv = df_gerire.index.get_level_values(COUNTRY_COL).astype(str).str.lower()
    yv = df_gerire.index.get_level_values(YEAR_COL)
    mask = ~(
        (cv.str.contains("germany") & (yv == 1990)) |
        (cv.str.contains("ireland") & (yv == 2015))
    )
    _, variants["gerire"], _, _ = estimate_ccemg(
        df_gerire[mask], dep, exog_vars, endog_vars, instruments)

    # (6) Inclure les années 1960
    _, variants["sixties"], _, _ = estimate_ccemg(
        df_full, dep, exog_vars, endog_vars, instruments)

    # ── Compilation ─────────────────────────────────────────────────────
    rows = []
    for name, tbl in variants.items():
        if tbl.empty:
            continue
        for _, row in tbl.iterrows():
            rows.append({
                "variant":  name,
                "variable": row["variable"],
                "coef":     row["coef"],
                "se":       row["se"],
                "t":        row.get("t", np.nan),
                "p":        row.get("p", np.nan),
            })
    return pd.DataFrame(rows)
