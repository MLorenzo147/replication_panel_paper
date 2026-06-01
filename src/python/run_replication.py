"""
run_replication.py — Script d'entrée unique pour la réplication
===============================================================
Référence : Huntington & Liddle (2022), "How energy prices shape OECD
            economic growth", Energy Economics, 111, 106082.

Usage :
    python src/python/run_replication.py                  # réplication seule
    python src/python/run_replication.py --extension      # + estimation FE
    python src/python/run_replication.py --help

Ce script orchestre les 3 modules (01_data_prep, 02_estimators, 03_exports)
et appelle optionnellement le module 04_extension.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path


def _import_module_by_path(name: str, filepath: Path):
    """Import un module Python depuis son chemin absolu."""
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═════════════════════════════════════════════════════════════════════════════
# Configuration des chemins
# ═════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR      = Path(__file__).resolve().parent

DATA_PATH    = PROJECT_ROOT / "data" / "growth_EE.xlsx"
TABLES_DIR   = PROJECT_ROOT / "outputs" / "tables"
FIGURES_DIR  = PROJECT_ROOT / "outputs" / "figures"

# Fallback si les données ne sont pas dans data/
if not DATA_PATH.exists():
    alt = PROJECT_ROOT / "growth_EE.xlsx"
    if alt.exists():
        DATA_PATH = alt


# ═════════════════════════════════════════════════════════════════════════════
# Import des modules frères (gestion du nom numérique 01_...)
# ═════════════════════════════════════════════════════════════════════════════

dp = _import_module_by_path("data_prep",   SRC_DIR / "01_data_prep.py")
est = _import_module_by_path("estimators", SRC_DIR / "02_estimators.py")
exp = _import_module_by_path("exports",    SRC_DIR / "03_exports.py")


# ═════════════════════════════════════════════════════════════════════════════
# Pipeline principale
# ═════════════════════════════════════════════════════════════════════════════

def run_replication(run_ext: bool = False) -> None:
    """Exécute la réplication complète du papier."""
    t0 = time.time()

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Chargement des données ───────────────────────────────────────
    print("=" * 65)
    print("  REPLICATION : Huntington & Liddle (2022)")
    print("  Energy Economics, 111, 106082")
    print("=" * 65)
    print(f"\n  Donnees : {DATA_PATH}")
    print(f"  Tables  : {TABLES_DIR}")
    print(f"  Figures : {FIGURES_DIR}\n")

    print("-- Chargement et preparation des donnees -------------------------")
    df_full = dp.load_and_prepare_data(DATA_PATH)
    df_base = df_full[
        df_full.index.get_level_values(dp.YEAR_COL) >= dp.BASE_START_YEAR
    ].copy()
    intensity_df = dp.load_table56(DATA_PATH)
    print(f"   Panel : {df_full.index.get_level_values(dp.COUNTRY_COL).nunique()} "
          f"pays x {df_full.index.get_level_values(dp.YEAR_COL).nunique()} annees "
          f"= {len(df_full)} obs")

    # -- 2. Table 1 : Statistiques descriptives
    print("\n-- Generation des Tables ----------------------------------------")
    exp.export_table1(df_full, TABLES_DIR)

    # ── 3. Table 2 : Tests CIPS ─────────────────────────────────────────
    import pandas as pd
    cips_rows = []
    for var in dp.CORE_VARS:
        for lag in range(0, 4):
            sl, pl   = est.cips_test_manual(df_full[var], lags=lag, trend="c")
            sd, pd_  = est.cips_test_manual(df_full[f"d{var}"], lags=lag, trend="c")
            slt, plt_ = est.cips_test_manual(df_full[var], lags=lag, trend="ct")
            cips_rows.append({
                "variable": var, "lag": lag,
                "stat_level": sl, "pvalue_level": pl,
                "stat_diff": sd,  "pvalue_diff": pd_,
                "stat_level_t": slt, "pvalue_level_t": plt_,
            })
    cips_df = pd.DataFrame(cips_rows)
    exp.export_table2(cips_df, TABLES_DIR)

    # ── 4. Table 3 : CCE-MG ────────────────────────────────────────────
    cce_regs = [
        "dlcpi", "dlenpr", "dopen", "dexpgdp", "diy",
        "l_lrgdpmad", "l_lcpi", "l_open", "l_iy",
    ]
    _, mg_cce, mg_robust, _ = est.estimate_ccemg(
        df_full, "dlrgdpmad", cce_regs, [], [], exog_only=True)
    exp.export_table3(mg_cce, mg_robust, TABLES_DIR)

    # ── 5. Table 4 : Robustesse ─────────────────────────────────────────
    exog_vars = [
        "l_dlcpi2", "dopen", "dexpgdp", "diy",
        "l_lrgdpmad", "l_lcpi", "l_open", "l_iy",
        "mod", "dlenprmod",
    ]
    endog_vars = ["dlenpr"]
    insts = [c for c in dp.INSTRUMENT_COLS if c in df_base.columns]

    robustness_df = est.build_robustness_table(
        df_base, df_full, "dlrgdpmad", exog_vars, endog_vars, insts)
    exp.export_table4(robustness_df, TABLES_DIR)

    # ── 6. Tables 5 & 6 : Réponses pays ────────────────────────────────
    cc_country, _, _, residuals = est.estimate_ccemg(
        df_base, "dlrgdpmad", exog_vars, endog_vars, insts)
    exp.export_table5(cc_country, TABLES_DIR, intensity_df)
    exp.export_table6(cc_country, TABLES_DIR, intensity_df)

    # -- 7. Figures A.1 - A.7
    print("\n-- Generation des Figures ----------------------------------------")
    exp.export_fig_a1(df_full, FIGURES_DIR)
    exp.export_fig_a2(df_full, FIGURES_DIR)
    exp.export_fig_a3(df_full, FIGURES_DIR)
    exp.export_fig_a4(df_full, FIGURES_DIR)
    exp.export_fig_a5(df_full, FIGURES_DIR)
    exp.export_fig_a6(df_full, FIGURES_DIR)

    df_base_res = df_base.copy()
    df_base_res["residual"] = residuals
    exp.export_fig_a7(df_base_res, FIGURES_DIR)

    # -- 8. Extension (optionnel)
    if run_ext:
        ext = _import_module_by_path("extension", SRC_DIR / "04_extension.py")
        ext.run_extension(df_base, intensity_df, TABLES_DIR)

    # -- Resume
    elapsed = time.time() - t0
    print(f"\n{'=' * 65}")
    print(f"  Pipeline terminee en {elapsed:.1f}s")
    print(f"     6 tables (CSV + PNG) -> {TABLES_DIR}")
    print(f"     7 figures (PNG)      -> {FIGURES_DIR}")
    if run_ext:
        print(f"     + Extension FE       -> {TABLES_DIR}")
    print(f"{'=' * 65}")


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Réplication de Huntington & Liddle (2022)")
    parser.add_argument(
        "--extension", action="store_true",
        help="Exécuter aussi l'estimation FE avec interaction (04_extension)")
    args = parser.parse_args()

    run_replication(run_ext=args.extension)
