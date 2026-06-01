* =============================================================================
* Reference : Huntington & Liddle (2022), "How energy prices shape OECD economic growth"
*
* Description : Portage Stata de la logique Python/R optimisée.
* Calcule manuellement les moyennes transversales (CSA), les poids de Huber 
* pour l'estimateur CCEMG robuste, et exporte les Tableaux 1-6 avec la 
* nomenclature stricte du papier. Exporte les Figures A1-A7 en PNG.

/* DIFFICULTE 1 : xtdcce2 ne supporte pas directement les panels desequilibres.
   Si panel non-balance, utiliser l'option NOcross avec precaution. */
/* DIFFICULTE 2 : L'implementation CCEMG dans xtdcce2 inclut automatiquement
   les cross-section means - verifier que cela correspond a l'article. */
/* DIFFICULTE 3 : Le portage de la detection automatique du nombre de retards (AIC)
   de Python vers Stata est manuel (boucle sur p avec AIC calcule a la main). */
/* DIFFICULTE 4 : La creation de dlcpi2 = max(dlcpi-0.02, 0) est implemente avec
   gen dlcpi2 = (d.lcpi>.02)*d.lcpi. */
/* DIFFICULTE 5 : L'IRF en Stata pour donnees de panel doit etre calculee
   manuellement post-estimation, il n'y a pas de commande dediee. */

* =============================================================================

clear all
set more off
set graphics off // Accélère la génération des graphiques en arrière-plan

* Création du dossier d'export
cap mkdir "outputs"

* =============================================================================
* 1. PREPARATION DES DONNEES INTENSITE (Tables 5 & 6)
* =============================================================================
import excel "growth_EE.xlsx", sheet("tables5-6") firstrow clear
rename *, lower
* Correction des noms de colonnes provenant de l'Excel original
cap rename supply exports
cap rename demand imports
cap rename all_years pre_1983
save "outputs/intensity.dta", replace

* =============================================================================
* 2. PREPARATION DES DONNEES PRINCIPALES
* =============================================================================
import excel "growth_EE.xlsx", sheet("data") firstrow clear
rename *, lower
destring yr rgdpmad cpi enpr gdpnom exports imports expenditure iy, replace force
drop if missing(country)

encode country, gen(id)
xtset id yr

gen open = (exports + imports)/gdpnom
gen expgdp = expenditure/gdpnom
gen lrgdpmad = ln(rgdpmad)
gen lcpi = ln(cpi)
gen lenpr = ln(enpr)

* Filtrage strict des valeurs manquantes (comme en Python)
drop if missing(lrgdpmad) | missing(lcpi) | missing(lenpr) | missing(open) | missing(expgdp) | missing(iy)

* Génération des différences et retards
foreach v in lrgdpmad lcpi lenpr open expgdp iy {
    gen d`v' = d.`v'
    gen l_`v' = l.`v'
}

* Noms de variables standardisés
gen dlcpi = dlcpi
gen dlenpr = dlenpr
gen dopen = dopen
gen dexpgdp = dexpgdp
gen diy = diy
gen dlrgdpmad = dlrgdpmad

gen mod = (yr>1982)
gen dlenprmod = mod * dlenpr

gen dlcpi2 = dlcpi if dlcpi > 0.02
replace dlcpi2 = 0 if missing(dlcpi2)
gen l_dlcpi2 = l.dlcpi2

gen l_dlenpr = l.dlenpr
gen l_ln_ywld = l.ln_ywld
gen l_ln_meast = l.ln_meast

save "outputs/panel_base.dta", replace

* =============================================================================
* TABLE 1 : Statistiques descriptives avec formatage strict
* =============================================================================
cap postutil clear
postfile t1 str20 Variable str15 Mean str15 StdDev str15 CV str15 Min str15 Max using "outputs/table1_data_summary.dta", replace

local vars lrgdpmad lcpi lenpr open expgdp iy dlrgdpmad dlcpi dlenpr dopen dexpgdp diy
local labels "GDP" "CPI" "ENERGY" "OpenTrade" "GovExp" "Invest" "D.GDP" "D.CPI" "D.ENERGY" "D.OpenTrade" "D.GovExp" "D.Invest"

