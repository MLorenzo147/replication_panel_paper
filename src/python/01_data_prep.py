"""
01_data_prep.py — Chargement et préparation des données panel
=============================================================
Référence : Huntington & Liddle (2022), "How energy prices shape OECD
            economic growth", Energy Economics, 111, 106082.

Ce module charge le fichier Excel ``growth_EE.xlsx``, construit toutes les
variables nécessaires (logs, différences, retards, dummy post-1982, CPI
tronqué, instruments, moyennes transversales) et fournit les constantes
globales utilisées par les modules 02 et 03.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd


# ═════════════════════════════════════════════════════════════════════════════
# Constantes globales
# ═════════════════════════════════════════════════════════════════════════════

COUNTRY_COL = "country"
YEAR_COL    = "yr"

RAW_GDP         = "rgdpmad"
RAW_CPI         = "cpi"
RAW_ENERGY      = "enpr"
RAW_GDPNOM      = "gdpnom"
RAW_EXPORTS     = "exports"
RAW_IMPORTS     = "imports"
RAW_EXPENDITURE = "expenditure"
RAW_INVEST      = "iy"

LOG_GDP    = "lrgdpmad"
LOG_CPI    = "lcpi"
LOG_ENERGY = "lenpr"
OPEN_TRADE = "open"
GOV_EXP    = "expgdp"
INVEST     = "iy"

CORE_VARS = [LOG_GDP, LOG_CPI, LOG_ENERGY, OPEN_TRADE, GOV_EXP, INVEST]

INSTRUMENT_COLS: List[str] = [
    "l_dlenpr", "l_lenpr",
    "ln_ywld", "ln_meast",
    "l_ln_ywld", "l_ln_meast",
    "usshare", "iranrev",
]

BASE_START_YEAR = 1972

# Mapping ISO → nom complet (pour les figures et Table 5)
COUNTRY_ISO = {
    "aus": "Australia",   "bel": "Belgium",       "can": "Canada",
    "che": "Switzerland", "deu": "Germany",        "dnk": "Denmark",
    "esp": "Spain",       "fin": "Finland",        "fra": "France",
    "gbr": "United Kingdom", "irl": "Ireland",     "ita": "Italy",
    "jpn": "Japan",       "nld": "Netherlands",    "nor": "Norway",
    "prt": "Portugal",    "swe": "Sweden",         "usa": "United States",
}

# Style matplotlib académique (fond blanc, sans bordures hautes/droites)
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
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def country_label(c: str) -> str:
    """Retourne le nom complet d'un pays depuis son code ISO."""
    return COUNTRY_ISO.get(c.lower().strip(), c)


# ═════════════════════════════════════════════════════════════════════════════
# Chargement et préparation
# ═════════════════════════════════════════════════════════════════════════════

