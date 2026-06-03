# 11_mega7.R — analysis of results/mega/mega7 (the "mega7" sweep).
#
# Context vs mega6 (cache_mega6.rds; raw dir results/mega_10v10_2 now gone):
#   * Much larger / deeper sample: median 237 matches/piece vs mega6's 11 at
#     2v2. Team sizes extended to team2..team10 (mega6 stopped at team8).
#   * NEW pooled artefact: ratings_combined.csv — every battle from every stage
#     and weather pooled into one flat ratings table (pair-game weighted).
#     Used here as the canonical aggregate / outlier source (§7-§8).
#   * Engine state = current working tree: barrier system, poison percentage
#     decay (V.25 decay_fraction=0.2), Glade Heron rework (flat-1 poison +
#     INT*0.8 haste + INT*0.2 burst, MR+40), loop.py removed. (provenance noted
#     in report — mega7 was run from this tree; treat kit reads as indicative.)
#
# Base R only. Run from repo root: Rscript reviews/mega_sim/11_mega7.R

source("reviews/mega_sim/00_load.R")  # power(), WEATHERS, OUTDIR

MEGA7  <- "results/mega/mega7"
OUTDIR <- "reviews/mega_sim"

STAGES7 <- paste0("team", 2:10, "-sample")
LBL7 <- setNames(paste0(2:10, "v", 2:10), STAGES7)
SIZE7 <- setNames(2:10, LBL7)
ORD7  <- names(SIZE7)

mn <- function(x) mean(x, na.rm=TRUE)
hr <- function(t) cat("\n", strrep("=",76), "\n", t, "\n", strrep("=",76), "\n", sep="")

