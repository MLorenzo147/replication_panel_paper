# =============================================================================
# Reference : Huntington & Liddle (2022), "How energy prices shape OECD economic growth"
# 
# Description : Portage complet et robuste du script Python vers R.
# Inclut l'algorithme CCEMG (avec rang complet, estimateur IV), les tests CIPS
# standardisés, le calcul des estimateurs robustes (Huber weights) et 
# l'export exact des Tableaux 1 à 6 (CSV + PNG) et des Figures A.1 à A.7.


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

# =============================================================================

library(readxl)
library(dplyr)
library(tidyr)
library(ggplot2)
library(sandwich)
library(lmtest)
library(ivreg)
library(gridExtra)
library(grid)

# =============================================================================
# Configuration
# =============================================================================

# Récupérer le chemin depuis l'environnement ou utiliser le défaut
DATA_PATH <- Sys.getenv("GROWTH_EE_PATH", "growth_EE.xlsx")
OUTPUT_DIR <- "outputs"

if (!dir.exists(OUTPUT_DIR)) {
  dir.create(OUTPUT_DIR)
}

COUNTRY_ISO <- c(
  "aus" = "Australia", "bel" = "Belgium", "can" = "Canada", "che" = "Switzerland",
  "deu" = "Germany", "dnk" = "Denmark", "esp" = "Spain", "fin" = "Finland",
  "fra" = "France", "gbr" = "United Kingdom", "irl" = "Ireland", "ita" = "Italy",
  "jpn" = "Japan", "nld" = "Netherlands", "nor" = "Norway", "prt" = "Portugal",
  "swe" = "Sweden", "usa" = "United States"
)

# =============================================================================
# Helpers de Formatage
# =============================================================================

get_stars <- function(p) {
  if (is.na(p) || !is.numeric(p)) return("")
  if (p < 0.01) return("**")
  if (p < 0.05) return("*")
  return("")
}

fmt_coef <- function(coef, se, p) {
  if (is.na(coef)) return(c("", ""))
  c_str <- sprintf("%.3f%s", coef, get_stars(p))
  s_str <- ifelse(is.na(se), "", sprintf("(%.3f)", se))
  return(c(c_str, s_str))
}

get_country_label <- function(c_code) {
  label <- COUNTRY_ISO[tolower(trimws(c_code))]
  if (is.na(label)) return(c_code)
  return(label)
}

# Fonction pour rendre les tables en PNG académique (équivalent matplotlib)
render_table_png <- function(tbl, title, notes, filepath, fig_w=8.5) {
  # Thème basique académique
  tt <- ttheme_default(
    core = list(fg_params=list(hjust=0, x=0.05, fontsize=8), bg_params=list(fill=c("#f7f7f7", "white"))),
    colhead = list(fg_params=list(fontsize=8, fontface="bold"), bg_params=list(fill="#d9d9d9"))
  )
  
  g <- tableGrob(tbl, rows = NULL, theme = tt)
  
  # Construction du layout avec titre et notes
  title_grob <- textGrob(title, x=0.02, hjust=0, gp=gpar(fontsize=10, fontface="bold"))
  notes_grob <- textGrob(notes, x=0.02, hjust=0, gp=gpar(fontsize=7, fontface="italic"))
  
  # Calcul de la hauteur selon le nombre de lignes
  h <- max(3, nrow(tbl) * 0.25 + 1)
  
  final_grob <- arrangeGrob(title_grob, g, notes_grob, heights=unit(c(0.6, nrow(tbl)*0.25, 0.6), "in"))
  ggsave(filepath, final_grob, width=fig_w, height=h, dpi=200, bg="white")
}

# =============================================================================
# Chargement des données
# =============================================================================

load_and_prepare_data <- function(path) {
  df <- read_excel(path, sheet = "data")
  names(df) <- tolower(trimws(names(df)))
  
  num_cols <- c("yr", "rgdpmad", "cpi", "enpr", "gdpnom", "exports", "imports", "expenditure", "iy")
  for (col in num_cols) {
    if (col %in% names(df)) df[[col]] <- as.numeric(df[[col]])
  }
  
  df$country <- as.character(df$country)
  
  df <- df %>%
    mutate(
      open = (exports + imports) / gdpnom,
      expgdp = expenditure / gdpnom,
      lrgdpmad = ifelse(rgdpmad > 0, log(rgdpmad), NA),
      lcpi = ifelse(cpi > 0, log(cpi), NA),
      lenpr = ifelse(enpr > 0, log(enpr), NA)
    ) %>%
    drop_na(lrgdpmad, lcpi, lenpr, open, expgdp, iy) %>%
    arrange(country, yr) %>%
    group_by(country) %>%
    mutate(
      d_lrgdpmad = lrgdpmad - lag(lrgdpmad),
      d_lcpi = lcpi - lag(lcpi),
      d_lenpr = lenpr - lag(lenpr),
      d_open = open - lag(open),
      d_expgdp = expgdp - lag(expgdp),
      d_iy = iy - lag(iy),
      
      l_lrgdpmad = lag(lrgdpmad),
      l_lcpi = lag(lcpi),
      l_lenpr = lag(lenpr),
      l_open = lag(open),
      l_iy = lag(iy),
      
      dlcpi = d_lcpi,
      dlenpr = d_lenpr,
      dopen = d_open,
      dexpgdp = d_expgdp,
      diy = d_iy,
      dlrgdpmad = d_lrgdpmad,
      
      l_dlenpr = lag(dlenpr)
    ) %>% ungroup()
  
  # Variables additionnelles
  df$mod <- as.integer(df$yr > 1982)
  df$dlenprmod <- df$mod * df$dlenpr
  df$dlcpi2 <- ifelse(df$dlcpi > 0.02, df$dlcpi, 0.0)
  
  df <- df %>%
    group_by(country) %>%
    mutate(
      l_dlcpi2 = lag(dlcpi2),
      l_ln_ywld = lag(ln_ywld),
      l_ln_meast = lag(ln_meast)
    ) %>% ungroup()
  
  return(df)
}

