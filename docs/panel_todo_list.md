# Checklist pour les Études en Données de Panel

## Guide méthodologique — Économétrie avancée (Master)

> Ce document constitue une liste de vérification exhaustive pour la conduite d'une étude empirique en données de panel. Il couvre l'ensemble des étapes, des tests préliminaires à la présentation des résultats.

---

## 1. Sélection et Structure du Panel

- [ ] Déterminer la nature du panel : **macro-panel** ($N$ petit, $T$ grand) ou **micro-panel** ($N$ grand, $T$ petit), car les propriétés asymptotiques des estimateurs en dépendent fondamentalement.
- [ ] Vérifier si le panel est **balancé** (cylindré) ou **non balancé** : identifier les observations manquantes et documenter les raisons de l'attrition.
- [ ] Calculer le ratio $N/T$ : si $N/T \to 0$ (panel long), les estimateurs hétérogènes (MG, CCEMG) sont appropriés ; si $T/N \to 0$ (panel court), privilégier les estimateurs GMM.
- [ ] Documenter la **fréquence temporelle** (annuelle, trimestrielle, mensuelle) et la **couverture géographique** (pays, régions, individus).
- [ ] Identifier les **dimensions potentielles de regroupement** (*clustering*) : pays, secteur, année.
- [ ] Vérifier la cohérence des identifiants d'unités et de périodes : pas de doublons, pas de trous non documentés.

---

## 2. Analyse Exploratoire

- [ ] Calculer les **statistiques descriptives** par variable : moyenne, écart-type, minimum, maximum, médiane, pour l'ensemble du panel et par unité.
- [ ] Réaliser la **décomposition de la variance** en composantes *between* (inter-unités), *within* (intra-unité) et totale. Comparer les magnitudes relatives.
- [ ] Produire des **graphiques exploratoires** : séries temporelles par unité, nuages de points, distributions marginales.
- [ ] Calculer la **matrice de corrélation** entre les variables explicatives pour détecter la multicolinéarité.
- [ ] Examiner les **valeurs aberrantes** par des diagrammes en boîte (*boxplots*) par unité et par période.
- [ ] Vérifier l'existence de **tendances temporelles communes** et de **ruptures structurelles** visuelles.

---

## 3. Tests de Stationnarité

- [ ] Appliquer le test **LLC** (Levin, Lin & Chu, 2002) : hypothèse nulle de racine unitaire commune. Disponible dans `plm::purtest(test = "levinlin")` (R), `xtunitroot llc` (Stata).
- [ ] Appliquer le test **IPS** (Im, Pesaran & Shin, 2003) : hypothèse nulle de racine unitaire avec hétérogénéité. Disponible dans `plm::purtest(test = "ips")` (R), `xtunitroot ips` (Stata).
- [ ] Appliquer le test **CIPS** (Pesaran, 2007) : racine unitaire robuste à la dépendance transversale. Implémentation manuelle recommandée (cf. `portage_commentary.md`).
- [ ] Appliquer le test **Hadri** (2000) : hypothèse nulle de stationnarité (test « inversé »). Disponible dans `plm::purtest(test = "hadri")` (R), `xtunitroot hadri` (Stata).
- [ ] Tester en **niveaux** et en **différences premières** : si la variable est I(1) en niveaux, vérifier qu'elle est I(0) en différences.
- [ ] Consigner le nombre de retards utilisé et la méthode de sélection (BIC, AIC, $\lfloor 4(T/100)^{1/4} \rfloor$).
- [ ] Synthétiser les résultats dans un **tableau récapitulatif** : variable, test, statistique, p-value, conclusion.

---

## 4. Tests de Dépendance Transversale

