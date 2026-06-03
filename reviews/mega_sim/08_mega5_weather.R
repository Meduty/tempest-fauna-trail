# 08_mega5_weather.R — the TWO weather systems, measured separately.
#
# Tempest has two decoupled weather systems (src/game/weather_effects.py):
#   1. Weather Favor  — node weather buffs/debuffs a piece by its affinity-vs-
#      weather ring relation (±15% stat pack). VARIES with node weather, so it
#      is visible in a cross-weather win-rate sweep (own vs off weather).
#   2. Affinity Clash — per-hit damage multiplier by attacker-affinity vs
#      DEFENDER-affinity (predator 1.30x ... prey 0.70x). WEATHER-INDEPENDENT,
#      so it is INVISIBLE to a cross-weather sweep and must be measured against
#      the OPPONENT's affinity instead.
#
# This script measures both, for mega5 (post-strengthen) and mega4 (pre-),
# and plots the Affinity Clash win curve. Replicates ring_relation() in R.
#
# Run: Rscript reviews/mega_sim/08_mega5_weather.R

OUTDIR <- "reviews/mega_sim"; PLOTS <- file.path(OUTDIR,"plots")
WEA <- c("clear","cloudy","mist","rain","snow","thunder")

# --- ring_relation, mirroring src/game/weather_effects.py --------------------
RING <- c("mist","cloudy","rain","snow","thunder")  # CYCLE_ORDER
REL_BY_DIST <- c("SELF","PRIMARY_PREDATOR","SECONDARY_PREDATOR",
                 "SECONDARY_PREY","PRIMARY_PREY")     # distance 0..4
ring_relation_vec <- function(a, b) {
  ia <- match(a, RING); ib <- match(b, RING)
  d <- (ia - ib) %% 5L
  rel <- REL_BY_DIST[d + 1L]
  rel[a == "clear" | b == "clear"] <- "NEUTRAL"
  rel
}

# piece_id -> affinity map from a ratings file (has all levels)
affinity_map <- function(dir) {
  d <- read.csv(file.path(dir, "ratings_1v1_clear.csv"), stringsAsFactors=FALSE)
  setNames(d$affinity, d$piece_id)
}

# --- Affinity Clash: 1v1 side-A win rate by ring relation (pooled weathers) --
# l1_only=TRUE restricts to level-1-vs-level-1 fights (bare ids, no "@") so the
# affinity signal isn't diluted by level mismatches — apples-to-apples vs mega4.
clash_by_relation <- function(dir, l1_only=FALSE) {
  amap <- affinity_map(dir)
  acc_w <- setNames(numeric(6), c(REL_BY_DIST, "NEUTRAL"))
  acc_n <- setNames(integer(6),  c(REL_BY_DIST, "NEUTRAL"))
  for (w in WEA) {
    f <- file.path(dir, sprintf("results_1v1_%s.csv", w))
    if (!file.exists(f)) next
    df <- read.csv(f, stringsAsFactors=FALSE)
    if (l1_only) df <- df[!grepl("@", df$team_a) & !grepl("@", df$team_b), ]
    rel <- ring_relation_vec(amap[df$team_a], amap[df$team_b])
    sc  <- ifelse(df$outcome=="win", 1, ifelse(df$outcome=="draw", 0.5, 0))
    aw <- tapply(sc, rel, sum); an <- tapply(sc, rel, length)
    for (k in names(aw)) { acc_w[k] <- acc_w[k] + aw[k]; acc_n[k] <- acc_n[k] + an[k] }
  }
  ord <- c("PRIMARY_PREDATOR","SECONDARY_PREDATOR","SELF","NEUTRAL",
           "SECONDARY_PREY","PRIMARY_PREY")
  data.frame(relation=ord, win_rate=as.numeric(acc_w[ord]/acc_n[ord]),
             n=as.integer(acc_n[ord]))
}
spread <- function(c) c$win_rate[c$relation=="PRIMARY_PREDATOR"] -
                      c$win_rate[c$relation=="PRIMARY_PREY"]

# --- Weather Favor: own-affinity-weather wr vs off-weather wr (cross-file) ----
favor_effect <- function(dir, stage="1v1") {
  rows <- list()
  for (w in WEA) {
    f <- file.path(dir, sprintf("ratings_%s_%s.csv", stage, w))
    if (file.exists(f)) { d <- read.csv(f, stringsAsFactors=FALSE); d$w <- w; rows[[w]] <- d }
  }
  R <- do.call(rbind, rows); adv <- c()
  for (p in unique(R$piece_id)) {
    s <- R[R$piece_id==p,]; aff <- s$affinity[1]; wr <- setNames(s$win_rate, s$w)
    if (aff %in% names(wr)) adv <- c(adv, wr[[aff]] - mean(wr[names(wr)!=aff]))
  }
  mean(adv)
}

cat("================ AFFINITY CLASH (system 2, weather-independent) ================\n")
c4    <- clash_by_relation("results/mega4")                    # all L1 already
c5L1  <- clash_by_relation("results/mega_10v10", l1_only=TRUE)  # apples-to-apples
c5all <- clash_by_relation("results/mega_10v10")                # diluted by levels
cmp <- data.frame(relation=c4$relation,
                  m4_L1=c4$win_rate, m5_L1=c5L1$win_rate, m5_all=c5all$win_rate,
                  n_m5_L1=c5L1$n)
print(cmp, row.names=FALSE, digits=3)
cat(sprintf("\nspread (predator - prey):  mega4 L1 = %.3f  ->  mega5 L1 = %.3f  (buff widened it)\n",
            spread(c4), spread(c5L1)))
cat(sprintf("           mega5 all-levels = %.3f  (level mismatches dilute affinity signal)\n",
            spread(c5all)))

cat("\n================ WEATHER FAVOR (system 1, node-weather stat pack) =============\n")
cat(sprintf("mega5 own-weather advantage (1v1) = %+.4f\n", favor_effect("results/mega_10v10")))
cat(sprintf("mega4 own-weather advantage (1v1) = %+.4f\n", favor_effect("results/mega4")))

# --- plot: Affinity Clash win curve, mega4 vs mega5 --------------------------
dir.create(PLOTS, showWarnings=FALSE)
png(file.path(PLOTS,"m5_06_affinity_clash.png"), 1050, 620, res=120)
par(mar=c(7,4,3,1))
ord <- c4$relation
M <- rbind(`mega4 (L1, pre-buff)`=c4$win_rate,
           `mega5 (L1, post-buff)`=c5L1$win_rate,
           `mega5 (all levels)`=c5all$win_rate)
barplot(M, beside=TRUE, names.arg=ord, col=c("grey65","#d62728","#f4a3a3"),
   ylim=c(0,0.70), las=2, ylab="side-A 1v1 win rate",
   main="Affinity Clash is strong; buff WIDENED it (L1 spread 0.25 -> 0.35)")
abline(h=0.5, lty=2, col="grey40")
legend("topright", rownames(M), fill=c("grey65","#d62728","#f4a3a3"), bty="n", cex=.85)
dev.off()
cat("\n[plot] wrote plots/m5_06_affinity_clash.png\n")

write.csv(cmp, file.path(OUTDIR,"tables/m5_affinity_clash.csv"), row.names=FALSE)
cat("[saved] tables/m5_affinity_clash.csv\n")
