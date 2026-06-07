"""05_template_outputs.py
Generate the additional tables and figures required by the course template.

Place this file in src/python/ and run from the repository with:
    python src/python/05_template_outputs.py

Outputs are written to outputs/template_diagnostics/.
"""

import os, sys, math, textwrap, shutil, subprocess, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
import statsmodels.api as sm
from statsmodels.nonparametric.smoothers_lowess import lowess

# If this file is placed in src/python/, PROJECT_ROOT is two levels above.
SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2] if len(SCRIPT_PATH.parents) >= 3 else Path.cwd()
ROOT = PROJECT_ROOT
OUT = ROOT / "outputs" / "template_diagnostics"
OUT.mkdir(parents=True, exist_ok=True)

# --- Load and prep data ---
data_path = ROOT / "data" / "growth_EE.xlsx"
if not data_path.exists():
    data_path = ROOT / "growth_EE.xlsx"
df_raw = pd.read_excel(data_path, sheet_name="data")
df_raw.columns = [str(c).strip().lower() for c in df_raw.columns]
# convert dots to nan
for c in df_raw.columns:
    if c != "country":
        df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce")
for c in [
    "yr",
    "rgdpmad",
    "cpi",
    "gdpnom",
    "exports",
    "imports",
    "expenditure",
    "iy",
    "ln_ywld",
    "ln_meast",
    "usshare",
    "iranrev",
]:
    df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce")
df_raw["enpr"] = pd.to_numeric(df_raw["enpr"], errors="coerce")
df_raw["country"] = df_raw["country"].astype(str).str.lower()
df = df_raw.copy()
df["open"] = (df["exports"] + df["imports"]) / df["gdpnom"]
df["expgdp"] = df["expenditure"] / df["gdpnom"]
for raw, out in [("rgdpmad", "lrgdpmad"), ("cpi", "lcpi"), ("enpr", "lenpr")]:
    df[out] = np.where(df[raw] > 0, np.log(df[raw]), np.nan)
core = ["lrgdpmad", "lcpi", "lenpr", "open", "expgdp", "iy"]
df = df.dropna(subset=core).sort_values(["country", "yr"]).copy()
for v in core:
    df["d" + v] = df.groupby("country")[v].diff()
    df["l_" + v] = df.groupby("country")[v].shift(1)
    df["l_d" + v] = df.groupby("country")["d" + v].shift(1)
# instruments lags
for v in ["ln_ywld", "ln_meast"]:
    df["l_" + v] = df.groupby("country")[v].shift(1)
