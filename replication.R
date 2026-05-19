# Auteur : A COMPLETER
# Date   : 2026-05-18
# Reference : Huntington & Liddle (2022), "How energy prices shape OECD economic growth",
# Energy Economics, 111, 106082.

# Packages
library(readxl)
library(plm)
library(lmtest)
library(sandwich)
library(ivreg)
library(ggplot2)

# DIFFICULTE 1 : Il n'existe pas de package R officiel pour xtdcce2.
# L'estimateur CCEMG doit etre implemente manuellement :
# boucle sur les pays avec lm() augmentee des cross-section means.

# DIFFICULTE 2 : Le test CIPS de Pesaran (2007) n'est pas dans plm.
# Utiliser CADFtest (package CADFtest) ou implementer manuellement.

# DIFFICULTE 3 : Le delta test de Pesaran-Yamagata (2008) n'est pas disponible
# dans CRAN. Une implementation manuelle est necessaire.

# DIFFICULTE 4 : plm ne gere pas nativement les IV pays par pays.
# Utiliser ivreg dans une boucle sur les pays.

# DIFFICULTE 5 : La decomposition Between/Within avec panel non-balance
# se fait via plm::Between() et plm::Within() — verifier la coherence
# avec les statistiques descriptives du papier.

# -----------------------------------------------------------------------------
# 1. Chargement et preparation des donnees
# -----------------------------------------------------------------------------

data_path <- "growth_EE.xlsx"
raw <- read_excel(data_path)

raw$country <- as.character(raw$country)
raw$yr <- as.integer(raw$yr)

pdata <- pdata.frame(raw, index = c("country", "yr"), drop.index = FALSE)

# Ratios et logs
pdata$open <- (pdata$exports + pdata$imports) / pdata$gdpnom
pdata$expgdp <- pdata$expenditure / pdata$gdpnom

pdata$lrgdpmad <- log(pdata$rgdpmad)
pdata$lcpi <- log(pdata$cpi)
pdata$lenpr <- log(pdata$enpr)

# Echantillon commun
base_vars <- c("lrgdpmad", "lcpi", "lenpr", "open", "expgdp", "iy")
pdata <- pdata[complete.cases(pdata[, base_vars]), ]

# Differences premieres
pdata$dlrgdpmad <- diff(pdata$lrgdpmad)
pdata$dlcpi <- diff(pdata$lcpi)
pdata$dlenpr <- diff(pdata$lenpr)
pdata$dopen <- diff(pdata$open)
pdata$dexpgdp <- diff(pdata$expgdp)
pdata$diy <- diff(pdata$iy)

# Lags en niveaux et differences
pdata$l_lrgdpmad <- lag(pdata$lrgdpmad, 1)
pdata$l_lcpi <- lag(pdata$lcpi, 1)
pdata$l_lenpr <- lag(pdata$lenpr, 1)
pdata$l_open <- lag(pdata$open, 1)
pdata$l_expgdp <- lag(pdata$expgdp, 1)
pdata$l_iy <- lag(pdata$iy, 1)

pdata$l_dlrgdpmad <- lag(pdata$dlrgdpmad, 1)
pdata$l_dlenpr <- lag(pdata$dlenpr, 1)

pdata$l2_lrgdpmad <- lag(pdata$lrgdpmad, 2)
pdata$l2_lenpr <- lag(pdata$lenpr, 2)

# Lags des instruments globaux (si disponibles)
if ("ln_ywld" %in% names(pdata)) {
  pdata$l_ln_ywld <- lag(pdata$ln_ywld, 1)
}
if ("ln_meast" %in% names(pdata)) {
  pdata$l_ln_meast <- lag(pdata$ln_meast, 1)
}

# Regimes et inflation
pdata$mod <- as.integer(pdata$yr > 1982)
pdata$premod <- as.integer(pdata$yr < 1983)
pdata$lenprmod <- pdata$mod * pdata$lenpr
pdata$dlenprmod <- pdata$mod * pdata$dlenpr
pdata$dlenprpre <- pdata$premod * pdata$dlenpr

pdata$dlcpi2 <- ifelse(pdata$dlcpi > 0.02, pdata$dlcpi, 0)
pdata$dlcpix <- pdata$dlcpi - pdata$dlcpi2
pdata$l_dlcpi2 <- lag(pdata$dlcpi2, 1)

# ECM: regression en niveaux + residu retarde
lr_model <- lm(lrgdpmad ~ lcpi + lenpr + open + expgdp + iy, data = pdata)
pdata$ecterm <- residuals(lr_model)
pdata$l_ecterm <- lag(pdata$ecterm, 1)

# -----------------------------------------------------------------------------
# 2. Statistiques descriptives panel
# -----------------------------------------------------------------------------

# Example simple: xtsum equivalent via summary
summary(pdata$lrgdpmad)

# Observations par pays / annee
obs_country <- aggregate(lrgdpmad ~ country, data = pdata, FUN = function(x) sum(!is.na(x)))
obs_year <- aggregate(lrgdpmad ~ yr, data = pdata, FUN = function(x) sum(!is.na(x)))
write.csv(obs_country, "outputs/obs_by_country.csv", row.names = FALSE)
write.csv(obs_year, "outputs/obs_by_year.csv", row.names = FALSE)

