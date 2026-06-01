import sys
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm

# Insert path to Python source code
sys.path.insert(0, str(Path(r"c:\Users\loren\OneDrive - Université Paris 1 Panthéon-Sorbonne\projetPython\Econometics2\src\python")))
dp = __import__("01_data_prep")

DATA_PATH = Path(r"c:\Users\loren\OneDrive - Université Paris 1 Panthéon-Sorbonne\projetPython\Econometics2\data\growth_EE.xlsx")

def analyze_panel():
    df = dp.load_and_prepare_data(DATA_PATH)
    # Base sample: year >= 1972
    df_base = df[df.index.get_level_values("yr") >= 1972].copy()
    
    # 1. Basic properties
    n_countries = df_base.index.get_level_values("country").nunique()
    n_years = df_base.index.get_level_values("yr").nunique()
    n_obs = len(df_base)
    print(f"Base panel: N={n_countries}, T={n_years}, total obs={n_obs}")
    
    # 2. Variance decomposition (Between / Within)
    # Variables list
    vars_to_decomp = [
        "lrgdpmad", "lcpi", "lenpr", "open", "expgdp", "iy",
        "dlrgdpmad", "dlcpi", "dlenpr", "dopen", "dexpgdp", "diy"
    ]
    
    decomp_rows = []
    for var in vars_to_decomp:
        # Drop missing
        s = df_base[var].dropna()
        if len(s) == 0:
            continue
            
        overall_mean = s.mean()
        overall_var = s.var(ddof=1)
        
        # Between: country mean
        country_means = s.groupby(level=0).mean()
        between_var = country_means.var(ddof=1)
        
        # Within: x_it - country_mean + overall_mean
        within_series = s - s.index.get_level_values("country").map(country_means) + overall_mean
        within_var = within_series.var(ddof=1)
        
        # Share of within variance
        share_within = (within_var / overall_var) * 100 if overall_var > 0 else 0
        
        decomp_rows.append({
            "Variable": var,
            "N_countries": s.index.get_level_values("country").nunique(),
            "N_obs": len(s),
            "Overall_Var": overall_var,
            "Between_Var": between_var,
            "Within_Var": within_var,
            "Share_Within": share_within
        })
        
    decomp_df = pd.DataFrame(decomp_rows)
    print("\n--- VARIANCE DECOMPOSITION ---")
    print(decomp_df.to_string(index=False))
    decomp_df.to_csv(r"c:\Users\loren\OneDrive - Université Paris 1 Panthéon-Sorbonne\projetPython\Econometics2\scratch\variance_decomp.csv", index=False)
    
    # 3. Simple correlations (Y = dlrgdpmad, X = dlenpr)
    # Overall, between, within, first-difference
    # For within and between, we use the levels
    df_base["mean_lrgdpmad"] = df_base.groupby(level=0)["lrgdpmad"].transform("mean")
    df_base["mean_lenpr"] = df_base.groupby(level=0)["lenpr"].transform("mean")
    df_base["within_lrgdpmad"] = df_base["lrgdpmad"] - df_base["mean_lrgdpmad"]
    df_base["within_lenpr"] = df_base["lenpr"] - df_base["mean_lenpr"]
    
    corr_overall_level = df_base["lrgdpmad"].corr(df_base["lenpr"])
    corr_between = df_base.groupby(level=0)[["lrgdpmad", "lenpr"]].mean().corr().iloc[0, 1]
    corr_within = df_base["within_lrgdpmad"].corr(df_base["within_lenpr"])
    corr_fd = df_base["dlrgdpmad"].corr(df_base["dlenpr"])
    
    print("\n--- CORRELATIONS (Y = GDP, X = Energy Price) ---")
    print(f"Overall Level Correlation: {corr_overall_level:.4f}")
    print(f"Between (Means) Correlation: {corr_between:.4f}")
    print(f"Within Correlation: {corr_within:.4f}")
    print(f"First-Difference (Growth) Correlation: {corr_fd:.4f}")
    
    # 4. Country-specific correlations and slopes (FD)
    country_stats = []
    for c in sorted(df_base.index.get_level_values("country").unique()):
        sub = df_base.xs(c, level="country").dropna(subset=["dlrgdpmad", "dlenpr"])
        n = len(sub)
        if n < 3:
            continue
        r = sub["dlrgdpmad"].corr(sub["dlenpr"])
        std_y = sub["dlrgdpmad"].std()
        std_x = sub["dlenpr"].std()
        slope = r * (std_y / std_x) if std_x > 0 else np.nan
        country_stats.append({
            "Country": c,
            "T": n,
            "corr": r,
            "std_y": std_y,
            "std_x": std_x,
            "slope": slope
        })
    c_df = pd.DataFrame(country_stats)
    print("\n--- COUNTRY-SPECIFIC STATS (FD) ---")
    print(c_df.to_string(index=False))
    c_df.to_csv(r"c:\Users\loren\OneDrive - Université Paris 1 Panthéon-Sorbonne\projetPython\Econometics2\scratch\country_stats_fd.csv", index=False)

    # 5. Country-specific correlations and slopes (TWFE)
    # For TWFE, we remove individual and time effects
    y_within = df_base["dlrgdpmad"].dropna()
    x_within = df_base["dlenpr"].dropna()
    common_idx = y_within.index.intersection(x_within.index)
    
    tw_df = df_base.loc[common_idx].copy()
    # Entity means are already removed for within, but let's do OLS on year dummies to get TWFE residuals
    year_dummies = pd.get_dummies(tw_df.index.get_level_values("yr"), drop_first=True).astype(float)
    year_dummies.index = tw_df.index
    
    y_twfe = sm.OLS(tw_df["dlrgdpmad"], sm.add_constant(year_dummies)).fit().resid
    x_twfe = sm.OLS(tw_df["dlenpr"], sm.add_constant(year_dummies)).fit().resid
    
    tw_df["y_twfe"] = y_twfe
    tw_df["x_twfe"] = x_twfe
    
    country_twfe = []
    for c in sorted(tw_df.index.get_level_values("country").unique()):
        sub = tw_df.xs(c, level="country")
        n = len(sub)
        r = sub["y_twfe"].corr(sub["x_twfe"])
        std_y = sub["y_twfe"].std()
        std_x = sub["x_twfe"].std()
        slope = r * (std_y / std_x) if std_x > 0 else np.nan
        country_twfe.append({
            "Country": c,
            "T": n,
            "corr": r,
            "std_y": std_y,
            "std_x": std_x,
            "slope": slope
        })
    ctw_df = pd.DataFrame(country_twfe)
    print("\n--- COUNTRY-SPECIFIC STATS (TWFE) ---")
    print(ctw_df.to_string(index=False))
    ctw_df.to_csv(r"c:\Users\loren\OneDrive - Université Paris 1 Panthéon-Sorbonne\projetPython\Econometics2\scratch\country_stats_twfe.csv", index=False)

if __name__ == '__main__':
    analyze_panel()
