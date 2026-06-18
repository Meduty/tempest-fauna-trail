# 13_mega8.R — analysis of results/mega/mega8 (the "mega8" sweep).
#
# Context vs mega7 (baseline pulled from cache_mega7.rds when present):
#   * Same stage shape as mega7 — team2..team10 sampled × 6 weathers, plus the
#     pooled ratings_combined.csv (every battle, all stages+weathers, one flat
#     table) used here as the canonical aggregate / outlier source (§7-§8).
#   * Engine state = current working tree AFTER the T.36b champion re-axis
#     (PR #45 merged to main): roster stat/playstyle rebalance. So mega8 is the
#     first sweep on the re-axed roster — the mega7→mega8 deltas isolate that
#     rebalance. Treat kit reads as indicative of the merged tree.
#
# Base R only. Run from repo root: Rscript reviews/mega_sim/13_mega8.R

source("reviews/mega_sim/00_load.R")  # power(), WEATHERS, OUTDIR

MEGA8  <- "results/mega/mega8"
OUTDIR <- "reviews/mega_sim"

STAGES8 <- paste0("team", 2:10, "-sample")
LBL8 <- setNames(paste0(2:10, "v", 2:10), STAGES8)
SIZE8 <- setNames(2:10, LBL8)
ORD8  <- names(SIZE8)

mn <- function(x) mean(x, na.rm=TRUE)
hr <- function(t) cat("\n", strrep("=",76), "\n", t, "\n", strrep("=",76), "\n", sep="")