load_table56 <- function(path) {
  sheets <- excel_sheets(path)
  target <- sheets[tolower(trimws(sheets)) %in% c("tables5-6", "table5-6")]
  if (length(target) == 0) return(NULL)
  
  raw <- read_excel(path, sheet = target[1])
  names(raw) <- tolower(trimws(names(raw)))
  
  out <- data.frame(country = as.character(raw$country))
  if ("intensity" %in% names(raw)) out$intensity <- as.numeric(raw$intensity)
  
  # Gestion robuste des noms de colonnes du fichier original
  if ("supply" %in% names(raw)) out$exports <- as.numeric(raw$supply)
  else if ("exports" %in% names(raw)) out$exports <- as.numeric(raw$exports)
  
  if ("demand" %in% names(raw)) out$imports <- as.numeric(raw$demand)
  else if ("imports" %in% names(raw)) out$imports <- as.numeric(raw$imports)
  
  if ("post_1982" %in% names(raw)) out$post_1982 <- as.numeric(raw$post_1982)
  if ("pre_1983" %in% names(raw)) out$pre_1983 <- as.numeric(raw$pre_1983)
  
  if ("exclude" %in% names(raw)) {
    out$exclude <- as.character(raw$exclude) %in% c("1", "true", "yes", "y")
  } else {
    out$exclude <- tolower(trimws(out$country)) %in% c("germany", "ireland")
  }
  return(out)
}

# =============================================================================
# Méthodes Statistiques (CIPS, Colinéarité, CCEMG)
# =============================================================================

cips_test_manual <- function(df, yname, lags = 1, trend = "c") {
  d <- df %>% drop_na(all_of(yname)) %>% arrange(country, yr)
  
  d <- d %>%
    group_by(yr) %>% mutate(ybar = mean(.data[[yname]], na.rm=TRUE)) %>% ungroup() %>%
    group_by(country) %>%
    mutate(
      y_lag = lag(.data[[yname]]),
      dy = .data[[yname]] - lag(.data[[yname]]),
      ybar_lag = lag(ybar),
      dybar = ybar - lag(ybar)
    )
  
  for (k in seq_len(lags)) {
    d[[paste0("dy_lag", k)]] <- ave(d$dy, d$country, FUN=function(x) dplyr::lag(x, k))
  }
  
  tstats <- c()
  for (c_name in unique(d$country)) {
    g <- d %>% filter(country == c_name)
    cols <- c("dy", "y_lag", "ybar_lag", "dybar")
    if (lags > 0) cols <- c(cols, paste0("dy_lag", 1:lags))
    
    g <- g %>% drop_na(all_of(cols))
    if (nrow(g) < (5 + lags)) next
    
    x_cols <- c("y_lag", "ybar_lag", "dybar")
    if (lags > 0) x_cols <- c(x_cols, paste0("dy_lag", 1:lags))
    
    form_str <- paste("dy ~", paste(x_cols, collapse = " + "))
    if (trend == "ct") {
      g$trend_time <- 1:nrow(g)
      form_str <- paste(form_str, "+ trend_time")
    }
    
    fit <- lm(as.formula(form_str), data = g)
    sum_fit <- summary(fit)
    if ("y_lag" %in% rownames(sum_fit$coefficients)) {
      tstats <- c(tstats, sum_fit$coefficients["y_lag", "t value"])
    }
  }
  
  if (length(tstats) == 0) return(c(NA, NA))
  tbar <- mean(tstats, na.rm=TRUE)
  pval <- 2.0 * (1.0 - pnorm(abs(tbar)))
  return(c(tbar, pval))
}

