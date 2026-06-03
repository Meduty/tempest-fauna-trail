# 06_mega5.R — analysis of results/mega_10v10 (the "mega5" sweep).
#
# New vs mega3/4:
#   * 10 stages: 1v1 + team2..team10 sample (was 1v1/2v2/3v3 only)
#   * levelled roster: 360 pieces = 120 bases x levels {1,2,3} (was 120 @ L1)
#   * new ratings columns: own_weather_wr, counter_weather_wr, weather_sensitivity,
#     n_pair_games/n_pair_wins/n_team_wins/n_team_draws/n_team_timeouts
#   * POST-BUFF code: mega3/4 recommendations (mage buff, weather strengthen)
#     are implemented, so this run TESTS whether they landed.
#
# mega4 = pre-buff baseline (120 pieces @ L1). For a fair before/after we
# filter mega5 to level==1.
#
# Base R only. Run: Rscript reviews/mega_sim/06_mega5.R

source("reviews/mega_sim/00_load.R")  # power(), helpers

MEGA5 <- "results/mega_10v10"
OUTDIR <- "reviews/mega_sim"
STAGES5 <- c("1v1","team2-sample","team3-sample","team4-sample","team5-sample",
             "team6-sample","team7-sample","team8-sample","team9-sample","team10-sample")
LBL5 <- c("1v1"="1v1","team2-sample"="2v2","team3-sample"="3v3","team4-sample"="4v4",
          "team5-sample"="5v5","team6-sample"="6v6","team7-sample"="7v7",
          "team8-sample"="8v8","team9-sample"="9v9","team10-sample"="10v10")
SIZE  <- c("1v1"=1,"2v2"=2,"3v3"=3,"4v4"=4,"5v5"=5,"6v6"=6,"7v7"=7,"8v8"=8,"9v9"=9,"10v10"=10)
ORD   <- c("1v1","2v2","3v3","4v4","5v5","6v6","7v7","8v8","9v9","10v10")

