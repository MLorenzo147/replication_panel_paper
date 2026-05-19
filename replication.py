"""
Auteur : A COMPLETER
Date   : 2026-05-18
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

try:
    from linearmodels.panel import BetweenOLS, FirstDifferenceOLS, PanelOLS, RandomEffects
    from linearmodels.iv import IV2SLS
except Exception as exc:  # pragma: no cover - runtime guard
    raise ImportError(
        "linearmodels est requis. Installez-le avec `pip install linearmodels`"
    ) from exc


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DATA_PATH = Path(os.environ.get("GROWTH_EE_PATH", str(Path(__file__).with_name("growth_EE.xlsx"))))
OUTPUT_DIR = Path(__file__).with_name("outputs")

COUNTRY_COL = "country"
YEAR_COL = "yr"

# Colonnes brutes
RAW_GDP = "rgdpmad"
RAW_CPI = "cpi"
RAW_ENERGY = "enpr"
RAW_GDPNOM = "gdpnom"
RAW_EXPORTS = "exports"
RAW_IMPORTS = "imports"
RAW_EXPENDITURE = "expenditure"
RAW_INVEST = "iy"

# Variables transformees
LOG_GDP = "lrgdpmad"
LOG_CPI = "lcpi"
LOG_ENERGY = "lenpr"
OPEN_TRADE = "open"
GOV_EXP = "expgdp"
INVEST = "iy"

CORE_VARS = [LOG_GDP, LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]

# Instruments explicites (optionnel). Si vide, detection automatique par pattern.
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

# Echantillon de base: par defaut, on coupe avant 1972 (option if yr>1971)
BASE_START_YEAR = 1972


# -----------------------------------------------------------------------------
# Chargement et preparation des donnees
# -----------------------------------------------------------------------------

def load_data(path: Path) -> pd.DataFrame:
    """Charge le fichier Excel et nettoie les noms de colonnes."""
    try:
        df = pd.read_excel(path, sheet_name="data")
    except PermissionError as exc:
        raise PermissionError(
            f"Impossible de lire {path}. Le fichier est probablement ouvert dans Excel ou verrouille par OneDrive. "
            "Fermez le classeur, ou copiez-le vers un chemin de travail libre puis lancez le script avec "
            "la variable d'environnement GROWTH_EE_PATH."
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
        raise ValueError(f"Colonnes manquantes dans les donnees: {missing}")

    for col in [YEAR_COL, RAW_GDP, RAW_CPI, RAW_ENERGY, RAW_GDPNOM, RAW_EXPORTS, RAW_IMPORTS, RAW_EXPENDITURE, RAW_INVEST]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def prepare_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Trie et cree le MultiIndex (country, yr)."""
    df = df.copy()
    df[COUNTRY_COL] = df[COUNTRY_COL].astype(str)
    df[YEAR_COL] = df[YEAR_COL].astype(int)
    df = df.sort_values([COUNTRY_COL, YEAR_COL])
    df = df.set_index([COUNTRY_COL, YEAR_COL])
    df = df.sort_index()
    return df


