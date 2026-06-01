"""
03_exports.py — Génération stricte des CSV et PNG académiques
=============================================================
Référence : Huntington & Liddle (2022), "How energy prices shape OECD
            economic growth", Energy Economics, 111, 106082.

Ce module exporte les Tables 1 à 6 (CSV + PNG format publication) et les
Figures A.1 à A.7 (PNG, thème académique fond blanc).

Règles de formatage appliquées :
  - Table 1 : CV vide pour les variables en différence première (D.)
  - Table 2 : Sections "No Trend" (niveaux + diffs) et "Trend" (niveaux)
  - Table 4 : Noms exacts (L.D.CPI>2%, D.Energy×mod) + ligne Price effect
  - Table 5 : Supply → Exports, Demand → Imports
  - Fig. A7 : D.GDP ligne continue + résidus pointillés superposés
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


# ── Constantes partagées (identiques à 01_data_prep.py) ─────────────────────
COUNTRY_COL = "country"
YEAR_COL    = "yr"
LOG_GDP     = "lrgdpmad"
LOG_CPI     = "lcpi"
LOG_ENERGY  = "lenpr"
OPEN_TRADE  = "open"
GOV_EXP     = "expgdp"
INVEST      = "iy"

COUNTRY_ISO = {
    "aus": "Australia",   "bel": "Belgium",       "can": "Canada",
    "che": "Switzerland", "deu": "Germany",        "dnk": "Denmark",
    "esp": "Spain",       "fin": "Finland",        "fra": "France",
    "gbr": "United Kingdom", "irl": "Ireland",     "ita": "Italy",
    "jpn": "Japan",       "nld": "Netherlands",    "nor": "Norway",
    "prt": "Portugal",    "swe": "Sweden",         "usa": "United States",
}

PAPER_RC = {
    "font.family":       "DejaVu Serif",
    "font.size":         9,
    "axes.titlesize":    9,
    "axes.labelsize":    8,
    "xtick.labelsize":   7,
    "ytick.labelsize":   7,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "figure.dpi":        200,
}


# ═════════════════════════════════════════════════════════════════════════════
# Helpers de mise en forme
# ═════════════════════════════════════════════════════════════════════════════

def _stars(p: float) -> str:
    """Étoiles de significativité (* p<0.05, ** p<0.01)."""
    if not np.isfinite(p):
        return ""
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def _fmt_coef(coef: float, se: float, p: float) -> tuple[str, str]:
    """Retourne (coef_string, se_string) au format papier b/(se)."""
    if not np.isfinite(coef):
        return "", ""
    c = f"{coef:.3f}{_stars(p)}"
    s = f"({se:.3f})" if np.isfinite(se) else ""
    return c, s


def _country_label(c: str) -> str:
    """Retourne le nom complet d'un pays depuis son code ISO."""
    return COUNTRY_ISO.get(c.lower().strip(), c)


# ═════════════════════════════════════════════════════════════════════════════
# Rendu PNG académique
# ═════════════════════════════════════════════════════════════════════════════

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

    # En-tête gris + gras
    for j in range(n_cols):
        t[0, j].set_facecolor("#d9d9d9")
        t[0, j].set_text_props(fontweight="bold")

    # Zèbre + alignement gauche 1ère colonne
    for i in range(1, n_rows + 1):
        bg = "#f7f7f7" if i % 2 == 0 else "white"
        t[i, 0].set_text_props(ha="left")
        for j in range(n_cols):
            t[i, j].set_facecolor(bg)

    ax.set_title(title, fontsize=9, fontweight="bold", loc="left", pad=3)
    if notes:
        fig.text(0.01, 0.005, notes, fontsize=6.5, va="bottom",
                 wrap=True, style="italic")
    plt.tight_layout()
    plt.savefig(filepath, dpi=200, bbox_inches="tight")
    plt.close()


