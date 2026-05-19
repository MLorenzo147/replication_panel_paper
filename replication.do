* Auteur : A COMPLETER
* Date   : 2026-05-18
* Reference : Huntington & Liddle (2022), "How energy prices shape OECD economic growth",
* Energy Economics, 111, 106082.

clear all
set more off

// Impact of energy prices on OECD growth with macro controls
// Uses World Development energy prices (leapfrogging)

* -----------------------------------------------------------------------------
* LOAD DATA
* -----------------------------------------------------------------------------
import excel "growth_EE.xlsx", firstrow clear

encode country, gen(id)
xtset id yr

gen open = (exports + imports)/gdpnom
gen expgdp = expenditure/gdpnom
gen recess = (yr==2009)

gen ireland = (id==11) & (yr==2015)
gen germany = (id==5) & (yr==1990)
gen abridged = 1 - germany - ireland

// for balanced data use option "if yr>1971"
quietly tab yr, gen(year)
drop year1 year2 year57

foreach logs in cpi rgdpmad enpr {
    gen l`logs' = ln(`logs')
}

quietly reg lrgdpmad lcpi lenpr open expgdp iy
keep if e(sample) == 1

foreach series in lrgdpmad lcpi lenpr open expgdp iy {
    gen d`series' = d.`series'
    gen ld`series' = l.d.`series'
    gen l`series' = l.`series'
}

gen mod = (yr>1982)
gen lenprmod = mod*lenpr
gen dlenprmod = mod*d.lenpr

gen premod = (yr<1983)
gen dlenprpre = premod*d.lenpr

// define inflation as exceeding 2% per annum
// dlcpi2 is the part above 2%, dlcpix the remainder

gen dlcpi2 = (d.lcpi>.02)*d.lcpi
gen dlcpix = d.lcpi - dlcpi2

// compute cross-country averages
local z "lrgdpmad lcpi lenpr open expgdp iy"
foreach k of local z {
    sort yr
    by yr: egen `k'T = mean(`k') if e(sample)
}

xtset id yr

// labels
label variable lrgdpmad "GDP"
label variable lcpi "CPI"
label variable lenpr "Energy"
label variable open "OpenTrade"
label variable expgdp "GovExp"
label variable iy "Invest"
label variable yr "Year"

xtsum lrgdpmad lcpi lenpr lenprmod open expgdp iy
xtsum d.(lrgdpmad lcpi lenpr lenprmod open expgdp iy)
xtsum lenpr enpr if yr>1982

* -----------------------------------------------------------------------------
* Table 1. Data Summary
* -----------------------------------------------------------------------------

tabstat lrgdpmad lcpi lenpr open expgdp iy, format(%9.2f) statistics(mean sd cv max min) noseparator columns(statistics)
tabstat dlrgdpmad dlcpi dlenpr dopen dexpgdp diy, statistics(mean sd cv max min) noseparator columns(statistics)

* -----------------------------------------------------------------------------
* Table 2. Pesaran (2007) Panel Unit Root Tests, All Years
* -----------------------------------------------------------------------------

multipurt lrgdpmad lcpi lenpr open expgdp iy, lags(3)
multipurt dlrgdpmad dlcpi dlenpr dopen dexpgdp diy, lags(3)

* -----------------------------------------------------------------------------
* Bounds test on each unit
* -----------------------------------------------------------------------------

list id country if yr==2016 & id==1, noobs
qui ardl lrgdpmad lcpi lenpr lenprmod open expgdp iy if id==1, ec1 aic maxlags(2) regstore(ecreg)
estat ectest
estimates restore ecreg
estat bgodfrey
estat durbinalt

forvalues i=2/18 {
    list id country if yr==2016 & id==`i', noobs
    qui ardl lrgdpmad lcpi lenpr lenprmod open expgdp iy if id==`i', ec1 aic maxlags(3) regstore(ecreg)
    estat ectest
    estimates restore ecreg
    estat bgodfrey
    estat durbinalt
}

