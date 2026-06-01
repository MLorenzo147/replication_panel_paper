"""
04_extension.py — Estimation originale : Fixed Effects avec interaction
=======================================================================
Référence : Extension du modèle de Huntington & Liddle (2022).

Ce script implémente l'estimation originale demandée dans le template du
devoir : une régression Fixed Effects (One-way) avec variable d'interaction
temporelle Z(i) × X(it), puis plot de l'effet marginal estimé.

Modèle estimé :
    Δlog(RGDP)_it = α_i + β₁·dlenpr_it + β₂·(intensity_i × dlenpr_it)
                    + γ·W_it + ε_it

Où :
    X_it = dlenpr (taux de croissance du prix de l'énergie)
    Z_i  = intensity (intensité énergétique initiale du pays, fixe)
    W_it = contrôles (dlcpi, dopen, dexpgdp, diy)

L'effet marginal de l'énergie est :
    ∂ΔY/∂X = β₁ + β₂ · Z_i

Ce qui teste l'hypothèse : les pays avec une intensité énergétique
plus élevée sont-ils plus sensibles aux chocs de prix de l'énergie ?
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from linearmodels.panel import PanelOLS
except ImportError as exc:
    raise ImportError(
        "linearmodels est requis. Installez-le avec `pip install linearmodels`"
    ) from exc


# ── Constantes ──────────────────────────────────────────────────────────────
PAPER_RC = {
    "font.family":       "DejaVu Serif",
    "font.size":         9,
    "axes.titlesize":    10,
    "axes.labelsize":    9,
    "xtick.labelsize":   8,
    "ytick.labelsize":   8,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "figure.dpi":        200,
}


def run_extension(
    df: pd.DataFrame,
    intensity_df: pd.DataFrame,
    out_dir: Path,
) -> None:
    """
    Exécute l'estimation FE avec interaction et le plot d'effet marginal.

    Parameters
    ----------
    df : DataFrame indexé (country, yr) avec les variables du panel
    intensity_df : DataFrame de l'onglet tables5-6 (country, intensity)
    out_dir : répertoire de sortie
    """
    print("\n-- Extension : Fixed Effects avec interaction -----------------")

    # ═════════════════════════════════════════════════════════════════════
    # 1. Construction de la variable d'interaction
    # ═════════════════════════════════════════════════════════════════════

    df_ext = df.copy()

    # Fusionner l'intensité (time-invariant) au panel
    int_map = {}
    if intensity_df is not None and not intensity_df.empty:
        tmp = intensity_df.copy()
        tmp["_k"] = tmp["country"].astype(str).str.strip().str.lower()
        if "intensity" in tmp.columns:
            int_map = tmp.set_index("_k")["intensity"].to_dict()

    # Mapping ISO -> nom complet pour faire correspondre les pays
    COUNTRY_ISO = {
        "aus": "Australia",   "bel": "Belgium",       "can": "Canada",
        "che": "Switzerland", "deu": "Germany",        "dnk": "Denmark",
        "esp": "Spain",       "fin": "Finland",        "fra": "France",
        "gbr": "United Kingdom", "irl": "Ireland",     "ita": "Italy",
        "jpn": "Japan",       "nld": "Netherlands",    "nor": "Norway",
        "prt": "Portugal",    "swe": "Sweden",         "usa": "United States",
    }

    # Assigner l'intensité à chaque observation
    countries_idx = df_ext.index.get_level_values("country")
    df_ext["intensity"] = countries_idx.map(
        lambda c: int_map.get(
            COUNTRY_ISO.get(str(c).strip().lower(), "").strip().lower(),
            np.nan
        )
    )

    # Variable d'interaction : Z(i) × X(it) = intensity × dlenpr
    df_ext["interaction"] = df_ext["intensity"] * df_ext["dlenpr"]

    # ═════════════════════════════════════════════════════════════════════
    # 2. Estimation Fixed Effects (One-way, Entity Effects)
    # ═════════════════════════════════════════════════════════════════════

    dep = "dlrgdpmad"
    regressors = ["dlenpr", "interaction", "dlcpi", "dopen", "dexpgdp", "diy"]

    # Filtrer les NaN
    est_df = df_ext[[dep] + regressors + ["intensity"]].dropna()

    if est_df.shape[0] < 20:
        print("WARN: Pas assez d'observations pour l'estimation FE. "
              "Verifiez que l'onglet tables5-6 contient les intensites.")
        return

    # Régression Fixed Effects avec erreurs clustered par pays
    formula = f"{dep} ~ 1 + {' + '.join(regressors)} + EntityEffects"
    model = PanelOLS.from_formula(formula, data=est_df)
    result = model.fit(cov_type="clustered", cluster_entity=True)

    print(result.summary)

    # Sauvegarder les résultats
    coef_df = pd.DataFrame({
        "Variable":  result.params.index,
        "Coef":      result.params.values,
        "Std.Err.":  result.std_errors.values,
        "t-stat":    result.tstats.values,
        "p-value":   result.pvalues.values,
    })
    coef_df.to_csv(out_dir / "extension_fe_interaction.csv", index=False)
    print(f"[OK] Resultats FE sauvegardes -> {out_dir / 'extension_fe_interaction.csv'}")

    # ═════════════════════════════════════════════════════════════════════
    # 3. Plot de l'effet marginal ∂Y/∂X = β₁ + β₂·Z(i)
    # ═════════════════════════════════════════════════════════════════════

    beta1 = result.params.get("dlenpr", np.nan)
    beta2 = result.params.get("interaction", np.nan)

    if not (np.isfinite(beta1) and np.isfinite(beta2)):
        print("WARN: Coefficients non finis, impossible de tracer l'effet marginal.")
        return

    # Extraire la variance-covariance pour les IC
    vcov = result.cov
    var_b1   = vcov.loc["dlenpr", "dlenpr"]
    var_b2   = vcov.loc["interaction", "interaction"]
    cov_b1b2 = vcov.loc["dlenpr", "interaction"]

    # Grille de valeurs de Z (intensité)
    z_values = est_df["intensity"].dropna().unique()
    z_grid = np.linspace(
        est_df["intensity"].min() * 0.9,
        est_df["intensity"].max() * 1.1,
        200,
    )

    # Effet marginal et intervalle de confiance à 95 %
    marginal_effect = beta1 + beta2 * z_grid
    se_marginal = np.sqrt(var_b1 + z_grid**2 * var_b2 + 2 * z_grid * cov_b1b2)
    ci_lower = marginal_effect - 1.96 * se_marginal
    ci_upper = marginal_effect + 1.96 * se_marginal

    # ── Plot ────────────────────────────────────────────────────────────
    plt.rcParams.update(PAPER_RC)
    fig, ax = plt.subplots(figsize=(8, 5))

    # Bande de confiance
    ax.fill_between(z_grid, ci_lower, ci_upper,
                    alpha=0.15, color="#2c7bb6",
                    label="IC 95 %")

    # Ligne de l'effet marginal
    ax.plot(z_grid, marginal_effect,
            color="#2c7bb6", lw=2,
            label=f"∂ΔY/∂X = {beta1:.3f} + {beta2:.3f}·Z")

    # Ligne zéro
    ax.axhline(0, color="black", lw=0.5, linestyle=":")

    # Points des pays observés
    marginal_countries = beta1 + beta2 * z_values
    ax.scatter(z_values, marginal_countries,
               color="#d7191c", s=25, zorder=5,
               label="Pays observés")

    ax.set_xlabel("Intensité énergétique Z(i)")
    ax.set_ylabel("Effet marginal ∂Δlog(RGDP)/∂Δlog(ENPR)")
    ax.set_title(
        "Effet marginal du prix de l'énergie\n"
        "selon l'intensité énergétique du pays",
        fontsize=10, fontweight="bold",
    )
    ax.legend(fontsize=8, loc="best", frameon=False)

    # Annotations : β₁ et β₂ avec p-values
    p1 = result.pvalues.get("dlenpr", np.nan)
    p2 = result.pvalues.get("interaction", np.nan)
    txt = (f"β₁ (dlenpr)     = {beta1:.4f} (p = {p1:.3f})\n"
           f"β₂ (interaction) = {beta2:.4f} (p = {p2:.3f})\n"
           f"N = {result.nobs}  |  R² within = {result.rsquared:.4f}")
    ax.text(0.02, 0.02, txt, transform=ax.transAxes,
            fontsize=7.5, verticalalignment="bottom",
            fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="#cccccc", alpha=0.9))

    plt.tight_layout()
    fig_path = out_dir / "extension_marginal_effect.png"
    plt.savefig(fig_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"[OK] Figure effet marginal -> {fig_path}")
    print(f"\n  beta1 = {beta1:.4f}  |  beta2 = {beta2:.4f}")
    print(f"  Interpretation : pour un pays a Z = {np.median(z_values):.3f},")
    print(f"  l'effet marginal est {beta1 + beta2 * np.median(z_values):.4f}")


# ═════════════════════════════════════════════════════════════════════════════
# Point d'entrée standalone
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from src.python import data_prep
    # Alias pour import simplifié
    try:
        dp = __import__("01_data_prep",
                        fromlist=["load_and_prepare_data", "load_table56"])
    except ImportError:
        # Si exécuté depuis la racine du projet
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "data_prep",
            Path(__file__).parent / "01_data_prep.py")
        dp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dp)

    DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "growth_EE.xlsx"
    OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "tables"

    df = dp.load_and_prepare_data(DATA_PATH)
    intensity_df = dp.load_table56(DATA_PATH)
    df_base = df[df.index.get_level_values("yr") >= 1972].copy()

    run_extension(df_base, intensity_df, OUTPUT_DIR)