# -----------------------------------------------------------------------------
# 3. Tests preliminaires
# -----------------------------------------------------------------------------

# CIPS: utiliser CADFtest (non inclus ici). Exemple:
# library(CADFtest)
# CADFtest(pdata$lrgdpmad, type = "trend", data = pdata)

# CD test: Pesaran CD via plm::pcdtest sur un modele FE
fe_tmp <- plm(lrgdpmad ~ lcpi + lenpr + open + expgdp + iy, data = pdata, model = "within")
cd_test <- pcdtest(fe_tmp, test = "cd")
print(cd_test)

# Delta test: implementation manuelle requise

# -----------------------------------------------------------------------------
# 4. Estimations panel (tableau recapitulatif)
# -----------------------------------------------------------------------------

between_mod <- plm(lrgdpmad ~ lcpi + lenpr + open + expgdp + iy, data = pdata, model = "between")
within_mod  <- plm(lrgdpmad ~ lcpi + lenpr + open + expgdp + iy, data = pdata, model = "within")

# Mundlak: ajouter moyennes individuelles
for (v in c("lcpi", "lenpr", "open", "expgdp", "iy")) {
  pdata[[paste0(v, "_mean")]] <- ave(pdata[[v]], pdata$country, FUN = mean)
}
re_mundlak <- plm(
  lrgdpmad ~ lcpi + lenpr + open + expgdp + iy +
    lcpi_mean + lenpr_mean + open_mean + expgdp_mean + iy_mean,
  data = pdata, model = "random"
)

twfe_mod <- plm(lrgdpmad ~ lcpi + lenpr + open + expgdp + iy, data = pdata,
                model = "within", effect = "twoways")
fd_mod <- plm(lrgdpmad ~ lcpi + lenpr + open + expgdp + iy, data = pdata, model = "fd")

# Export simple des coefficients
panel_tbl <- data.frame(
  model = c("between", "within", "re_mundlak", "twfe", "fd"),
  coef = I(list(
    coef(between_mod),
    coef(within_mod),
    coef(re_mundlak),
    coef(twfe_mod),
    coef(fd_mod)
  ))
)
write.csv(panel_tbl, "outputs/panel_models_table.csv", row.names = FALSE)

# -----------------------------------------------------------------------------
# 5. Modele dynamique ARDL + Anderson-Hsiao (IV)
# -----------------------------------------------------------------------------

dyn_ols <- lm(
  dlrgdpmad ~ l_dlrgdpmad + dlenpr + l_dlenpr + dlcpi2 + dopen + dexpgdp + diy + l_ecterm,
  data = pdata
)

# IV Anderson-Hsiao
# Instruments: L2_GDP, L2_ENERGY
iv_formula <- dlrgdpmad ~ l_dlrgdpmad + dlenpr + l_dlenpr + dlcpi2 + dopen + dexpgdp + diy + l_ecterm |
  l2_lrgdpmad + l2_lenpr + l_dlenpr + dlcpi2 + dopen + dexpgdp + diy + l_ecterm

dyn_iv <- ivreg(iv_formula, data = pdata)

# -----------------------------------------------------------------------------
# 6. CCEMG avec IV (implementation manuelle)
# -----------------------------------------------------------------------------

# Cross-section means
vars_for_means <- c(
  "dlrgdpmad",
  "dlenpr",
  "dlcpi2",
  "dopen",
  "dexpgdp",
  "diy",
  "l_lrgdpmad",
  "l_lcpi",
  "l_open",
  "l_iy",
  "mod",
  "dlenprmod"
)
for (v in vars_for_means) {
  pdata[[paste0(v, "_csmean")]] <- ave(pdata[[v]], pdata$yr, FUN = mean)
  pdata[[paste0(v, "_csmean_lag")]] <- lag(pdata[[paste0(v, "_csmean")]], 1)
}

# Boucle pays
countries <- unique(pdata$country)
cc_results <- list()

for (cty in countries) {
  g <- subset(pdata, country == cty)
  if (nrow(g) < 10) next

  # A adapter: instruments supply shocks
  # ivreg(dlrgdpmad ~ dlenpr + dlenprmod + dlcpi2 + dopen + dexpgdp + diy + l_lrgdpmad + l_lcpi + l_open + l_iy + mod + csmeans |
  #       l_dlenpr + l_lenpr + ln_ywld + ln_meast + l_ln_ywld + l_ln_meast + usshare + iranrev, data = g)
  fit <- lm(dlrgdpmad ~ dlenpr + dlenprmod + dlcpi2 + dopen + dexpgdp + diy + l_lrgdpmad + l_lcpi + l_open + l_iy + mod,
            data = g)
  cc_results[[cty]] <- coef(fit)
}

# -----------------------------------------------------------------------------
# 7. Robustesse (Table 4)
# -----------------------------------------------------------------------------
# Exemples: variations de la specification

# -----------------------------------------------------------------------------
# 8. Graphiques
# -----------------------------------------------------------------------------

# Fig 1 : evolution lenpr par pays
p1 <- ggplot(pdata, aes(x = yr, y = lenpr, color = country)) +
  geom_line(alpha = 0.6) +
  theme_minimal() +
  guides(color = "none")

ggsave("outputs/fig1_energy_prices.png", p1, width = 8, height = 4, dpi = 150)
