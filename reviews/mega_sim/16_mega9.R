# 16_mega9.R — analysis of results/mega/mega9 (the "mega9" sweep).
#
# Context vs mega8 (baseline pulled from cache_mega8.rds when present):
#   * Same stage shape as mega8 — team2..team10 sampled × 6 weathers, plus the
#     pooled ratings_combined.csv (every battle, all stages+weathers, one flat
#     table) used here as the canonical aggregate / outlier source (§7-§8).
#   * Engine state = current working tree AFTER the T.36c per-piece tuning pass:
#     kit bug fixes (Cliffeyrie talon cadence, Steam Engineer vent passive,
#     Mirewarden int/auto on-hit), over-coeff trims (Glade/Veilfang/Borealis/
#     Mournhollow/Springfrog/Ember/Coral), Hierarch utility buff, and 5 under-piece
#     stat_overrides (Aurion/Maw/Stone Warden/Marshghast/Dredge). So the mega8→mega9
#     deltas isolate the T.36c tune of the 18 problem pieces (§9.4 in the mega8 report).
#
# Base R only. Run from repo root: Rscript reviews/mega_sim/16_mega9.R

source("reviews/mega_sim/00_load.R")  # power(), WEATHERS, OUTDIR

MEGA9  <- "results/mega/mega9"
OUTDIR <- "reviews/mega_sim"

STAGES9 <- paste0("team", 2:10, "-sample")
LBL9 <- setNames(paste0(2:10, "v", 2:10), STAGES9)
SIZE9 <- setNames(2:10, LBL9)
ORD9  <- names(SIZE9)

mn <- function(x) mean(x, na.rm=TRUE)
hr <- function(t) cat("\n", strrep("=",76), "\n", t, "\n", strrep("=",76), "\n", sep="")