// slope homogeneity
// option hac uses Bartlett kernel to adjust for autocorrelation in the residual
// (1) all coefficients are homogenous
// (2) all first-difference coefficients are homogenous
// (3) all lagged coefficients are homogenous
xthst d.(lrgdpmad lcpi lenpr open expgdp iy) l.lrgdpmad l.lcpi l.lenpr l.open l.expgdp l.iy, hac
xthst d.(lrgdpmad lcpi lenpr open expgdp iy) l.lrgdpmad l.lcpi l.lenpr l.open l.expgdp l.iy, hac partial(l.lrgdpmad l.lcpi l.lenpr l.open l.expgdp l.iy)
xthst d.(lrgdpmad lcpi lenpr open expgdp iy) l.lrgdpmad l.lcpi l.lenpr l.open l.expgdp l.iy, hac partial(d.(lrgdpmad lcpi lenpr open expgdp iy))

// computing outlier-robust (instead of unweighted) means
xtmg dlrgdpmad dlcpi dlenpr dopen dexpgdp diy llrgdpmad llcpi llenpr lopen lexpgdp liy lrgdpmadT lcpiT lenprT openT expgdpT iyT
// drop insignificant llenpr lexpgdp
xtmg dlrgdpmad dlcpi dlenpr dopen dexpgdp diy llrgdpmad llcpi lopen liy lrgdpmadT lcpiT lenprT openT expgdpT iyT, res(elrgdpmad)
est store cce
xtmg dlrgdpmad dlcpi dlenpr dopen dexpgdp diy llrgdpmad llcpi lopen liy lrgdpmadT lcpiT lenprT openT expgdpT iyT, robust
est store ccerobust
xtdcce2 dlrgdpmad dlcpi dlenpr dopen dexpgdp diy llrgdpmad llcpi lopen liy, cross(lrgdpmad lcpi lenpr open expgdp iy) reportc
est store dccecce

// Table 3. Coefficients in Unweighted and Outlier-Robust Means Methods
est tab cce ccerobust dccecce, b(%9.3f) star
hausman cce ccerobust, sigmamore force

