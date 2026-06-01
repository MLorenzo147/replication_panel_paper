# Rapport de Réplication et Réponses au Devoir d'Économétrie des Données de Panel

**Cours** : Économétrie des données de panel (Master 2)  
**Université** : Université Paris 1 Panthéon-Sorbonne  
**Étudiant** : Lorenzo  
**Date** : Juin 2026  
**Papier répliqué** : Huntington, H. & Liddle, B. (2022), *"How energy prices shape OECD economic growth: Panel evidence from multiple decades"*, Energy Economics, 111, 106082.

---

## 1. Informations Générales et Références

* **Référence APA du papier répliqué** :  
  Huntington, H., & Liddle, B. (2022). How energy prices shape OECD economic growth: Panel evidence from multiple decades. *Energy Economics*, 111, 106082.
* **Lien vers l'article (avec DOI)** : [https://doi.org/10.1016/j.eneco.2022.106082](https://doi.org/10.1016/j.eneco.2022.106082)

### Table 1: Key correlation of the paper

| Variable Dépendante ($Y$) | Variable Explicative Principale ($X$) | Niveau d'Analyse | Source des Données |
| :--- | :--- | :--- | :--- |
| Croissance du PIB réel par habitant (`dlrgdpmad`) | Croissance du prix réel de l'énergie (`dlenpr`) | Pays (18 pays de l'OCDE) | Maddison Project Database / Penn World Table / EIA |

* **Lien vers le jeu de données** : Le fichier source de données est [growth_EE.xlsx](file:///c:/Users/loren/OneDrive%20-%20Universit%C3%A9%20Paris%201%20Panth%C3%A9on-Sorbonne/projetPython/Econometics2/data/growth_EE.xlsx).

---

## 2. Résumé (Abstract) & Introduction

### Résumé (Abstract — ~100 mots)
Ce travail propose la réplication et l'extension du papier de Huntington & Liddle (2022). À l'aide d'un panel de 18 pays de l'OCDE sur la période 1960-2016, nous analysons les propriétés de stationnarité (tests CIPS) et de dépendance transversale (test CD de Pesaran). Nous estimons l'impact des hausses de prix de l'énergie sur la croissance économique par des estimateurs de panel homogènes (OLS, FE, RE-Mundlak, FD) et hétérogènes (CCEMG, Robust Mean Group avec poids de Huber). Une extension par effets fixes avec interaction temporelle révèle l'effet marginal des prix de l'énergie modulé par l'intensité énergétique initiale des pays.

### Introduction (1 page — 3 paragraphes sur les résultats originaux ou non documentés)
1. **Influence des Outliers et Robustesse** : L'utilisation de l'estimateur robuste (Robust Mean Group avec pondération de Huber) modère très significativement l'impact estimé du prix de l'énergie par rapport à l'estimateur CCEMG non pondéré (le coefficient passe de $-0.076$ à $-0.039$). Cela met en évidence que l'estimation standard est fortement influencée par des pays aux comportements extrêmes (tels que l'Irlande ou l'Allemagne) ayant subi des chocs macroéconomiques atypiques. Cette sensibilité aux valeurs aberrantes n'est pas discutée en profondeur dans l'article original.
2. **Homogénéité des Pentes et Dépendance Transversale** : Les diagnostics statistiques du panel révèlent des violations majeures des hypothèses des modèles homogènes classiques. Le test CD de Pesaran rejette massivement l'indépendance transversale ($p=0.0$), et le test de Pesaran-Yamagata rejette l'homogénéité des pentes avec une statistique $\tilde{\Delta}$ extrêmement élevée ($16682.99$, $p=0.0$). Ces résultats invalident formellement l'utilisation des modèles Pooled OLS ou Fixed Effects homogènes simples, justifiant l'approche par groupes moyens (Mean Group) de l'article.
3. **Résultats de l'Extension** : L'extension sous forme de modèle à Effets Fixes temporels avec interaction ($Z_i \times X_{it}$) montre que le coefficient d'intérêt direct du prix de l'énergie ($\beta_1$) est négatif et statistiquement significatif à $-0.0756$ ($p=0.021$). En revanche, le coefficient de l'interaction avec l'intensité énergétique de départ ($\beta_2$) est positif mais statistiquement non significatif ($0.0076$, $p=0.115$). Cela suggère qu'à court terme, l'intensité énergétique initiale ne module pas linéairement et de manière significative la réponse des pays aux chocs énergétiques au sein d'une structure à effets fixes.

### Table 2: Key items found by order of interest

1. L'hétérogénéité des pentes entre pays est statistiquement majeure (Pesaran-Yamagata $\tilde{\Delta}$ test).
2. La dépendance transversale est extrêmement forte sur l'ensemble des variables (Pesaran CD test).
3. L'impact de court terme des chocs de prix de l'énergie sur la croissance est négatif et significatif.
4. L'exclusion ou la pondération robuste (Huber) des pays aberrants divise par deux l'effet estimé.
5. Les estimations dynamiques en variables instrumentales (GMM / Anderson-Hsiao) souffrent d'un biais d'explosivité ($\beta_y > 1$).

---

## 3. Caractéristiques des Données et Sélection du Panel

### Table 3: Caractéristiques des données

| Période maximale | Fréquence | Nombre d'individus | Obs. temporelles max | Structure |
| :--- | :--- | :--- | :--- | :--- |
| **Historique** : 1960–2016  | Annuelle | $N_{total} = 18$ pays | $T_{max} = 57$ ans | Unbalanced (historique) |
| **Référence** : 1972–2016 | Annuelle | $N = 18$ pays | $T = 45$ ans | Balanced (période de base) |

* **Commentaire sur la sélection et le biais** :  
  L'exclusion initiale de certaines observations s'explique par l'absence de données historiques homogènes au début du panel (l'Australie débute en 1972 et l'Allemagne en 1962). La sous-période 1972-2016 permet d'obtenir un panel parfaitement cylindré (balanced) de $N=18$ pays et $T=45$ ans, soit 810 observations. Le panel étant restreint à 18 pays développés de l'OCDE, il présente un biais de sélection inhérent (exclusion des pays à faible revenu et en développement).

### Structure des observations manquantes (Non-cylindrage)
* **Australie** : 45 observations (données manquantes pour 1960-1971).
* **Allemagne** : 55 observations (données manquantes pour 1960-1961).
* **Autres pays (16)** : 57 observations complètes (1960-2016).
* **Analyse de l'attrition** : Il n'y a pas d'attrition à la fin du panel (tous les pays sont observés jusqu'en 2016). Les données manquantes se situent uniquement en début de période.