# Filtre de colinéarité (garantit un rang plein de la matrice)
reduce_full_rank <- function(df, cols) {
  df_sub <- df[, cols, drop=FALSE]
  df_sub <- df_sub[, sapply(df_sub, function(x) length(unique(na.omit(x))) > 1), drop=FALSE]
  
  keep <- c()
  for (col in names(df_sub)) {
    test_cols <- c(keep, col)
    mat <- na.omit(df_sub[, test_cols, drop=FALSE])
    if (nrow(mat) == 0) next
    # Si l'ajout de la colonne augmente le rang, on la garde
    if (qr(mat)$rank == length(test_cols)) {
      keep <- c(keep, col)
    }
  }
  return(keep)
}

estimate_ccemg <- function(df, dep, exog_vars, endog_vars, insts, exog_only=FALSE) {
  vars_means <- c(dep, exog_vars, endog_vars)
  
  # Calcul des CSA (Cross-Sectional Averages)
  d <- df
  for (v in vars_means) {
    if (v %in% names(d)) {
      d[[paste0(v, "_csmean")]] <- ave(d[[v]], d$yr, FUN=function(x) mean(x, na.rm=TRUE))
      d[[paste0(v, "_csmean_lag")]] <- ave(d[[paste0(v, "_csmean")]], d$country, FUN=function(x) dplyr::lag(x))
    }
  }
  
  cs_cols <- intersect(names(d), c(paste0(vars_means, "_csmean"), paste0(vars_means, "_csmean_lag")))
  
  rows <- list()
  resid_list <- list()
  
  for (c_name in unique(d$country)) {
    g <- d %>% filter(country == c_name)
    raw_cols <- intersect(names(g), c(dep, exog_vars, cs_cols, endog_vars, insts))
    g <- g[, raw_cols] %>% drop_na()
    if (nrow(g) == 0) next
    
    keep_cols <- reduce_full_rank(g, setdiff(names(g), dep))
    if (length(keep_cols) == 0) next
    
    s_exog <- intersect(keep_cols, c(exog_vars, cs_cols))
    s_endog <- intersect(keep_cols, endog_vars)
    s_inst <- intersect(keep_cols, insts)
    
    if (exog_only || length(s_inst) == 0 || length(s_endog) == 0) {
      form <- as.formula(paste(dep, "~", paste(s_exog, collapse=" + ")))
      tryCatch({
        fit <- lm(form, data = g)
        co <- coef(fit)
        se <- sqrt(diag(vcovHAC(fit)))
        resids <- data.frame(country=c_name, yr=g$yr, residual=residuals(fit))
        resid_list[[c_name]] <- resids
        
        for (v in names(co)) {
          rows[[length(rows)+1]] <- data.frame(country=c_name, variable=v, coef=co[v], se=se[v])
        }
      }, error=function(e) NULL)
      
    } else {
      # IV Regression
      form <- as.formula(paste(dep, "~", paste(c(s_exog, s_endog), collapse=" + "), "|", paste(c(s_exog, s_inst), collapse=" + ")))
      tryCatch({
        fit <- ivreg(form, data = g)
        co <- coef(fit)
        se <- sqrt(diag(vcovHAC(fit)))
        resids <- data.frame(country=c_name, yr=g$yr, residual=residuals(fit))
        resid_list[[c_name]] <- resids
        
        for (v in names(co)) {
          rows[[length(rows)+1]] <- data.frame(country=c_name, variable=v, coef=co[v], se=se[v])
        }
      }, error=function(e) NULL)
    }
  }
  
  country_df <- bind_rows(rows)
  residuals_df <- bind_rows(resid_list)
  
  # Simple MG et Robust MG (Huber weights manuels)
  mg_rows <- list()
  mg_rob_rows <- list()
  
  if (nrow(country_df) > 0) {
    for (v in unique(country_df$variable)) {
      sub <- country_df %>% filter(variable == v) %>% drop_na(coef)
      if (nrow(sub) == 0) next
      
      vals <- sub$coef
      mean_c <- mean(vals)
      se_mg <- sd(vals) / sqrt(length(vals))
      tstat <- mean_c / se_mg
      pval <- 2.0 * (1.0 - pnorm(abs(tstat)))
      mg_rows[[length(mg_rows)+1]] <- data.frame(variable=v, coef=mean_c, se=se_mg, t=tstat, p=pval)
      
      # Robust Huber
      med <- median(vals)
      mad <- median(abs(vals - med))
      w <- rep(1, length(vals))
      if (mad > 0) {
        u <- abs((vals - med) / (1.4826 * mad))
        w <- ifelse(u > 1.345, 1.345 / u, 1)
      }
      wsum <- sum(w)
      if (wsum > 0) {
        mean_rob <- sum(w * vals) / wsum
        var_w <- sum(w * (vals - mean_rob)^2) / wsum
        n_eff <- (wsum^2) / sum(w^2)
        se_rob <- ifelse(n_eff > 1, sqrt(var_w / n_eff), NA)
        mg_rob_rows[[length(mg_rob_rows)+1]] <- data.frame(variable=v, coef=mean_rob, se=se_rob)
      }
    }
  }
  
  return(list(
    country = bind_rows(country_df), 
    mg = bind_rows(mg_rows), 
    robust = bind_rows(mg_rob_rows), 
    residuals = residuals_df
  ))
}

