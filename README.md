# Réplication de Huntington & Liddle (2022)

## *How Energy Prices Shape OECD Economic Growth: Panel Evidence from Multiple Decades*

> **Cours** : Économétrie avancée — Données de panel (Master 2)  
> **Université** : Université Paris 1 Panthéon-Sorbonne    
> **Date** : Juin 2026

---

## Description du Projet

Ce dépôt contient la réplication intégrale de l'article de Huntington & Liddle (2022), publié dans *Energy Economics*, dans trois langages de programmation : **Python**, **R** et **Stata**. L'article étudie l'impact des prix de l'énergie sur la croissance économique des pays de l'OCDE à l'aide d'estimateurs de panel hétérogènes (Mean Group, CCEMG) tenant compte de la dépendance transversale.

---

## Structure du Répertoire

```
Econometics2/
│
├── README.md                    ← Ce fichier
│
├── data/                        ← Données sources
│   └── growth_EE.xlsx           ← Fichier Excel brut contenant les onglets 'data' et 'tables5-6'
│
├── src/                         ← Code source du projet
│   ├── python/                  ← Code Python optimisé et modulaire
│   │   ├── __init__.py
│   │   ├── 01_data_prep.py      ← Chargement, variables, retards, différences et dummy post-1982
│   │   ├── 02_estimators.py     ← Estimateurs (CIPS t-bar, CCEMG avec CSA dynamiques, Robust MG)
│   │   ├── 03_exports.py        ← Production des Tables 1 à 6 (CSV+PNG) et des Figures A.1 à A.7
│   │   ├── 04_extension.py      ← Extension Fixed Effects avec variable d'interaction
│   │   └── run_replication.py   ← Orchestrateur unique de la pipeline
│   │
│   ├── R/                       ← Portage R
│   │   └── replication.R        ← Script de réplication en R
│   │
│   └── stata/                   ← Portage Stata
│       └── replication.do       ← Script de réplication en Stata
│
├── outputs/                     ← Résultats générés
│   ├── tables/                  ← Tableaux (CSV + PNG format publication)
│   └── figures/                 ← Figures (PNG format publication)
│
└── docs/                        ← Documentation additionnelle
    ├── portage_commentary.md    ← Note de synthèse sur les difficultés du portage Python → R / Stata
    └── panel_todo_list.md       ← Check-list exhaustive pour les études futures en données de panel
```

---

## Prérequis

### Python (≥ 3.9)

| Package | Version minimale | Usage |
|---------|-----------------|-------|
| `numpy` | ≥ 1.21 | Calcul matriciel, pondérations de Huber |
| `pandas` | ≥ 1.3 | Manipulation des données de panel |
| `statsmodels` | ≥ 0.13 | Estimation OLS, tests statistiques, moyennes transversales |
| `scipy` | ≥ 1.7 | Décomposition QR (réduction du rang), fonctions statistiques |
| `matplotlib` | ≥ 3.5 | Production graphique des figures et tableaux |
| `linearmodels` | ≥ 4.25 | Estimation IV-2SLS et PanelOLS (Fixed Effects) |

Installation :

```bash
pip install numpy pandas statsmodels scipy matplotlib linearmodels
```

### R (≥ 4.1)

| Package | Usage |
|---------|-------|
| `readxl` | Lecture des fichiers Excel (.xlsx) |
| `dplyr` | Manipulation de données |
| `tidyr` | Mise en forme des données (diffs, lags) |
| `ggplot2` | Production des graphiques |
| `sandwich` | Calcul de covariance robuste / HAC |
| `lmtest` | Tests sur les coefficients |
| `ivreg` | Estimation de variables instrumentales (2SLS) |
| `gridExtra` | Mise en forme des tableaux graphiques |

Installation :

```r
install.packages(c("readxl", "dplyr", "tidyr", "ggplot2", "sandwich", "lmtest", "ivreg", "gridExtra"))
```

### Stata (≥ 14)

L'ensemble des estimations est réalisé avec les commandes natives de Stata (`regress`, `ivregress`, `xtreg`) et une programmation personnalisée `calc_huber` directement embarquée pour le calcul des poids de Huber. 

Aucune installation de package externe n'est requise. Si vous le souhaitez, pour comparaison, vous pouvez installer l'estimateur DCCE externe officiel :
```stata
ssc install xtdcce2
```

---

## Exécution

> **Important** : Placez-vous à la racine du répertoire `Econometics2/` avant de lancer les commandes ci-dessous.

### Python

```bash
# Pour exécuter la réplication principale seule (Tables 1-6 et Figures A.1-A.7)
python src/python/run_replication.py

# Pour exécuter la réplication principale ET l'extension Fixed Effects (avec graphique d'effet marginal)
python src/python/run_replication.py --extension
```