---

## 4. Classification des Variables et Décomposition de la Variance

La décomposition de la variance sur le panel de référence (1972-2016) donne les résultats suivants :

### Table 4: Décomposition de la variance (Variables en niveaux et différences)

| Variable | Libellé | N | NT | Var. Totale | Var. Between | Var. Within | % Variance Within |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Variables en Niveaux** | | | | | | | |
| `lcpi` | Log IPC | 18 | 810 | 0.3656 | 0.0069 | 0.3591 | **98.22 %** (Temporelle) |
| `lenpr` | Log Prix Énergie | 18 | 810 | 0.0512 | 0.0100 | 0.0417 | **81.52 %** (Temporelle) |
| `lrgdpmad` | Log PIB réel | 18 | 810 | 0.0977 | 0.0315 | 0.0679 | **69.50 %** (Temporelle) |
| `iy` | Investissement (% PIB) | 18 | 810 | 0.0015 | 0.0005 | 0.0010 | **66.34 %** (Intermédiaire) |
| `open` | Ouverture Trade (% PIB)| 18 | 810 | 0.0934 | 0.0760 | 0.0215 | **23.05 %** (Sluggish) |
| `expgdp` | Dépenses Pub (% PIB) | 18 | 810 | 0.0082 | 0.0071 | 0.0014 | **17.46 %** (Sluggish) |
| **Variables en Différences** | | | | | | | |
| `dlenpr` | Croissance Prix Énergie| 18 | 809 | 0.0054 | 0.0000 | 0.0054 | **99.62 %** (Pure Within) |
| `dopen` | Var. Ouverture Trade | 18 | 809 | 0.0077 | 0.0000 | 0.0077 | **99.74 %** (Pure Within) |
| `dlrgdpmad`| Croissance PIB réel | 18 | 809 | 0.0006 | 0.0000 | 0.0005 | **96.11 %** (Pure Within) |
| `diy` | Var. Taux Invest. | 18 | 809 | 0.0002 | 0.0000 | 0.0002 | **88.95 %** (Pure Within) |