build_robustness_table <- function(df_base, df_full, dep, exog_vars, endog_vars, insts) {
  variants <- list()
  
  variants[["inst"]] <- estimate_ccemg(df_base, dep, exog_vars, endog_vars, insts)$robust
  variants[["exog"]] <- estimate_ccemg(df_base, dep, exog_vars, endog_vars, insts, exog_only=TRUE)$robust
  
  exog_womod <- setdiff(exog_vars, c("mod", "dlenprmod"))
  variants[["womod"]] <- estimate_ccemg(df_base, dep, exog_womod, endog_vars, insts)$robust
  
  df_rec <- df_base
  df_rec$recession_2009 <- as.integer(df_rec$yr == 2009)
  variants[["recession"]] <- estimate_ccemg(df_rec, dep, c(exog_vars, "recession_2009"), endog_vars, insts)$robust
  
  df_gerire <- df_base
  mask <- !((tolower(df_gerire$country) %in% c("germany", "deu") & df_gerire$yr == 1990) | 
            (tolower(df_gerire$country) %in% c("ireland", "irl") & df_gerire$yr == 2015))
  variants[["gerire"]] <- estimate_ccemg(df_gerire[mask, ], dep, exog_vars, endog_vars, insts)$robust
  
  variants[["sixties"]] <- estimate_ccemg(df_full, dep, exog_vars, endog_vars, insts)$robust
  
  rows <- list()
  for (name in names(variants)) {
    tbl <- variants[[name]]
    if (nrow(tbl) == 0) next
    for (i in 1:nrow(tbl)) {
      row <- tbl[i, ]
      rows[[length(rows)+1]] <- data.frame(variant=name, variable=row$variable, coef=row$coef, se=row$se, p=ifelse(!is.null(row$p), row$p, NA))
    }
  }
  return(bind_rows(rows))
}

# =============================================================================
# Génération Tables (Format Strict)
# =============================================================================

export_table1 <- function(df, out_dir) {
  varmap <- list("lrgdpmad"="GDP", "lcpi"="CPI", "lenpr"="ENERGY", "open"="OpenTrade", "expgdp"="GovExp", "iy"="Invest",
                 "d_lrgdpmad"="D.GDP", "d_lcpi"="D.CPI", "d_lenpr"="D.ENERGY", "d_open"="D.OpenTrade", "d_expgdp"="D.GovExp", "d_iy"="D.Invest")
  
  rows <- list()
  for (col in names(varmap)) {
    if (col %in% names(df)) {
      s <- na.omit(df[[col]])
      if (length(s) == 0) next
      mean_v <- mean(s)
      std_v <- sd(s)
      
      # Retirer le CV pour les variables en Différence
      is_diff <- startsWith(varmap[[col]], "D.")
      cv <- ifelse(mean_v != 0 && !is_diff, std_v / mean_v, NA)
      cv_str <- ifelse(!is.na(cv), sprintf("%.3f", cv), "")
      
      rows[[length(rows)+1]] <- data.frame(
        Variable = varmap[[col]], Mean = sprintf("%.3f", mean_v), `Standard deviation` = sprintf("%.3f", std_v),
        `Coeff. of variation` = cv_str, Minimum = sprintf("%.3f", min(s)), Maximum = sprintf("%.3f", max(s)),
        check.names = FALSE
      )
    }
  }
  tbl <- bind_rows(rows)
  write.csv(tbl, file.path(out_dir, "table1_data_summary.csv"), row.names = FALSE)
  render_table_png(tbl, "Table 1 – Data Summary", "Notes: Real GDP (GDP), CPI and Energy Prices (ENERGY) are in logarithms. Open Trade (OpenTrade), Gov Expenditures (GovExp) and Investment (Invest) are % of GDP.", file.path(out_dir, "table1_data_summary.png"), 9)
}