def add_transformations(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute differences, retards et variables de regime."""
    df = df.copy()
    # Ratios macro
    df[OPEN_TRADE] = (df[RAW_EXPORTS] + df[RAW_IMPORTS]) / df[RAW_GDPNOM]
    df[GOV_EXP] = df[RAW_EXPENDITURE] / df[RAW_GDPNOM]

    # Logs (protege contre valeurs non-positives)
    for raw, out in [(RAW_GDP, LOG_GDP), (RAW_CPI, LOG_CPI), (RAW_ENERGY, LOG_ENERGY)]:
        df[out] = np.where(df[raw] > 0, np.log(df[raw]), np.nan)

    # Nettoyage des infinis potentiels
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # Echantillon commun (comme keep if e(sample) == 1)
    base_vars = [LOG_GDP, LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]
    df = df.dropna(subset=base_vars)

    # Differences et lags
    for var in base_vars:
        dvar = f"d{var}"
        df[dvar] = df.groupby(level=0)[var].diff()
        df[f"l_{var}"] = df.groupby(level=0)[var].shift(1)
        df[f"l_d{var}"] = df.groupby(level=0)[dvar].shift(1)

    # Lags t-2 pour Anderson-Hsiao
    df["l2_lrgdpmad"] = df.groupby(level=0)[LOG_GDP].shift(2)
    df["l2_lenpr"] = df.groupby(level=0)[LOG_ENERGY].shift(2)

    # Regimes et interactions
    year_index = df.index.get_level_values(YEAR_COL)
    df["mod"] = (year_index > 1982).astype(int)
    df["premod"] = (year_index < 1983).astype(int)
    df["lenprmod"] = df["mod"] * df[LOG_ENERGY]
    df["dlenprmod"] = df["mod"] * df["dlenpr"]
    df["dlenprpre"] = df["premod"] * df["dlenpr"]

    # Inflation > 2%
    df["dlcpi2"] = np.where(df["dlcpi"] > 0.02, df["dlcpi"], 0.0)
    df["dlcpix"] = df["dlcpi"] - df["dlcpi2"]
    df["l_dlcpi2"] = df.groupby(level=0)["dlcpi2"].shift(1)

    # Lags des instruments globaux
    if "ln_ywld" in df.columns:
        df["l_ln_ywld"] = df.groupby(level=0)["ln_ywld"].shift(1)
    if "ln_meast" in df.columns:
        df["l_ln_meast"] = df.groupby(level=0)["ln_meast"].shift(1)

    # Moyennes transversales (suffixe T)
    for var in base_vars:
        df[f"{var}T"] = df.groupby(level=1)[var].transform("mean")

    return df


def compute_ecm(df: pd.DataFrame) -> Tuple[pd.DataFrame, sm.regression.linear_model.RegressionResultsWrapper]:
    """Calcule le terme ECM a partir d'une regression en niveaux."""
    df = df.copy()
    y = df[LOG_GDP]
    X = df[[LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]]
    X = sm.add_constant(X, has_constant="add")
    model = sm.OLS(y, X, missing="drop").fit()
    resid = y - X @ model.params
    df["ecterm"] = resid
    df["l_ecterm"] = resid.groupby(level=0).shift(1)
    return df, model


# -----------------------------------------------------------------------------
# Statistiques descriptives panel
# -----------------------------------------------------------------------------

def panel_variance_decomp(df: pd.DataFrame, variables: Iterable[str]) -> pd.DataFrame:
    """Decomposition variance between/within/two-way/FD pour chaque variable."""
    rows = []
    for var in variables:
        series = df[var].dropna()
        if series.empty:
            continue

        n_entities = series.index.get_level_values(0).nunique()
        nt = series.shape[0]
        avg_t = nt / n_entities if n_entities else np.nan

        overall_var = series.var(ddof=1)
        mean_i = series.groupby(level=0).mean()
        between_var = mean_i.var(ddof=1)

        within = series - series.groupby(level=0).transform("mean")
        within_var = within.var(ddof=1)

        mean_t = series.groupby(level=1).transform("mean")
        twfe = series - series.groupby(level=0).transform("mean") - mean_t + series.mean()
        twfe_var = twfe.var(ddof=1)

        fd = series.groupby(level=0).diff()
        fd_var = fd.var(ddof=1)

        within_pct = (within_var / overall_var * 100.0) if overall_var else np.nan

        rows.append(
            {
                "variable": var,
                "N": n_entities,
                "NT": nt,
                "NT_over_N": avg_t,
                "var_total": overall_var,
                "var_between": between_var,
                "var_within": within_var,
                "var_twfe": twfe_var,
                "var_fd": fd_var,
                "pct_within": within_pct,
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values("pct_within", ascending=False)
    return out


def observation_tables(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Tableaux d'observations par pays et par annee."""
    df_reset = df.reset_index()
    by_country = df_reset.groupby(COUNTRY_COL).size().to_frame("n_obs")
    by_year = df_reset.groupby(YEAR_COL).size().to_frame("n_obs")
    matrix = df_reset.pivot_table(index=COUNTRY_COL, columns=YEAR_COL, values=LOG_GDP, aggfunc="size")
    return {"by_country": by_country, "by_year": by_year, "matrix": matrix}


# -----------------------------------------------------------------------------
# Tests preliminaires
# -----------------------------------------------------------------------------

def _cips_from_linearmodels(series: pd.Series, lags: int = 1) -> Optional[Tuple[float, float]]:
    return None


def _cips_manual(series: pd.Series, lags: int = 1) -> Tuple[float, float]:
    df = series.dropna().reset_index()
    df = df.sort_values([COUNTRY_COL, YEAR_COL])
    yname = series.name

    df["ybar"] = df.groupby(YEAR_COL)[yname].transform("mean")
    df["y_lag"] = df.groupby(COUNTRY_COL)[yname].shift(1)
    df["dy"] = df.groupby(COUNTRY_COL)[yname].diff()

    ybar_by_year = df[[YEAR_COL, "ybar"]].drop_duplicates().sort_values(YEAR_COL)
    ybar_by_year = ybar_by_year.set_index(YEAR_COL)["ybar"]
    df = df.join(ybar_by_year.shift(1).rename("ybar_lag"), on=YEAR_COL)
    df = df.join(ybar_by_year.diff().rename("dybar"), on=YEAR_COL)

    for k in range(1, lags + 1):
        df[f"dy_lag{k}"] = df.groupby(COUNTRY_COL)["dy"].shift(k)

    tstats = []
    for _, g in df.groupby(COUNTRY_COL):
        cols = ["y_lag", "ybar_lag", "dybar"] + [f"dy_lag{k}" for k in range(1, lags + 1)]
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
    pvalue = 2.0 * (1.0 - stats.norm.cdf(abs(cips_stat)))
    return cips_stat, pvalue


def cips_test(series: pd.Series, lags: int = 1) -> Tuple[float, float]:
    """Test CIPS (Pesaran, 2007) avec fallback manuel."""
    res = _cips_from_linearmodels(series, lags=lags)
    if res is not None:
        return res
    return _cips_manual(series, lags=lags)


def pesaran_cd(series: pd.Series) -> Tuple[float, float, float]:
    """Test CD de Pesaran (2004) sur une serie panel."""
    pivot = series.unstack(COUNTRY_COL)
    pivot = pivot.dropna(axis=1, how="all")
    entities = pivot.columns
    n = len(entities)
    if n < 2:
        return np.nan, np.nan, np.nan

    # Nombre moyen d'observations par paire
    t = pivot.shape[0]
    corr_sum = 0.0
    count = 0

    for i in range(n):
        for j in range(i + 1, n):
            x = pivot.iloc[:, i]
            y = pivot.iloc[:, j]
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


def delta_test_pesaran_yamagata(df: pd.DataFrame, y: str, xvars: List[str]) -> Tuple[float, float]:
    """Delta test de Pesaran-Yamagata (2008) pour heterogeneite des pentes."""
    df = df[[y] + xvars].dropna()
    if df.empty:
        return np.nan, np.nan

    X = sm.add_constant(df[xvars], has_constant="add")
    pooled = sm.OLS(df[y], X).fit()
    b_pooled = pooled.params.values

    k = len(xvars)
    s_stat = 0.0
    n_entities = 0

    for _, g in df.groupby(level=0):
        if g.shape[0] <= k + 2:
            continue
        Xi = sm.add_constant(g[xvars], has_constant="add")
        yi = g[y]
        res_i = sm.OLS(yi, Xi).fit()
        sigma2_i = res_i.scale
        diff = (res_i.params.values - b_pooled).reshape(-1, 1)
        xtx = Xi.to_numpy().T @ Xi.to_numpy()
        quad = diff.T @ (xtx / sigma2_i) @ diff
        s_stat += float(np.asarray(quad).squeeze())
        n_entities += 1

    if n_entities == 0:
        return np.nan, np.nan

    delta = np.sqrt(n_entities) * ((s_stat - k) / np.sqrt(2.0 * k))
    pvalue = 2.0 * (1.0 - stats.norm.cdf(abs(delta)))
    return float(delta), float(pvalue)


# -----------------------------------------------------------------------------
# Estimations panel (tableau recapitulatif)
# -----------------------------------------------------------------------------

def estimate_static_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Estime Between, Within, RE-Mundlak, TWFE et FD dans un seul tableau."""
    formula_base = "lrgdpmad ~ 1 + lcpi + lenpr + open + expgdp + iy"

    between = BetweenOLS.from_formula(formula_base, data=df).fit()
    within = PanelOLS.from_formula(formula_base + " + EntityEffects", data=df).fit(
        cov_type="clustered", cluster_entity=True
    )

    # Mundlak: ajoute les moyennes individuelles des regressseurs
    df_m = df.copy()
    for v in ["lcpi", "lenpr", "open", "expgdp", "iy"]:
        df_m[f"{v}_mean"] = df_m.groupby(level=0)[v].transform("mean")

    formula_mundlak = (
        formula_base + " + lcpi_mean + lenpr_mean + open_mean + expgdp_mean + iy_mean"
    )
    re_mundlak = RandomEffects.from_formula(formula_mundlak, data=df_m).fit()

    twfe = PanelOLS.from_formula(formula_base + " + EntityEffects + TimeEffects", data=df).fit(
        cov_type="clustered", cluster_entity=True
    )

    fd = FirstDifferenceOLS.from_formula("lrgdpmad ~ lcpi + lenpr + open + expgdp + iy", data=df).fit()

    results = {
        "between": between,
        "within": within,
        "re_mundlak": re_mundlak,
        "twfe": twfe,
        "fd": fd,
    }

    table = _results_to_table(results)
    return table


def _results_to_table(results: Dict[str, object]) -> pd.DataFrame:
    rows = []
    for model_name, res in results.items():
        params = res.params
        se = res.std_errors
        tstats = res.tstats
        pvals = res.pvalues
        for var in params.index:
            rows.append(
                {
                    "model": model_name,
                    "variable": var,
                    "coef": params[var],
                    "se": se[var],
                    "t": tstats[var],
                    "p": pvals[var],
                }
            )
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Modele dynamique ARDL + Anderson-Hsiao
# -----------------------------------------------------------------------------

def fit_dynamic_ols(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    """OLS dynamique avec lag de la variable dependante."""
    y = df["dlrgdpmad"]
    X = df[
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
    ]
    X = sm.add_constant(X, has_constant="add")
    res = sm.OLS(y, X, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 1})
    return res


def fit_dynamic_iv(df: pd.DataFrame) -> IV2SLS:
    """IV Anderson-Hsiao avec instruments en niveaux t-2."""
    y = df["dlrgdpmad"]
    endog = df[["l_dlrgdpmad", "dlenpr"]]
    exog = df[
        [
            "l_dlenpr",
            "dlcpi2",
            "dopen",
            "dexpgdp",
            "diy",
            "l_ecterm",
        ]
    ]
    instruments = df[["l2_lrgdpmad", "l2_lenpr"]]

    model = IV2SLS(y, sm.add_constant(exog, has_constant="add"), endog, instruments)
    res = model.fit(cov_type="robust")
    return res


def hausman_test(ols_res, iv_res) -> Tuple[float, float]:
    """Test de Hausman entre OLS et IV."""
    b_ols = ols_res.params
    b_iv = iv_res.params

    common = [k for k in b_ols.index if k in b_iv.index]
    b_diff = (b_iv[common] - b_ols[common]).values

    v_ols = ols_res.cov_params().loc[common, common]
    v_iv = iv_res.cov.loc[common, common]

    v_diff = v_iv - v_ols
    try:
        stat = float(b_diff.T @ np.linalg.inv(v_diff) @ b_diff)
        df = len(common)
        pval = 1.0 - stats.chi2.cdf(stat, df)
        return stat, pval
    except np.linalg.LinAlgError:
        return np.nan, np.nan


def compute_irf(beta1: float, beta2: float, rho: float, horizons: int = 4) -> List[float]:
    """IRF pour 4 periodes en suivant la recursion demandee."""
    irf = []
    if horizons < 1:
        return irf

    tau1 = beta1
    irf.append(tau1)

    if horizons >= 2:
        tau2 = rho * beta1 + beta2
        irf.append(tau2)

    for h in range(3, horizons + 1):
        tau_prev = irf[-1]
        tau_h = rho * tau_prev + rho * beta2
        irf.append(tau_h)

    return irf


def irf_standard_errors(beta1: float, beta2: float, rho: float, se: Dict[str, float]) -> List[float]:
    """Approximation simple des SE des IRF sans covariance."""
    se_b1 = se.get("dlenpr", np.nan)
    se_b2 = se.get("l_dlenpr", np.nan)
    se_rho = se.get("l_dlrgdpmad", np.nan)

    out = []
    if np.isnan(se_b1) or np.isnan(se_b2) or np.isnan(se_rho):
        return [np.nan] * 4

    # tau1
    out.append(se_b1)

    # tau2
    out.append(np.sqrt((rho * se_b1) ** 2 + (beta1 * se_rho) ** 2 + se_b2 ** 2))

    # tau3, tau4: recursion approchee
    tau_prev = None
    for _ in range(3, 5):
        if tau_prev is None:
            tau_prev = rho * beta1 + beta2
        se_tau = np.sqrt((rho * out[-1]) ** 2 + (se_rho * tau_prev) ** 2 + (rho * se_b2) ** 2)
        out.append(se_tau)
        tau_prev = rho * tau_prev + rho * beta2

    return out


# -----------------------------------------------------------------------------
# CCEMG avec IV
# -----------------------------------------------------------------------------

def infer_instruments(df: pd.DataFrame) -> List[str]:
    if INSTRUMENT_COLS:
        return [c for c in INSTRUMENT_COLS if c in df.columns]

    patterns = ["OPEC", "US", "SHOCK", "SUPPLY", "INSTR", "IV_"]
    candidates = []
    for c in df.columns:
        uc = c.upper()
        if any(p in uc for p in patterns):
            candidates.append(c)
    return candidates


def add_cross_section_means(df: pd.DataFrame, variables: List[str]) -> pd.DataFrame:
    df = df.copy()
    for var in variables:
        cs = df.groupby(level=1)[var].transform("mean")
        df[f"{var}_csmean"] = cs
        df[f"{var}_csmean_lag"] = cs.groupby(level=0).shift(1)
    return df


def _reduce_full_rank(frame: pd.DataFrame) -> pd.DataFrame:
    """Supprime les colonnes constantes ou lineairement redondantes."""
    frame = frame.copy()
    frame = frame.loc[:, frame.nunique(dropna=True) > 1]
    kept: List[str] = []
    for column in frame.columns:
        candidate = frame[kept + [column]].dropna()
        if candidate.empty:
            continue
        matrix = candidate.to_numpy(dtype=float)
        if np.linalg.matrix_rank(matrix) > len(kept):
            kept.append(column)
    return frame[kept]


def estimate_ccemg(
    df: pd.DataFrame,
    dep: str,
    exog_vars: List[str],
    endog_vars: List[str],
    instruments: List[str],
    exog_only: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Estime CCEMG pays par pays, retourne coefs par pays et MG final."""
    vars_for_means = [dep] + exog_vars + endog_vars
    df = add_cross_section_means(df, vars_for_means)

    cs_vars = [f"{v}_csmean" for v in vars_for_means] + [f"{v}_csmean_lag" for v in vars_for_means]

    rows = []
    for country, g in df.groupby(level=0):
        g = g.copy()
        y = g[dep]
        exog = g[exog_vars + cs_vars]

        if exog_only or not instruments:
            model_frame = pd.concat([y, exog], axis=1).dropna()
            model_frame = _reduce_full_rank(model_frame)
            y_reg = model_frame[dep]
            exog_reg = sm.add_constant(model_frame.drop(columns=[dep]), has_constant="add")
            res = sm.OLS(y_reg, exog_reg, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 1})
            params = res.params
            se = res.bse
        else:
            endog = g[endog_vars]
            instr = g[instruments]

            model_frame = pd.concat([y, exog, endog, instr], axis=1).dropna()
            model_frame = _reduce_full_rank(model_frame)
            y_reg = model_frame[dep]
            exog_reg = model_frame[[c for c in exog.columns if c in model_frame.columns]]
            endog_reg = model_frame[[c for c in endog.columns if c in model_frame.columns]]
            instr_reg = model_frame[[c for c in instr.columns if c in model_frame.columns]]
            res = IV2SLS(y_reg, sm.add_constant(exog_reg, has_constant="add"), endog_reg, instr_reg).fit(cov_type="kernel", kernel="bartlett", bandwidth=1)
            params = res.params
            se = res.std_errors

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

    # MG
    mg_rows = []
    for var, g in country_df.groupby("variable"):
        if g["coef"].dropna().empty:
            continue
        mean_coef = g["coef"].mean()
        se_mg = g["coef"].std(ddof=1) / np.sqrt(g.shape[0]) if g.shape[0] > 1 else np.nan
        tstat = mean_coef / se_mg if se_mg and np.isfinite(se_mg) else np.nan
        pval = 2.0 * (1.0 - stats.norm.cdf(abs(tstat))) if np.isfinite(tstat) else np.nan
        mg_rows.append(
            {"variable": var, "coef": mean_coef, "se": se_mg, "t": tstat, "p": pval}
        )

    mg_df = pd.DataFrame(mg_rows)
    return country_df, mg_df


# -----------------------------------------------------------------------------
# Robustesse
# -----------------------------------------------------------------------------

def build_robustness_table(
    df_base: pd.DataFrame,
    df_full: pd.DataFrame,
    dep: str,
    exog_vars: List[str],
    endog_vars: List[str],
    instruments: List[str],
) -> pd.DataFrame:
    """Construit la table de robustesse (6 colonnes)."""
    variants = {}

    # (1) inst
    _, mg_inst = estimate_ccemg(df_base, dep, exog_vars, endog_vars, instruments, exog_only=False)
    variants["inst"] = mg_inst

    # (2) exog
    _, mg_exog = estimate_ccemg(df_base, dep, exog_vars, endog_vars, instruments, exog_only=True)
    variants["exog"] = mg_exog

    # (3) womod: sans mod et dlenprmod
    exog_womod = [v for v in exog_vars if v not in ("mod", "dlenprmod")]
    endog_womod = endog_vars
    _, mg_womod = estimate_ccemg(df_base, dep, exog_womod, endog_womod, instruments, exog_only=False)
    variants["womod"] = mg_womod

    # (4) recession: ajoute dummy 2009
    df_rec = df_base.copy()
    df_rec["recession_2009"] = (df_rec.index.get_level_values(YEAR_COL) == 2009).astype(int)
    exog_rec = exog_vars + ["recession_2009"]
    _, mg_rec = estimate_ccemg(df_rec, dep, exog_rec, endog_vars, instruments, exog_only=False)
    variants["recession"] = mg_rec

    # (5) gerire: exclure Allemagne 1990 et Irlande 2015
    df_gerire = df_base.copy()
    idx = df_gerire.index
    country_vals = idx.get_level_values(COUNTRY_COL)
    year_vals = idx.get_level_values(YEAR_COL)
    if country_vals.str.match(r"^\d+$").any():
        mask = ~(((country_vals == "5") & (year_vals == 1990)) | ((country_vals == "11") & (year_vals == 2015)))
    else:
        mask = ~(
            ((country_vals.str.contains("germany", case=False)) & (year_vals == 1990))
            | ((country_vals.str.contains("ireland", case=False)) & (year_vals == 2015))
        )
    df_gerire = df_gerire[mask]
    _, mg_gerire = estimate_ccemg(df_gerire, dep, exog_vars, endog_vars, instruments, exog_only=False)
    variants["gerire"] = mg_gerire

    # (6) sixties: inclure 1960-1961
    df_sixties = df_full.copy()
    _, mg_sixties = estimate_ccemg(df_sixties, dep, exog_vars, endog_vars, instruments, exog_only=False)
    variants["sixties"] = mg_sixties

    # Assemble en tableau
    rows = []
    for name, table in variants.items():
        for _, row in table.iterrows():
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


# -----------------------------------------------------------------------------
# Graphiques
# -----------------------------------------------------------------------------

def plot_energy_prices(df: pd.DataFrame, out_path: Path) -> None:
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 6))
    for country, g in df.reset_index().groupby(COUNTRY_COL):
        g = g.sort_values(YEAR_COL)
        plt.plot(g[YEAR_COL], g[LOG_ENERGY], alpha=0.6, linewidth=1.0, label=country)

    plt.title("Evolution des prix de l'energie par pays")
    plt.xlabel("Annee")
    plt.ylabel("lenpr (log)")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_country_coeffs(country_df: pd.DataFrame, out_path: Path, var: str = "dlenpr") -> None:
    import matplotlib.pyplot as plt

    data = country_df[country_df["variable"] == var].copy()
    data = data.dropna(subset=["coef", "se"])
    data = data.sort_values("coef")
    if data.empty:
        return

    y_pos = np.arange(len(data))
    ci_low = data["coef"] - 1.96 * data["se"]
    ci_high = data["coef"] + 1.96 * data["se"]

    plt.figure(figsize=(8, max(4, 0.25 * len(data))))
    plt.hlines(y_pos, ci_low, ci_high, color="gray")
    plt.plot(data["coef"], y_pos, "o", color="black")
    plt.yticks(y_pos, data["country"])
    plt.axvline(0, color="red", linestyle="--", linewidth=1)
    plt.title("Coefficients pays pour dlenpr (CCEMG)")
    plt.xlabel("Coefficient")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_irf(irf_df: pd.DataFrame, out_path: Path) -> None:
    import matplotlib.pyplot as plt

    plt.figure(figsize=(6, 4))
    plt.plot(irf_df["h"], irf_df["tau"], marker="o", color="black")
    plt.fill_between(irf_df["h"], irf_df["lower"], irf_df["upper"], color="gray", alpha=0.3)
    plt.axhline(0, color="red", linestyle="--", linewidth=1)
    plt.title("IRF moyenne OCDE (4 periodes)")
    plt.xlabel("Periode")
    plt.ylabel("Reponse")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_boxplots_transforms(df: pd.DataFrame, out_path: Path) -> None:
    import matplotlib.pyplot as plt

    df = df.copy()
    df["GDP_within"] = df[LOG_GDP] - df.groupby(level=0)[LOG_GDP].transform("mean")
    mean_t = df.groupby(level=1)[LOG_GDP].transform("mean")
    df["GDP_twfe"] = df[LOG_GDP] - df.groupby(level=0)[LOG_GDP].transform("mean") - mean_t + df[LOG_GDP].mean()

    df_reset = df.reset_index()
    countries = df_reset[COUNTRY_COL].unique()

    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=False)
    for ax, col, title in zip(
        axes,
        ["GDP_within", "dlrgdpmad", "GDP_twfe"],
        ["Within", "First differences", "Two-way FE"],
    ):
        data = [df_reset.loc[df_reset[COUNTRY_COL] == c, col].dropna().values for c in countries]
        ax.boxplot(data, labels=countries, vert=True, showfliers=False)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=90)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