* **Commentaire sur la décomposition** :  
  Les variables d'ouverture commerciale (`open`) et de dépenses publiques (`expgdp`) sont extrêmement persistantes et se comportent comme des variables quasi-invariantes dans le temps par pays (le Between représente respectivement 77 % et 82 % de leur variance). À l'inverse, l'IPC (`lcpi`) et les variables sous forme de taux de croissance (différences premières) varient presque exclusivement dans la dimension temporelle (Within > 96 %).

---

## 5. Analyse de Corrélation et Paradoxe de Simpson

L'analyse de la relation entre le PIB ($Y$) et le prix de l'énergie ($X$) selon les transformations met en évidence un effet de composition important :

* **Corrélation globale en niveaux (`lrgdpmad` et `lenpr`)** : **`+0.3999`**  
  *Explication* : Cette corrélation est positive et forte car les deux variables partagent une tendance temporelle positive croissante (croissance économique et hausse tendancielle des prix de l'énergie sur 50 ans).
* **Corrélation Within en niveaux** : **`+0.5945`**  
  *Explication* : En retirant les effets fixes individuels mais en conservant la tendance temporelle, la corrélation positive se renforce.
* **Corrélation Between (Moyennes individuelles)** : **`-0.2006`**  
  *Explication* : Les pays ayant en moyenne les prix de l'énergie les plus élevés ont en moyenne un niveau de PIB plus faible, ce qui est conforme à la théorie économique.
* **Corrélation en Différences Premières (Taux de croissance `dlrgdpmad` et `dlenpr`)** : **`-0.0807`**  
  *Explication* : Une fois les tendances déterministes et les effets spécifiques aux pays éliminés par différenciation, la relation de court terme apparaît négative. Un choc de prix de l'énergie est corrélé à un ralentissement de la croissance économique.

---

## 6. Hétérogénéité Individuelle des Corrélations et des Pentes

Le tableau ci-dessous trie la corrélation en différences premières (croissance du PIB vs croissance du prix de l'énergie) par pays, mettant en évidence une forte hétérogénéité :

### Table 5: Corrélations et pentes spécifiques en Différences Premières (FD)

| Pays | T | Corrélation $r(\Delta Y, \Delta X)$ | Écart-type $\sigma(\Delta Y)$ | Écart-type $\sigma(\Delta X)$ | Pente $\beta = r \cdot \frac{\sigma(Y)}{\sigma(X)}$ |
| :--- | :-: | :-: | :-: | :-: | :-: |
| **Suisse (CHE)** | 45 | **0.321** | 0.0200 | 0.0718 | 0.0895 |
| **Allemagne (DEU)** | 45 | **0.150** | 0.0203 | 0.0566 | 0.0540 |
| **Canada (CAN)** | 45 | **0.145** | 0.0212 | 0.0767 | 0.0400 |
| **Finlande (FIN)** | 45 | **0.106** | 0.0321 | 0.0673 | 0.0507 |
| **Suède (SWE)** | 45 | 0.077 | 0.0216 | 0.0611 | 0.0273 |
| **France (FRA)** | 45 | -0.020 | 0.0150 | 0.0599 | -0.0049 |
| **Norvège (NOR)** | 45 | -0.028 | 0.0169 | 0.0727 | -0.0064 |
| **États-Unis (USA)** | 45 | -0.053 | 0.0207 | 0.0938 | -0.0117 |
| **Pays-Bas (NLD)** | 45 | -0.092 | 0.0169 | 0.0744 | -0.0208 |
| **Espagne (ESP)** | 45 | -0.092 | 0.0269 | 0.0976 | -0.0254 |
| **Belgique (BEL)** | 45 | -0.113 | 0.0176 | 0.0763 | -0.0260 |
| **Australie (AUS)** | 44 | -0.115 | 0.0158 | 0.0523 | -0.0348 |
| **Japon (JPN)** | 45 | -0.130 | 0.0228 | 0.0812 | -0.0367 |
| **Italie (ITA)** | 45 | **-0.224** | 0.0225 | 0.0735 | -0.0685 |
| **Portugal (PRT)** | 45 | **-0.239** | 0.0318 | 0.0789 | -0.0962 |
| **Danemark (DNK)** | 45 | **-0.262** | 0.0207 | 0.0862 | -0.0629 |
| **Irlande (IRL)** | 45 | **-0.282** | 0.0436 | 0.0809 | -0.1516 |
| **Royaume-Uni (GBR)** | 45 | **-0.372** | 0.0211 | 0.0553 | -0.1419 |

### Typologie des Pays
1. **Groupe à corrélation négative marquée ($r < -0.08$)** : GBR, IRL, DNK, PRT, ITA, JPN, AUS, BEL, ESP, NLD. Ce groupe comprend les grands pays importateurs nets d'énergie (comme l'Italie et le Japon) dont l'économie subit de plein fouet les chocs de prix.
2. **Groupe à corrélation positive ($r > 0.08$)** : CHE, DEU, CAN, FIN. Ce groupe inclut le Canada, grand producteur et exportateur d'énergie (ce qui explique un effet richesse positif lors des chocs de prix), ainsi que des pays comme la Suisse (faible dépendance énergétique fossile directe dans la valeur ajoutée).
3. **Groupe neutre (corrélation faible, $|r| \le 0.08$)** : USA, NOR, FRA, SWE.

---

## 7. Résultats des Estimations de Panel Statiques

Ce tableau synthétise les résultats des régressions statiques en panel sur les variables en niveaux et en différences :

### Table 6: Résultats des estimations de panel statiques (Variable dep = PIB)

| Régresseur | Between OLS | Within (Entity FE) | Random Effects (Mundlak) | Two-Way FE | First Differences (FD) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Log IPC (`lcpi`)** | 0.835\*\*\* | 0.380\*\*\* | 0.380\*\*\* | 0.136\*\*\* | 0.513\*\*\* |
| | (0.154) | (0.038) | (0.008) | (0.044) | (0.006) |
| **Log Prix Énergie (`lenpr`)** | **-0.255** | **0.025** | **0.025** | **-0.070** | **-0.098\*\*\*** |
| | (0.295) | (0.080) | (0.025) | (0.132) | (0.021) |
| **Ouverture Trade (`open`)** | -0.233 | 0.338\*\*\* | 0.338\*\*\* | 0.159\* | 0.090\*\*\* |
| | (0.131) | (0.064) | (0.033) | (0.090) | (0.019) |
| **Dépenses Pub (`expgdp`)** | 0.528 | -0.706\*\* | -0.706\*\*\* | 0.136 | -0.492\*\*\* |
| | (0.522) | (0.306) | (0.122) | (0.348) | (0.081) |
| **Investissement (`iy`)** | -0.586 | 0.182 | 0.182 | 0.523 | 0.679\*\*\* |
| | (1.435) | (0.745) | (0.154) | (0.450) | (0.109) |
| **Moyennes Mundlak** | | | | | |
| `lcpi_mean` | — | — | 0.455\*\* (0.201) | — | — |
| `lenpr_mean` | — | — | -0.279 (0.386) | — | — |
| `open_mean` | — | — | -0.571\*\*\* (0.174) | — | — |
| `expgdp_mean` | — | — | 1.234\* (0.691) | — | — |
| `iy_mean` | — | — | -0.767 (1.875) | — | — |
| **Constante** | 7.367\*\*\* | 7.895\*\*\* | 7.366\*\*\* | 9.134\*\*\* | — |
| | (1.559) | (0.413) | (2.031) | (0.765) | |
| **N** | 18 | 18 | 18 | 18 | 18 |
| **Obs** | 18 | 810 | 810 | 810 | 809 |

*Note: Écarts-types entre parenthèses. \* p<0.10, \*\* p<0.05, \*\*\* p<0.01.*

### Interprétation et Choix du Modèle
* **Mundlak et Spécification RE** :  
  L'estimation de Mundlak (Random Effects avec ajout des moyennes temporelles de chaque pays) montre des coefficients très significatifs sur les moyennes temporelles (`lcpi_mean`, `open_mean`, `expgdp_mean`). Cela prouve que les effets individuels non observés des pays sont corrélés avec les régresseurs. La spécification Random Effects standard est donc rejetée, et l'estimateur Within (Fixed Effects) doit être préféré.
* **Effet du Prix de l'Énergie** :  
  Dans les modèles en niveaux (Between, Within, TWFE), le coefficient du prix de l'énergie n'est pas statistiquement significatif. Cependant, dans le modèle en **premières différences (FD)**, le prix de l'énergie exerce un effet négatif très fort et hautement significatif ($-0.098$, $p < 0.01$). Cela confirme que les variations de court terme (chocs de prix) affectent immédiatement la croissance du PIB, tandis que les relations de long terme en niveaux sont masquées par les tendances communes.

---

## 8. Estimations de Panel Dynamiques (Modèle ARDL)

Le modèle estimé est un modèle ARDL(1,1) en premières différences :

$$\Delta Y_{it} = \beta_y \Delta Y_{it-1} + \beta_1 \Delta X_{it} + \beta_2 \Delta X_{it-1} + \gamma \Delta W_{it} + \Delta \alpha_i + \Delta \alpha_t + \Delta \epsilon_{it}$$

Les estimations ont été réalisées sous OLS (homogène) et sous Variables Instrumentales (IV) en utilisant les niveaux retardés $Y_{it-2}$ et $X_{it-2}$ comme instruments.

### Table 7: Estimations du modèle dynamic ARDL

| Paramètre / Variable | OLS Dynamique (FD) | IV Dynamique (FD) |
| :--- | :---: | :---: |
| **$\beta_y$ (`l_dlrgdpmad`)** | **0.3120\*\*\*** (0.0390) | **1.0156\*\*\*** (0.1297) |
| **$\beta_1$ (`dlenpr`)** | **-0.0388\*\*\*** (0.0124) | **-0.0086** (0.0547) |
| **$\beta_2$ (`l_dlenpr`)** | **-0.0404\*\*\*** (0.0108) | **-0.0134** (0.0157) |
| `dlcpi2` | 0.0155 (0.0184) | -0.0849\* (0.0462) |
| `dopen` | 0.0596\*\* (0.0284) | 0.0736\*\* (0.0331) |
| `dexpgdp` | -0.1499 (0.0957) | -0.0634 (0.1496) |
| `diy` | 0.5520\*\*\* (0.0792) | 0.1452 (0.1031) |
| `l_ecterm` | -0.0157\*\*\* (0.0036) | -0.0133\*\*\* (0.0044) |
| `const` | 0.0157\*\*\* (0.0011) | 0.0027 (0.0024) |
| **Test de Hausman** | — | **53.55\*\*\*** ($p = 2.30e-8$) |

*Note: Écarts-types entre parenthèses. \* p<0.10, \*\* p<0.05, \*\*\* p<0.01.*

### Analyse du Diagnostic Dynamique
1. **Biais de l'estimation IV et Explosivité ($\beta_y > 1$)** :  
   Dans l'estimation OLS, le coefficient autorégressif est stable à $\hat{\beta}_y = 0.312$.  
   Cependant, lors de l'estimation par variables instrumentales (IV), le coefficient $\hat{\beta}_y$ monte à **`1.0156`**, ce qui dépasse l'unité. Un paramètre supérieur ou égal à 1 traduit un processus explosif (non stationnaire). Par conséquent, **la formule du coefficient de long terme $\beta_{LT} = \frac{\beta_1 + \beta_2}{1 - \beta_y}$ n'est pas définie** (car la série des coefficients de long terme diverge vers l'infini).