- [ ] Appliquer le test **CD de Pesaran** (2004) : valide sous $N$ et $T$ grands, robuste aux panels non balancés. Disponible dans `plm::pcdtest()` (R), `xtcd2` (Stata).
- [ ] Appliquer le test **LM de Breusch-Pagan** (1980) : valide lorsque $T > N$. Attention : biaisé lorsque $N$ est grand relativement à $T$.
- [ ] Appliquer le test **LM ajusté de Pesaran** (2004, *scaled LM*) : correction pour $N$ grand.
- [ ] Appliquer le test de **Frees** (1995) : basé sur la somme des carrés des corrélations en coupe transversale. Disponible via `xtcsd` (Stata).
- [ ] Interpréter les résultats : si la dépendance transversale est détectée, les estimateurs standards (FE, RE, MG) sont **inconsistants** → envisager CCEMG ou AMG.

---

## 5. Test d'Hétérogénéité des Pentes

- [ ] Appliquer le test **Delta** ($\tilde{\Delta}$) de Pesaran & Yamagata (2008) : hypothèse nulle d'homogénéité des pentes $\beta_i = \beta$ pour tout $i$.
- [ ] Rapporter les deux versions : $\tilde{\Delta}$ (version standard) et $\tilde{\Delta}_{adj}$ (version ajustée pour petit échantillon).
- [ ] Si l'homogénéité est rejetée, les estimateurs à **pentes hétérogènes** (MG, PMG, CCEMG) sont préférables au FE poolé.
- [ ] En cas de non-rejet, l'estimateur FE poolé ou le Pooled Mean Group (PMG) peuvent être retenus.
- [ ] Documenter le niveau de significativité retenu et discuter la puissance du test.

---

## 6. Choix du Modèle de Base

- [ ] Estimer le modèle **Pooled OLS** comme point de référence (benchmark naïf).
- [ ] Estimer le modèle à **effets fixes** (FE) : `plm(model = "within")` (R), `xtreg, fe` (Stata), `PanelOLS(entity_effects=True)` (Python/linearmodels).
- [ ] Estimer le modèle à **effets aléatoires** (RE) : `plm(model = "random")` (R), `xtreg, re` (Stata), `RandomEffects` (Python/linearmodels).
- [ ] Appliquer le **test de Hausman** (1978) pour discriminer FE et RE : `phtest()` (R), `hausman` (Stata). Si $H_0$ rejetée → FE préféré.
- [ ] Envisager l'approche de **Mundlak** (1978) : ajouter les moyennes temporelles des régresseurs dans le modèle RE. Si les coefficients des moyennes sont significatifs, cela confirme la corrélation entre effets individuels et régresseurs.
- [ ] Tester l'ajout d'**effets temporels** (*two-way fixed effects*, TWFE) : test $F$ joint de significativité des dummies temporelles.
- [ ] Vérifier la significativité des **effets fixes individuels** par un test $F$ (Pooled OLS vs FE).

---

## 7. Estimateurs Hétérogènes

- [ ] Estimer le modèle **Mean Group** (MG) de Pesaran & Smith (1995) : régression pays par pays, puis moyenne des coefficients.
- [ ] Estimer le modèle **Pooled Mean Group** (PMG) de Pesaran, Shin & Smith (1999) : coefficients de long terme homogènes, dynamique de court terme hétérogène. Disponible dans `plm::pmg()` (R), `xtpmg` (Stata).
- [ ] Estimer le modèle **CCEMG** de Pesaran (2006) : MG augmenté des moyennes en coupe transversale. Implémentation manuelle ou `xtdcce2` (Stata).
- [ ] Estimer le modèle **AMG** (*Augmented Mean Group*) de Eberhardt & Teal (2010) : MG augmenté d'une tendance commune estimée par les dummies temporelles d'un modèle FE poolé.
- [ ] Estimer le modèle **DCCE** (*Dynamic Common Correlated Effects*) de Chudik & Pesaran (2015) : CCEMG dynamique avec retards de la variable dépendante.
- [ ] Appliquer les **pondérations de Huber** (cf. section 4 du `portage_commentary.md`) pour obtenir des estimateurs MG robustes aux valeurs aberrantes.
- [ ] Comparer les coefficients MG, CCEMG et AMG dans un **tableau synthétique**.

---

## 8. Modèles Dynamiques