# ═════════════════════════════════════════════════════════════════════════════
# TABLE 1 — Data Summary
# ═════════════════════════════════════════════════════════════════════════════

def export_table1(df: pd.DataFrame, out_dir: Path) -> None:
    """Statistiques descriptives. CV vide pour les variables en D."""
    varmap = {
        LOG_GDP:    "GDP",         LOG_CPI:    "CPI",
        LOG_ENERGY: "ENERGY",      OPEN_TRADE: "OpenTrade",
        GOV_EXP:    "GovExp",      INVEST:     "Invest",
        f"d{LOG_GDP}":    "D.GDP",     f"d{LOG_CPI}":    "D.CPI",
        f"d{LOG_ENERGY}": "D.ENERGY",  f"d{OPEN_TRADE}": "D.OpenTrade",
        f"d{GOV_EXP}":    "D.GovExp",  f"d{INVEST}":     "D.Invest",
    }

    df_r = df.reset_index()
    rows = []
    for col, label in varmap.items():
        if col not in df_r.columns:
            continue
        s = df_r[col].dropna()
        mean, std_w, mn, mx = s.mean(), s.std(ddof=1), s.min(), s.max()

        # Règle : pas de CV pour les variables en différence première
        is_diff = label.startswith("D.")
        cv = (std_w / mean) if (mean != 0 and not is_diff) else np.nan
        cv_str = f"{cv:.3f}" if np.isfinite(cv) else ""

        rows.append({
            "Variable":            label,
            "Mean":                f"{mean:.3f}",
            "Standard deviation":  f"{std_w:.3f}",
            "Coeff. of variation": cv_str,
            "Minimum":             f"{mn:.3f}",
            "Maximum":             f"{mx:.3f}",
        })

    tbl = pd.DataFrame(rows)
    tbl.to_csv(out_dir / "table1_data_summary.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 1 – Data Summary",
        notes=("Notes: Real GDP (GDP), CPI and Energy Prices (ENERGY) are "
               "in logarithms. Open Trade (OpenTrade), Gov Expenditures "
               "(GovExp) and Investment (Invest) are % of GDP. Overall "
               "standard deviations, minimums and maximums are reported. "
               "D. denotes change."),
        filepath=out_dir / "table1_data_summary.png",
        fig_w=9.5, row_h=0.30,
    )
    print("[OK] Table 1 exportée")


# ═════════════════════════════════════════════════════════════════════════════
# TABLE 2 — CIPS Unit Root Tests
# ═════════════════════════════════════════════════════════════════════════════