2. **Fonctions de Réponse Impulsionnelle (IRF)** :  
   Malgré cette divergence de long terme, nous pouvons calculer la réponse impulsionnelle transitoire pour les 4 premières périodes suite à un choc d'une unité sur le prix de l'énergie ($X$) :
   * **t = 1** : $\hat{\beta}_1 = -0.0086$
   * **t = 2** : $\hat{\beta}_y \hat{\beta}_1 + \hat{\beta}_2 = 1.0156 \cdot (-0.0086) - 0.0134 = -0.0222$
   * **t = 3** : $\hat{\beta}_y^2 \hat{\beta}_1 + \hat{\beta}_y \hat{\beta}_2 = -0.0362$
   * **t = 4** : $\hat{\beta}_y^3 \hat{\beta}_1 + \hat{\beta}_y^2 \hat{\beta}_2 = -0.0504$
3. **Test d'Endogénéité de Hausman** :  
   La statistique de Hausman vaut `53.55` avec une p-value extrêmement faible ($2.30e-8$). Cela rejette catégoriquement l'hypothèse nulle de consistance de l'OLS, confirmant que l'introduction des variables instrumentales est nécessaire pour corriger le biais d'endogénéité (bien que l'instrumentation en niveaux souffre ici d'une faiblesse caractérisée par le coefficient autoregressif explosif).