df["mod"] = (df["yr"] > 1982).astype(int)
df["dlenprmod"] = df["dlenpr"] * df["mod"]
df["dlcpi2"] = df["dlcpi"].where(df["dlcpi"] > 0.02, 0)
df["l_dlcpi2"] = df.groupby("country")["dlcpi2"].shift(1)
country_names = {
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
df["country_name"] = df["country"].map(country_names)

# Output helpers
plt.rcParams.update(
    {
        "font.family": "DejaVu Serif",
        "font.size": 9,
        "figure.dpi": 200,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def save_table_image(tbl, title, path, notes="", fontsize=7.5, fig_w=10, row_h=0.34):
    tbl = tbl.copy()
    tbl = tbl.fillna("")
    nrows, ncols = tbl.shape
    fig_h = max(2.0, row_h * (nrows + 2) + 0.8)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    table = ax.table(
        cellText=tbl.astype(str).values.tolist(),
        colLabels=list(tbl.columns),
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(fontsize)
    table.scale(1, 1.25)
    for j in range(ncols):
        table[0, j].set_facecolor("#d9eaf7")
        table[0, j].set_text_props(fontweight="bold")
    for i in range(1, nrows + 1):
        for j in range(ncols):
            table[i, j].set_facecolor("#f5f5f5" if i % 2 == 0 else "white")
            if j == 0:
                table[i, j].get_text().set_ha("left")
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    if notes:
        fig.text(0.01, 0.01, notes, fontsize=6.5, style="italic", wrap=True)
    plt.tight_layout(rect=(0, 0.035 if notes else 0, 1, 1))
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


# Sample availability
avail = df.groupby("yr")["country"].nunique().reset_index(name="N")
fig, ax = plt.subplots(figsize=(8, 3.5))
ax.plot(avail["yr"], avail["N"], marker="o", markersize=2)
ax.set_title("Sample availability by year, 1960-2016")
ax.set_xlabel("Year")
ax.set_ylabel("Number of countries observed")
ax.grid(True, alpha=0.25)
fig.savefig(OUT / "sample_availability.png", bbox_inches="tight")
plt.close(fig)

# Transformations
vars_for = [
    "dlrgdpmad",
    "dlenpr",
    "dlcpi",
    "dopen",
    "dexpgdp",
    "diy",
    "lrgdpmad",
    "lcpi",
    "lenpr",
    "open",
    "expgdp",
    "iy",
]
# transformation functions for df with multi-index
dfi = df.set_index(["country", "yr"]).sort_index()


def within(s):
    return s - s.groupby(level=0).transform("mean")


def between(s):
    return s.groupby(level=0).transform("mean")


def twfe(s):
    return (
        s
        - s.groupby(level=0).transform("mean")
        - s.groupby(level=1).transform("mean")
        + s.mean()
    )


def firstdiff(s):
    return s.groupby(level=0).diff()


# variance classification on baseline 1972-2016, core + diffs
baseline = dfi[dfi.index.get_level_values("yr") >= 1972].copy()
class_vars = [
    "lrgdpmad",
    "lcpi",
    "lenpr",
    "open",
    "expgdp",
    "iy",
    "dlrgdpmad",
    "dlcpi",
    "dlenpr",
    "dopen",
    "dexpgdp",
    "diy",
]
rows = []
for v in class_vars:
    s = baseline[v].dropna()
    ov = s.var(ddof=1)
    b = between(s).dropna().var(ddof=1)
    w = within(s).dropna().var(ddof=1)
    rows.append(
        {
            "Variable": v,
            "N": s.index.get_level_values(0).nunique(),
            "NT": len(s),
            "NT/N": round(len(s) / max(1, s.index.get_level_values(0).nunique()), 1),
            "Overall variance": ov,
            "Between variance": b,
            "Within variance": w,
            "% within": 100 * w / ov if ov and np.isfinite(ov) else np.nan,
        }
    )
varclass = pd.DataFrame(rows).sort_values("% within", ascending=False)
varclass_fmt = varclass.copy()
for c in ["Overall variance", "Between variance", "Within variance", "% within"]:
    varclass_fmt[c] = varclass_fmt[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
varclass_fmt.to_csv(OUT / "variable_classification.csv", index=False)
save_table_image(
    varclass_fmt,
    "Variable classification by within-variance share",
    OUT / "variable_classification.png",
    "Notes: baseline sample 1972-2016. Variables sorted by the share of within variance in total variance.",
    fontsize=6.5,
    fig_w=11,
    row_h=0.29,
)

# distributions for Y X transformations
Y = "dlrgdpmad"
X = "dlenpr"
trans = {
    "Between": between(baseline[Y]),
    "One-way within": within(baseline[Y]),
    "First differences": firstdiff(baseline[Y]),
    "Two-way FE": twfe(baseline[Y]),
}
transX = {
    "Between": between(baseline[X]),
    "One-way within": within(baseline[X]),
    "First differences": firstdiff(baseline[X]),
    "Two-way FE": twfe(baseline[X]),
}


def dist_plot(series, title, path):
    s = pd.Series(series).dropna().astype(float)
    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    ax.hist(s, bins=30, density=True, alpha=0.35, edgecolor="black")
    if len(s) > 2 and s.std() > 0:
        xs = np.linspace(s.min(), s.max(), 200)
        ax.plot(
            xs,
            stats.norm.pdf(xs, s.mean(), s.std(ddof=1)),
            lw=1.5,
            label="Normal same mean/sd",
        )
        try:
            kde = stats.gaussian_kde(s)
            ax.plot(xs, kde(xs), lw=1.5, label="KDE")
        except Exception:
            pass
    ax.axvline(s.mean(), color="black", lw=0.8, linestyle="--")
    ax.set_title(title)
    ax.legend(fontsize=7)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


for name, s in trans.items():
    dist_plot(
        s,
        f"{name} transformation - GDP growth (Y)",
        OUT / f'dist_Y_{name.replace(" ","_").replace("-","_")}.png',
    )
for name, s in transX.items():
    dist_plot(
        s,
        f"{name} transformation - Energy price growth (X)",
        OUT / f'dist_X_{name.replace(" ","_").replace("-","_")}.png',
    )

# Combined 2x4 distrib image
fig, axs = plt.subplots(2, 4, figsize=(13, 6))
for j, (name, s) in enumerate(trans.items()):
    ss = pd.Series(s).dropna().astype(float)
    ax = axs[0, j]
    ax.hist(ss, bins=25, density=True, alpha=0.35, edgecolor="black")
    if ss.std() > 0:
        xs = np.linspace(ss.min(), ss.max(), 200)
        ax.plot(xs, stats.norm.pdf(xs, ss.mean(), ss.std(ddof=1)), lw=1)
        try:
            ax.plot(xs, stats.gaussian_kde(ss)(xs), lw=1)
        except Exception:
            pass
    ax.set_title(name)
    ax.set_xlabel("Y")
for j, (name, s) in enumerate(transX.items()):
    ss = pd.Series(s).dropna().astype(float)
    ax = axs[1, j]
    ax.hist(ss, bins=25, density=True, alpha=0.35, edgecolor="black")
    if ss.std() > 0:
        xs = np.linspace(ss.min(), ss.max(), 200)
        ax.plot(xs, stats.norm.pdf(xs, ss.mean(), ss.std(ddof=1)), lw=1)
        try:
            ax.plot(xs, stats.gaussian_kde(ss)(xs), lw=1)
        except Exception:
            pass
    ax.set_xlabel("X")
axs[0, 0].set_ylabel("GDP growth")
axs[1, 0].set_ylabel("Energy price growth")
fig.suptitle(
    "Distributions by panel transformation: histogram, normal fit and KDE",
    fontweight="bold",
)
fig.tight_layout(rect=(0, 0, 1, 0.95))
fig.savefig(OUT / "distributions_all_transformations.png", bbox_inches="tight")
plt.close(fig)

# scatter with fit lowess for transformations
fig, axs = plt.subplots(2, 2, figsize=(9, 7))
for ax, (name, sy) in zip(axs.ravel(), trans.items()):
    sx = transX[name]
    tmp = pd.DataFrame({"x": sx, "y": sy}).dropna()
    ax.scatter(tmp["x"], tmp["y"], s=10, alpha=0.55)
    if len(tmp) > 5:
        Xmat = sm.add_constant(tmp["x"])
        res = sm.OLS(tmp["y"], Xmat).fit()
        xs = np.linspace(tmp.x.min(), tmp.x.max(), 100)
        ax.plot(
            xs, res.params.iloc[0] + res.params.iloc[1] * xs, lw=1.5, label="linear"
        )
        try:
            coef = np.polyfit(tmp.x, tmp.y, 2)
            ax.plot(xs, np.polyval(coef, xs), lw=1.2, linestyle="--", label="quadratic")
            lw = lowess(tmp.y, tmp.x, frac=0.4, return_sorted=True)
            ax.plot(lw[:, 0], lw[:, 1], lw=1.2, linestyle=":", label="LOWESS")
        except Exception:
            pass
        r = tmp.corr().iloc[0, 1]
        ax.text(
            0.02,
            0.95,
            f"r = {r:.3f}",
            transform=ax.transAxes,
            va="top",
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="lightgray"),
        )
    ax.axhline(0, color="black", lw=0.5)
    ax.axvline(0, color="black", lw=0.5)
    ax.set_title(name)
    ax.set_xlabel("Energy price growth X")
    ax.set_ylabel("GDP growth Y")
    ax.legend(fontsize=6, loc="best")
fig.suptitle(
    "Bivariate graphs with linear, quadratic and LOWESS fits", fontweight="bold"
)
fig.tight_layout(rect=(0, 0, 1, 0.94))
fig.savefig(OUT / "bivariate_transformations_fits.png", bbox_inches="tight")
plt.close(fig)

# Boxplots by country for Y and X transformations
for var, label, tdict in [(Y, "GDP growth", trans), (X, "Energy price growth", transX)]:
    fig, axs = plt.subplots(2, 2, figsize=(13, 8), sharey=False)
    for ax, (name, s) in zip(axs.ravel(), tdict.items()):
        tmp = s.rename("v").reset_index().dropna()
        tmp["country_name"] = tmp["country"].map(country_names)
        order = tmp.groupby("country_name")["v"].var().sort_values().index.tolist()
        data = [tmp.loc[tmp.country_name == c, "v"].values for c in order]
        ax.boxplot(data, tick_labels=order, vert=True, showfliers=False)
        ax.tick_params(axis="x", labelrotation=90, labelsize=6)
        ax.set_title(name)
    fig.suptitle(f"Boxplots by country: {label}", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUT / f"boxplots_{var}.png", bbox_inches="tight")
    plt.close(fig)

# Correlation matrices for selected variables, transformations
corr_vars = ["dlrgdpmad", "dlenpr", "dlcpi", "dopen", "dexpgdp", "diy"]
labels = ["D.GDP", "D.ENERGY", "D.CPI", "D.OpenTrade", "D.GovExp", "D.Invest"]
matrices = {}
for tname, func in [
    ("between", between),
    ("within", within),
    ("twfe", twfe),
    ("first_diff", firstdiff),
]:
    data = pd.DataFrame(
        {lab: func(baseline[var]) for var, lab in zip(corr_vars, labels)}
    ).dropna()
    corr = data.corr().round(3)
    matrices[tname] = corr
    corr.to_csv(OUT / f"corr_{tname}.csv")
    save_table_image(
        corr.reset_index().rename(columns={"index": "Variable"}),
        f'Correlation matrix - {tname.replace("_"," ")}',
        OUT / f"corr_{tname}.png",
        fontsize=7,
        fig_w=8,
        row_h=0.32,
    )

# Heterogeneity FD and TWFE
hetero_tables = {}
for name, sy, sx in [
    ("FD", firstdiff(baseline[Y]), firstdiff(baseline[X])),
    ("TWFE", twfe(baseline[Y]), twfe(baseline[X])),
]:
    tmp = pd.DataFrame({"Y": sy, "X": sx}).dropna().reset_index()
    rows = []
    for c, g in tmp.groupby("country"):
        if len(g) >= 3 and g.X.std(ddof=1) > 0:
            r = g[["Y", "X"]].corr().iloc[0, 1]
            sdY = g.Y.std(ddof=1)
            sdX = g.X.std(ddof=1)
            beta = r * sdY / sdX
            diag = (
                "positive > 0.08"
                if r > 0.08
                else ("negative < -0.08" if r < -0.08 else "weak")
            )
            rows.append(
                {
                    "Country": country_names.get(c, c),
                    "T(i)": len(g),
                    "r(Y,X)": r,
                    "sd(Y)": sdY,
                    "sd(X)": sdX,
                    "sd(Y)/sd(X)": sdY / sdX,
                    "beta": beta,
                    "Diagnosis": diag,
                }
            )
    ht = pd.DataFrame(rows).sort_values("r(Y,X)", ascending=False)
    hetero_tables[name] = ht
    fmt = ht.copy()
    for col in ["r(Y,X)", "sd(Y)", "sd(X)", "sd(Y)/sd(X)", "beta"]:
        fmt[col] = fmt[col].map(lambda x: f"{x:.3f}")
    fmt.to_csv(OUT / f"heterogeneity_{name}.csv", index=False)
    save_table_image(
        fmt,
        f"Heterogeneity of key correlation by country - {name}",
        OUT / f"heterogeneity_{name}.png",
        fontsize=6.5,
        fig_w=11,
        row_h=0.32,
    )

# Descriptive stats transformed variables Y and X
desc_rows = []
for v, label, tdict in [(Y, "Y = D.GDP", trans), (X, "X = D.ENERGY", transX)]:
    for name, s in tdict.items():
        ss = pd.Series(s).dropna().astype(float)
        m = ss.mean()
        sd = ss.std(ddof=1)
        desc_rows.append(
            {
                "Variable": label,
                "Transformation": name,
                "N": len(ss),
                "Q1": ss.quantile(0.25),
                "Median": ss.median(),
                "Q3": ss.quantile(0.75),
                "Mean": m,
                "Std.Err.": sd,
                "Std. Min": (ss.min() - m) / sd,
                "Std. Max": (ss.max() - m) / sd,
                "Skew": stats.skew(ss),
                "Kurtosis": stats.kurtosis(ss),
            }
        )
desc = pd.DataFrame(desc_rows)
fmt = desc.copy()
for c in fmt.columns:
    if c not in ["Variable", "Transformation", "N"]:
        fmt[c] = fmt[c].map(lambda x: f"{x:.3f}")
fmt.to_csv(OUT / "transformed_descriptive_stats.csv", index=False)
save_table_image(
    fmt,
    "Descriptive statistics by transformation for Y and X",
    OUT / "transformed_descriptive_stats.png",
    fontsize=6.5,
    fig_w=12,
    row_h=0.31,
)

# Check FD first observations by country
fdcheck = baseline[[Y, X]].copy()
fdcheck["FD_Y"] = firstdiff(baseline[Y])
fdcheck["FD_X"] = firstdiff(baseline[X])
fdcheck_out = fdcheck.reset_index().groupby("country").head(3)
fdcheck_out["country"] = fdcheck_out["country"].map(country_names)
fdcheck_fmt = fdcheck_out[["country", "yr", Y, X, "FD_Y", "FD_X"]].copy()
for c in [Y, X, "FD_Y", "FD_X"]:
    fdcheck_fmt[c] = fdcheck_fmt[c].map(lambda x: "." if pd.isna(x) else f"{x:.4f}")
fdcheck_fmt.to_csv(OUT / "fd_check_first_observations.csv", index=False)
save_table_image(
    fdcheck_fmt.head(30),
    "First-difference check: first 30 observations",
    OUT / "fd_check_first_observations.png",
    "The first transformed observation of each country is missing, preventing accidental differencing across countries.",
    fontsize=6.0,
    fig_w=10,
    row_h=0.24,
)

# Estimations: simple panel transformations with all controls
regvars = ["dlenpr", "dlcpi", "dopen", "dexpgdp", "diy"]


def ols_table(y, X, label):
    data = pd.concat([y.rename("Y"), X], axis=1).dropna()
    if len(data) < 20:
        return None
    res = sm.OLS(data["Y"], sm.add_constant(data.drop(columns="Y"))).fit(cov_type="HC1")
    return label, res, data


est_rows = []
# between use country means of baseline
bd = baseline[[Y] + regvars].groupby(level=0).mean()
res = sm.OLS(bd[Y], sm.add_constant(bd[regvars])).fit(cov_type="HC1")
estimates = {"Between": res}
# within
wdata = pd.DataFrame({v: within(baseline[v]) for v in [Y] + regvars}).dropna()
estimates["Within FE"] = sm.OLS(wdata[Y], wdata[regvars]).fit(cov_type="HC1")
# Mundlak RE approximated via pooled OLS with entity means of X
md = baseline[[Y] + regvars].copy()
for v in regvars:
    md[f"{v}_mean"] = baseline[v].groupby(level=0).transform("mean")
md = md.dropna()
estimates["Mundlak pooled RE"] = sm.OLS(
    md[Y], sm.add_constant(md[regvars + [f"{v}_mean" for v in regvars]])
).fit(cov_type="HC1")
# TWFE residualization
Tdata = pd.DataFrame({v: twfe(baseline[v]) for v in [Y] + regvars}).dropna()
estimates["Two-way FE"] = sm.OLS(Tdata[Y], Tdata[regvars]).fit(cov_type="HC1")
# FD
FDdata = pd.DataFrame({v: firstdiff(baseline[v]) for v in [Y] + regvars}).dropna()
estimates["First differences"] = sm.OLS(FDdata[Y], FDdata[regvars]).fit(cov_type="HC1")
# Compile coefficients selected
for var in ["dlenpr", "dlcpi", "dopen", "dexpgdp", "diy"]:
    row = {"Variable": var}
    for name, res in estimates.items():
        if var in res.params.index:
            p = res.pvalues[var]
            star = "**" if p < 0.01 else "*" if p < 0.05 else ""
            row[name] = f"{res.params[var]:.3f}{star}\n({res.bse[var]:.3f})"
        else:
            row[name] = ""
    est_rows.append(row)
# N row
row = {"Variable": "N"}
for name, res in estimates.items():
    row[name] = str(int(res.nobs))
est_rows.append(row)
est_tbl = pd.DataFrame(est_rows)
est_tbl.to_csv(OUT / "panel_estimations_summary.csv", index=False)
save_table_image(
    est_tbl,
    "Panel estimates: Between, Within, Mundlak, TWFE and FD",
    OUT / "panel_estimations_summary.png",
    "Notes: b/(robust se). Mundlak includes country-specific means of regressors; TWFE is obtained by residualizing country and year means.",
    fontsize=6.5,
    fig_w=12,
    row_h=0.42,
)

# Dynamic ARDL/Anderson-Hsiao-type diagnostics (try IV2SLS if linearmodels available)
dyn = baseline.copy()
dyn["lag_dY"] = dyn.groupby(level=0)[Y].shift(1)
dyn["lag_dX"] = dyn.groupby(level=0)[X].shift(1)
dyn["Y_lag2"] = dyn.groupby(level=0)["lrgdpmad"].shift(2)
dyn["X_lag2"] = dyn.groupby(level=0)["lenpr"].shift(2)
dyn["D_lag_dY"] = firstdiff(dyn["lag_dY"])
# Model on differences: Y ~ lag_dY + X + lag_dX + controls in levels diff transformations (already diff vars)
dyn_vars = [
    Y,
    "lag_dY",
    X,
    "lag_dX",
    "dlcpi",
    "dopen",
    "dexpgdp",
    "diy",
    "Y_lag2",
    "X_lag2",
]
dyn_df = dyn[dyn_vars].dropna()
# OLS dynamic
olsdyn = sm.OLS(
    dyn_df[Y],
    sm.add_constant(
        dyn_df[["lag_dY", X, "lag_dX", "dlcpi", "dopen", "dexpgdp", "diy"]]
    ),
).fit(cov_type="HC1")
# first stages: regress lag_dY and X maybe lag_dX on instruments Y_lag2 X_lag2 + exog controls
fs_rows = []
for endv in ["lag_dY", X, "lag_dX"]:
    fs = sm.OLS(
        dyn_df[endv],
        sm.add_constant(
            dyn_df[["Y_lag2", "X_lag2", "dlcpi", "dopen", "dexpgdp", "diy"]]
        ),
    ).fit(cov_type="HC1")
    fs_rows.append(
        {
            "Endogenous/checked variable": endv,
            "N": int(fs.nobs),
            "R2": fs.rsquared,
            "Partial signal comment": (
                "weak if R2 below 0.10"
                if fs.rsquared < 0.10
                else "mechanical or sufficient raw R2"
            ),
        }
    )
fs_tbl = pd.DataFrame(fs_rows)
fmt = fs_tbl.copy()
fmt["R2"] = fmt["R2"].map(lambda x: f"{x:.3f}")
fmt.to_csv(OUT / "dynamic_first_stage_diagnostics.csv", index=False)
save_table_image(
    fmt,
    "Dynamic IV first-stage diagnostics",
    OUT / "dynamic_first_stage_diagnostics.png",
    "Notes: preliminary OLS first-stage diagnostics using second lags in levels as instruments and current differenced controls.",
    fontsize=7,
    fig_w=10,
    row_h=0.4,
)
# Try IV
iv_result = None
try:
    from linearmodels.iv import IV2SLS

    # instrument lag_dY and X with Y_lag2 X_lag2, keep lag_dX as exog? actually need enough inst; two endog two instruments
    iv = IV2SLS(
        dependent=dyn_df[Y],
        exog=sm.add_constant(dyn_df[["lag_dX", "dlcpi", "dopen", "dexpgdp", "diy"]]),
        endog=dyn_df[["lag_dY", X]],
        instruments=dyn_df[["Y_lag2", "X_lag2"]],
    ).fit(cov_type="robust")
    iv_result = iv
except Exception as e:
    iv_error = str(e)
# dynamic table
rows = []
for var in ["lag_dY", X, "lag_dX", "dlcpi", "dopen", "dexpgdp", "diy"]:
    p = olsdyn.pvalues.get(var, np.nan)
    star = "**" if p < 0.01 else "*" if p < 0.05 else ""
    row = {
        "Variable": var,
        "Dynamic OLS": f"{olsdyn.params.get(var,np.nan):.3f}{star}\n({olsdyn.bse.get(var,np.nan):.3f})",
    }
    if iv_result is not None and var in iv_result.params.index:
        p = iv_result.pvalues[var]
        star = "**" if p < 0.01 else "*" if p < 0.05 else ""
        row["IV2SLS (AH-type)"] = (
            f"{iv_result.params[var]:.3f}{star}\n({iv_result.std_errors[var]:.3f})"
        )
    else:
        row["IV2SLS (AH-type)"] = ""
    rows.append(row)
rows.append(
    {
        "Variable": "N",
        "Dynamic OLS": str(int(olsdyn.nobs)),
        "IV2SLS (AH-type)": (
            str(int(iv_result.nobs)) if iv_result is not None else "not estimated"
        ),
    }
)
dyn_tbl = pd.DataFrame(rows)
dyn_tbl.to_csv(OUT / "dynamic_ols_iv_results.csv", index=False)
save_table_image(
    dyn_tbl,
    "Dynamic ARDL / Anderson-Hsiao-type estimates",
    OUT / "dynamic_ols_iv_results.png",
    "Notes: b/(robust se). IV uses second lags in levels as instruments. Interpretation is diagnostic if the autoregressive parameter is not stable.",
    fontsize=7,
    fig_w=9,
    row_h=0.42,
)
# IRF based on IV if available else OLS
params = iv_result.params if iv_result is not None else olsdyn.params
by = float(params.get("lag_dY", np.nan))
b1 = float(params.get(X, np.nan))
b2 = float(params.get("lag_dX", np.nan))
irfs = []
for h in range(1, 5):
    if h == 1:
        val = b1
    elif h == 2:
        val = by * b1 + b2
    elif h == 3:
        val = by**2 * b1 + by * b2
    elif h == 4:
        val = by**3 * b1 + by**2 * b2
    irfs.append({"Horizon": h, "Impulse response": val})
irf = pd.DataFrame(irfs)
irf.to_csv(OUT / "dynamic_impulse_responses.csv", index=False)
fig, ax = plt.subplots(figsize=(5.5, 3.5))
ax.plot(irf["Horizon"], irf["Impulse response"], marker="o")
ax.axhline(0, color="black", lw=0.8)
ax.set_xticks([1, 2, 3, 4])
ax.set_xlabel("Horizon")
ax.set_ylabel("Response of GDP growth")
ax.set_title("Impulse responses to a one-unit increase in energy-price growth")
fig.savefig(OUT / "dynamic_impulse_responses.png", bbox_inches="tight")
plt.close(fig)
# Long run coefficient
lt = None
if np.isfinite(by) and abs(by) < 1:
    lt = (b1 + b2) / (1 - by)
else:
    lt = np.nan


print(f"[OK] Template diagnostics exported to {OUT}")