def load_and_prepare_data(path: Path) -> pd.DataFrame:
    """
    Charge l'onglet ``data`` du fichier Excel, construit toutes les
    variables dérivées et retourne un DataFrame indexé (country, yr).

    Variables construites :
    - Logs : lrgdpmad, lcpi, lenpr
    - Ratios : open (trade openness), expgdp (gov. expenditures / GDP)
    - Différences premières : dlrgdpmad, dlcpi, dlenpr, dopen, dexpgdp, diy
    - Retards : l_lrgdpmad, l_lcpi, …, l_dlenpr
    - Dummy : mod (yr > 1982), dlenprmod, dlcpi2 (CPI > 2 %), l_dlcpi2
    - Instruments retardés : l_ln_ywld, l_ln_meast
    """
    df = pd.read_excel(path, sheet_name="data")
    df.columns = [str(c).strip() for c in df.columns]

    # ── Conversion numérique ────────────────────────────────────────────
    for col in [YEAR_COL, RAW_GDP, RAW_CPI, RAW_ENERGY, RAW_GDPNOM,
                RAW_EXPORTS, RAW_IMPORTS, RAW_EXPENDITURE, RAW_INVEST]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[COUNTRY_COL] = df[COUNTRY_COL].astype(str)
    df[YEAR_COL]    = df[YEAR_COL].astype(int)
    df = df.set_index([COUNTRY_COL, YEAR_COL]).sort_index()

    # ── Ratios et logs ──────────────────────────────────────────────────
    df[OPEN_TRADE] = (df[RAW_EXPORTS] + df[RAW_IMPORTS]) / df[RAW_GDPNOM]
    df[GOV_EXP]    = df[RAW_EXPENDITURE] / df[RAW_GDPNOM]

    for raw, out in [(RAW_GDP, LOG_GDP), (RAW_CPI, LOG_CPI),
                     (RAW_ENERGY, LOG_ENERGY)]:
        df[out] = np.where(df[raw] > 0, np.log(df[raw]), np.nan)

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df = df.dropna(subset=CORE_VARS)

    # ── Différences premières et retards ────────────────────────────────
    for var in CORE_VARS:
        df[f"d{var}"]   = df.groupby(level=0)[var].diff()
        df[f"l_{var}"]  = df.groupby(level=0)[var].shift(1)

    df["l_dlenpr"] = df.groupby(level=0)["dlenpr"].shift(1)

    # ── Dummy post-1982 (Great Moderation) ──────────────────────────────
    year_idx = df.index.get_level_values(YEAR_COL)
    df["mod"]        = (year_idx > 1982).astype(int)
    df["dlenprmod"]  = df["mod"] * df["dlenpr"]

    # ── CPI tronqué à 2 % ──────────────────────────────────────────────
    df["dlcpi2"]     = np.where(df["dlcpi"] > 0.02, df["dlcpi"], 0.0)
    df["l_dlcpi2"]   = df.groupby(level=0)["dlcpi2"].shift(1)

    # ── Instruments retardés (si présents dans le fichier) ──────────────
    for col in ["ln_ywld", "ln_meast"]:
        if col in df.columns:
            df[f"l_{col}"] = df.groupby(level=0)[col].shift(1)

    return df


def load_table56(path: Path) -> Optional[pd.DataFrame]:
    """
    Charge l'onglet ``tables5-6`` (intensité énergétique, exports/imports).

    Gère les noms de colonnes variables du fichier original :
    - ``supply`` → ``exports``
    - ``demand`` → ``imports``
    """
    for sheet in ("tables5-6", "table5-6"):
        try:
            raw = pd.read_excel(path, sheet_name=sheet)
            raw.columns = [str(c).strip().lower() for c in raw.columns]

            out = pd.DataFrame()
            if "country" in raw.columns:
                out["country"] = raw["country"].astype(str).str.strip()
            else:
                return None

            if "intensity" in raw.columns:
                out["intensity"] = pd.to_numeric(raw["intensity"],
                                                  errors="coerce")

            # Correction cruciale : Supply = Exports, Demand = Imports
            if "supply" in raw.columns:
                out["exports"] = pd.to_numeric(raw["supply"], errors="coerce")
            elif "exports" in raw.columns:
                out["exports"] = pd.to_numeric(raw["exports"], errors="coerce")

            if "demand" in raw.columns:
                out["imports"] = pd.to_numeric(raw["demand"], errors="coerce")
            elif "imports" in raw.columns:
                out["imports"] = pd.to_numeric(raw["imports"], errors="coerce")

            if "post_1982" in raw.columns:
                out["post_1982"] = pd.to_numeric(raw["post_1982"],
                                                  errors="coerce")
            if "pre_1983" in raw.columns:
                out["pre_1983"] = pd.to_numeric(raw["pre_1983"],
                                                 errors="coerce")

            if "exclude" in raw.columns:
                out["exclude"] = (raw["exclude"].astype(str).str.strip()
                                  .str.lower()
                                  .isin(["1", "true", "yes", "y"]))
            elif "country" in out.columns:
                out["exclude"] = (out["country"].str.lower()
                                  .isin(["germany", "ireland"]))

            return out
        except Exception:
            continue
    return None