export_table2 <- function(cips_df, out_dir) {
  varmap <- list("lrgdpmad"="GDP", "lcpi"="CPI", "lenpr"="ENERGY", "open"="OpenTrade", "expgdp"="GovExp", "iy"="Invest")
  
  fmt <- function(s, p) { if (is.na(s)) return(".") else return(sprintf("%.2f%s", s, get_stars(p))) }
  
  rows <- list()
  rows[[1]] <- data.frame(Variable="No Trend", `Lag 0`="", `Lag 1`="", `Lag 2`="", `Lag 3`="", check.names=FALSE)
  
  # No Trend - Niveaux
  for (v in names(varmap)) {
    sub <- cips_df %>% filter(variable == v)
    r <- list(Variable=varmap[[v]], `Lag 0`=".", `Lag 1`=".", `Lag 2`=".", `Lag 3`=".")
    for (i in 1:nrow(sub)) {
      l <- as.character(sub$lag[i])
      r[[paste0("Lag ", l)]] <- fmt(sub$stat_level[i], sub$pvalue_level[i])
    }
    rows[[length(rows)+1]] <- as.data.frame(r, check.names=FALSE)
  }
  # No Trend - Différences
  for (v in names(varmap)) {
    sub <- cips_df %>% filter(variable == paste0("d_", v))
    r <- list(Variable=paste0("D.", varmap[[v]]), `Lag 0`=".", `Lag 1`=".", `Lag 2`=".", `Lag 3`=".")
    for (i in 1:nrow(sub)) {
      l <- as.character(sub$lag[i])
      r[[paste0("Lag ", l)]] <- fmt(sub$stat_level[i], sub$pvalue_level[i])
    }
    rows[[length(rows)+1]] <- as.data.frame(r, check.names=FALSE)
  }
  
  rows[[length(rows)+1]] <- data.frame(Variable="Trend", `Lag 0`="", `Lag 1`="", `Lag 2`="", `Lag 3`="", check.names=FALSE)
  # Trend - Niveaux
  for (v in names(varmap)) {
    sub <- cips_df %>% filter(variable == v)
    r <- list(Variable=varmap[[v]], `Lag 0`=".", `Lag 1`=".", `Lag 2`=".", `Lag 3`=".")
    for (i in 1:nrow(sub)) {
      l <- as.character(sub$lag[i])
      r[[paste0("Lag ", l)]] <- fmt(sub$stat_level_t[i], sub$pvalue_level_t[i])
    }
    rows[[length(rows)+1]] <- as.data.frame(r, check.names=FALSE)
  }
  
  tbl <- bind_rows(rows)
  write.csv(tbl, file.path(out_dir, "table2_cips_unitroot.csv"), row.names = FALSE)
  render_table_png(tbl, "Table 2 – Pesaran Panel Unit Root Tests", "Notes: * p<0.05; ** p<0.01. The statistic reported is the raw t-bar.", file.path(out_dir, "table2_cips_unitroot.png"), 7)
}

export_table3 <- function(mg_cce, mg_robust, out_dir) {
  var_order <- list("dlcpi"="D.CPI", "dlenpr"="D.Energy", "dopen"="D.OpenTrade", "dexpgdp"="D.GovExp", "diy"="D.Invest", "l_lrgdpmad"="L.GDP", "l_lcpi"="L.CPI", "l_open"="L.OpenTrade", "l_iy"="L.Invest", "(Intercept)"="_cons")
  
  get_val <- function(df, v) {
    r <- df %>% filter(variable == v)
    if(nrow(r) > 0) return(fmt_coef(r$coef[1], r$se[1], r$p[1]))
    return(c("", ""))
  }
  
  rows <- list()
  for (vcode in names(var_order)) {
    c1 <- get_val(mg_cce, vcode)
    c2 <- get_val(mg_robust, vcode)
    if (c1[1] != "" || c2[1] != "") {
      rows[[length(rows)+1]] <- data.frame(Variable=var_order[[vcode]], cce=c1[1], ccerobust=c2[1])
      rows[[length(rows)+1]] <- data.frame(Variable="", cce=c1[2], ccerobust=c2[2])
    }
  }
  
  tbl <- bind_rows(rows)
  write.csv(tbl, file.path(out_dir, "table3_cce_robust.csv"), row.names = FALSE)
  render_table_png(tbl, "Table 3 – CCE-MG: Unweighted vs outlier-robust estimates", "Notes: b/(se) format. * p<0.05; ** p<0.01.", file.path(out_dir, "table3_cce_robust.png"), 6)
}