// decompose cpi and energy prices
xtdcce2 d.lrgdpmad l.dlcpi2 l.dlcpix d.open d.expgdp d.iy l.lrgdpmad l.lcpi l.open l.iy mod dlenprmod (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if yr>1971, cross(lrgdpmad lcpi lenpr open expgdp iy) reportc exponent
// select cpi over 2%
xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy l.lrgdpmad l.lcpi l.open l.iy mod dlenprmod (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if yr>1971, cross(lrgdpmad lcpi lenpr open expgdp iy) reportc exponent
xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy l.lrgdpmad l.lcpi l.open l.iy mod dlenprmod (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if yr>1971, cross(lrgdpmad lcpi lenpr open expgdp iy) reportc exponent showi
predict res, residuals
est store inst
pescadf res, lags(0)
label variable res "Residuals"
xtsum res d.lrgdpmad if d.lrgdpmad <0.2 & yr>1971

// country charts displaying variable and residuals
// Figure A-7. Actual Change in Real GDP and Residuals by Country
xtline d.lrgdpmad res if d.lrgdpmad <0.2 & yr>1971, scheme(s2mono)
drop res

// F-statistic when excluding instrumental variables from first-round estimates
xtdcce2 d.lenpr l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev l.dlcpi2 d.open d.expgdp d.iy l.lrgdpmad l.lcpi l.open l.iy mod dlenprmod if yr>1971, cross(lrgdpmad lcpi lenpr open expgdp iy) reportc exponent

test l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev

xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy l.lrgdpmad l.lcpi l.open l.iy mod dlenprmod d.lenpr if yr>1971, cross(lrgdpmad lcpi lenpr open expgdp iy) reportc exponent
predict res, residuals
est store exog
pescadf res, lags(0)
drop res

xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy l.lrgdpmad l.lcpi l.open l.iy (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if yr>1971, cross(lrgdpmad lcpi lenpr open expgdp iy) reportc exponent showi
predict res, residuals
est store w_o_mod
pescadf res, lags(0)
drop res

xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy l.lrgdpmad l.lcpi l.open l.iy mod dlenprmod recess (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if yr>1971, cross(lrgdpmad lcpi lenpr open expgdp iy) reportc exponent
predict res, residuals
est store recession
pescadf res, lags(0)
drop res

xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy l.lrgdpmad l.lcpi l.open l.iy mod dlenprmod (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if abridged==1 & yr>1971, cross(lrgdpmad lcpi lenpr open expgdp iy) reportc exponent
predict res, residuals
est store ger_ire
pescadf res, lags(0)
drop res

xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy l.lrgdpmad l.lcpi l.open l.iy mod dlenprmod (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev), cross(lrgdpmad lcpi lenpr open expgdp iy) reportc exponent
predict res, residuals
est store sixties
pescadf res, lags(0)
drop res

// template for panel results
// Table 4. CCE-Mean-Group Estimates for Real GDP Growth
label variable dlcpi2 "D.CPI"
label variable dlenprmod "D.Energy83"

estout inst exog w_o_mod recession ger_ire sixties, cells(b(star fmt(3)) se(par fmt(3))) starlevels(* 0.05 ** 0.01) legend label stats(N rmse ztbar cd alpha, fmt(0 3 3 2 3) star(ztbar cd) label(Observations RMSE CIPS CD Exponent)) varwidth(12) modelwidth(9)

// plot variables over time by panel
// Figure A-1 through Figure A-6
xtline open
xtline iy
xtline lcpi
xtline lrgdpmad
xtline lenpr
xtline expgdp

// ADD THIS CODE TO ABOVE CODE TO
// compute error-correction term for Table 4

// no CSA
xtdcce2 lrgdpmad lenpr lcpi open expgdp iy if yr>1971, nocross reportc
predict ecterm, residuals
xtdcce2 d.lrgdpmad d.lenpr l.dlcpi2 d.open d.expgdp d.iy l.ecterm if yr>1971, nocross reportc
xtdcce2 d.lrgdpmad d.lenpr l.dlcpi2 d.open d.expgdp d.iy if yr>1971, lr(lrgdpmad lenpr lcpi open expgdp iy) nocross reportc

// with CSA
xtdcce2 lrgdpmad lenpr lcpi open expgdp iy if yr>1971, cr(_all) reportc
predict ectermcf, cfresiduals

xtdcce2 d.lrgdpmad d.lenpr l.dlcpi2 d.open d.expgdp d.iy dlenprmod l.ectermcf if yr>1971, cross(_all) reportc
xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy dlenprmod l.ectermcf (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if yr>1971, cross(_all) reportc
xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy l.ectermcf (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if yr>1971, cross(_all) reportc

xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy dlenprmod recess l.ectermcf (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if yr>1971, cr(iy ln_ywld ln_meast usshare iranrev open expgdp lrgdpmad lenpr dlcpi2 ectermcf) reportc

xtdcce2 lrgdpmad lenpr lcpi open expgdp iy if abridged==1 & yr>1971, cross(_all) reportc
predict ectermcf2, cfresiduals
xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy dlenprmod l.ectermcf2 (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev) if abridged==1 & yr>1971, cross(_all) reportc

xtdcce2 lrgdpmad lenpr lcpi open expgdp iy, cr(_all) reportc
predict ectermcf3, cfresiduals
xtdcce2 d.lrgdpmad l.dlcpi2 d.open d.expgdp d.iy dlenprmod l.ectermcf3 (d.lenpr=l.d.lenpr l.lenpr ln_ywld ln_meast l.ln_ywld l.ln_meast usshare iranrev), cross(_all) reportc

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

* === TABLE 5-6 ALIGNED START ===
* -----------------------------------------------------------------------------
* Table 5-6 (aligned with replication_final)
* -----------------------------------------------------------------------------
preserve
import excel "growth_EE.xlsx", sheet("tables5-6") firstrow clear
rename Country country

destring Intensity Supply Demand Post_1982 All_years, replace force
keep if !missing(Intensity)

gen Exports = Supply
gen Imports = Demand
gen Pre_1983 = All_years

order country Intensity Exports Imports Post_1982 Pre_1983
export delimited using "outputs/table5_country_responses.csv", replace

* Table 6 regressions
*  (1) Pre-1983 ~ Intensity
*  (2) Post-1982 ~ Intensity
*  (3) Pre-1983 excl outliers
*  (4) Post-1982 excl outliers

tempfile t6
postfile handle str60 Specification double Coef tstat N F RMSE using `t6', replace

regress Pre_1983 Intensity, vce(robust)
post handle ("(1) Pre-1983 ~ Intensity") (_b[Intensity]) (_b[Intensity]/_se[Intensity]) (e(N)) (e(F)) (e(rmse))

regress Post_1982 Intensity, vce(robust)
post handle ("(2) Post-1982 ~ Intensity") (_b[Intensity]) (_b[Intensity]/_se[Intensity]) (e(N)) (e(F)) (e(rmse))

capture confirm variable exclude
if _rc {
    preserve
    regress Pre_1983 Intensity, vce(robust)
    predict r_pre, resid
    gen abs_r_pre = abs(r_pre)
    gsort -abs_r_pre
    drop in 1/2
    regress Pre_1983 Intensity, vce(robust)
    post handle ("(3) Pre-1983 (excl. outliers)") (_b[Intensity]) (_b[Intensity]/_se[Intensity]) (e(N)) (e(F)) (e(rmse))
    restore

    preserve
    regress Post_1982 Intensity, vce(robust)
    predict r_post, resid
    gen abs_r_post = abs(r_post)
    gsort -abs_r_post
    drop in 1/2
    regress Post_1982 Intensity, vce(robust)
    post handle ("(4) Post-1982 (excl. outliers)") (_b[Intensity]) (_b[Intensity]/_se[Intensity]) (e(N)) (e(F)) (e(rmse))
    restore
}
else {
    preserve
    keep if !exclude
    regress Pre_1983 Intensity, vce(robust)
    post handle ("(3) Pre-1983 (excl. outliers)") (_b[Intensity]) (_b[Intensity]/_se[Intensity]) (e(N)) (e(F)) (e(rmse))
    restore

    preserve
    keep if !exclude
    regress Post_1982 Intensity, vce(robust)
    post handle ("(4) Post-1982 (excl. outliers)") (_b[Intensity]) (_b[Intensity]/_se[Intensity]) (e(N)) (e(F)) (e(rmse))
    restore
}

postclose handle
use `t6', clear
export delimited using "outputs/table6_intensity_regression.csv", replace
restore
* === TABLE 5-6 ALIGNED END ===


* -----------------------------------------------------------------------------
* Table 5-6 from tables5-6 sheet (EIA intensity + exports/imports)
* -----------------------------------------------------------------------------
preserve
import excel "growth_EE.xlsx", sheet("tables5-6") firstrow clear
capture rename Country country
capture rename Intensity intensity
capture rename Supply exports
capture rename Demand imports
capture rename Post_1982 post_1982
capture rename All_years pre_1983
keep country intensity exports imports post_1982 pre_1983
keep if !missing(country)
keep if !missing(intensity) | country=="Average"
export delimited using "outputs/table5_country_responses.csv", replace
restore

preserve
import excel "growth_EE.xlsx", sheet("tables5-6") firstrow clear
capture rename Country country
capture rename Intensity intensity
capture rename Post_1982 post_1982
capture rename All_years pre_1983
keep country intensity post_1982 pre_1983
keep if !missing(intensity) & country!="Average"

tempname h
postfile `h' str50 Specification double Coef tstat N using "outputs/table6_intensity_regression.csv", replace

reg pre_1983 intensity, robust
post `h' ("(1) Pre-1983 ~ Intensity") (_b[intensity]) (_b[intensity]/_se[intensity]) (e(N))

reg post_1982 intensity, robust
post `h' ("(2) Post-1982 ~ Intensity") (_b[intensity]) (_b[intensity]/_se[intensity]) (e(N))

reg pre_1983 intensity, robust
predict resid_pre if e(sample), resid
keep if e(sample)
gen absres = abs(resid_pre)
gsort -absres
gen outlier = _n<=2
reg pre_1983 intensity if !outlier, robust
post `h' ("(3) Pre-1983 (excl. outliers)") (_b[intensity]) (_b[intensity]/_se[intensity]) (e(N))

drop resid_pre absres outlier
reg post_1982 intensity, robust
predict resid_post if e(sample), resid
keep if e(sample)
gen absres = abs(resid_post)
gsort -absres
gen outlier = _n<=2
reg post_1982 intensity if !outlier, robust
post `h' ("(4) Post-1982 (excl. outliers)") (_b[intensity]) (_b[intensity]/_se[intensity]) (e(N))

postclose `h'
restore