load_ratings5 <- function(dir=MEGA5, stages=STAGES5) {
  rows <- list()
  for (st in stages) for (w in WEATHERS) {
    f <- file.path(dir, sprintf("ratings_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE)
    d$stage <- LBL5[[st]]; d$weather <- w
    rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}

R5 <- load_ratings5()
R5$stage <- factor(R5$stage, levels=ORD)
cat(sprintf("mega5 loaded: %d rated rows, %d unique pieces, stages=%s\n",
            nrow(R5), length(unique(R5$piece_id)), paste(levels(droplevels(R5$stage)),collapse=",")))

hr <- function(t) cat("\n", strrep("=",76), "\n", t, "\n", strrep("=",76), "\n", sep="")
mn <- function(x) mean(x, na.rm=TRUE)

# within-tier deficit of a role vs the rest
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
hr("0. SAMPLE SIZES + n_matches per stage")
samp <- do.call(rbind, lapply(ORD, function(s){
  d <- R5[R5$stage==s,]
  data.frame(stage=s, size=SIZE[[s]], rows=nrow(d),
             nm_min=min(d$n_matches), nm_med=median(d$n_matches), nm_max=max(d$n_matches))
}))
print(samp, row.names=FALSE)

# ============================================================================
hr("1. AGGREGATE FACTION BALANCE + variance shrink by size")
bal <- do.call(rbind, lapply(ORD, function(s){
  d <- R5[R5$stage==s,]
  ppm <- aggregate(win_rate~piece_id, d, mn)$win_rate  # collapse weather
  data.frame(stage=s, size=SIZE[[s]],
             champ=mn(d$win_rate[d$kind=="champion"]),
             enemy=mn(d$win_rate[d$kind=="enemy"]),
             sd_wr=sd(ppm), timeout=mn(d$timeout_rate))
}))
print(bal, row.names=FALSE, digits=3)

# ============================================================================
hr("2. ROLE win_rate by size")
roles <- c("mage","warrior","marksman","assassin","bruiser","hybrid","support")
roles <- intersect(roles, unique(R5$role))
role_wr <- sapply(ORD, function(s){
  d <- R5[R5$stage==s,]; sapply(roles, function(rr) mn(d$win_rate[d$role==rr]))
})
print(round(role_wr,3))
cat("\n--- ROLE wr_delta by size ---\n")
role_wd <- sapply(ORD, function(s){
  d <- R5[R5$stage==s,]; sapply(roles, function(rr) mn(d$wr_delta[d$role==rr]))
})
print(round(role_wd,3))

# ============================================================================
hr("3. MAGE deficit + TIER cliff by size")
mt <- do.call(rbind, lapply(ORD, function(s){
  d <- R5[R5$stage==s,]
  data.frame(stage=s, size=SIZE[[s]],
             mage=mn(d$win_rate[d$role=="mage"]),
             nonmage=mn(d$win_rate[d$role!="mage"]),
             within_tier_def=within_tier_deficit(d,"mage"),
             cor_tier_wr=cor(d$tier, d$win_rate, use="complete.obs"))
}))
print(mt, row.names=FALSE, digits=3)

# ============================================================================
hr("4. LEVEL dimension (L1/L2/L3) — on-budget check")
for (s in c("1v1","3v3","6v6","10v10")) {
  d <- R5[R5$stage==s,]
  cat("\n", s, ":\n", sep="")
  lv <- do.call(rbind, lapply(1:3, function(l){
    dl <- d[d$level==l,]
    data.frame(level=l, win_rate=mn(dl$win_rate), wr_delta=mn(dl$wr_delta),
               timeout=mn(dl$timeout_rate), n=length(unique(dl$piece_id)))
  }))
  print(lv, row.names=FALSE, digits=3)
}

# ============================================================================
hr("5. WEATHER — own vs counter, sensitivity by size")
wx <- do.call(rbind, lapply(ORD, function(s){
  d <- R5[R5$stage==s,]
  data.frame(stage=s, size=SIZE[[s]], own=mn(d$own_weather_wr),
             counter=mn(d$counter_weather_wr),
             own_minus_counter=mn(d$own_weather_wr)-mn(d$counter_weather_wr),
             sensitivity=mn(d$weather_sensitivity))
}))
print(wx, row.names=FALSE, digits=3)

cat("\n--- 5b. per-affinity own-weather effect (1v1, L1) ---\n")
d <- R5[R5$stage=="1v1" & R5$level==1,]
aff <- do.call(rbind, lapply(c("clear","cloudy","mist","rain","snow","thunder"), function(a){
  ar <- d[d$affinity==a,]
  data.frame(affinity=a, own=mn(ar$own_weather_wr), counter=mn(ar$counter_weather_wr),
             delta=mn(ar$own_weather_wr)-mn(ar$counter_weather_wr),
             sens=mn(ar$weather_sensitivity), n=length(unique(ar$piece_id)))
}))
print(aff, row.names=FALSE, digits=3)

# ============================================================================
hr("6. BEFORE/AFTER vs mega4 (pre-buff). mega5 filtered to LEVEL 1.")
load_ratings4 <- function() {
  rows <- list()
  for (st in c("1v1","team2-sample","team3-sample")) for (w in WEATHERS) {
    f <- file.path("results/mega4", sprintf("ratings_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE); d$stage <- LBL5[[st]]; rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}
R4 <- load_ratings4()
for (s in c("1v1","2v2","3v3")) {
  m4 <- R4[R4$stage==s,]; m5 <- R5[R5$stage==s & R5$level==1,]
  cat("\n", s, " (mega4 vs mega5-L1):\n", sep="")
  tab <- do.call(rbind, lapply(roles, function(rr){
    a <- mn(m4$win_rate[m4$role==rr]); b <- mn(m5$win_rate[m5$role==rr])
    if (is.nan(a) & is.nan(b)) return(NULL)
    data.frame(role=rr, m4_wr=a, m5_wr=b, delta=b-a)
  }))
  print(tab, row.names=FALSE, digits=3)
  cat(sprintf("  mage within-tier deficit: mega4=%.3f  mega5-L1=%.3f\n",
              within_tier_deficit(m4,"mage"), within_tier_deficit(m5,"mage")))
  cat(sprintf("  overall mage wr: mega4=%.3f  mega5-L1=%.3f\n",
              mn(m4$win_rate[m4$role=="mage"]), mn(m5$win_rate[m5$role=="mage"])))
}

# ============================================================================
hr("7. TIMEOUTS by role across sizes")
to <- sapply(ORD, function(s){
  d <- R5[R5$stage==s,]; sapply(roles, function(rr) mn(d$timeout_rate[d$role==rr]))
})
print(round(to,3))

# ============================================================================
hr("8. OUTLIERS — pooled mean across all stages (mega5)")
agg <- aggregate(cbind(win_rate, wr_delta) ~ piece_id+name+affinity+role+tier+level, R5, mn)
agg <- agg[order(agg$win_rate),]
cat("\nWEAKEST 10:\n"); print(head(agg[,c("name","affinity","role","tier","level","win_rate","wr_delta")],10), row.names=FALSE, digits=3)
cat("\nSTRONGEST 10:\n"); print(head(agg[order(-agg$win_rate),c("name","affinity","role","tier","level","win_rate","wr_delta")],10), row.names=FALSE, digits=3)
agg <- agg[order(agg$wr_delta),]
cat("\nMOST UNDER-TUNED (wr_delta), n>=20 pooled:\n")
print(head(agg[,c("name","affinity","role","tier","level","win_rate","wr_delta")],10), row.names=FALSE, digits=3)
cat("\nMOST OVER-TUNED (wr_delta):\n")
print(head(agg[order(-agg$wr_delta),c("name","affinity","role","tier","level","win_rate","wr_delta")],10), row.names=FALSE, digits=3)

# ---- save tables + cache ----
dir.create(file.path(OUTDIR,"tables"), showWarnings=FALSE)
write.csv(bal,  file.path(OUTDIR,"tables/m5_faction_by_size.csv"), row.names=FALSE)
write.csv(mt,   file.path(OUTDIR,"tables/m5_mage_tier_by_size.csv"), row.names=FALSE)
write.csv(wx,   file.path(OUTDIR,"tables/m5_weather_by_size.csv"), row.names=FALSE)
write.csv(aff,  file.path(OUTDIR,"tables/m5_weather_by_affinity.csv"), row.names=FALSE)
write.csv(as.data.frame(role_wr), file.path(OUTDIR,"tables/m5_role_wr_by_size.csv"))
write.csv(as.data.frame(role_wd), file.path(OUTDIR,"tables/m5_role_wd_by_size.csv"))
write.csv(as.data.frame(to), file.path(OUTDIR,"tables/m5_timeout_by_size.csv"))
write.csv(agg, file.path(OUTDIR,"tables/m5_piece_overall.csv"), row.names=FALSE)
saveRDS(list(R5=R5, bal=bal, mt=mt, wx=wx, aff=aff, role_wr=role_wr, role_wd=role_wd,
             to=to, agg=agg, samp=samp), file.path(OUTDIR,"cache_mega5.rds"))
cat("\n[saved] tables/m5_*.csv + cache_mega5.rds\n")