def export_table2(cips_df: pd.DataFrame, out_dir: Path) -> None:
    """
    Table 2 : Pesaran (2007) panel unit root tests.

    Structure stricte du papier :
    - Section "No Trend" : niveaux (Lag 0-3) puis différences (D.)
    - Section "Trend"    : niveaux seulement (avec tendance)
    """
    varmap = {
        LOG_GDP:    "GDP",       LOG_CPI:    "CPI",
        LOG_ENERGY: "ENERGY",    OPEN_TRADE: "OpenTrade",
        GOV_EXP:    "GovExp",    INVEST:     "Invest",
    }

    def fmt(s, p):
        if not np.isfinite(float(s)):
            return "."
        return f"{float(s):.2f}{_stars(float(p))}"

    rows = []

    # ── Section "No Trend" ──────────────────────────────────────────────
    rows.append({"Variable": "No Trend",
                 "Lag 0": "", "Lag 1": "", "Lag 2": "", "Lag 3": ""})

    # Niveaux
    for var in varmap:
        sub = cips_df[cips_df["variable"] == var]
        lag_map = {int(r["lag"]): (r["stat_level"], r["pvalue_level"])
                   for _, r in sub.iterrows()}
        lvl = {k: lag_map.get(k, (np.nan, np.nan)) for k in range(4)}
        rows.append({
            "Variable": varmap[var],
            "Lag 0": fmt(*lvl[0]), "Lag 1": fmt(*lvl[1]),
            "Lag 2": fmt(*lvl[2]), "Lag 3": fmt(*lvl[3]),
        })

    # Différences
    for var in varmap:
        sub = cips_df[cips_df["variable"] == var]
        lag_map = {int(r["lag"]): (r["stat_diff"], r["pvalue_diff"])
                   for _, r in sub.iterrows()}
        dif = {k: lag_map.get(k, (np.nan, np.nan)) for k in range(4)}
        rows.append({
            "Variable": f"D.{varmap[var]}",
            "Lag 0": fmt(*dif[0]), "Lag 1": fmt(*dif[1]),
            "Lag 2": fmt(*dif[2]), "Lag 3": fmt(*dif[3]),
        })

    # ── Section "Trend" ─────────────────────────────────────────────────
    rows.append({"Variable": "Trend",
                 "Lag 0": "", "Lag 1": "", "Lag 2": "", "Lag 3": ""})

    # Niveaux seulement (avec tendance)
    for var in varmap:
        sub = cips_df[cips_df["variable"] == var]
        lag_map = {int(r["lag"]): (r["stat_level_t"],
                                    r.get("pvalue_level_t", np.nan))
                   for _, r in sub.iterrows()}
        lvl_t = {k: lag_map.get(k, (np.nan, np.nan)) for k in range(4)}
        rows.append({
            "Variable": varmap[var],
            "Lag 0": fmt(*lvl_t[0]), "Lag 1": fmt(*lvl_t[1]),
            "Lag 2": fmt(*lvl_t[2]), "Lag 3": fmt(*lvl_t[3]),
        })

    tbl = pd.DataFrame(rows).rename(columns={
        "0": "Lag 0", "1": "Lag 1", "2": "Lag 2", "3": "Lag 3"
    })
    tbl.to_csv(out_dir / "table2_cips_unitroot.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 2 – Pesaran Panel Unit Root Tests",
        notes=("Notes: * p<0.05; ** p<0.01. D. = first-difference. "
               "Null: all panels have a unit root. "
               "The statistic reported is the raw t-bar."),
        filepath=out_dir / "table2_cips_unitroot.png",
        fig_w=8.5, row_h=0.28,
    )
    print("[OK] Table 2 exportée")


# ═════════════════════════════════════════════════════════════════════════════
# TABLE 3 — CCE-MG: Unweighted vs Robust
# ═════════════════════════════════════════════════════════════════════════════