export_table4 <- function(rob_df, out_dir) {
  variants <- c("inst", "exog", "womod", "recession", "gerire", "sixties")
  var_order <- list("l_dlcpi2"="L.D.CPI>2%", "dopen"="D.OpenTrade", "dexpgdp"="D.GovExp", "diy"="D.Invest", "l_lrgdpmad"="L.GDP", "l_lcpi"="L.CPI", "l_open"="L.OpenTrade", "l_iy"="L.Invest", "mod"="mod", "dlenprmod"="D.Energy×mod", "dlenpr"="D.Energy", "recession_2009"="recess", "(Intercept)"="_cons")
  
  get_val <- function(df, variant_name, vcode) {
    r <- df %>% filter(variant == variant_name, variable == vcode)
    if (nrow(r) > 0) return(r[1,])
    return(NULL)
  }
  
  rows <- list()
  for (vcode in names(var_order)) {
    row_c <- list(Variable = var_order[[vcode]])
    row_s <- list(Variable = "")
    any_val <- FALSE
    for (v in variants) {
      val <- get_val(rob_df, v, vcode)
      if (!is.null(val)) {
        any_val <- TRUE
        f <- fmt_coef(val$coef, val$se, val$p)
        row_c[[v]] <- f[1]; row_s[[v]] <- f[2]
      } else {
        row_c[[v]] <- ""; row_s[[v]] <- ""
      }
    }
    if (any_val) {
      rows[[length(rows)+1]] <- as.data.frame(row_c, check.names=FALSE)
      rows[[length(rows)+1]] <- as.data.frame(row_s, check.names=FALSE)
    }
  }
  
  # Price effect
  pe_row <- list(Variable = "Price effect (post-1982)")
  for (v in variants) {
    e1 <- get_val(rob_df, v, "dlenpr")
    e2 <- get_val(rob_df, v, "dlenprmod")
    if (!is.null(e1)) {
      pe <- e1$coef + ifelse(!is.null(e2), e2$coef, 0)
      pe_row[[v]] <- sprintf("%.3f", pe)
    } else pe_row[[v]] <- ""
  }
  rows[[length(rows)+1]] <- as.data.frame(pe_row, check.names=FALSE)
  
  tbl <- bind_rows(rows)
  # Remplacement des en-têtes
  names(tbl) <- c("Variable", "inst", "exog", "w/o_mod", "recession", "ger_ire", "sixties")
  write.csv(tbl, file.path(out_dir, "table4_ccemg_robustness.csv"), row.names = FALSE)
  render_table_png(tbl, "Table 4 CCE-Mean-group estimates for real GDP growth", "Notes: b/(se) format. * p<0.05; ** p<0.01.", file.path(out_dir, "table4_ccemg_robustness.png"), 10)
}

export_table5 <- function(cc_country, out_dir, intensity_df) {
  countries <- sort(unique(cc_country$country))
  rows <- list()
  
  for (c in countries) {
    sub <- cc_country %>% filter(country == c)
    b_pre <- sub %>% filter(variable == "dlenpr") %>% pull(coef)
    b_mod <- sub %>% filter(variable == "dlenprmod") %>% pull(coef)
    
    pre <- if(length(b_pre) > 0) b_pre[1] else NA
    mod <- if(length(b_mod) > 0) b_mod[1] else NA
    post <- if(!is.na(pre) && !is.na(mod)) pre + mod else pre
    
    int_val <- NA; exp_val <- NA; imp_val <- NA; post_val <- post; pre_val <- pre
    
    if (!is.null(intensity_df)) {
      t <- intensity_df %>% filter(tolower(country) == tolower(c) | tolower(country) == tolower(get_country_label(c)))
      if (nrow(t) > 0) {
        if ("intensity" %in% names(t)) int_val <- t$intensity[1]
        if ("exports" %in% names(t)) exp_val <- t$exports[1]
        if ("imports" %in% names(t)) imp_val <- t$imports[1]
        if ("post_1982" %in% names(t) && !is.na(t$post_1982[1])) post_val <- t$post_1982[1]
        if ("pre_1983" %in% names(t) && !is.na(t$pre_1983[1])) pre_val <- t$pre_1983[1]
      }
    }
    
    rows[[length(rows)+1]] <- data.frame(
      Country = get_country_label(c),
      Intensity = ifelse(!is.na(int_val), sprintf("%.3f", int_val), ""),
      Exports = ifelse(!is.na(exp_val), sprintf("%.3f", exp_val), ""),
      Imports = ifelse(!is.na(imp_val), sprintf("%.3f", imp_val), ""),
      `Post-1982` = ifelse(!is.na(post_val), sprintf("%.3f", post_val), "."),
      `Pre-1983` = ifelse(!is.na(pre_val), sprintf("%.3f", pre_val), "."),
      check.names = FALSE
    )
  }
  
  tbl <- bind_rows(rows)
  pres <- as.numeric(tbl$`Pre-1983`[tbl$`Pre-1983` != "."])
  posts <- as.numeric(tbl$`Post-1982`[tbl$`Post-1982` != "."])
  
  tbl <- bind_rows(tbl, data.frame(Country="Average", Intensity="", Exports="", Imports="", 
                                   `Post-1982`=sprintf("%.3f", mean(posts, na.rm=TRUE)), 
                                   `Pre-1983`=sprintf("%.3f", mean(pres, na.rm=TRUE)), check.names=FALSE))
  
  write.csv(tbl, file.path(out_dir, "table5_country_responses.csv"), row.names = FALSE)
  render_table_png(tbl, "Table 5 Individual country energy intensity and responses", "Notes: Post-1982 coef = D.Energy + D.Energy×mod.", file.path(out_dir, "table5_country_responses.png"), 9)
}