# -----------------------------------------------------------------------------
# Pipeline principale
# -----------------------------------------------------------------------------

def run_all() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    df_raw = load_data(DATA_PATH)
    df = prepare_panel(df_raw)
    df = add_transformations(df)
    df, ecm_model = compute_ecm(df)

    df_full = df

    # Option echantillon de base pour CCEMG
    if BASE_START_YEAR is not None:
        df_base = df_full[df_full.index.get_level_values(YEAR_COL) >= BASE_START_YEAR]
    else:
        df_base = df_full

    # 1) Stats descriptives
    var_table = panel_variance_decomp(df_full, CORE_VARS)
    var_table.to_csv(OUTPUT_DIR / "descriptive_variance.csv", index=False)

    quasi = var_table[var_table["pct_within"] < 10.0]
    quasi.to_csv(OUTPUT_DIR / "quasi_time_invariant.csv", index=False)

    obs_tables = observation_tables(df_full)
    obs_tables["by_country"].to_csv(OUTPUT_DIR / "obs_by_country.csv")
    obs_tables["by_year"].to_csv(OUTPUT_DIR / "obs_by_year.csv")
    obs_tables["matrix"].to_csv(OUTPUT_DIR / "obs_matrix.csv")

    # 2) Tests preliminaires
    cips_rows = []
    for var in [LOG_GDP, LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]:
        stat_lvl, p_lvl = cips_test(df_full[var], lags=1)
        dvar = f"d{var}"
        stat_diff, p_diff = cips_test(df_full[dvar], lags=1)
        cips_rows.append(
            {
                "variable": var,
                "stat_level": stat_lvl,
                "pvalue_level": p_lvl,
                "stat_diff": stat_diff,
                "pvalue_diff": p_diff,
            }
        )
    pd.DataFrame(cips_rows).to_csv(OUTPUT_DIR / "cips_tests.csv", index=False)

    cd_rows = []
    for var in [LOG_GDP, LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]:
        stat, pval, avg_corr = pesaran_cd(df_full[var])
        cd_rows.append({"variable": var, "cd_stat": stat, "pvalue": pval, "avg_corr": avg_corr})
    pd.DataFrame(cd_rows).to_csv(OUTPUT_DIR / "cd_tests.csv", index=False)

    delta_stat, delta_p = delta_test_pesaran_yamagata(
        df_full, LOG_GDP, [LOG_ENERGY, LOG_CPI, OPEN_TRADE, GOV_EXP, INVEST]
    )
    pd.DataFrame(
        [{"delta_stat": delta_stat, "pvalue": delta_p}]
    ).to_csv(OUTPUT_DIR / "delta_test.csv", index=False)

    # 3) Estimations panel
    panel_table = estimate_static_panel(df_full)
    panel_table.to_csv(OUTPUT_DIR / "panel_models_table.csv", index=False)

    # 4) Modele dynamique
    dyn_ols = fit_dynamic_ols(df_full)
    dyn_iv = fit_dynamic_iv(df_full)

    ols_table = pd.DataFrame(
        {
            "coef": dyn_ols.params,
            "se": dyn_ols.bse,
            "t": dyn_ols.tvalues,
            "p": dyn_ols.pvalues,
        }
    )
    ols_table.to_csv(OUTPUT_DIR / "ardl_ols.csv")

    iv_table = pd.DataFrame(
        {
            "coef": dyn_iv.params,
            "se": dyn_iv.std_errors,
            "t": dyn_iv.tstats,
            "p": dyn_iv.pvalues,
        }
    )
    iv_table.to_csv(OUTPUT_DIR / "ardl_iv.csv")

    # Premier stage
    try:
        fs = dyn_iv.first_stage
        fs_rows = []
        for name, stage in fs.items():
            fs_rows.append({"endog": name, "r2": stage.rsquared})
        pd.DataFrame(fs_rows).to_csv(OUTPUT_DIR / "first_stage_r2.csv", index=False)
    except Exception:
        pd.DataFrame([], columns=["endog", "r2"]).to_csv(OUTPUT_DIR / "first_stage_r2.csv", index=False)

    # Hausman OLS vs IV
    h_stat, h_p = hausman_test(dyn_ols, dyn_iv)
    pd.DataFrame([{"hausman_stat": h_stat, "pvalue": h_p}]).to_csv(
        OUTPUT_DIR / "hausman_ols_iv.csv", index=False
    )

    # IRF et long terme
    rho = dyn_iv.params.get("l_dlrgdpmad", np.nan)
    b1 = dyn_iv.params.get("dlenpr", np.nan)
    b2 = dyn_iv.params.get("l_dlenpr", np.nan)
    irf_vals = compute_irf(b1, b2, rho, horizons=4)
    se_irf = irf_standard_errors(b1, b2, rho, dyn_iv.std_errors.to_dict())

    irf_df = pd.DataFrame(
        {
            "h": np.arange(1, 5),
            "tau": irf_vals,
            "se": se_irf,
        }
    )
    irf_df["lower"] = irf_df["tau"] - 1.96 * irf_df["se"]
    irf_df["upper"] = irf_df["tau"] + 1.96 * irf_df["se"]
    irf_df.to_csv(OUTPUT_DIR / "irf.csv", index=False)

    if np.isfinite(rho) and abs(rho) >= 1:
        warnings.warn("|rho| >= 1: IRF explosive et LT invalide.")

    lt_coef = (b1 + b2) / (1.0 - rho) if np.isfinite(rho) and abs(rho) < 1 else np.nan
    pd.DataFrame([{"lt_coef": lt_coef, "rho": rho}]).to_csv(
        OUTPUT_DIR / "long_term.csv", index=False
    )

    # 5) CCEMG avec IV
    instruments = infer_instruments(df)
    if not instruments:
        warnings.warn("Aucun instrument detecte. dlenpr sera traite comme exogene.")

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
        df_base, dep, exog_vars, endog_vars, instruments, exog_only=not instruments
    )
    cc_country.to_csv(OUTPUT_DIR / "ccemg_country_coefs.csv", index=False)
    cc_mg.to_csv(OUTPUT_DIR / "ccemg_mg.csv", index=False)

    robustness = build_robustness_table(df_base, df_full, dep, exog_vars, endog_vars, instruments)
    robustness.to_csv(OUTPUT_DIR / "ccemg_robustness_table.csv", index=False)

    # 6) Graphiques
    plot_energy_prices(df_full, OUTPUT_DIR / "fig1_energy_prices.png")
    plot_country_coeffs(cc_country, OUTPUT_DIR / "fig2_country_coeffs.png", var="dlenpr")
    plot_irf(irf_df, OUTPUT_DIR / "fig3_irf.png")
    plot_boxplots_transforms(df_full, OUTPUT_DIR / "fig4_boxplots.png")


if __name__ == "__main__":
    run_all()
