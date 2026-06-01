# Commentaire sur le Portage du Code de Réplication

## Réplication de Huntington & Liddle (2022) — Python, R et Stata

> **Référence** : Huntington, H. & Liddle, B. (2022). *How energy prices shape OECD economic growth: Panel evidence from multiple decades*. Energy Economics.

---

## Table des matières

1. [Introduction](#1-introduction)
2. [Estimateur CCEMG](#2-estimateur-ccemg)
3. [Test CIPS de Pesaran](#3-test-cips-de-pesaran)
4. [Pondérations de Huber](#4-pondérations-de-huber)
5. [Estimation par Variables Instrumentales](#5-estimation-par-variables-instrumentales)
6. [Réduction de Rang Matriciel](#6-réduction-de-rang-matriciel)
7. [Formats d'Exportation](#7-formats-dexportation)
8. [Conclusion](#8-conclusion)

---

## 1. Introduction

Le portage d'un code économétrique d'un langage à un autre ne se réduit jamais à une simple traduction syntaxique. Les différences entre Python, R et Stata — tant sur le plan des bibliothèques disponibles que sur les conventions d'estimation — engendrent des difficultés spécifiques que ce document se propose de recenser et d'analyser. Chaque section ci-dessous traite d'un aspect méthodologique du modèle de Huntington & Liddle (2022) et détaille les adaptations nécessaires dans chacun des trois environnements.

---

## 2. Estimateur CCEMG

### 2.1. Principe de l'estimateur

L'estimateur *Common Correlated Effects Mean Group* (CCEMG), introduit par Pesaran (2006), repose sur deux idées complémentaires :

- **Hétérogénéité des pentes** : on estime un modèle propre à chaque unité du panel (pays), puis on agrège les coefficients par la moyenne (approche *Mean Group* de Pesaran & Smith, 1995).
- **Facteurs communs inobservés** : les moyennes en coupe transversale des variables dépendantes et indépendantes sont incluses comme régresseurs auxiliaires afin de filtrer la dépendance transversale.

### 2.2. Implémentation en Python

En Python, nous procédons par une boucle explicite sur les pays. Pour chaque pays $i$ :

1. On construit la matrice de régresseurs augmentée des moyennes en coupe transversale $\bar{y}_t$ et $\bar{x}_t$.
2. On estime par OLS (ou IV-2SLS lorsque des instruments sont requis) à l'aide de `statsmodels.OLS` ou `linearmodels.IV2SLS`.
3. On stocke le vecteur de coefficients $\hat{\beta}_i$.

Le coefficient CCEMG final est $\hat{\beta}_{MG} = N^{-1} \sum_{i=1}^{N} \hat{\beta}_i$, et son écart-type est calculé selon la formule du *Mean Group* (variance inter-pays des $\hat{\beta}_i$).

### 2.3. Portage en R

En R, **il n'existe pas d'équivalent natif du package Stata `xtdcce2`** (Ditzen, 2018). L'utilisateur doit donc :

- Construire manuellement les moyennes en coupe transversale via `dplyr::group_by(year) %>% summarise(across(..., mean))`.
- Estimer le modèle pays par pays avec `lm()` pour les spécifications OLS et `ivreg::ivreg()` pour les spécifications IV.
- Calculer les matrices de variance-covariance robustes à l'hétéroscédasticité et à l'autocorrélation (HAC) avec `sandwich::vcovHAC()`.
- Agréger les coefficients et calculer l'écart-type *Mean Group* à la main.

Cette absence de package intégré rend le code R sensiblement plus long et sujet à des erreurs de manipulation des indices.

### 2.4. Portage en Stata

Bien que le package `xtdcce2` de Ditzen (2018) soit disponible en Stata et offre une implémentation directe du CCEMG, nous avons choisi une **implémentation manuelle** avec `ivregress 2sls` pays par pays. Ce choix se justifie par :

- Le contrôle total sur la construction des moyennes transversales.
- La possibilité de reproduire exactement la logique de la boucle Python (et ainsi de comparer les résultats coefficient par coefficient).
- La transparence pédagogique : pour un cours de Master, il est plus formateur de comprendre le mécanisme que de recourir à une boîte noire.

L'implémentation repose sur une boucle `foreach` sur les valeurs de la variable pays, avec `preserve` / `restore` pour isoler le sous-échantillon.

---

## 3. Test CIPS de Pesaran

### 3.1. Principe du test

Le test CIPS (*Cross-sectionally Augmented IPS*) de Pesaran (2007) est un test de racine unitaire en panel qui tient compte de la dépendance transversale. Pour chaque unité $i$, on estime la régression CADF (*Cross-sectionally Augmented Dickey-Fuller*) :

$$\Delta y_{it} = \alpha_i + \rho_i \, y_{i,t-1} + \gamma_i \, \bar{y}_{t-1} + \delta_i \, \Delta\bar{y}_t + \varepsilon_{it}$$

La statistique CIPS est la moyenne des statistiques $t$ individuelles : $\overline{t} = N^{-1} \sum_{i=1}^{N} t_i(\rho_i)$.

### 3.2. Disponibilité dans les packages existants

| Langage | Package candidat | Disponibilité du CIPS |
|---------|------------------|-----------------------|
| Python  | Aucun package standard | ✗ — Implémentation manuelle |
| R       | `plm` (Croissant & Millo) | ✗ — `plm::purtest()` ne propose pas le CIPS |
| Stata   | `multipurt` (Lewandowski) | Partiellement — mais non standard |

### 3.3. Notre approche

Dans les trois langages, nous avons implémenté **manuellement** la régression CADF :

1. Calcul des moyennes en coupe transversale $\bar{y}_t$ et $\Delta\bar{y}_t$.
2. Estimation OLS de la régression CADF pour chaque pays.
3. Extraction de la statistique $t$ de $\hat{\rho}_i$.
4. Calcul de la statistique $\bar{t}$ (t-bar).

> **Note importante** : Nous rapportons la statistique $\bar{t}$ brute et non la version $Z$ standardisée (qui requiert les moments tabulés par Pesaran, 2007, Table II). Ce choix est cohérent avec la présentation de Huntington & Liddle (2022) et simplifie la comparaison inter-langages.

### 3.4. Difficultés spécifiques

- **Gestion des retards** : la construction de $y_{i,t-1}$ et $\Delta\bar{y}_t$ est triviale en Python (`shift()` de pandas) et en Stata (`L.` et `D.`), mais requiert une attention particulière en R avec `dplyr::lag()` (qui peut entrer en conflit avec `stats::lag()`).
- **Panels non cylindrés** : si le panel est non balancé, le nombre de retards de $\Delta\bar{y}_t$ peut varier. Nous avons imposé un panel balancé pour éviter cette complication.

---

## 4. Pondérations de Huber

### 4.1. Motivation

L'estimateur *Mean Group* robuste pondère les coefficients individuels $\hat{\beta}_i$ afin de réduire l'influence des valeurs aberrantes. La fonction de pondération de Huber (Huber, 1964) attribue un poids :

$$w_i = \begin{cases} 1 & \text{si } |u_i| \leq c \\ c / |u_i| & \text{si } |u_i| > c \end{cases}$$

où $u_i = (\hat{\beta}_i - \text{med}(\hat{\beta})) / \text{MAD}(\hat{\beta})$ et $c = 1{,}345$ (valeur conventionnelle assurant 95 % d'efficacité sous la loi normale).

### 4.2. Implémentation en Python

```python
import numpy as np

median_b = np.median(betas)
mad_b = np.median(np.abs(betas - median_b))
u = (betas - median_b) / (mad_b + 1e-12)
weights = np.where(np.abs(u) <= 1.345, 1.0, 1.345 / np.abs(u))
beta_robust = np.average(betas, weights=weights)
```

L'implémentation est directe grâce à la vectorisation de NumPy.

### 4.3. Implémentation en R

```r
median_b <- median(betas)
mad_b <- median(abs(betas - median_b))
u <- (betas - median_b) / (mad_b + 1e-12)
weights <- ifelse(abs(u) <= 1.345, 1, 1.345 / abs(u))
beta_robust <- weighted.mean(betas, weights)
```

La logique est quasi identique. La seule difficulté est de ne **pas** utiliser la fonction `mad()` de R base, qui inclut un facteur de normalisation ($\times 1{,}4826$) inadapté ici. Nous calculons donc le MAD manuellement.

### 4.4. Implémentation en Stata

En Stata, il n'existe pas de fonction vectorisée native pour le calcul des poids de Huber. Nous avons créé un **programme `calc_huber`** en logique `ado` :

```stata
program define calc_huber, rclass
    syntax varname, [C(real 1.345)]
    
    quietly summarize `varlist', detail
    local med = r(p50)
    
    tempvar dev abs_dev
    gen `dev' = `varlist' - `med'
    gen `abs_dev' = abs(`dev')
    quietly summarize `abs_dev', detail
    local mad = r(p50)
    
    tempvar u w
    gen `u' = `dev' / (`mad' + 1e-12)
    gen `w' = cond(abs(`u') <= `c', 1, `c' / abs(`u'))
    
    quietly summarize `varlist' [aweight = `w']
    return scalar beta_robust = r(mean)
end
```

Cette approche, bien que fonctionnelle, est significativement plus verbeuse et moins lisible que les versions Python et R.

---

## 5. Estimation par Variables Instrumentales

### 5.1. Cadre général

Certaines spécifications du modèle de Huntington & Liddle (2022) recourent à l'estimation par variables instrumentales (IV-2SLS) pour traiter l'endogénéité potentielle des prix de l'énergie. Le premier retard du prix est utilisé comme instrument.

### 5.2. Packages et commandes

| Langage | Package / Commande | Appel typique |
|---------|---------------------|---------------|
| Python  | `linearmodels.IV2SLS` | `IV2SLS(dependent, exog, endog, instruments).fit(cov_type='kernel')` |
| R       | `ivreg::ivreg()` | `ivreg(y ~ x1 + x2 | z1 + z2, data = df)` |
| Stata   | `ivregress 2sls` | `ivregress 2sls y x1 (x2 = z1), vce(robust)` |

### 5.3. Différences dans les matrices de variance-covariance HAC

Les trois implémentations utilisent des estimateurs de variance-covariance robustes à l'hétéroscédasticité et à l'autocorrélation, mais avec des **spécifications par défaut différentes** :

| Paramètre | Python (`linearmodels`) | R (`sandwich`) | Stata |
|-----------|------------------------|----------------|-------|
| Noyau (*kernel*) | Bartlett | Bartlett (par défaut dans `vcovHAC`) | Bartlett (par défaut) |
| Bande passante | Automatique (Newey-West) | `bwAndrews()` ou `bwNeweyWest()` | $\lfloor 0{,}75 \cdot T^{1/3} \rfloor$ |
| Correction degrés de liberté | Non (par défaut) | Oui (ajustable) | Oui (`small` option) |

Ces différences peuvent engendrer de **légères divergences numériques** dans les écarts-types, et donc dans les statistiques $t$ et les niveaux de significativité. Pour maximiser la reproductibilité, nous avons :

- Fixé la bande passante manuellement dans les trois langages.
- Désactivé la correction des degrés de liberté lorsque cela était possible.

### 5.4. Remarque sur la syntaxe de formule

La syntaxe de spécification du modèle IV diffère notablement :

- **Python** sépare explicitement les arguments `exog`, `endog` et `instruments` comme des matrices distinctes.
- **R** utilise une syntaxe de formule avec le séparateur `|` : les variables à gauche de `|` sont les régresseurs, celles à droite sont les instruments (en incluant les exogènes).
- **Stata** utilise la notation `(endogène = instruments)` au sein de la commande `ivregress`.

Cette hétérogénéité syntaxique est une source fréquente de confusion lors du portage.

---

## 6. Réduction de Rang Matriciel

### 6.1. Le problème de la colinéarité

Lorsque l'on augmente la matrice de régresseurs avec les moyennes en coupe transversale (et éventuellement leurs retards), il est fréquent que la matrice résultante soit de rang réduit — c'est-à-dire que certaines colonnes soient des combinaisons linéaires des autres. L'estimation OLS standard échoue alors (matrice $X'X$ singulière).

### 6.2. La fonction `_reduce_full_rank`

Dans le code Python original, la fonction `_reduce_full_rank` procède par **décomposition QR avec pivotement** :

```python
from numpy.linalg import qr

def _reduce_full_rank(X):
    Q, R, P = qr(X, mode='economic', pivoting=True)
    rank = np.sum(np.abs(np.diag(R)) > 1e-10)
    keep = P[:rank]
    return X[:, keep]
```

Cette fonction identifie les colonnes linéairement indépendantes et élimine les colonnes redondantes.

### 6.3. Portage en R

```r
reduce_full_rank <- function(X) {
  qr_decomp <- qr(X)
  rank <- qr_decomp$rank
  pivot <- qr_decomp$pivot[1:rank]
  return(X[, pivot, drop = FALSE])
}
```

R dispose nativement de `qr()` avec pivotement, ce qui rend le portage relativement direct. Toutefois, la convention d'indexation (1-indexé en R vs 0-indexé en Python) nécessite une attention particulière.

### 6.4. Portage en Stata

Stata ne dispose pas d'une fonction `qr` accessible à l'utilisateur dans le langage standard. Nous avons utilisé les **fonctions matricielles de Mata** :

```stata
mata:
    void reduce_full_rank(string scalar matname) {
        real matrix X, Q, R
        real colvector p
        real scalar rk
        
        X = st_matrix(matname)
        _qrp(X, Q, R, p)
        rk = rank(X)
        X = X[., p[1..rk]]
        st_matrix(matname, X)
    }
end
```

Le recours à Mata ajoute une couche de complexité non négligeable : il faut transférer les données entre l'environnement Stata et l'environnement Mata, ce qui alourdit le code.

### 6.5. Pourquoi aucun package ne fournit cette fonctionnalité

La réduction automatique de rang est une opération spécifique au contexte CCEMG. Les packages économétriques standards (comme `plm` en R ou `reghdfe` en Stata) gèrent la colinéarité par suppression *ad hoc* de variables, mais ne fournissent pas une fonction générique de type `_reduce_full_rank` basée sur la décomposition QR. C'est pourquoi une implémentation manuelle a été nécessaire dans les trois langages.

---

## 7. Formats d'Exportation

### 7.1. Tableaux

| Langage | Outil principal | Format de sortie |
|---------|----------------|------------------|
| Python  | `matplotlib.table` | PNG (image) + CSV (données) |
| R       | `gridExtra::tableGrob` + `ggplot2` | PNG (image) + CSV |
| Stata   | `putexcel` / `postfile` | XLSX / DTA + PNG (via `graph export`) |

### 7.2. Difficultés de formatage

- **Python** : `matplotlib.table` offre un contrôle fin sur les couleurs de cellules, les largeurs de colonnes et les polices, mais la mise en page requiert de nombreux ajustements manuels (`bbox`, `cellLoc`, etc.).
- **R** : `tableGrob` permet de créer des objets graphiques tabulaires intégrables dans un `ggplot`, mais le rendu typographique est moins soigné que celui de `kableExtra` (lequel produit du HTML/LaTeX et non des images PNG).
- **Stata** : `putexcel` produit des fichiers Excel bien formatés, mais l'exportation en image nécessite un passage intermédiaire. L'alternative `postfile` crée des fichiers `.dta` exploitables mais sans mise en forme visuelle.

### 7.3. Figures

Les figures sont produites avec `matplotlib` (Python), `ggplot2` (R) et `graph twoway` (Stata). Les différences esthétiques sont mineures, mais la **grammaire graphique** diffère considérablement :

- `ggplot2` repose sur une grammaire des graphiques (Wilkinson, 2005) avec un système de couches (*layers*).
- `matplotlib` utilise un modèle impératif (figure → axes → tracé).
- Stata adopte une syntaxe déclarative compacte mais moins flexible.

---

## 8. Conclusion

Le portage du code de réplication de Huntington & Liddle (2022) vers R et Stata met en lumière plusieurs constats :

1. **L'écosystème Python est le plus flexible** pour l'économétrie de panel avancée, grâce à la programmation vectorisée de NumPy et à la richesse de `linearmodels` et `statsmodels`.
2. **R offre une infrastructure solide** (`sandwich`, `plm`, `ivreg`) mais souffre de l'absence de certains tests spécialisés (CIPS) et d'estimateurs intégrés (CCEMG).
3. **Stata dispose de packages spécialisés** (`xtdcce2`) mais l'implémentation manuelle reste préférable à des fins pédagogiques et de contrôle.
4. **Les divergences numériques** entre les trois langages sont faibles mais non nulles, principalement dues aux choix par défaut des matrices HAC et aux algorithmes de décomposition QR.

---

## Références

- Ditzen, J. (2018). Estimating dynamic common-correlated effects in Stata. *The Stata Journal*, 18(3), 585–617.
- Huber, P. J. (1964). Robust estimation of a location parameter. *Annals of Mathematical Statistics*, 35(1), 73–101.
- Huntington, H. & Liddle, B. (2022). How energy prices shape OECD economic growth. *Energy Economics*.
- Pesaran, M. H. (2006). Estimation and inference in large heterogeneous panels with a multifactor error structure. *Econometrica*, 74(4), 967–1012.
- Pesaran, M. H. (2007). A simple panel unit root test in the presence of cross-section dependence. *Journal of Applied Econometrics*, 22(2), 265–312.
- Pesaran, M. H. & Smith, R. (1995). Estimating long-run relationships from dynamic heterogeneous panels. *Journal of Econometrics*, 68(1), 79–113.