def export_table3(
    mg_cce: pd.DataFrame,
    mg_robust: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Table 3 : CCE-MG coefficients (unweighted vs Huber-robust)."""
    VAR_ORDER = [
        ("dlcpi",      "D.CPI"),
        ("dlenpr",     "D.Energy"),
        ("dopen",      "D.OpenTrade"),
        ("dexpgdp",    "D.GovExp"),
        ("diy",        "D.Invest"),
        ("l_lrgdpmad", "L.GDP"),
        ("l_lcpi",     "L.CPI"),
        ("l_open",     "L.OpenTrade"),
        ("l_iy",       "L.Invest"),
        ("const",      "_cons"),
    ]

    def extract(mg):
        out = {}
        for code, label in VAR_ORDER:
            r = mg[mg["variable"] == code]
            if r.empty and code == "const":
                # Fallback : R produit "(Intercept)" au lieu de "const"
                r = mg[mg["variable"] == "(Intercept)"]
            if r.empty:
                out[label] = ("", "")
            else:
                out[label] = _fmt_coef(
                    r.iloc[0]["coef"], r.iloc[0]["se"],
                    r.iloc[0].get("p", np.nan))
        return out

    d_cce    = extract(mg_cce)
    d_robust = extract(mg_robust)

    rows = []
    for _, label in VAR_ORDER:
        c1, s1 = d_cce.get(label, ("", ""))
        c2, s2 = d_robust.get(label, ("", ""))
        if c1 or c2:
            rows.append({"Variable": label, "cce": c1, "ccerobust": c2})
            rows.append({"Variable": "",    "cce": s1, "ccerobust": s2})

    tbl = pd.DataFrame(rows)
    tbl.to_csv(out_dir / "table3_cce_robust.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 3 – CCE-MG: Unweighted vs outlier-robust estimates",
        notes="Notes: b/(se) format. * p<0.05; ** p<0.01. D. = change; L. = lag.",
        filepath=out_dir / "table3_cce_robust.png",
        fig_w=7.5, row_h=0.26,
    )
    print("[OK] Table 3 exportée")


# ═════════════════════════════════════════════════════════════════════════════
# TABLE 4 — CCEMG Robustness (6 specifications)
# ═════════════════════════════════════════════════════════════════════════════

def export_table4(robustness_df: pd.DataFrame, out_dir: Path) -> None:
    """
    Table 4 : 6 colonnes de robustesse CCEMG.

    Labels exacts du papier : L.D.CPI>2%, D.Energy×mod, etc.
    Ligne finale : "Price effect (post-1982)" = D.Energy + D.Energy×mod.
    """
    VARIANTS = ["inst", "exog", "womod", "recession", "gerire", "sixties"]
    COL_LABELS = {
        "inst": "inst", "exog": "exog", "womod": "w/o_mod",
        "recession": "recession", "gerire": "ger_ire", "sixties": "sixties",
    }
    VAR_ORDER = [
        ("l_dlcpi2",       "L.D.CPI>2%"),
        ("dopen",          "D.OpenTrade"),
        ("dexpgdp",        "D.GovExp"),
        ("diy",            "D.Invest"),
        ("l_lrgdpmad",     "L.GDP"),
        ("l_lcpi",         "L.CPI"),
        ("l_open",         "L.OpenTrade"),
        ("l_iy",           "L.Invest"),
        ("mod",            "mod"),
        ("dlenprmod",      "D.Energy×mod"),
        ("dlenpr",         "D.Energy"),
        ("recession_2009", "recess"),
        ("const",          "_cons"),
    ]

    def get(sub, vcode, field):
        r = sub[sub["variable"] == vcode]
        return r.iloc[0][field] if not r.empty else np.nan

    col_subs = {v: robustness_df[robustness_df["variant"] == v]
                for v in VARIANTS}
    rows = []

    for vcode, vlabel in VAR_ORDER:
        row_c = {"Variable": vlabel}
        row_s = {"Variable": ""}
        any_val = False
        for v in VARIANTS:
            coef = get(col_subs[v], vcode, "coef")
            se   = get(col_subs[v], vcode, "se")
            p    = get(col_subs[v], vcode, "p")
            c, s = _fmt_coef(coef, se, p)
            if c:
                any_val = True
            row_c[COL_LABELS[v]] = c
            row_s[COL_LABELS[v]] = s
        if any_val:
            rows.extend([row_c, row_s])

    # Ligne "Price effect (post-1982)"
    pe_row = {"Variable": "Price effect (post-1982)"}
    for v in VARIANTS:
        b_e = get(col_subs[v], "dlenpr",    "coef")
        b_m = get(col_subs[v], "dlenprmod", "coef")
        pe  = (b_e + b_m if np.isfinite(b_e) and np.isfinite(b_m)
               else b_e)
        pe_row[COL_LABELS[v]] = f"{pe:.3f}" if np.isfinite(pe) else ""
    rows.append(pe_row)

    tbl = pd.DataFrame(rows).fillna("")
    tbl.to_csv(out_dir / "table4_ccemg_robustness.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 4 CCE-Mean-group estimates for real GDP growth",
        notes=("Notes: b/(se) format. * p<0.05; ** p<0.01. "
               "inst=IV; exog=exogenous; w/o_mod=no split; "
               "recession=2009 dummy; ger_ire=excl outliers; "
               "sixties=incl 1960."),
        filepath=out_dir / "table4_ccemg_robustness.png",
        fig_w=10.5, row_h=0.26,
    )
    print("[OK] Table 4 exportée")


# ═════════════════════════════════════════════════════════════════════════════
# TABLE 5 — Country-specific responses
# ═════════════════════════════════════════════════════════════════════════════

def export_table5(
    country_coef_df: pd.DataFrame,
    out_dir: Path,
    intensity_df: Optional[pd.DataFrame] = None,
) -> None:
    """
    Table 5 : Intensité + Exports(Supply) + Imports(Demand) + Post/Pre.
    """
    countries = sorted(country_coef_df["country"].unique())
    i_map, e_map, im_map, po_map, pr_map = {}, {}, {}, {}, {}

    if intensity_df is not None and not intensity_df.empty:
        tmp = intensity_df.copy()
        tmp["_k"] = tmp["country"].astype(str).str.strip().str.lower()
        if "intensity" in tmp.columns:
            i_map = tmp.set_index("_k")["intensity"].to_dict()
        if "exports" in tmp.columns:
            e_map = tmp.set_index("_k")["exports"].to_dict()
        if "imports" in tmp.columns:
            im_map = tmp.set_index("_k")["imports"].to_dict()
        if "post_1982" in tmp.columns:
            po_map = tmp.set_index("_k")["post_1982"].to_dict()
        if "pre_1983" in tmp.columns:
            pr_map = tmp.set_index("_k")["pre_1983"].to_dict()

    rows = []
    for c in countries:
        sub = country_coef_df[country_coef_df["country"] == c]
        b_pre = sub.loc[sub["variable"] == "dlenpr",    "coef"]
        b_mod = sub.loc[sub["variable"] == "dlenprmod", "coef"]
        pre   = b_pre.values[0] if len(b_pre)  else np.nan
        mod   = b_mod.values[0] if len(b_mod)  else np.nan
        post  = (pre + mod if np.isfinite(pre) and np.isfinite(mod)
                 else pre)

        k  = str(c).strip().lower()
        nk = _country_label(c).strip().lower()
        intensity = i_map.get(k, i_map.get(nk, np.nan))
        exports   = e_map.get(k, e_map.get(nk, np.nan))
        imports   = im_map.get(k, im_map.get(nk, np.nan))
        post_val  = po_map.get(k, po_map.get(nk, post))
        pre_val   = pr_map.get(k, pr_map.get(nk, pre))

        rows.append({
            "Country":   _country_label(c),
            "Intensity": f"{intensity:.3f}" if np.isfinite(intensity) else "",
            "Exports":   f"{exports:.3f}"   if np.isfinite(exports)   else "",
            "Imports":   f"{imports:.3f}"   if np.isfinite(imports)   else "",
            "Post-1982": f"{post_val:.3f}"  if np.isfinite(post_val)  else ".",
            "Pre-1983":  f"{pre_val:.3f}"   if np.isfinite(pre_val)   else ".",
        })

    # Ligne Average
    pres  = [float(r["Pre-1983"])  for r in rows if r["Pre-1983"]  != "."]
    posts = [float(r["Post-1982"]) for r in rows if r["Post-1982"] != "."]
    rows.append({
        "Country":   "Average",
        "Intensity": "",
        "Exports":   "",
        "Imports":   "",
        "Post-1982": f"{np.mean(posts):.3f}" if posts else ".",
        "Pre-1983":  f"{np.mean(pres):.3f}"  if pres  else ".",
    })

    tbl = pd.DataFrame(rows)
    tbl.to_csv(out_dir / "table5_country_responses.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 5 Individual country energy intensity and responses",
        notes=("Notes: Post-1982 coef = D.Energy + D.Energy×mod. "
               "Pre-1983 coef = D.Energy only. "
               "Intensity uses sheet table5-6 when available."),
        filepath=out_dir / "table5_country_responses.png",
        fig_w=9, row_h=0.28,
    )
    print("[OK] Table 5 exportée")


# ═════════════════════════════════════════════════════════════════════════════
# TABLE 6 — Regressions on intensity
# ═════════════════════════════════════════════════════════════════════════════

def export_table6(
    country_coef_df: pd.DataFrame,
    out_dir: Path,
    intensity_df: Optional[pd.DataFrame] = None,
) -> None:
    """
    Table 6 : 4 régressions cross-section (pre/post × all/excl outliers)
    des réponses pays sur l'intensité énergétique.
    """
    if intensity_df is None or intensity_df.empty:
        tbl = pd.DataFrame([
            {"Specification": "(1) Pre-1983 ~ Intensity",
             "Coef": "n/a", "t-stat": "n/a", "N": 18,
             "F": "n/a", "RMSE": "n/a"},
        ])
    else:
        countries = sorted(country_coef_df["country"].unique())
        coefs = {}
        for c in countries:
            sub   = country_coef_df[country_coef_df["country"] == c]
            b_pre = sub.loc[sub["variable"] == "dlenpr",    "coef"].values
            b_mod = sub.loc[sub["variable"] == "dlenprmod", "coef"].values
            pre   = b_pre[0] if len(b_pre)  else np.nan
            mod   = b_mod[0] if len(b_mod)  else np.nan
            coefs[c] = {
                "pre":  pre,
                "post": (pre + mod if np.isfinite(pre) and np.isfinite(mod)
                         else pre),
            }

        def _run_reg(sub):
            sub = sub.dropna(subset=["y", "intensity"])
            if sub.shape[0] < 3:
                return np.nan, np.nan, np.nan, np.nan, sub.shape[0]
            res = sm.OLS(
                sub["y"],
                sm.add_constant(sub[["intensity"]])
            ).fit(cov_type="HC1")
            return (
                res.params.get("intensity", np.nan),
                res.tvalues.get("intensity", np.nan),
                float(res.fvalue) if np.isfinite(res.fvalue) else np.nan,
                float(np.sqrt(np.mean(res.resid ** 2))),
                sub.shape[0],
            )

        tmp = intensity_df.copy()
        tmp["_k"] = tmp["country"].astype(str).str.strip().str.lower()
        out = []
        for c in countries:
            k  = str(c).strip().lower()
            nk = _country_label(c).strip().lower()
            row = {"country": nk, "pre": coefs[c]["pre"],
                   "post": coefs[c]["post"], "intensity": np.nan,
                   "exclude": False}
            matches = tmp["_k"].isin([k, nk])
            if matches.any():
                if "pre_1983" in tmp.columns:
                    row["pre"] = tmp.loc[matches, "pre_1983"].iloc[0]
                if "post_1982" in tmp.columns:
                    row["post"] = tmp.loc[matches, "post_1982"].iloc[0]
                if "intensity" in tmp.columns:
                    row["intensity"] = tmp.loc[matches, "intensity"].iloc[0]
                if "exclude" in tmp.columns:
                    row["exclude"] = bool(tmp.loc[matches, "exclude"].iloc[0])
            out.append(row)

        reg_df = pd.DataFrame(out)
        spec_rows = []

        coef, tstat, fval, rmse, n = _run_reg(
            reg_df.rename(columns={"pre": "y"}))
        spec_rows.append({
            "Specification": "(1) Pre-1983 ~ Intensity",
            "Coef":   f"{coef:.3f}" if np.isfinite(coef) else "n/a",
            "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a",
            "N": n,
            "F":    f"{fval:.2f}" if np.isfinite(fval) else "n/a",
            "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a",
        })

        coef, tstat, fval, rmse, n = _run_reg(
            reg_df.rename(columns={"post": "y"}))
        spec_rows.append({
            "Specification": "(2) Post-1982 ~ Intensity",
            "Coef":   f"{coef:.3f}" if np.isfinite(coef) else "n/a",
            "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a",
            "N": n,
            "F":    f"{fval:.2f}" if np.isfinite(fval) else "n/a",
            "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a",
        })

        sub_df = reg_df[~reg_df["exclude"]]
        coef, tstat, fval, rmse, n = _run_reg(
            sub_df.rename(columns={"pre": "y"}))
        spec_rows.append({
            "Specification": "(3) Pre-1983 ~ Intensity (excl. outliers)",
            "Coef":   f"{coef:.3f}" if np.isfinite(coef) else "n/a",
            "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a",
            "N": n,
            "F":    f"{fval:.2f}" if np.isfinite(fval) else "n/a",
            "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a",
        })

        coef, tstat, fval, rmse, n = _run_reg(
            sub_df.rename(columns={"post": "y"}))
        spec_rows.append({
            "Specification": "(4) Post-1982 ~ Intensity (excl. outliers)",
            "Coef":   f"{coef:.3f}" if np.isfinite(coef) else "n/a",
            "t-stat": f"{tstat:.2f}" if np.isfinite(tstat) else "n/a",
            "N": n,
            "F":    f"{fval:.2f}" if np.isfinite(fval) else "n/a",
            "RMSE": f"{rmse:.3f}" if np.isfinite(rmse) else "n/a",
        })

        tbl = pd.DataFrame(spec_rows)

    tbl.to_csv(out_dir / "table6_intensity_regression.csv", index=False)
    _render_table_png(
        tbl,
        title="Table 6 Regressions of country-specific responses "
              "on energy intensity",
        notes=("Notes: Intensity = energy use per unit of GDP (EIA). "
               "* p<0.05; ** p<0.01. Robust standard errors."),
        filepath=out_dir / "table6_intensity_regression.png",
        fig_w=9, row_h=0.35,
    )
    print("[OK] Table 6 exportée")


# ═════════════════════════════════════════════════════════════════════════════
# FIGURES A.1 – A.6 : Grille 4×5 par pays
# ═════════════════════════════════════════════════════════════════════════════

def _country_grid(
    df: pd.DataFrame,
    ycol: str,
    ylabel: str,
    suptitle: str,
    figname: str,
    out_dir: Path,
    hline: Optional[float] = None,
) -> None:
    """Grille 4×5 de séries temporelles par pays (style académique)."""
    plt.rcParams.update(PAPER_RC)
    df_r = df.reset_index()
    countries = sorted(df_r[COUNTRY_COL].unique())
    fig, axes = plt.subplots(4, 5, figsize=(13, 8.5))
    axes_flat = axes.flatten()

    for idx, c in enumerate(countries[:20]):
        ax  = axes_flat[idx]
        sub = (df_r[df_r[COUNTRY_COL] == c]
               .sort_values(YEAR_COL)
               .dropna(subset=[ycol]))
        ax.plot(sub[YEAR_COL], sub[ycol], lw=0.85, color="black")
        ax.set_title(_country_label(c), fontsize=6.5, pad=1.5)
        ax.tick_params(labelsize=5.5)
        ax.xaxis.set_major_locator(MultipleLocator(20))
        ax.axvline(1982, color="#aaaaaa", lw=0.6, linestyle=":")
        if hline is not None:
            ax.axhline(hline, color="red", lw=0.5, linestyle="--")

    for idx in range(len(countries), len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.text(0.5, 0.01, "Year", ha="center", fontsize=8)
    fig.text(0.01, 0.5, ylabel, va="center", rotation="vertical",
             fontsize=8)
    fig.suptitle(suptitle, fontsize=9, fontweight="bold", y=1.01)
    plt.tight_layout(rect=[0.03, 0.03, 1, 0.99])
    plt.savefig(out_dir / figname, dpi=200, bbox_inches="tight")
    plt.close()


def export_fig_a1(df, out_dir):
    _country_grid(df, LOG_GDP, "Log Real GDP",
                  "Fig. A.1 – Country real GDP levels (log)",
                  "figA1_gdp_levels.png", out_dir)
    print("[OK] Fig. A.1")


def export_fig_a2(df, out_dir):
    _country_grid(df, LOG_CPI, "Log CPI",
                  "Fig. A.2 – Country CPI levels (log)",
                  "figA2_cpi_levels.png", out_dir)
    print("[OK] Fig. A.2")


def export_fig_a3(df, out_dir):
    _country_grid(df, LOG_ENERGY, "Log Energy Price",
                  "Fig. A.3 – Country energy price levels (log)",
                  "figA3_energy_levels.png", out_dir)
    print("[OK] Fig. A.3")


def export_fig_a4(df, out_dir):
    _country_grid(df, OPEN_TRADE, "OpenTrade (% GDP)",
                  "Fig. A.4 – Country open trade (% of GDP)",
                  "figA4_opentrade.png", out_dir)
    print("[OK] Fig. A.4")


def export_fig_a5(df, out_dir):
    _country_grid(df, GOV_EXP, "Gov. Expenditures (% GDP)",
                  "Fig. A.5 – Country government expenditures (% of GDP)",
                  "figA5_govexp.png", out_dir)
    print("[OK] Fig. A.5")


def export_fig_a6(df, out_dir):
    _country_grid(df, INVEST, "Investment (% GDP)",
                  "Fig. A.6 – Country investment (% of GDP)",
                  "figA6_investment.png", out_dir)
    print("[OK] Fig. A.6")


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE A.7 — ΔY et résidus par pays
# ═════════════════════════════════════════════════════════════════════════════

def export_fig_a7(df: pd.DataFrame, out_dir: Path) -> None:
    """
    Figure A.7 : D.GDP (ligne continue noire) + résidus CCEMG
    (ligne pointillée grise) superposés, par pays.
    """
    plt.rcParams.update(PAPER_RC)
    df_r = df.reset_index()
    countries = sorted(df_r[COUNTRY_COL].unique())
    fig, axes = plt.subplots(4, 5, figsize=(13, 8.5))
    axes_flat = axes.flatten()

    for idx, c in enumerate(countries[:20]):
        ax  = axes_flat[idx]
        sub = (df_r[df_r[COUNTRY_COL] == c]
               .sort_values(YEAR_COL)
               .dropna(subset=[f"d{LOG_GDP}"]))
        # D.GDP — ligne continue
        ax.plot(sub[YEAR_COL], sub[f"d{LOG_GDP}"],
                lw=0.85, color="black", label="D.GDP")
        # Résidus — ligne pointillée
        if "residual" in sub.columns:
            ax.plot(sub[YEAR_COL], sub["residual"],
                    lw=0.7, color="#777777", linestyle="--",
                    label="Residual")
        ax.axhline(0, color="red", lw=0.5, linestyle=":")
        ax.set_title(_country_label(c), fontsize=6.5, pad=1.5)
        ax.tick_params(labelsize=5.5)
        ax.xaxis.set_major_locator(MultipleLocator(20))

    for idx in range(len(countries), len(axes_flat)):
        axes_flat[idx].set_visible(False)

    handles = [
        plt.Line2D([0], [0], color="black",   lw=1,   label="D.GDP"),
        plt.Line2D([0], [0], color="#777777", lw=0.8,
                   linestyle="--", label="Residuals"),
    ]
    fig.legend(handles=handles, loc="lower right",
               fontsize=7, frameon=False)
    fig.text(0.5, 0.01, "Year", ha="center", fontsize=8)
    fig.suptitle("Fig. A.7 – Actual change in Real GDP and "
                 "CCEMG residuals by country",
                 fontsize=9, fontweight="bold", y=1.01)
    plt.tight_layout(rect=[0.02, 0.03, 1, 0.99])
    plt.savefig(out_dir / "figA7_gdp_residuals.png",
                dpi=200, bbox_inches="tight")
    plt.close()
    print("[OK] Fig. A.7")