- [ ] Estimer un modèle **ARDL** (*Autoregressive Distributed Lag*) en panel : sélectionner l'ordre des retards par BIC/AIC.
- [ ] Appliquer l'estimateur d'**Anderson-Hsiao** (1981) : différences premières instrumentées par $y_{i,t-2}$. Consistant mais inefficient.
- [ ] Appliquer l'estimateur **Arellano-Bond** (1991) GMM en différences : `pgmm()` dans `plm` (R), `xtabond2` (Stata, Roodman 2009).
- [ ] Appliquer l'estimateur **Blundell-Bond** (1998) System GMM : combine les équations en niveaux et en différences. `pgmm()` avec `transformation = "ld"` (R), `xtabond2, system` (Stata).
- [ ] Vérifier la **prolifération des instruments** : le nombre d'instruments ne doit pas dépasser $N$. Utiliser la commande `collapse` dans `xtabond2` si nécessaire (Roodman, 2009).
- [ ] Rapporter les coefficients de court terme et de long terme séparément.

---

## 9. Tests de Spécification

- [ ] Appliquer le test de **Sargan** (1958) / **Hansen** (1982) de sur-identification : la p-value ne doit être ni trop basse (instruments invalides) ni trop élevée (instruments proliférants).
- [ ] Appliquer le test d'autocorrélation d'**Arellano-Bond** : AR(1) en différences (attendu significatif), AR(2) en différences (doit être non significatif pour valider les instruments).
- [ ] Tester la **faiblesse des instruments** : statistique $F$ du premier étage (*first-stage F-statistic*). Règle de base de Stock & Yogo (2005) : $F > 10$.
- [ ] Appliquer le test de **Kleibergen-Paap** (2006) de sous-identification (*rank test*) si les erreurs ne sont pas i.i.d.
- [ ] Vérifier la **stabilité des coefficients** en retirant des unités ou des périodes (analyse de sensibilité).

---

## 10. Endogénéité et Variables Instrumentales

- [ ] Identifier les sources potentielles d'**endogénéité** : simultanéité, erreur de mesure, variable omise.
- [ ] Distinguer les **instruments internes** (retards de la variable dépendante et des régresseurs) des **instruments externes** (variables exclues du modèle structurel).
- [ ] Rapporter la **statistique $F$ du premier étage** pour chaque variable endogène instrumentée.
- [ ] Appliquer le test de **Durbin-Wu-Hausman** pour tester formellement l'endogénéité des régresseurs suspects.
- [ ] Discuter la **pertinence économique** des instruments choisis : l'exclusion restriction doit être justifiée théoriquement, pas seulement statistiquement.
- [ ] En cas d'instruments faibles, envisager les méthodes robustes : **Anderson-Rubin** (1949), **LIML** (*Limited Information Maximum Likelihood*).

---

## 11. Cointégration en Panel

- [ ] Appliquer les tests de **Pedroni** (1999, 2004) : sept statistiques (quatre *within-dimension*, trois *between-dimension*). Disponible dans `plm::coint()` (R, partiellement), `xtcointtest` (Stata 17+).
- [ ] Appliquer le test de **Kao** (1999) : test de cointégration résiduel de type Dickey-Fuller. `plm::coint(test = "kao")` (R).
- [ ] Appliquer les tests de **Westerlund** (2005, 2007) : robustes à la dépendance transversale et à l'hétérogénéité. `xtwest` (Stata).
- [ ] Si la cointégration est confirmée, estimer les coefficients de long terme par **FMOLS** (*Fully Modified OLS*) de Pedroni (2000) ou par **DOLS** (*Dynamic OLS*) de Kao & Chiang (2001).
- [ ] Rapporter le **vecteur de cointégration** estimé et l'interpréter économiquement.
- [ ] Estimer un **modèle à correction d'erreur** (ECM) en panel pour quantifier la vitesse d'ajustement vers l'équilibre de long terme.

---

## 12. Robustesse et Diagnostics