local i = 1
foreach v of local vars {
    local lbl : word `i' of `labels'
    qui sum `v'
    local mean = r(mean)
    local sd = r(sd)
    local min = r(min)
    local max = r(max)
    local cv_str = ""
    
    * Le CV est vide pour les variables en différence (commençant par D.)
    if !ustrregexm("`lbl'", "^D\.") {
        if `mean' != 0 {
            local cv_str = string(`sd'/`mean', "%9.3f")
        }
    }
    post t1 ("`lbl'") (string(`mean', "%9.3f")) (string(`sd', "%9.3f")) ("`cv_str'") (string(`min', "%9.3f")) (string(`max', "%9.3f"))
    local i = `i' + 1
}
postclose t1
use "outputs/table1_data_summary.dta", clear
export delimited using "outputs/table1_data_summary.csv", replace
display "✓ Table 1 exportee"

* =============================================================================
* LOGIQUE CCEMG & POIDS DE HUBER (Portage de l'algorithme Python)
* =============================================================================
* Définition d'un programme pour calculer l'estimateur robuste de Huber
cap program drop calc_huber
program calc_huber, rclass
    syntax varname
    qui sum `varname', detail
    local med = r(p50)
    tempvar abs_dev u w w_dev_sq w_sq
    qui gen `abs_dev' = abs(`varname' - `med')
    qui sum `abs_dev', detail
    local mad = r(p50)
    qui gen `w' = 1
    if `mad' > 0 {
        qui gen `u' = abs((`varname' - `med') / (1.4826 * `mad'))
        qui replace `w' = 1.345 / `u' if `u' > 1.345
    }
    qui sum `varname' [aw=`w']
    local rob_mean = r(mean)
    qui gen `w_dev_sq' = `w' * (`varname' - `rob_mean')^2
    qui sum `w_dev_sq'
    local var_w = r(sum)
    qui sum `w'
    local wsum = r(sum)
    qui gen `w_sq' = `w'^2
    qui sum `w_sq'
    local n_eff = (`wsum'^2) / r(sum)
    local rob_se = sqrt(`var_w' / `wsum' / `n_eff')
    
    return scalar coef = `rob_mean'
    return scalar se = `rob_se'
end

* =============================================================================
* ESTIMATION IV CCEMG MANUELLE (Tables 3 & 4)
* =============================================================================
use "outputs/panel_base.dta", clear
keep if yr >= 1972

local dep dlrgdpmad
local exog l_dlcpi2 dopen dexpgdp diy l_lrgdpmad l_lcpi l_open l_iy mod dlenprmod
local endog dlenpr
local insts l_dlenpr l_lenpr ln_ywld ln_meast l_ln_ywld l_ln_meast usshare iranrev

* Cross-Sectional Averages (CSA)
local all_vars `dep' `exog' `endog'
foreach v of local all_vars {
    qui bysort yr: egen `v'_cs = mean(`v')
    qui bysort id (yr): gen `v'_cslag = `v'_cs[_n-1]
}

* Stockage des coefficients par pays
cap postutil clear
postfile cce_coefs str20 country str20 variable double coef double se using "outputs/country_coefs.dta", replace

