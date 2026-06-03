# 09_mega6.R — analysis of results/mega_10v10_2 (the "mega6" sweep).
#
# Context vs mega5 (results/mega_10v10):
#   * Smaller per-stage sample (~1000 battles/weather vs 30k–12k): trades depth
#     for wider coverage and faster iteration.
#   * NEW: mage INT-fix (commit b812e38) — support abilities now correctly scale
#     from INT instead of adding raw damage.  This is the primary hypothesis to test.
#   * NEW: improved level-scaling + matchup handling (commit 2c1f530).
#   * No 1v1 stage (--skip 1v1); stages = team2..team8 only.
#   * mega7 = results/mega_10v10_3 (same engine, teams 2-3 only, interrupted).
#     team2 data is bit-identical to mega6; team3 has 17 vs 20 median matches.
#     Treated as a partial confirmation of mega6; not a separate analysis.
#
# Key question: did the INT-fix close the residual mage deficit?
# Base R only. Run from repo root: Rscript reviews/mega_sim/09_mega6.R

source("reviews/mega_sim/00_load.R")  # power(), WEATHERS, OUTDIR

MEGA6  <- "results/mega_10v10_2"
MEGA5  <- "results/mega_10v10"
OUTDIR <- "reviews/mega_sim"

STAGES6 <- c("team2-sample","team3-sample","team4-sample","team5-sample",
             "team6-sample","team7-sample","team8-sample")
LBL6 <- c("team2-sample"="2v2","team3-sample"="3v3","team4-sample"="4v4",
          "team5-sample"="5v5","team6-sample"="6v6","team7-sample"="7v7",
          "team8-sample"="8v8")
SIZE6 <- c("2v2"=2,"3v3"=3,"4v4"=4,"5v5"=5,"6v6"=6,"7v7"=7,"8v8"=8)
ORD6  <- names(SIZE6)