---

## 9. Résultats de l'Extension : Fixed Effects avec Interaction

Pour analyser le rôle modérateur de la structure énergétique nationale, nous avons estimé l'extension suivante en Panel OLS avec effets fixes de pays :

$$\Delta \text{log}(RGDP)_{it} = \alpha_i + \beta_1 \cdot \text{dlenpr}_{it} + \beta_2 \cdot (\text{intensity}_i \times \text{dlenpr}_{it}) + \gamma \cdot \mathbf{W}_{it} + \epsilon_{it}$$

Où :
* $X_{it}$ : `dlenpr` (taux de croissance du prix de l'énergie).
* $Z_i$ : `intensity` (Intensité énergétique initiale du pays en 1980, fixe par pays, issue de la Table 5).
* $W_{it}$ : variables de contrôle (`dlcpi`, `dopen`, `dexpgdp`, `diy`).

### Résultats de l'estimation de l'extension
* **Observations** : 809 (18 pays, 1972–2016)
* **Effets Fixes inclus** : Entity (Pays)
* **Type d'erreurs** : Clustered par pays

| Variable | Coefficient | Std. Err. | t-stat | P-value |
| :--- | :---: | :---: | :---: | :---: |
| **Intercept** | 0.0182 | 0.0012 | 14.619 | 0.0000 |
| **`dlenpr` ($\beta_1$)** | **-0.0756** | 0.0327 | -2.310 | **0.0211** |
| **`interaction` ($\beta_2$)** | **0.0076** | 0.0048 | 1.579 | **0.1148** |
| `dlcpi` | 0.0485 | 0.0283 | 1.715 | 0.0868 |
| `dopen` | 0.0563 | 0.0224 | 2.514 | 0.0121 |
| `dexpgdp` | -0.1980 | 0.1270 | -1.559 | 0.1195 |
| `diy` | 0.7719 | 0.1222 | 6.319 | 0.0000 |

### Interprétation de l'Effet Marginal
L'effet marginal de la croissance du prix de l'énergie sur la croissance économique est donné par :

$$\frac{\partial \Delta \text{log}(RGDP)_{it}}{\partial \text{dlenpr}_{it}} = \beta_1 + \beta_2 \cdot \text{intensity}_i$$

* **Effet direct ($\beta_1$)** : Le coefficient est négatif et statistiquement significatif à $-0.0756$ ($p < 0.05$), confirmant qu'un choc de prix de l'énergie ralentit significativement la croissance.
* **Effet de l'interaction ($\beta_2$)** : Le coefficient de l'interaction est positif à $0.0076$, mais **non statistiquement significatif** au seuil de 5 % ou 10 % ($p = 0.1148$).
* **Effet marginal pour un pays médian** : Pour un pays ayant une intensité énergétique médiane de $Z = 4.656$ (comme la France ou le Royaume-Uni), l'effet marginal vaut :
  $$-0.0756 + 0.0076 \cdot 4.656 = -0.0402$$
  Ainsi, une hausse de 10 % du prix de l'énergie réduit la croissance annuelle du PIB par habitant de 0.402 point de pourcentage.
* **Conclusion sur l'interaction** : Contrairement aux résultats de coupe transversale de la Table 6 de l'article original, l'estimation en effets fixes temporels ne permet pas d'établir que l'intensité énergétique de départ module de façon statistiquement significative l'effet à court terme des variations de prix énergétiques sur la croissance.

---

## 10. Checklist Méthodologique de Référence (To-Do List)

En s'appuyant sur cette réplication, voici la check-list à suivre pour toute future étude en données de panel :

1. **Vérification de la structure et cylindrage** :
   - [x] Identifier $N$ (nombre d'individus) et $T$ (nombre de périodes).
   - [x] Vérifier la présence de trous (panel non balancé) et de biais d'attrition.
2. **Décomposition des variances (Within / Between)** :
   - [x] Calculer la part de variance intra-groupe (Within) pour chaque régresseur.
   - [x] Classer les variables (temporelles, sluggish/quasi-fixes, ou invariantes).
3. **Tests de stationnarité et dépendance transversale** :
   - [x] Tester l'indépendance transversale par le test CD de Pesaran.
   - [x] Exécuter le test de racine unitaire CIPS (Pesaran 2007) si CD est présent.
4. **Validation de l'hétérogénéité des pentes** :
   - [x] Lancer le test de Pesaran-Yamagata ($\tilde{\Delta}$). Si rejeté, préférer des estimateurs Mean Group (MG, CCEMG) aux modèles homogènes.
5. **Choix OLS vs FE vs RE** :
   - [x] Réaliser le test de spécification de Mundlak (Random Effects avec ajout des moyennes temporelles) pour valider le modèle RE ou FE.
6. **Robustesse face aux outliers** :
   - [x] Appliquer les poids de Huber (Robust Mean Group) pour vérifier la sensibilité aux individus aberrants (ex: Allemagne, Irlande).