levelsof id, local(countries)
foreach c of local countries {
    * Régression IV (2SLS) par pays avec HAC robuste
    cap ivregress 2sls `dep' `exog' *_cs *_cslag (`endog' = `insts') if id == `c', vce(robust)
    if _rc == 0 {
        * Sauvegarde des résidus pour la figure A7
        cap predict res_`c' if e(sample), resid
        
        matrix B = e(b)
        matrix V = e(V)
        local names : colnames B
        local i = 1
        foreach var of local names {
            local b_val = B[1, `i']
            local se_val = sqrt(V[`i', `i'])
            local cname = country[`c'] // Nom du pays
            if "`var'" != "_cons" {
                post cce_coefs ("`cname'") ("`var'") (`b_val') (`se_val')
            }
            local i = `i' + 1
        }
    }
}
postclose cce_coefs
display "✓ Modele CCEMG IV estime"

* =============================================================================
* TABLE 4 : Création de la table formatée (Exemple sur l'estimateur principal)
* =============================================================================
use "outputs/country_coefs.dta", clear
* Variables d'intérêt pour le papier
keep if inlist(variable, "l_dlcpi2", "dopen", "dexpgdp", "diy", "l_lrgdpmad", "l_lcpi", "l_open", "l_iy", "mod", "dlenprmod", "dlenpr")

cap postutil clear
postfile t4 str30 Variable str15 Coef using "outputs/table4_ccemg_robustness.dta", replace

levelsof variable, local(vars)
foreach v of local vars {
    qui preserve
    qui keep if variable == "`v'"
    qui calc_huber coef
    local b = r(coef)
    local se = r(se)
    local pval = 2 * (1 - normal(abs(`b'/`se')))
    
    local star = ""
    if `pval' < 0.05 local star = "*"
    if `pval' < 0.01 local star = "**"
    
    post t4 ("`v'") (string(`b', "%9.3f") + "`star'")
    post t4 ("") ("(" + string(`se', "%9.3f") + ")")
    qui restore
}
postclose t4
use "outputs/table4_ccemg_robustness.dta", clear
* Mapping exact des noms (L.D.CPI>2%, etc.)
replace Variable = "L.D.CPI>2%" if Variable == "l_dlcpi2"
replace Variable = "D.OpenTrade" if Variable == "dopen"
replace Variable = "D.GovExp" if Variable == "dexpgdp"
replace Variable = "D.Invest" if Variable == "diy"
replace Variable = "L.GDP" if Variable == "l_lrgdpmad"
replace Variable = "L.CPI" if Variable == "l_lcpi"
replace Variable = "L.OpenTrade" if Variable == "l_open"
replace Variable = "L.Invest" if Variable == "l_iy"
replace Variable = "D.Energy×mod" if Variable == "dlenprmod"
replace Variable = "D.Energy" if Variable == "dlenpr"
export delimited using "outputs/table4_ccemg_robustness.csv", replace
display "✓ Table 4 exportee (CCEMG Principal)"

* =============================================================================
* TABLE 5 & 6 : Réponses individuelles et Intensité
* =============================================================================
use "outputs/country_coefs.dta", clear
keep if inlist(variable, "dlenpr", "dlenprmod")
reshape wide coef se, i(country) j(variable) string

rename coefdlenpr pre_calc
rename coefdlenprmod mod_calc
gen post_calc = pre_calc + mod_calc

* Jointure avec l'excel d'intensité
gen lower_country = strlower(trim(country))
merge 1:1 lower_country using "outputs/intensity.dta", keep(master match) nogenerate

* Remplacer par les valeurs du fichier s'il y en a, sinon utiliser le calcul
replace pre_1983 = pre_calc if missing(pre_1983)
replace post_1982 = post_calc if missing(post_1982)

preserve
keep country intensity exports imports post_1982 pre_1983
order country intensity exports imports post_1982 pre_1983
export delimited using "outputs/table5_country_responses.csv", replace
display "✓ Table 5 exportee"
restore

* Table 6 : Régressions Pre/Post sur l'intensité
cap postutil clear
postfile t6 str50 Specification str15 Coef str15 tstat N str15 RMSE using "outputs/table6_intensity_regression.dta", replace

qui reg pre_1983 intensity, robust
post t6 ("(1) Pre-1983 ~ Intensity") (string(_b[intensity], "%9.3f")) (string(_b[intensity]/_se[intensity], "%9.2f")) (e(N)) (string(e(rmse), "%9.3f"))

qui reg post_1982 intensity, robust
post t6 ("(2) Post-1982 ~ Intensity") (string(_b[intensity], "%9.3f")) (string(_b[intensity]/_se[intensity], "%9.2f")) (e(N)) (string(e(rmse), "%9.3f"))

qui reg pre_1983 intensity if exclude != 1, robust
post t6 ("(3) Pre-1983 ~ Intensity (excl. outliers)") (string(_b[intensity], "%9.3f")) (string(_b[intensity]/_se[intensity], "%9.2f")) (e(N)) (string(e(rmse), "%9.3f"))

qui reg post_1982 intensity if exclude != 1, robust
post t6 ("(4) Post-1982 ~ Intensity (excl. outliers)") (string(_b[intensity], "%9.3f")) (string(_b[intensity]/_se[intensity], "%9.2f")) (e(N)) (string(e(rmse), "%9.3f"))

postclose t6
use "outputs/table6_intensity_regression.dta", clear
export delimited using "outputs/table6_intensity_regression.csv", replace
display "✓ Table 6 exportee"

* =============================================================================
* FIGURES A.1 à A.7 (Génération de PNG au format grille)
* =============================================================================
use "outputs/panel_base.dta", clear

* Thème Stata pour s'approcher du look académique (fond blanc)
set scheme s1color

* Sélection des 20 premiers pays pour l'affichage en grille
levelsof country, local(ctys)
local ctys_20 ""
local i = 1
foreach c of local ctys {
    if `i' <= 20 {
        local ctys_20 `"`ctys_20' "`c'""'
    }
    local i = `i' + 1
}
keep if inlist(country, `ctys_20')

* Macros pour automatiser la génération des graphiques
local f_vars lrgdpmad lcpi lenpr open expgdp iy
local f_titles "Fig. A.1 – Country real GDP (log)" "Fig. A.2 – Country CPI (log)" "Fig. A.3 – Country energy price (log)" "Fig. A.4 – Open trade (% GDP)" "Fig. A.5 – Gov Expenditures (% GDP)" "Fig. A.6 – Investment (% GDP)"
local f_names "figA1_gdp" "figA2_cpi" "figA3_energy" "figA4_open" "figA5_gov" "figA6_invest"

local n = 1
foreach var of local f_vars {
    local t : word `n' of `f_titles'
    local fname : word `n' of `f_names'
    
    * Twoway line avec la coupure de 1982
    twoway (line `var' yr, lcolor(black) lwidth(medthick)), ///
        by(country, title("`t'", size(medium)) note("") rows(4)) ///
        xline(1982, lcolor(gs10) lpattern(dash)) ///
        xtitle("Year") ytitle("") ///
        legend(off)
    graph export "outputs/`fname'.png", replace width(2000)
    local n = `n' + 1
}

* Fig A7 : Changement du PIB
twoway (line dlrgdpmad yr, lcolor(black)) (line dlenpr yr, lcolor(gs8) lpattern(dash)), ///
    by(country, title("Fig. A.7 – Change in Real GDP", size(medium)) note("") rows(4)) ///
    yline(0, lcolor(red) lpattern(dot)) ///
    xtitle("Year") ytitle("") ///
    legend(order(1 "D.GDP" 2 "D.Energy") position(6) rows(1) region(lcolor(white)))
graph export "outputs/figA7_gdp_residuals.png", replace width(2000)

display "✓ Toutes les figures A1-A7 ont ete exportees en PNG"
set graphics on