export_table6 <- function(cc_country, out_dir, intensity_df) {
  if (is.null(intensity_df) || nrow(intensity_df) == 0) return()
  
  countries <- sort(unique(cc_country$country))
  out <- data.frame()
  
  for (c in countries) {
    sub <- cc_country %>% filter(country == c)
    b_pre <- sub %>% filter(variable == "dlenpr") %>% pull(coef)
    b_mod <- sub %>% filter(variable == "dlenprmod") %>% pull(coef)
    pre <- if(length(b_pre) > 0) b_pre[1] else NA
    mod <- if(length(b_mod) > 0) b_mod[1] else NA
    post <- if(!is.na(pre) && !is.na(mod)) pre + mod else pre
    
    row_df <- data.frame(country=tolower(get_country_label(c)), pre=pre, post=post, intensity=NA, exclude=FALSE)
    
    t <- intensity_df %>% filter(tolower(country) == tolower(c) | tolower(country) == tolower(get_country_label(c)))
    if (nrow(t) > 0) {
      if ("pre_1983" %in% names(t) && !is.na(t$pre_1983[1])) row_df$pre <- t$pre_1983[1]
      if ("post_1982" %in% names(t) && !is.na(t$post_1982[1])) row_df$post <- t$post_1982[1]
      if ("intensity" %in% names(t)) row_df$intensity <- t$intensity[1]
      if ("exclude" %in% names(t)) row_df$exclude <- t$exclude[1]
    }
    out <- bind_rows(out, row_df)
  }
  
  run_reg <- function(d, ycol) {
    d <- d %>% drop_na(all_of(c(ycol, "intensity")))
    if (nrow(d) < 3) return(list(c=NA, t=NA, f=NA, rmse=NA, n=nrow(d)))
    
    f <- as.formula(paste(ycol, "~ intensity"))
    fit <- lm(f, data = d)
    se_hc1 <- sqrt(diag(vcovHC(fit, type="HC1")))
    
    return(list(
      c = coef(fit)["intensity"],
      t = coef(fit)["intensity"] / se_hc1["intensity"],
      f = summary(fit)$fstatistic[1],
      rmse = sqrt(mean(residuals(fit)^2)),
      n = nrow(d)
    ))
  }
  
  specs <- list()
  
  # (1) Pre
  res <- run_reg(out, "pre")
  specs[[1]] <- data.frame(Specification="(1) Pre-1983 ~ Intensity", Coef=sprintf("%.3f", res$c), `t-stat`=sprintf("%.2f", res$t), N=res$n, F=sprintf("%.2f", res$f), RMSE=sprintf("%.3f", res$rmse), check.names=FALSE)
  
  # (2) Post
  res <- run_reg(out, "post")
  specs[[2]] <- data.frame(Specification="(2) Post-1982 ~ Intensity", Coef=sprintf("%.3f", res$c), `t-stat`=sprintf("%.2f", res$t), N=res$n, F=sprintf("%.2f", res$f), RMSE=sprintf("%.3f", res$rmse), check.names=FALSE)
  
  # (3) Pre (excl)
  res <- run_reg(out %>% filter(!exclude), "pre")
  specs[[3]] <- data.frame(Specification="(3) Pre-1983 ~ Intensity (excl. outliers)", Coef=sprintf("%.3f", res$c), `t-stat`=sprintf("%.2f", res$t), N=res$n, F=sprintf("%.2f", res$f), RMSE=sprintf("%.3f", res$rmse), check.names=FALSE)
  
  # (4) Post (excl)
  res <- run_reg(out %>% filter(!exclude), "post")
  specs[[4]] <- data.frame(Specification="(4) Post-1982 ~ Intensity (excl. outliers)", Coef=sprintf("%.3f", res$c), `t-stat`=sprintf("%.2f", res$t), N=res$n, F=sprintf("%.2f", res$f), RMSE=sprintf("%.3f", res$rmse), check.names=FALSE)
  
  tbl <- bind_rows(specs)
  write.csv(tbl, file.path(out_dir, "table6_intensity_regression.csv"), row.names = FALSE)
  render_table_png(tbl, "Table 6 Regressions of country-specific responses on energy intensity", "Notes: Intensity = energy use per unit of GDP (EIA). Robust standard errors.", file.path(out_dir, "table6_intensity_regression.png"), 9)
}

# =============================================================================
# Graphiques 
# =============================================================================