Les résultats sont sauvegardés dans `outputs/tables/` et `outputs/figures/`.

### R

```bash
Rscript src/R/replication.R
```

Les résultats de la réplication en R sont exportés directement.

### Stata

Exécuter la commande suivante dans Stata :

```stata
do "src/stata/replication.do"
```

---

## Résultats Produits (Python)

### Tableaux (outputs/tables/)

Chaque tableau est exporté sous deux formats : **CSV** (données brutes) et **PNG** (rendu formaté académique).

| Tableau | Description |
|---------|-------------|
| `table1_data_summary` | Statistiques descriptives du panel (CV vide pour les variables en différence D.) |
| `table2_cips_unitroot` | Tests de racine unitaire CIPS (sans et avec tendance) |
| `table3_cce_robust` | Résultats CCEMG (Unweighted vs Robust MG avec pondération de Huber) |
| `table4_ccemg_robustness` | Spécifications de robustesse CCEMG (IV, Exogène, w/o Mod, Dummy Récession, Outliers, 1960s) |
| `table5_country_responses` | Réponses individuelles des pays (Intensités, Exports, Imports, coefficients Pre/Post) |
| `table6_intensity_regression` | Régressions transversales des coefficients post-1982 sur l'intensité énergétique |
| `extension_fe_interaction` | Résultats de l'estimation Fixed Effects de l'extension (*uniquement avec `--extension`*) |

### Figures (outputs/figures/)

Toutes les figures sont exportées en **PNG** (200 DPI).

| Figure | Fichier | Description |
|--------|---------|-------------|
| Figure A.1 | `figA1_gdp_levels.png` | Niveaux de PIB réel des pays (log) |
| Figure A.2 | `figA2_cpi_levels.png` | Niveaux d'IPC des pays (log) |
| Figure A.3 | `figA3_energy_levels.png` | Niveaux des prix de l'énergie des pays (log) |
| Figure A.4 | `figA4_opentrade.png` | Ouverture commerciale des pays (% du PIB) |
| Figure A.5 | `figA5_govexp.png` | Dépenses publiques des pays (% du PIB) |
| Figure A.6 | `figA6_investment.png` | Taux d'investissement des pays (% du PIB) |
| Figure A.7 | `figA7_gdp_residuals.png` | Variations réelles du PIB (ligne continue) et résidus CCEMG (ligne pointillée) superposés |
| Effet Marginal | `outputs/tables/extension_marginal_effect.png` | Effet marginal du prix de l'énergie selon l'intensité énergétique (*uniquement avec `--extension`*) |

---

## Méthodologie

L'article de Huntington & Liddle (2022) utilise l'estimateur CCEMG (*Common Correlated Effects Mean Group*) de Pesaran (2006) pour estimer l'impact des prix de l'énergie sur la croissance économique dans un panel de pays de l'OCDE. Les caractéristiques méthodologiques principales sont :

1. **Hétérogénéité des pentes** : les coefficients sont estimés pays par pays, puis agrégés par la moyenne.
2. **Dépendance transversale** : les moyennes transversales (CSA) sont ajoutées comme régresseurs pour filtrer les facteurs communs inobservés.
3. **Robustesse** : les pondérations de Huber sont appliquées pour atténuer l'influence des pays aux coefficients extrêmes.
4. **Variables instrumentales** : le premier retard du prix de l'énergie est utilisé comme instrument pour traiter l'endogénéité potentielle.

Pour une discussion détaillée des difficultés de portage entre Python, R et Stata, consulter le document [`docs/portage_commentary.md`](docs/portage_commentary.md).

Pour une checklist méthodologique complète pour les études en données de panel, consulter le document [`docs/panel_todo_list.md`](docs/panel_todo_list.md).

---

## Références

- Ditzen, J. (2018). Estimating dynamic common-correlated effects in Stata. *The Stata Journal*, 18(3), 585–617.
- Huntington, H. & Liddle, B. (2022). How energy prices shape OECD economic growth: Panel evidence from multiple decades. *Energy Economics*.
- Pesaran, M. H. (2006). Estimation and inference in large heterogeneous panels with a multifactor error structure. *Econometrica*, 74(4), 967–1012.
- Pesaran, M. H. (2007). A simple panel unit root test in the presence of cross-section dependence. *Journal of Applied Econometrics*, 22(2), 265–312.
- Pesaran, M. H. & Smith, R. (1995). Estimating long-run relationships from dynamic heterogeneous panels. *Journal of Econometrics*, 68(1), 79–113.

---

## Licence

Ce projet est réalisé dans un cadre académique. Les données et la méthodologie sont la propriété intellectuelle des auteurs originaux (Huntington & Liddle, 2022). Le code de réplication est fourni à des fins pédagogiques uniquement.