- [ ] Identifier les **valeurs aberrantes** par les résidus studentisés, la distance de Cook, ou les statistiques DFBETAS.
- [ ] Tester la sensibilité des résultats à la **suppression d'unités** (*leave-one-out*) : recalculer les coefficients MG en excluant chaque pays tour à tour.
- [ ] Tester la sensibilité à la **période d'estimation** : sous-échantillons temporels (avant/après un choc structurel).
- [ ] Rechercher les **ruptures structurelles** avec le test de Bai & Perron (2003) appliqué pays par pays, ou le test de Ditzen, Karavias & Westerlund (2024) en panel.
- [ ] Appliquer une **validation croisée** (*cross-validation*) temporelle si l'objectif est prédictif : estimer sur $[1, T-h]$ et évaluer sur $[T-h+1, T]$.
- [ ] Vérifier la **normalité des résidus** par le test de Jarque-Bera (1987) appliqué aux résidus poolés et par unité.
- [ ] Tester l'**hétéroscédasticité** par le test de Breusch-Pagan (1979) ou le test de White (1980) modifié pour le panel.

---

## 13. Présentation des Résultats

- [ ] Formater les tableaux selon les conventions académiques : une colonne par spécification, une ligne par variable.
- [ ] Rapporter les **coefficients** avec 3 à 4 décimales significatives et les **écarts-types** entre parenthèses.
- [ ] Utiliser un système d'**étoiles de significativité** cohérent et le documenter en note de bas de tableau :
  - `***` : $p < 0{,}01$
  - `**` : $p < 0{,}05$
  - `*` : $p < 0{,}10$
- [ ] Inclure les **statistiques de diagnostic** en bas de tableau : $N$, $T$, $R^2$, RMSE, statistique $F$, tests de spécification.
- [ ] Ajouter des **notes explicatives** sous chaque tableau : description des variables, source des données, méthode d'estimation.
- [ ] Produire les figures en **haute résolution** (300 DPI minimum) avec des légendes claires et des axes correctement libellés.
- [ ] Numéroter les tableaux et figures de manière cohérente et y faire référence dans le texte.
- [ ] Fournir les **fichiers de données et de code** en annexe ou via un dépôt (GitHub, Zenodo) pour assurer la reproductibilité.

---

## Références Bibliographiques

| Auteurs | Année | Titre / Sujet |
|---------|-------|---------------|
| Arellano, M. & Bond, S. | 1991 | GMM en différences premières |
| Bai, J. & Perron, P. | 2003 | Ruptures structurelles multiples |
| Blundell, R. & Bond, S. | 1998 | System GMM |
| Chudik, A. & Pesaran, M. H. | 2015 | DCCE dynamique |
| Ditzen, J. | 2018 | `xtdcce2` — Stata |
| Eberhardt, M. & Teal, F. | 2010 | AMG estimator |
| Hadri, K. | 2000 | Test de stationnarité en panel |
| Hansen, L. P. | 1982 | GMM et test de sur-identification |
| Hausman, J. | 1978 | Test de spécification FE vs RE |
| Im, K. S., Pesaran, M. H. & Shin, Y. | 2003 | Test IPS |
| Kao, C. | 1999 | Test de cointégration en panel |
| Levin, A., Lin, C. F. & Chu, C. S. J. | 2002 | Test LLC |
| Mundlak, Y. | 1978 | Approche correlated random effects |
| Pedroni, P. | 1999, 2004 | Tests de cointégration en panel |
| Pesaran, M. H. | 2004 | Test CD de dépendance transversale |
| Pesaran, M. H. | 2006 | CCEMG estimator |
| Pesaran, M. H. | 2007 | Test CIPS |
| Pesaran, M. H. & Smith, R. | 1995 | Mean Group estimator |
| Pesaran, M. H., Shin, Y. & Smith, R. | 1999 | PMG estimator |
| Pesaran, M. H. & Yamagata, T. | 2008 | Test Delta d'homogénéité |
| Roodman, D. | 2009 | `xtabond2` — Stata |
| Stock, J. H. & Yogo, M. | 2005 | Instruments faibles |
| Westerlund, J. | 2005, 2007 | Tests de cointégration robustes |