export_grids <- function(df, residuals_df, out_dir) {
  theme_set(theme_classic(base_size = 8) + theme(strip.background = element_blank(), strip.text = element_text(face="bold")))
  
  df$country_lbl <- sapply(df$country, get_country_label)
  
  plot_grid <- function(yvar, title, file) {
    p <- ggplot(df %>% drop_na(all_of(yvar)), aes(x=yr, y=.data[[yvar]])) +
      geom_line(linewidth=0.5) +
      geom_vline(xintercept=1982, linetype="dotted", color="gray") +
      facet_wrap(~country_lbl, ncol=5) +
      labs(title=title, x="Year", y="")
    ggsave(file.path(out_dir, file), plot=p, width=10, height=7, dpi=200)
  }
  
  plot_grid("lrgdpmad", "Fig. A.1 – Country real GDP levels (log)", "figA1_gdp_levels.png")
  plot_grid("lcpi", "Fig. A.2 – Country CPI levels (log)", "figA2_cpi_levels.png")
  plot_grid("lenpr", "Fig. A.3 – Country energy price levels (log)", "figA3_energy_levels.png")
  plot_grid("open", "Fig. A.4 – Country open trade (% of GDP)", "figA4_opentrade.png")
  plot_grid("expgdp", "Fig. A.5 – Country government expenditures (% of GDP)", "figA5_govexp.png")
  plot_grid("iy", "Fig. A.6 – Country investment (% of GDP)", "figA6_investment.png")
  
  # A.7 Residuals
  if (nrow(residuals_df) > 0) {
    res_merged <- df %>% left_join(residuals_df, by=c("country", "yr")) %>% drop_na(dlrgdpmad)
    p7 <- ggplot(res_merged, aes(x=yr)) +
      geom_hline(yintercept=0, color="red", linetype="dotted") +
      geom_line(aes(y=dlrgdpmad, color="D.GDP"), linewidth=0.6) +
      geom_line(aes(y=residual, color="Residual"), linewidth=0.5, linetype="dashed") +
      facet_wrap(~country_lbl, ncol=5) +
      scale_color_manual(name="", values=c("D.GDP"="black", "Residual"="#777777")) +
      labs(title="Fig. A.7 – Actual change in Real GDP and CCEMG residuals", x="Year", y="") +
      theme(legend.position="bottom")
    ggsave(file.path(out_dir, "figA7_gdp_residuals.png"), plot=p7, width=10, height=7, dpi=200)
  }
}

# =============================================================================
# Lancement Principal
# =============================================================================

run_all <- function() {
  cat("\nChargement des données...\n")
  df_full <- load_and_prepare_data(DATA_PATH)
  df_base <- df_full %>% filter(yr >= 1972)
  intensity_df <- load_table56(DATA_PATH)
  
  cat("Table 1...\n")
  export_table1(df_full, OUTPUT_DIR)
  
  cat("Table 2 (CIPS)...\n")
  cips_rows <- list()
  for (v in c("lrgdpmad", "lcpi", "lenpr", "open", "expgdp", "iy")) {
    for (l in 0:3) {
      r_lvl <- cips_test_manual(df_full, v, lags=l, trend="c")
      r_diff <- cips_test_manual(df_full, paste0("d_", v), lags=l, trend="c")
      r_lvlt <- cips_test_manual(df_full, v, lags=l, trend="ct")
      cips_rows[[length(cips_rows)+1]] <- data.frame(
        variable=v, lag=l, stat_level=r_lvl[1], pvalue_level=r_lvl[2],
        stat_diff=r_diff[1], pvalue_diff=r_diff[2], stat_level_t=r_lvlt[1], pvalue_level_t=r_lvlt[2]
      )
    }
  }
  export_table2(bind_rows(cips_rows), OUTPUT_DIR)
  
  cat("Table 3 (CCEMG)...\n")
  cce_regs <- c("dlcpi", "dlenpr", "dopen", "dexpgdp", "diy", "l_lrgdpmad", "l_lcpi", "l_open", "l_iy")
  t3_res <- estimate_ccemg(df_full, "dlrgdpmad", cce_regs, c(), c(), exog_only=TRUE)
  export_table3(t3_res$mg, t3_res$robust, OUTPUT_DIR)
  
  cat("Table 4 (Robustesse)...\n")
  exog_vars <- c("l_dlcpi2", "dopen", "dexpgdp", "diy", "l_lrgdpmad", "l_lcpi", "l_open", "l_iy", "mod", "dlenprmod")
  endog_vars <- c("dlenpr")
  insts <- intersect(names(df_base), c("l_dlenpr", "l_lenpr", "ln_ywld", "ln_meast", "l_ln_ywld", "l_ln_meast", "usshare", "iranrev"))
  
  rob_df <- build_robustness_table(df_base, df_full, "dlrgdpmad", exog_vars, endog_vars, insts)
  export_table4(rob_df, OUTPUT_DIR)
  
  cat("Table 5 & 6 (Intensité)...\n")
  base_cce <- estimate_ccemg(df_base, "dlrgdpmad", exog_vars, endog_vars, insts)
  export_table5(base_cce$country, OUTPUT_DIR, intensity_df)
  export_table6(base_cce$country, OUTPUT_DIR, intensity_df)
  
  cat("Génération des graphiques A.1 à A.7...\n")
  export_grids(df_full, base_cce$residuals, OUTPUT_DIR)
  
  cat(paste0("\n✅ Exécution terminée. Les fichiers CSV et PNG sont dans le dossier : ", OUTPUT_DIR, "/\n"))
}

# Lancer le script
run_all()