load_ratings6 <- function(dir=MEGA6, stages=STAGES6) {
  rows <- list()
  for (st in stages) for (w in WEATHERS) {
    f <- file.path(dir, sprintf("ratings_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE)
    d$stage <- LBL6[[st]]; d$weather <- w
    rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}

R6 <- load_ratings6()
R6$stage <- factor(R6$stage, levels=ORD6)
ORD6_pres <- levels(droplevels(R6$stage))
cat(sprintf("mega6 loaded: %d rated rows, %d unique pieces, stages=%s\n",
    nrow(R6), length(unique(R6$piece_id)), paste(ORD6_pres, collapse=",")))

# load mega5 for comparison (team2/3/4 only — use levels that overlap)
load_ratings5_compat <- function() {
  STAGES5c <- c("team2-sample","team3-sample","team4-sample")
  LBL5c <- c("team2-sample"="2v2","team3-sample"="3v3","team4-sample"="4v4")
  rows <- list()
  for (st in STAGES5c) for (w in WEATHERS) {
    f <- file.path(MEGA5, sprintf("ratings_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE)
    d$stage <- LBL5c[[st]]; d$weather <- w
    rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}
R5c <- load_ratings5_compat()
cat(sprintf("mega5 (compat subset): %d rows\n", nrow(R5c)))

mn   <- function(x) mean(x, na.rm=TRUE)
hr   <- function(t) cat("\n", strrep("=",76), "\n", t, "\n", strrep("=",76), "\n", sep="")

# within-tier mage deficit
within_tier_deficit <- function(df, role="mage") {
  tiers <- sort(unique(df$tier)); diffs <- c()
  for (t in tiers) {
    sub <- df[df$tier==t,]
    a <- sub$win_rate[sub$role==role]; b <- sub$win_rate[sub$role!=role]
    if (length(a) & length(b)) diffs <- c(diffs, mn(b)-mn(a))
  }
  mn(diffs)
}

roles <- c("mage","warrior","marksman","assassin","bruiser","hybrid","support")
roles <- intersect(roles, unique(R6$role))

# ============================================================================
hr("0. SAMPLE SIZE + COVERAGE by stage x weather")
cov <- do.call(rbind, lapply(ORD6_pres, function(s) {
  d <- R6[R6$stage==s,]
  data.frame(stage=s, size=SIZE6[[s]], rows=nrow(d),
             weathers=length(unique(d$weather)),
             nm_min=min(d$n_matches), nm_med=median(d$n_matches), nm_max=max(d$n_matches),
             timeout_mean=round(mn(d$timeout_rate),3))
}))
print(cov, row.names=FALSE)

# ============================================================================
hr("1. AGGREGATE BALANCE — champ vs enemy, variance by size")
bal6 <- do.call(rbind, lapply(ORD6_pres, function(s) {
  d <- R6[R6$stage==s,]
  ppm <- aggregate(win_rate~piece_id, d, mn)$win_rate
  data.frame(stage=s, size=SIZE6[[s]],
             champ=mn(d$win_rate[d$kind=="champion"]),
             enemy=mn(d$win_rate[d$kind=="enemy"]),
             sd_wr=sd(ppm), timeout=mn(d$timeout_rate))
}))
print(bal6, row.names=FALSE, digits=3)

# ============================================================================
hr("2. ROLE WIN_RATE + WR_DELTA by size")
role_wr6 <- sapply(ORD6_pres, function(s) {
  d <- R6[R6$stage==s,]; sapply(roles, function(rr) mn(d$win_rate[d$role==rr]))
})
role_wd6 <- sapply(ORD6_pres, function(s) {
  d <- R6[R6$stage==s,]; sapply(roles, function(rr) mn(d$wr_delta[d$role==rr]))
})
cat("\n--- Role win_rate by stage ---\n"); print(round(role_wr6, 3))
cat("\n--- Role wr_delta by stage ---\n"); print(round(role_wd6, 3))

# ============================================================================
hr("3. MAGE DEFICIT (KEY FINDING — INT-fix hypothesis)")
mt6 <- do.call(rbind, lapply(ORD6_pres, function(s) {
  d <- R6[R6$stage==s,]
  data.frame(stage=s, size=SIZE6[[s]],
             mage=mn(d$win_rate[d$role=="mage"]),
             nonmage=mn(d$win_rate[d$role!="mage"]),
             within_tier_def=within_tier_deficit(d, "mage"),
             cor_tier_wr=cor(d$tier, d$win_rate, use="complete.obs"))
}))
print(mt6, row.names=FALSE, digits=3)

# Before/after comparison at matched stages (2v2, 3v3, 4v4) — L1 only for apples
cat("\n--- BEFORE (mega5 L1) vs AFTER (mega6 L1) mage within-tier deficit ---\n")
for (s in intersect(ORD6_pres, c("2v2","3v3","4v4"))) {
  m5 <- R5c[R5c$stage==s & R5c$level==1,]
  m6 <- R6[R6$stage==s & R6$level==1,]
  cat(sprintf("  %s  mega5=%.3f  mega6=%.3f  (delta=%+.3f)\n",
      s, within_tier_deficit(m5,"mage"), within_tier_deficit(m6,"mage"),
      within_tier_deficit(m6,"mage")-within_tier_deficit(m5,"mage")))
}

# ============================================================================
hr("4. LEVEL EFFECTS (L1 / L2 / L3 on-budget check)")
lv6 <- do.call(rbind, lapply(ORD6_pres, function(s) {
  d <- R6[R6$stage==s,]
  do.call(rbind, lapply(1:3, function(l) {
    dl <- d[d$level==l,]
    data.frame(stage=s, size=SIZE6[[s]], level=l,
               win_rate=mn(dl$win_rate), wr_delta=mn(dl$wr_delta),
               timeout=mn(dl$timeout_rate), n_pieces=length(unique(dl$piece_id)))
  }))
}))
print(lv6, row.names=FALSE, digits=3)

# ============================================================================
hr("5. WEATHER — own-affinity vs counter (by size + by affinity)")
wx6 <- do.call(rbind, lapply(ORD6_pres, function(s) {
  d <- R6[R6$stage==s,]
  data.frame(stage=s, size=SIZE6[[s]],
             own=mn(d$own_weather_wr), counter=mn(d$counter_weather_wr),
             own_minus_counter=mn(d$own_weather_wr)-mn(d$counter_weather_wr),
             sensitivity=mn(d$weather_sensitivity))
}))
print(wx6, row.names=FALSE, digits=3)

# Per-affinity in 2v2 (nearest to 1v1 signal-to-noise)
cat("\n--- 5b. per-affinity own-weather effect (2v2, L1) ---\n")
d2 <- R6[R6$stage=="2v2" & R6$level==1,]
aff6 <- do.call(rbind, lapply(WEATHERS, function(a) {
  ar <- d2[d2$affinity==a,]
  if (!nrow(ar)) return(NULL)
  data.frame(affinity=a, own=mn(ar$own_weather_wr), counter=mn(ar$counter_weather_wr),
             delta=mn(ar$own_weather_wr)-mn(ar$counter_weather_wr),
             sens=mn(ar$weather_sensitivity), n_pieces=length(unique(ar$piece_id)))
}))
print(aff6, row.names=FALSE, digits=3)

# Compare weather strength mega5 vs mega6 (2v2)
cat("\n--- 5c. own-weather advantage: mega5 vs mega6 (2v2) ---\n")
for (s in c("2v2","3v3")) {
  d5 <- R5c[R5c$stage==s,]; d6 <- R6[R6$stage==s,]
  cat(sprintf("  %s  mega5 own=%.4f ctr=%.4f  |  mega6 own=%.4f ctr=%.4f\n",
      s, mn(d5$own_weather_wr), mn(d5$counter_weather_wr),
         mn(d6$own_weather_wr), mn(d6$counter_weather_wr)))
}

# ============================================================================
hr("6. ROLE BEFORE/AFTER: mega5-L1 vs mega6-L1 (2v2, 3v3, 4v4)")
for (s in intersect(ORD6_pres, c("2v2","3v3","4v4"))) {
  m5 <- R5c[R5c$stage==s & R5c$level==1,]
  m6 <- R6[R6$stage==s & R6$level==1,]
  cat("\n", s, "(mega5-L1 vs mega6-L1):\n", sep="")
  tab <- do.call(rbind, lapply(roles, function(rr) {
    a <- mn(m5$win_rate[m5$role==rr]); b <- mn(m6$win_rate[m6$role==rr])
    if (is.nan(a) & is.nan(b)) return(NULL)
    data.frame(role=rr, m5_wr=round(a,3), m6_wr=round(b,3), delta=round(b-a,3),
               m5_wd=round(mn(m5$wr_delta[m5$role==rr]),3),
               m6_wd=round(mn(m6$wr_delta[m6$role==rr]),3))
  }))
  print(tab, row.names=FALSE)
}

# ============================================================================
hr("7. TIMEOUTS by role across sizes")
to6 <- sapply(ORD6_pres, function(s) {
  d <- R6[R6$stage==s,]; sapply(roles, function(rr) mn(d$timeout_rate[d$role==rr]))
})
print(round(to6, 3))

# ============================================================================
hr("8. OUTLIERS — pooled mean across all stages (mega6)")
agg6 <- aggregate(cbind(win_rate, wr_delta, timeout_rate) ~
                  piece_id+name+affinity+role+tier+level, R6, mn)
agg6 <- agg6[order(agg6$win_rate),]
cat("\nWEAKEST 10:\n")
print(head(agg6[,c("name","affinity","role","tier","level","win_rate","wr_delta")],10),
      row.names=FALSE, digits=3)
cat("\nSTRONGEST 10:\n")
print(head(agg6[order(-agg6$win_rate),c("name","affinity","role","tier","level","win_rate","wr_delta")],10),
      row.names=FALSE, digits=3)
agg6s <- agg6[order(agg6$wr_delta),]
cat("\nMOST UNDER-TUNED (wr_delta < 0):\n")
print(head(agg6s[,c("name","affinity","role","tier","level","win_rate","wr_delta")],10),
      row.names=FALSE, digits=3)
cat("\nMOST OVER-TUNED (wr_delta > 0):\n")
print(head(agg6s[order(-agg6s$wr_delta),c("name","affinity","role","tier","level","win_rate","wr_delta")],10),
      row.names=FALSE, digits=3)

# ============================================================================
hr("9. MAGE DEEP-DIVE: per-mage wr_delta (pooled) sorted")
m_only <- R6[R6$role=="mage",]
mage_agg <- aggregate(cbind(win_rate, wr_delta) ~ piece_id+name+tier+affinity+level, m_only, mn)
mage_agg <- mage_agg[order(mage_agg$wr_delta),]
cat("All mage pieces by wr_delta (ascending = most under-tuned first):\n")
print(mage_agg[,c("name","affinity","tier","level","win_rate","wr_delta")],
      row.names=FALSE, digits=3)

# compare mage wr_delta mega5 vs mega6 (2v2, L1)
cat("\n--- MAGE wr_delta mega5-L1 vs mega6-L1 (2v2, individual pieces) ---\n")
m5m <- R5c[R5c$stage=="2v2" & R5c$level==1 & R5c$role=="mage",]
m6m <- R6[R6$stage=="2v2" & R6$level==1 & R6$role=="mage",]
m5agg <- aggregate(wr_delta~piece_id+name+tier, m5m, mn)
m6agg <- aggregate(wr_delta~piece_id+name+tier, m6m, mn)
mcmp <- merge(m5agg, m6agg, by=c("piece_id","name","tier"), suffixes=c("_m5","_m6"))
mcmp$delta <- mcmp$wr_delta_m6 - mcmp$wr_delta_m5
mcmp <- mcmp[order(mcmp$delta),]
print(mcmp[,c("name","tier","wr_delta_m5","wr_delta_m6","delta")],
      row.names=FALSE, digits=3)

# ============================================================================
hr("10. SUMMARY TABLE (key numbers for report)")
cat("\nMEGA6 key numbers:\n")
cat(sprintf("  Stages covered: %s\n", paste(ORD6_pres, collapse=", ")))
cat(sprintf("  Total rated rows: %d\n", nrow(R6)))
cat(sprintf("  Unique piece_ids: %d\n", length(unique(R6$piece_id))))
cat(sprintf("  Levels: %s\n", paste(sort(unique(R6$level)), collapse=",")))
cat(sprintf("  Mean timeout rate (all): %.3f\n", mn(R6$timeout_rate)))
# mage overall
cat(sprintf("  Mage overall wr (all stages): %.3f\n", mn(R6$win_rate[R6$role=="mage"])))
cat(sprintf("  Non-mage overall wr: %.3f\n", mn(R6$win_rate[R6$role!="mage"])))
cat(sprintf("  Within-tier mage deficit (2v2): %.3f\n", within_tier_deficit(R6[R6$stage=="2v2",],"mage")))
# weather
cat(sprintf("  Own-weather advantage (2v2): %+.4f\n",
    mn(R6$own_weather_wr[R6$stage=="2v2"]) - mn(R6$counter_weather_wr[R6$stage=="2v2"])))

# ---- SAVE ----
dir.create(file.path(OUTDIR,"tables"), showWarnings=FALSE)
write.csv(cov,    file.path(OUTDIR,"tables/m6_coverage.csv"), row.names=FALSE)
write.csv(bal6,   file.path(OUTDIR,"tables/m6_faction_by_size.csv"), row.names=FALSE)
write.csv(mt6,    file.path(OUTDIR,"tables/m6_mage_tier_by_size.csv"), row.names=FALSE)
write.csv(lv6,    file.path(OUTDIR,"tables/m6_level_by_size.csv"), row.names=FALSE)
write.csv(wx6,    file.path(OUTDIR,"tables/m6_weather_by_size.csv"), row.names=FALSE)
write.csv(aff6,   file.path(OUTDIR,"tables/m6_weather_by_affinity.csv"), row.names=FALSE)
write.csv(as.data.frame(role_wr6), file.path(OUTDIR,"tables/m6_role_wr_by_size.csv"))
write.csv(as.data.frame(role_wd6), file.path(OUTDIR,"tables/m6_role_wd_by_size.csv"))
write.csv(as.data.frame(to6),      file.path(OUTDIR,"tables/m6_timeout_by_size.csv"))
write.csv(agg6,   file.path(OUTDIR,"tables/m6_piece_overall.csv"), row.names=FALSE)
write.csv(mage_agg, file.path(OUTDIR,"tables/m6_mage_detail.csv"), row.names=FALSE)

saveRDS(list(R6=R6, R5c=R5c, bal6=bal6, mt6=mt6, lv6=lv6, wx6=wx6, aff6=aff6,
             role_wr6=role_wr6, role_wd6=role_wd6, to6=to6, agg6=agg6,
             mage_agg=mage_agg, cov=cov, roles=roles, ORD6_pres=ORD6_pres,
             SIZE6=SIZE6),
        file.path(OUTDIR,"cache_mega6.rds"))
cat("\n[saved] tables/m6_*.csv + cache_mega6.rds\n")