load_ratings9 <- function(dir=MEGA9, stages=STAGES9) {
  rows <- list()
  for (st in stages) for (w in WEATHERS) {
    f <- file.path(dir, sprintf("ratings_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE)
    d$stage <- LBL9[[st]]; d$weather <- w
    rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}

R9 <- load_ratings9()
R9$stage <- factor(R9$stage, levels=ORD9)
ORD9_pres <- levels(droplevels(R9$stage))

# Combined (pooled) ratings — the new flat file.
CB <- read.csv(file.path(MEGA9, "ratings_combined.csv"), stringsAsFactors=FALSE)

cat(sprintf("mega9 loaded: %d per-stage rows, %d unique pieces, stages=%s\n",
    nrow(R9), length(unique(R9$piece_id)), paste(ORD9_pres, collapse=",")))
cat(sprintf("combined: %d rows (pooled all stages+weathers)\n", nrow(CB)))

# mega8 baseline from cache (raw data deleted).
M8 <- tryCatch(readRDS(file.path(OUTDIR,"cache_mega8.rds")), error=function(e) NULL)
R8 <- if (!is.null(M8)) M8$R8 else NULL
if (!is.null(R8)) cat(sprintf("mega8 baseline (cache): %d rows\n", nrow(R8)))

roles <- sort(unique(R9$role))

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
cov <- do.call(rbind, lapply(ORD9_pres, function(s) {
  d <- R9[R9$stage==s,]
  data.frame(stage=s, size=SIZE9[[s]], rows=nrow(d),
             weathers=length(unique(d$weather)),
             nm_min=min(d$n_matches), nm_med=median(d$n_matches), nm_max=max(d$n_matches),
             timeout_mean=round(mn(d$timeout_rate),3))
}))
print(cov, row.names=FALSE)

# ============================================================================
hr("1. AGGREGATE BALANCE — champ vs enemy, variance by size")
bal9 <- do.call(rbind, lapply(ORD9_pres, function(s) {
  d <- R9[R9$stage==s,]
  ppm <- aggregate(win_rate~piece_id, d, mn)$win_rate
  data.frame(stage=s, size=SIZE9[[s]],
             champ=mn(d$win_rate[d$kind=="champion"]),
             enemy=mn(d$win_rate[d$kind=="enemy"]),
             sd_wr=sd(ppm), timeout=mn(d$timeout_rate))
}))
print(bal9, row.names=FALSE, digits=3)

# ============================================================================
hr("2. ROLE WIN_RATE + WR_DELTA by size")
role_wr9 <- sapply(ORD9_pres, function(s) {
  d <- R9[R9$stage==s,]; sapply(roles, function(rr) mn(d$win_rate[d$role==rr]))
})
role_wd9 <- sapply(ORD9_pres, function(s) {
  d <- R9[R9$stage==s,]; sapply(roles, function(rr) mn(d$wr_delta[d$role==rr]))
})
cat("\n--- Role win_rate by stage ---\n"); print(round(role_wr9, 3))
cat("\n--- Role wr_delta by stage ---\n"); print(round(role_wd9, 3))
cat("\n--- Role win_rate (COMBINED / pooled) ---\n")
print(round(sort(tapply(CB$win_rate, CB$role, mn)), 3))
cat("\n--- Role wr_delta (COMBINED / pooled) ---\n")
print(round(sort(tapply(CB$wr_delta, CB$role, mn)), 3))

# ============================================================================
hr("3. MAGE DEFICIT by size + within-tier; vs mega8 baseline")
mt9 <- do.call(rbind, lapply(ORD9_pres, function(s) {
  d <- R9[R9$stage==s,]
  data.frame(stage=s, size=SIZE9[[s]],
             mage=mn(d$win_rate[d$role=="mage"]),
             nonmage=mn(d$win_rate[d$role!="mage"]),
             within_tier_def=within_tier_deficit(d, "mage"),
             cor_tier_wr=cor(d$tier, d$win_rate, use="complete.obs"))
}))
print(mt9, row.names=FALSE, digits=3)
if (!is.null(R8)) {
  cat("\n--- within-tier mage deficit: mega8 vs mega9 (matched sizes) ---\n")
  R8$stage <- as.character(R8$stage)
  for (s in intersect(ORD9_pres, unique(R8$stage))) {
    d8 <- R8[R8$stage==s,]; d9 <- R9[R9$stage==s,]
    cat(sprintf("  %s  mega8=%.3f  mega9=%.3f  (delta=%+.3f)\n",
        s, within_tier_deficit(d8,"mage"), within_tier_deficit(d9,"mage"),
        within_tier_deficit(d9,"mage")-within_tier_deficit(d8,"mage")))
  }
}

# ============================================================================
hr("4. LEVEL EFFECTS (L1 / L2 / L3)")
lv9 <- do.call(rbind, lapply(ORD9_pres, function(s) {
  d <- R9[R9$stage==s,]
  do.call(rbind, lapply(1:3, function(l) {
    dl <- d[d$level==l,]
    data.frame(stage=s, size=SIZE9[[s]], level=l,
               win_rate=mn(dl$win_rate), wr_delta=mn(dl$wr_delta),
               timeout=mn(dl$timeout_rate))
  }))
}))
print(lv9, row.names=FALSE, digits=3)
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
R9$cw       <- vapply(as.character(R9$affinity), counter_of, character(1))
R9$is_own   <- as.character(R9$weather)==as.character(R9$affinity)
R9$is_ctr   <- as.character(R9$weather)==R9$cw
R9$is_clear <- as.character(R9$weather)=="clear"
wmean <- function(v,w){ k<-!is.na(v)&!is.na(w)&w>0; if(!any(k)) NA else sum(v[k]*w[k])/sum(w[k]) }

wx9 <- do.call(rbind, lapply(ORD9_pres, function(s) {
  d <- R9[R9$stage==s,]
  own <- wmean(d$win_rate[d$is_own],  d$n_matches[d$is_own])
  ctr <- wmean(d$win_rate[d$is_ctr],  d$n_matches[d$is_ctr])
  base<- wmean(d$win_rate[d$is_clear],d$n_matches[d$is_clear])
  # sensitivity: per-piece spread of per-weather win_rate, averaged
  sp <- tapply(seq_len(nrow(d)), d$piece_id, function(ix) {
    wr <- d$win_rate[ix]; if(length(wr)<2) NA else max(wr)-min(wr) })
  data.frame(stage=s, size=SIZE9[[s]], clear_base=base, own=own, counter=ctr,
             own_minus_counter=own-ctr, own_minus_clear=own-base,
             sensitivity=mn(as.numeric(sp)))
}))
print(wx9, row.names=FALSE, digits=3)

cat("\n--- 5b. per-affinity own / clear / counter (RAW, pooled all stages) ---\n")
aff9 <- do.call(rbind, lapply(order_w, function(a) {
  ar <- R9[as.character(R9$affinity)==a,]
  if (!nrow(ar)) return(NULL)
  own <- wmean(ar$win_rate[ar$is_own],  ar$n_matches[ar$is_own])
  ctr <- wmean(ar$win_rate[ar$is_ctr],  ar$n_matches[ar$is_ctr])
  base<- wmean(ar$win_rate[ar$is_clear],ar$n_matches[ar$is_clear])
  data.frame(affinity=a, clear=base, own=own, counter=ctr,
             own_minus_clear=own-base, own_minus_counter=own-ctr)
}))
print(aff9, row.names=FALSE, digits=3)

cat("\n--- 5c. METRIC ARTEFACT: buggy column-average vs correct raw ---\n")
buggy_own <- mn(R9$own_weather_wr); buggy_ctr <- mn(R9$counter_weather_wr)
pct0 <- round(100*mean(R9$counter_weather_wr==0, na.rm=TRUE),1)
cat(sprintf("  column-avg (zeros in): own=%.3f counter=%.3f delta=%+.3f  [counter==0 in %.1f%% rows]\n",
    buggy_own, buggy_ctr, buggy_own-buggy_ctr, pct0))
cat(sprintf("  RAW (correct)        : own=%.3f counter=%.3f delta=%+.3f\n",
    wmean(R9$win_rate[R9$is_own],R9$n_matches[R9$is_own]),
    wmean(R9$win_rate[R9$is_ctr],R9$n_matches[R9$is_ctr]),
    wmean(R9$win_rate[R9$is_own],R9$n_matches[R9$is_own])-wmean(R9$win_rate[R9$is_ctr],R9$n_matches[R9$is_ctr])))

# ============================================================================
hr("6. TIMEOUTS by role across sizes")
to9 <- sapply(ORD9_pres, function(s) {
  d <- R9[R9$stage==s,]; sapply(roles, function(rr) mn(d$timeout_rate[d$role==rr]))
})
print(round(to9, 3))

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
spread9 <- do.call(rbind, lapply(split(R9, R9$piece_id), function(d) {
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
spread9 <- spread9[order(-spread9$excess_sd),]
cat("\nMOST CONTEXT-VOLATILE 25 (excess wr_delta sd beyond sampling noise):\n")
print(head(spread9[,c("name","affinity","role","tier","n_ctx","tot_matches",
                      "wd_pooled","wd_sd","noise_sd","excess_sd","wd_range")],25),
      row.names=FALSE, digits=3)
cat(sprintf("\n  excess_sd > 0 in %d/%d pieces; median excess=%.3f, p90=%.3f\n",
    sum(spread9$excess_sd>0), nrow(spread9), median(spread9$excess_sd),
    quantile(spread9$excess_sd, .9)))

# ============================================================================
hr("8. MAGE DEEP-DIVE (combined, per piece)")
mc <- CB[CB$role=="mage",]
mc <- mc[order(mc$wr_delta),]
cat("All mage pieces by wr_delta (ascending):\n")
print(mc[,c("name","affinity","tier","level","win_rate","wr_delta")], row.names=FALSE, digits=3)

# ============================================================================
hr("9. SUMMARY NUMBERS")
cat(sprintf("  Stages: %s\n", paste(ORD9_pres, collapse=", ")))
cat(sprintf("  Per-stage rated rows: %d ; combined pieces: %d\n", nrow(R9), nrow(CB)))
cat(sprintf("  Median matches/piece (combined): %d\n", median(CB$n_matches)))
cat(sprintf("  Mean timeout (combined): %.3f\n", mn(CB$timeout_rate)))
cat(sprintf("  Mage wr (combined): %.3f ; non-mage: %.3f ; gap: %+.3f\n",
    mn(CB$win_rate[CB$role=="mage"]), mn(CB$win_rate[CB$role!="mage"]),
    mn(CB$win_rate[CB$role!="mage"]) - mn(CB$win_rate[CB$role=="mage"])))
cat(sprintf("  Within-tier mage deficit (2v2): %.3f\n", within_tier_deficit(R9[R9$stage=="2v2",],"mage")))
cat(sprintf("  Own-weather advantage (RAW, all stages): own-counter=%+.4f  own-clear=%+.4f\n",
    wmean(R9$win_rate[R9$is_own],R9$n_matches[R9$is_own]) -
      wmean(R9$win_rate[R9$is_ctr],R9$n_matches[R9$is_ctr]),
    wmean(R9$win_rate[R9$is_own],R9$n_matches[R9$is_own]) -
      wmean(R9$win_rate[R9$is_clear],R9$n_matches[R9$is_clear])))
cat(sprintf("  Champion wr (combined): %.3f ; enemy: %.3f\n",
    mn(CB$win_rate[CB$kind=="champion"]), mn(CB$win_rate[CB$kind=="enemy"])))

# ---- SAVE ----
dir.create(file.path(OUTDIR,"tables"), showWarnings=FALSE)
write.csv(cov,  file.path(OUTDIR,"tables/m9_coverage.csv"), row.names=FALSE)
write.csv(bal9, file.path(OUTDIR,"tables/m9_faction_by_size.csv"), row.names=FALSE)
write.csv(mt9,  file.path(OUTDIR,"tables/m9_mage_by_size.csv"), row.names=FALSE)
write.csv(lv9,  file.path(OUTDIR,"tables/m9_level_by_size.csv"), row.names=FALSE)
write.csv(wx9,  file.path(OUTDIR,"tables/m9_weather_by_size.csv"), row.names=FALSE)
write.csv(aff9, file.path(OUTDIR,"tables/m9_weather_by_affinity.csv"), row.names=FALSE)
write.csv(as.data.frame(role_wr9), file.path(OUTDIR,"tables/m9_role_wr_by_size.csv"))
write.csv(as.data.frame(role_wd9), file.path(OUTDIR,"tables/m9_role_wd_by_size.csv"))
write.csv(as.data.frame(to9),      file.path(OUTDIR,"tables/m9_timeout_by_size.csv"))
write.csv(CB,   file.path(OUTDIR,"tables/m9_combined.csv"), row.names=FALSE)
write.csv(mc,   file.path(OUTDIR,"tables/m9_mage_detail.csv"), row.names=FALSE)
write.csv(abs_out,  file.path(OUTDIR,"tables/m9_abs_outliers.csv"), row.names=FALSE)
write.csv(spread9,  file.path(OUTDIR,"tables/m9_spread_outliers.csv"), row.names=FALSE)

saveRDS(list(R9=R9, CB=CB, R8=R8, bal9=bal9, mt9=mt9, lv9=lv9, lvc=lvc, wx9=wx9,
             aff9=aff9, role_wr9=role_wr9, role_wd9=role_wd9, to9=to9,
             abs_out=abs_out, spread9=spread9,
             roles=roles, ORD9_pres=ORD9_pres, SIZE9=SIZE9),
        file.path(OUTDIR,"cache_mega9.rds"))
cat("\n[saved] tables/m9_*.csv + cache_mega9.rds\n")