load_ratings7 <- function(dir=MEGA7, stages=STAGES7) {
  rows <- list()
  for (st in stages) for (w in WEATHERS) {
    f <- file.path(dir, sprintf("ratings_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE)
    d$stage <- LBL7[[st]]; d$weather <- w
    rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}

R7 <- load_ratings7()
R7$stage <- factor(R7$stage, levels=ORD7)
ORD7_pres <- levels(droplevels(R7$stage))

# Combined (pooled) ratings — the new flat file.
CB <- read.csv(file.path(MEGA7, "ratings_combined.csv"), stringsAsFactors=FALSE)

cat(sprintf("mega7 loaded: %d per-stage rows, %d unique pieces, stages=%s\n",
    nrow(R7), length(unique(R7$piece_id)), paste(ORD7_pres, collapse=",")))
cat(sprintf("combined: %d rows (pooled all stages+weathers)\n", nrow(CB)))

# mega6 baseline from cache (raw data deleted).
M6 <- tryCatch(readRDS(file.path(OUTDIR,"cache_mega6.rds")), error=function(e) NULL)
R6 <- if (!is.null(M6)) M6$R6 else NULL
if (!is.null(R6)) cat(sprintf("mega6 baseline (cache): %d rows\n", nrow(R6)))

roles <- sort(unique(R7$role))

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
cov <- do.call(rbind, lapply(ORD7_pres, function(s) {
  d <- R7[R7$stage==s,]
  data.frame(stage=s, size=SIZE7[[s]], rows=nrow(d),
             weathers=length(unique(d$weather)),
             nm_min=min(d$n_matches), nm_med=median(d$n_matches), nm_max=max(d$n_matches),
             timeout_mean=round(mn(d$timeout_rate),3))
}))
print(cov, row.names=FALSE)

# ============================================================================
hr("1. AGGREGATE BALANCE — champ vs enemy, variance by size")
bal7 <- do.call(rbind, lapply(ORD7_pres, function(s) {
  d <- R7[R7$stage==s,]
  ppm <- aggregate(win_rate~piece_id, d, mn)$win_rate
  data.frame(stage=s, size=SIZE7[[s]],
             champ=mn(d$win_rate[d$kind=="champion"]),
             enemy=mn(d$win_rate[d$kind=="enemy"]),
             sd_wr=sd(ppm), timeout=mn(d$timeout_rate))
}))
print(bal7, row.names=FALSE, digits=3)

# ============================================================================
hr("2. ROLE WIN_RATE + WR_DELTA by size")
role_wr7 <- sapply(ORD7_pres, function(s) {
  d <- R7[R7$stage==s,]; sapply(roles, function(rr) mn(d$win_rate[d$role==rr]))
})
role_wd7 <- sapply(ORD7_pres, function(s) {
  d <- R7[R7$stage==s,]; sapply(roles, function(rr) mn(d$wr_delta[d$role==rr]))
})
cat("\n--- Role win_rate by stage ---\n"); print(round(role_wr7, 3))
cat("\n--- Role wr_delta by stage ---\n"); print(round(role_wd7, 3))
cat("\n--- Role win_rate (COMBINED / pooled) ---\n")
print(round(sort(tapply(CB$win_rate, CB$role, mn)), 3))
cat("\n--- Role wr_delta (COMBINED / pooled) ---\n")
print(round(sort(tapply(CB$wr_delta, CB$role, mn)), 3))

# ============================================================================
hr("3. MAGE DEFICIT by size + within-tier; vs mega6 baseline")
mt7 <- do.call(rbind, lapply(ORD7_pres, function(s) {
  d <- R7[R7$stage==s,]
  data.frame(stage=s, size=SIZE7[[s]],
             mage=mn(d$win_rate[d$role=="mage"]),
             nonmage=mn(d$win_rate[d$role!="mage"]),
             within_tier_def=within_tier_deficit(d, "mage"),
             cor_tier_wr=cor(d$tier, d$win_rate, use="complete.obs"))
}))
print(mt7, row.names=FALSE, digits=3)
if (!is.null(R6)) {
  cat("\n--- within-tier mage deficit: mega6 vs mega7 (matched sizes) ---\n")
  R6$stage <- as.character(R6$stage)
  for (s in intersect(ORD7_pres, unique(R6$stage))) {
    d6 <- R6[R6$stage==s,]; d7 <- R7[R7$stage==s,]
    cat(sprintf("  %s  mega6=%.3f  mega7=%.3f  (delta=%+.3f)\n",
        s, within_tier_deficit(d6,"mage"), within_tier_deficit(d7,"mage"),
        within_tier_deficit(d7,"mage")-within_tier_deficit(d6,"mage")))
  }
}

# ============================================================================
hr("4. LEVEL EFFECTS (L1 / L2 / L3)")
lv7 <- do.call(rbind, lapply(ORD7_pres, function(s) {
  d <- R7[R7$stage==s,]
  do.call(rbind, lapply(1:3, function(l) {
    dl <- d[d$level==l,]
    data.frame(stage=s, size=SIZE7[[s]], level=l,
               win_rate=mn(dl$win_rate), wr_delta=mn(dl$wr_delta),
               timeout=mn(dl$timeout_rate))
  }))
}))
print(lv7, row.names=FALSE, digits=3)
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
R7$cw       <- vapply(as.character(R7$affinity), counter_of, character(1))
R7$is_own   <- as.character(R7$weather)==as.character(R7$affinity)
R7$is_ctr   <- as.character(R7$weather)==R7$cw
R7$is_clear <- as.character(R7$weather)=="clear"
wmean <- function(v,w){ k<-!is.na(v)&!is.na(w)&w>0; if(!any(k)) NA else sum(v[k]*w[k])/sum(w[k]) }

wx7 <- do.call(rbind, lapply(ORD7_pres, function(s) {
  d <- R7[R7$stage==s,]
  own <- wmean(d$win_rate[d$is_own],  d$n_matches[d$is_own])
  ctr <- wmean(d$win_rate[d$is_ctr],  d$n_matches[d$is_ctr])
  base<- wmean(d$win_rate[d$is_clear],d$n_matches[d$is_clear])
  # sensitivity: per-piece spread of per-weather win_rate, averaged
  sp <- tapply(seq_len(nrow(d)), d$piece_id, function(ix) {
    wr <- d$win_rate[ix]; if(length(wr)<2) NA else max(wr)-min(wr) })
  data.frame(stage=s, size=SIZE7[[s]], clear_base=base, own=own, counter=ctr,
             own_minus_counter=own-ctr, own_minus_clear=own-base,
             sensitivity=mn(as.numeric(sp)))
}))
print(wx7, row.names=FALSE, digits=3)

cat("\n--- 5b. per-affinity own / clear / counter (RAW, pooled all stages) ---\n")
aff7 <- do.call(rbind, lapply(order_w, function(a) {
  ar <- R7[as.character(R7$affinity)==a,]
  if (!nrow(ar)) return(NULL)
  own <- wmean(ar$win_rate[ar$is_own],  ar$n_matches[ar$is_own])
  ctr <- wmean(ar$win_rate[ar$is_ctr],  ar$n_matches[ar$is_ctr])
  base<- wmean(ar$win_rate[ar$is_clear],ar$n_matches[ar$is_clear])
  data.frame(affinity=a, clear=base, own=own, counter=ctr,
             own_minus_clear=own-base, own_minus_counter=own-ctr)
}))
print(aff7, row.names=FALSE, digits=3)

cat("\n--- 5c. METRIC ARTEFACT: buggy column-average vs correct raw ---\n")
buggy_own <- mn(R7$own_weather_wr); buggy_ctr <- mn(R7$counter_weather_wr)
pct0 <- round(100*mean(R7$counter_weather_wr==0, na.rm=TRUE),1)
cat(sprintf("  column-avg (zeros in): own=%.3f counter=%.3f delta=%+.3f  [counter==0 in %.1f%% rows]\n",
    buggy_own, buggy_ctr, buggy_own-buggy_ctr, pct0))
cat(sprintf("  RAW (correct)        : own=%.3f counter=%.3f delta=%+.3f\n",
    wmean(R7$win_rate[R7$is_own],R7$n_matches[R7$is_own]),
    wmean(R7$win_rate[R7$is_ctr],R7$n_matches[R7$is_ctr]),
    wmean(R7$win_rate[R7$is_own],R7$n_matches[R7$is_own])-wmean(R7$win_rate[R7$is_ctr],R7$n_matches[R7$is_ctr])))

# ============================================================================
hr("6. TIMEOUTS by role across sizes")
to7 <- sapply(ORD7_pres, function(s) {
  d <- R7[R7$stage==s,]; sapply(roles, function(rr) mn(d$timeout_rate[d$role==rr]))
})
print(round(to7, 3))

# ============================================================================
hr("7. OUTLIERS — from COMBINED (pooled, pair-game weighted)")
ord_wr <- CB[order(CB$win_rate),]
cat("\nWEAKEST 12 (win_rate):\n")
print(head(ord_wr[,c("name","affinity","role","tier","level","win_rate","wr_delta","n_matches")],12), row.names=FALSE, digits=3)
cat("\nSTRONGEST 12 (win_rate):\n")
print(head(ord_wr[order(-ord_wr$win_rate),c("name","affinity","role","tier","level","win_rate","wr_delta","n_matches")],12), row.names=FALSE, digits=3)
ord_wd <- CB[order(CB$wr_delta),]
cat("\nMOST UNDER-TUNED 12 (wr_delta):\n")
print(head(ord_wd[,c("name","affinity","role","tier","level","win_rate","wr_delta")],12), row.names=FALSE, digits=3)
cat("\nMOST OVER-TUNED 12 (wr_delta):\n")
print(head(ord_wd[order(-ord_wd$wr_delta),c("name","affinity","role","tier","level","win_rate","wr_delta")],12), row.names=FALSE, digits=3)

# ============================================================================
hr("8. MAGE DEEP-DIVE (combined, per piece)")
mc <- CB[CB$role=="mage",]
mc <- mc[order(mc$wr_delta),]
cat("All mage pieces by wr_delta (ascending):\n")
print(mc[,c("name","affinity","tier","level","win_rate","wr_delta")], row.names=FALSE, digits=3)

# ============================================================================
hr("9. SUMMARY NUMBERS")
cat(sprintf("  Stages: %s\n", paste(ORD7_pres, collapse=", ")))
cat(sprintf("  Per-stage rated rows: %d ; combined pieces: %d\n", nrow(R7), nrow(CB)))
cat(sprintf("  Median matches/piece (combined): %d\n", median(CB$n_matches)))
cat(sprintf("  Mean timeout (combined): %.3f\n", mn(CB$timeout_rate)))
cat(sprintf("  Mage wr (combined): %.3f ; non-mage: %.3f ; gap: %+.3f\n",
    mn(CB$win_rate[CB$role=="mage"]), mn(CB$win_rate[CB$role!="mage"]),
    mn(CB$win_rate[CB$role!="mage"]) - mn(CB$win_rate[CB$role=="mage"])))
cat(sprintf("  Within-tier mage deficit (2v2): %.3f\n", within_tier_deficit(R7[R7$stage=="2v2",],"mage")))
cat(sprintf("  Own-weather advantage (RAW, all stages): own-counter=%+.4f  own-clear=%+.4f\n",
    wmean(R7$win_rate[R7$is_own],R7$n_matches[R7$is_own]) -
      wmean(R7$win_rate[R7$is_ctr],R7$n_matches[R7$is_ctr]),
    wmean(R7$win_rate[R7$is_own],R7$n_matches[R7$is_own]) -
      wmean(R7$win_rate[R7$is_clear],R7$n_matches[R7$is_clear])))
cat(sprintf("  Champion wr (combined): %.3f ; enemy: %.3f\n",
    mn(CB$win_rate[CB$kind=="champion"]), mn(CB$win_rate[CB$kind=="enemy"])))

# ---- SAVE ----
dir.create(file.path(OUTDIR,"tables"), showWarnings=FALSE)
write.csv(cov,  file.path(OUTDIR,"tables/m7_coverage.csv"), row.names=FALSE)
write.csv(bal7, file.path(OUTDIR,"tables/m7_faction_by_size.csv"), row.names=FALSE)
write.csv(mt7,  file.path(OUTDIR,"tables/m7_mage_by_size.csv"), row.names=FALSE)
write.csv(lv7,  file.path(OUTDIR,"tables/m7_level_by_size.csv"), row.names=FALSE)
write.csv(wx7,  file.path(OUTDIR,"tables/m7_weather_by_size.csv"), row.names=FALSE)
write.csv(aff7, file.path(OUTDIR,"tables/m7_weather_by_affinity.csv"), row.names=FALSE)
write.csv(as.data.frame(role_wr7), file.path(OUTDIR,"tables/m7_role_wr_by_size.csv"))
write.csv(as.data.frame(role_wd7), file.path(OUTDIR,"tables/m7_role_wd_by_size.csv"))
write.csv(as.data.frame(to7),      file.path(OUTDIR,"tables/m7_timeout_by_size.csv"))
write.csv(CB,   file.path(OUTDIR,"tables/m7_combined.csv"), row.names=FALSE)
write.csv(mc,   file.path(OUTDIR,"tables/m7_mage_detail.csv"), row.names=FALSE)

saveRDS(list(R7=R7, CB=CB, R6=R6, bal7=bal7, mt7=mt7, lv7=lv7, lvc=lvc, wx7=wx7,
             aff7=aff7, role_wr7=role_wr7, role_wd7=role_wd7, to7=to7,
             roles=roles, ORD7_pres=ORD7_pres, SIZE7=SIZE7),
        file.path(OUTDIR,"cache_mega7.rds"))
cat("\n[saved] tables/m7_*.csv + cache_mega7.rds\n")