load_ratings8 <- function(dir=MEGA8, stages=STAGES8) {
  rows <- list()
  for (st in stages) for (w in WEATHERS) {
    f <- file.path(dir, sprintf("ratings_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE)
    d$stage <- LBL8[[st]]; d$weather <- w
    rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}

R8 <- load_ratings8()
R8$stage <- factor(R8$stage, levels=ORD8)
ORD8_pres <- levels(droplevels(R8$stage))

# Combined (pooled) ratings — the new flat file.
CB <- read.csv(file.path(MEGA8, "ratings_combined.csv"), stringsAsFactors=FALSE)

cat(sprintf("mega8 loaded: %d per-stage rows, %d unique pieces, stages=%s\n",
    nrow(R8), length(unique(R8$piece_id)), paste(ORD8_pres, collapse=",")))
cat(sprintf("combined: %d rows (pooled all stages+weathers)\n", nrow(CB)))

# mega7 baseline from cache (raw data deleted).
M7 <- tryCatch(readRDS(file.path(OUTDIR,"cache_mega7.rds")), error=function(e) NULL)
R7 <- if (!is.null(M7)) M7$R7 else NULL
if (!is.null(R7)) cat(sprintf("mega7 baseline (cache): %d rows\n", nrow(R7)))

roles <- sort(unique(R8$role))

within_tier_deficit <- function(df, role="mage") {
  tiers <- sort(unique(df$tier)); diffs <- c()
  for (t in tiers) {
    sub <- df[df$tier==t,]
    a <- sub$win_rate[sub$role==role]; b <- sub$win_rate[sub$role!=role]
    if (length(a) & length(b)) diffs <- c(diffs, mn(b)-mn(a))
  }
  mn(diffs)
}

# ============================================================================
hr("0. SAMPLE SIZE + COVERAGE by stage")
cov <- do.call(rbind, lapply(ORD8_pres, function(s) {
  d <- R8[R8$stage==s,]
  data.frame(stage=s, size=SIZE8[[s]], rows=nrow(d),
             weathers=length(unique(d$weather)),
             nm_min=min(d$n_matches), nm_med=median(d$n_matches), nm_max=max(d$n_matches),
             timeout_mean=round(mn(d$timeout_rate),3))
}))
print(cov, row.names=FALSE)

# ============================================================================
hr("1. AGGREGATE BALANCE — champ vs enemy, variance by size")
bal8 <- do.call(rbind, lapply(ORD8_pres, function(s) {
  d <- R8[R8$stage==s,]
  ppm <- aggregate(win_rate~piece_id, d, mn)$win_rate
  data.frame(stage=s, size=SIZE8[[s]],
             champ=mn(d$win_rate[d$kind=="champion"]),
             enemy=mn(d$win_rate[d$kind=="enemy"]),
             sd_wr=sd(ppm), timeout=mn(d$timeout_rate))
}))
print(bal8, row.names=FALSE, digits=3)

# ============================================================================
hr("2. ROLE WIN_RATE + WR_DELTA by size")
role_wr8 <- sapply(ORD8_pres, function(s) {
  d <- R8[R8$stage==s,]; sapply(roles, function(rr) mn(d$win_rate[d$role==rr]))
})
role_wd8 <- sapply(ORD8_pres, function(s) {
  d <- R8[R8$stage==s,]; sapply(roles, function(rr) mn(d$wr_delta[d$role==rr]))
})
cat("\n--- Role win_rate by stage ---\n"); print(round(role_wr8, 3))
cat("\n--- Role wr_delta by stage ---\n"); print(round(role_wd8, 3))
cat("\n--- Role win_rate (COMBINED / pooled) ---\n")
print(round(sort(tapply(CB$win_rate, CB$role, mn)), 3))
cat("\n--- Role wr_delta (COMBINED / pooled) ---\n")
print(round(sort(tapply(CB$wr_delta, CB$role, mn)), 3))

# ============================================================================
hr("3. MAGE DEFICIT by size + within-tier; vs mega7 baseline")
mt8 <- do.call(rbind, lapply(ORD8_pres, function(s) {
  d <- R8[R8$stage==s,]
  data.frame(stage=s, size=SIZE8[[s]],
             mage=mn(d$win_rate[d$role=="mage"]),
             nonmage=mn(d$win_rate[d$role!="mage"]),
             within_tier_def=within_tier_deficit(d, "mage"),
             cor_tier_wr=cor(d$tier, d$win_rate, use="complete.obs"))
}))
print(mt8, row.names=FALSE, digits=3)
if (!is.null(R7)) {
  cat("\n--- within-tier mage deficit: mega7 vs mega8 (matched sizes) ---\n")
  R7$stage <- as.character(R7$stage)
  for (s in intersect(ORD8_pres, unique(R7$stage))) {
    d7 <- R7[R7$stage==s,]; d8 <- R8[R8$stage==s,]
    cat(sprintf("  %s  mega7=%.3f  mega8=%.3f  (delta=%+.3f)\n",
        s, within_tier_deficit(d7,"mage"), within_tier_deficit(d8,"mage"),
        within_tier_deficit(d8,"mage")-within_tier_deficit(d7,"mage")))
  }
}

# ============================================================================
hr("4. LEVEL EFFECTS (L1 / L2 / L3)")
lv8 <- do.call(rbind, lapply(ORD8_pres, function(s) {
  d <- R8[R8$stage==s,]
  do.call(rbind, lapply(1:3, function(l) {
    dl <- d[d$level==l,]
    data.frame(stage=s, size=SIZE8[[s]], level=l,
               win_rate=mn(dl$win_rate), wr_delta=mn(dl$wr_delta),
               timeout=mn(dl$timeout_rate))
  }))
}))
print(lv8, row.names=FALSE, digits=3)
cat("\n--- level (COMBINED) ---\n")
lvc <- do.call(rbind, lapply(1:3, function(l) {
  d <- CB[CB$level==l,]
  data.frame(level=l, win_rate=mn(d$win_rate), wr_delta=mn(d$wr_delta),
             timeout=mn(d$timeout_rate))
}))
print(lvc, row.names=FALSE, digits=3)

# ============================================================================
hr("5. WEATHER — own vs counter, computed from RAW per-weather win_rate")
# IMPORTANT: do NOT average the own_weather_wr/counter_weather_wr columns.
# In the as-run CSVs those columns zero-fill missing weathers (clear-affinity
# has no counter; sampling misses the single counter weather ~37% of rows),
# which fabricates a huge own-minus-counter gap. We recompute from the raw
# per-weather win_rate instead (validated identical to the NaN-skipping metric).
order_w <- c("mist","cloudy","rain","snow","thunder")
counter_of <- function(a){ i<-match(a,order_w); if(is.na(i)) NA_character_ else order_w[(i %% 5)+1] }
R8$cw       <- vapply(as.character(R8$affinity), counter_of, character(1))
R8$is_own   <- as.character(R8$weather)==as.character(R8$affinity)
R8$is_ctr   <- as.character(R8$weather)==R8$cw
R8$is_clear <- as.character(R8$weather)=="clear"
wmean <- function(v,w){ k<-!is.na(v)&!is.na(w)&w>0; if(!any(k)) NA else sum(v[k]*w[k])/sum(w[k]) }

wx8 <- do.call(rbind, lapply(ORD8_pres, function(s) {
  d <- R8[R8$stage==s,]
  own <- wmean(d$win_rate[d$is_own],  d$n_matches[d$is_own])
  ctr <- wmean(d$win_rate[d$is_ctr],  d$n_matches[d$is_ctr])
  base<- wmean(d$win_rate[d$is_clear],d$n_matches[d$is_clear])
  # sensitivity: per-piece spread of per-weather win_rate, averaged
  sp <- tapply(seq_len(nrow(d)), d$piece_id, function(ix) {
    wr <- d$win_rate[ix]; if(length(wr)<2) NA else max(wr)-min(wr) })
  data.frame(stage=s, size=SIZE8[[s]], clear_base=base, own=own, counter=ctr,
             own_minus_counter=own-ctr, own_minus_clear=own-base,
             sensitivity=mn(as.numeric(sp)))
}))
print(wx8, row.names=FALSE, digits=3)

cat("\n--- 5b. per-affinity own / clear / counter (RAW, pooled all stages) ---\n")
aff8 <- do.call(rbind, lapply(order_w, function(a) {
  ar <- R8[as.character(R8$affinity)==a,]
  if (!nrow(ar)) return(NULL)
  own <- wmean(ar$win_rate[ar$is_own],  ar$n_matches[ar$is_own])
  ctr <- wmean(ar$win_rate[ar$is_ctr],  ar$n_matches[ar$is_ctr])
  base<- wmean(ar$win_rate[ar$is_clear],ar$n_matches[ar$is_clear])
  data.frame(affinity=a, clear=base, own=own, counter=ctr,
             own_minus_clear=own-base, own_minus_counter=own-ctr)
}))
print(aff8, row.names=FALSE, digits=3)

cat("\n--- 5c. METRIC ARTEFACT: buggy column-average vs correct raw ---\n")
buggy_own <- mn(R8$own_weather_wr); buggy_ctr <- mn(R8$counter_weather_wr)
pct0 <- round(100*mean(R8$counter_weather_wr==0, na.rm=TRUE),1)
cat(sprintf("  column-avg (zeros in): own=%.3f counter=%.3f delta=%+.3f  [counter==0 in %.1f%% rows]\n",
    buggy_own, buggy_ctr, buggy_own-buggy_ctr, pct0))
cat(sprintf("  RAW (correct)        : own=%.3f counter=%.3f delta=%+.3f\n",
    wmean(R8$win_rate[R8$is_own],R8$n_matches[R8$is_own]),
    wmean(R8$win_rate[R8$is_ctr],R8$n_matches[R8$is_ctr]),
    wmean(R8$win_rate[R8$is_own],R8$n_matches[R8$is_own])-wmean(R8$win_rate[R8$is_ctr],R8$n_matches[R8$is_ctr])))

# ============================================================================
hr("6. TIMEOUTS by role across sizes")
to8 <- sapply(ORD8_pres, function(s) {
  d <- R8[R8$stage==s,]; sapply(roles, function(rr) mn(d$timeout_rate[d$role==rr]))
})
print(round(to8, 3))

# ============================================================================
hr("7. OUTLIERS — from COMBINED (pooled, pair-game weighted)")
# Within-tier z-score of wr_delta: how odd is this piece RELATIVE to its tier
# cohort (controls for the fact that high tiers carry larger residual variance).
CB$wd_z <- ave(CB$wr_delta, CB$tier, FUN=function(x){
  s <- sd(x); if (is.na(s) || s==0) rep(0, length(x)) else (x-mean(x))/s })
abs_cols <- c("name","affinity","role","tier","level","win_rate","wr_delta","wd_z","n_matches")

ord_wr <- CB[order(CB$win_rate),]
cat("\nWEAKEST 20 (win_rate):\n")
print(head(ord_wr[,c("name","affinity","role","tier","level","win_rate","wr_delta","n_matches")],20), row.names=FALSE, digits=3)
cat("\nSTRONGEST 20 (win_rate):\n")
print(head(ord_wr[order(-ord_wr$win_rate),c("name","affinity","role","tier","level","win_rate","wr_delta","n_matches")],20), row.names=FALSE, digits=3)
ord_wd <- CB[order(CB$wr_delta),]
cat("\nMOST UNDER-TUNED 20 (wr_delta; wd_z = within-tier z):\n")
print(head(ord_wd[,abs_cols],20), row.names=FALSE, digits=3)
cat("\nMOST OVER-TUNED 20 (wr_delta; wd_z = within-tier z):\n")
print(head(ord_wd[order(-ord_wd$wr_delta),abs_cols],20), row.names=FALSE, digits=3)
cat("\nMOST ODD vs TIER COHORT 20 (|within-tier z| of wr_delta):\n")
print(head(CB[order(-abs(CB$wd_z)),abs_cols],20), row.names=FALSE, digits=3)

# Absolute-outlier table (union of the extremes) for the report / plots.
abs_out <- CB[order(-abs(CB$wr_delta)),][1:30, abs_cols]

# ============================================================================
hr("7b. SPREAD OUTLIERS — wr_delta volatility across stage x weather contexts")
# "Odd" can also mean INCONSISTENT: a piece whose pooled wr_delta sits near 0
# but swings hard across formats/weathers is just as much an outlier as one
# with a large pooled residual. Per-cell samples are thin, so raw spread is
# dominated by binomial noise — we subtract the EXPECTED noise sd and rank by
# the EXCESS (context-driven) spread.
spread8 <- do.call(rbind, lapply(split(R8, R8$piece_id), function(d) {
  w  <- d$n_matches; w[is.na(w)] <- 0
  wd <- d$wr_delta;  wr <- d$win_rate; nm <- d$n_matches
  k  <- !is.na(wd) & !is.na(wr) & w > 0
  if (sum(k) < 3) return(NULL)
  wd <- wd[k]; wt <- w[k]; wr <- wr[k]; nm <- nm[k]
  wbar  <- sum(wt*wd)/sum(wt)
  wsd   <- sqrt(sum(wt*(wd-wbar)^2)/sum(wt))      # match-weighted sd of wr_delta
  # Expected per-cell binomial sd. Use the piece's POOLED win-rate for the
  # variance numerator — a per-cell wr(1-wr) collapses to 0 on single-match
  # cells (p=0/1), which would understate noise and fake excess spread.
  pbar  <- sum(wt*wr)/sum(wt)
  noise <- sqrt(pbar*(1-pbar)*mean(1/pmax(nm,1)))
  data.frame(name=d$name[1], affinity=d$affinity[1], role=d$role[1],
             tier=d$tier[1], n_ctx=sum(k), tot_matches=sum(nm),
             wd_pooled=wbar, wd_sd=wsd, wd_range=max(wd)-min(wd),
             noise_sd=noise, excess_sd=wsd-noise, stringsAsFactors=FALSE)
}))
spread8 <- spread8[order(-spread8$excess_sd),]
cat("\nMOST CONTEXT-VOLATILE 25 (excess wr_delta sd beyond sampling noise):\n")
print(head(spread8[,c("name","affinity","role","tier","n_ctx","tot_matches",
                      "wd_pooled","wd_sd","noise_sd","excess_sd","wd_range")],25),
      row.names=FALSE, digits=3)
cat(sprintf("\n  excess_sd > 0 in %d/%d pieces; median excess=%.3f, p90=%.3f\n",
    sum(spread8$excess_sd>0), nrow(spread8), median(spread8$excess_sd),
    quantile(spread8$excess_sd, .9)))

# ============================================================================
hr("8. MAGE DEEP-DIVE (combined, per piece)")
mc <- CB[CB$role=="mage",]
mc <- mc[order(mc$wr_delta),]
cat("All mage pieces by wr_delta (ascending):\n")
print(mc[,c("name","affinity","tier","level","win_rate","wr_delta")], row.names=FALSE, digits=3)

# ============================================================================
hr("9. SUMMARY NUMBERS")
cat(sprintf("  Stages: %s\n", paste(ORD8_pres, collapse=", ")))
cat(sprintf("  Per-stage rated rows: %d ; combined pieces: %d\n", nrow(R8), nrow(CB)))
cat(sprintf("  Median matches/piece (combined): %d\n", median(CB$n_matches)))
cat(sprintf("  Mean timeout (combined): %.3f\n", mn(CB$timeout_rate)))
cat(sprintf("  Mage wr (combined): %.3f ; non-mage: %.3f ; gap: %+.3f\n",
    mn(CB$win_rate[CB$role=="mage"]), mn(CB$win_rate[CB$role!="mage"]),
    mn(CB$win_rate[CB$role!="mage"]) - mn(CB$win_rate[CB$role=="mage"])))
cat(sprintf("  Within-tier mage deficit (2v2): %.3f\n", within_tier_deficit(R8[R8$stage=="2v2",],"mage")))
cat(sprintf("  Own-weather advantage (RAW, all stages): own-counter=%+.4f  own-clear=%+.4f\n",
    wmean(R8$win_rate[R8$is_own],R8$n_matches[R8$is_own]) -
      wmean(R8$win_rate[R8$is_ctr],R8$n_matches[R8$is_ctr]),
    wmean(R8$win_rate[R8$is_own],R8$n_matches[R8$is_own]) -
      wmean(R8$win_rate[R8$is_clear],R8$n_matches[R8$is_clear])))
cat(sprintf("  Champion wr (combined): %.3f ; enemy: %.3f\n",
    mn(CB$win_rate[CB$kind=="champion"]), mn(CB$win_rate[CB$kind=="enemy"])))

# ---- SAVE ----
dir.create(file.path(OUTDIR,"tables"), showWarnings=FALSE)
write.csv(cov,  file.path(OUTDIR,"tables/m8_coverage.csv"), row.names=FALSE)
write.csv(bal8, file.path(OUTDIR,"tables/m8_faction_by_size.csv"), row.names=FALSE)
write.csv(mt8,  file.path(OUTDIR,"tables/m8_mage_by_size.csv"), row.names=FALSE)
write.csv(lv8,  file.path(OUTDIR,"tables/m8_level_by_size.csv"), row.names=FALSE)
write.csv(wx8,  file.path(OUTDIR,"tables/m8_weather_by_size.csv"), row.names=FALSE)
write.csv(aff8, file.path(OUTDIR,"tables/m8_weather_by_affinity.csv"), row.names=FALSE)
write.csv(as.data.frame(role_wr8), file.path(OUTDIR,"tables/m8_role_wr_by_size.csv"))
write.csv(as.data.frame(role_wd8), file.path(OUTDIR,"tables/m8_role_wd_by_size.csv"))
write.csv(as.data.frame(to8),      file.path(OUTDIR,"tables/m8_timeout_by_size.csv"))
write.csv(CB,   file.path(OUTDIR,"tables/m8_combined.csv"), row.names=FALSE)
write.csv(mc,   file.path(OUTDIR,"tables/m8_mage_detail.csv"), row.names=FALSE)
write.csv(abs_out,  file.path(OUTDIR,"tables/m8_abs_outliers.csv"), row.names=FALSE)
write.csv(spread8,  file.path(OUTDIR,"tables/m8_spread_outliers.csv"), row.names=FALSE)

saveRDS(list(R8=R8, CB=CB, R7=R7, bal8=bal8, mt8=mt8, lv8=lv8, lvc=lvc, wx8=wx8,
             aff8=aff8, role_wr8=role_wr8, role_wd8=role_wd8, to8=to8,
             abs_out=abs_out, spread8=spread8,
             roles=roles, ORD8_pres=ORD8_pres, SIZE8=SIZE8),
        file.path(OUTDIR,"cache_mega8.rds"))
cat("\n[saved] tables/m8_*.csv + cache_mega8.rds\n")
