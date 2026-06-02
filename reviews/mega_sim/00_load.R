# 00_load.R — load mega3 ratings + results, attach stage/weather, derive power.
# Sourced by analysis scripts. Base R only.

MEGA   <- "results/mega3"
OUTDIR <- "reviews/mega_sim"
WEATHERS <- c("clear","cloudy","mist","rain","snow","thunder")
STAGES   <- c("1v1","team2-sample","team3-sample")
STAGE_LBL <- c("1v1"="1v1", "team2-sample"="2v2", "team3-sample"="3v3")

# --- power scaling (mirror src/game/scaling.py) ---
# P(T,L) = 2 ^ ((T-1)/3 + triplings(L)); level always 1 in ratings -> triplings(1)=0
power <- function(tier, level=1) {
  tri <- ifelse(level>=3, 1, ifelse(level==2, 0.585, 0))  # log2(3)=1.585 step; lvl proxy
  2 ^ ((tier-1)/3 + tri)
}

# --- load all ratings (per-piece, per stage+weather). dir defaults to MEGA. ---
# schema-tolerant: mega4 dropped beta/beta_ratio/beta_deviation_pct (BT->deterministic).
# keeps only the common column set so rbind across runs works.
COMMON_RATING_COLS <- c("piece_id","name","affinity","role","tier","level","kind",
  "n_matches","mean_duration_ticks","win_rate","expected_wr","wr_delta",
  "expected_power","timeout_rate","stage","weather")
load_ratings <- function(dir=MEGA, common=FALSE) {
  rows <- list()
  for (st in STAGES) for (w in WEATHERS) {
    f <- file.path(dir, sprintf("ratings_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE)
    d$stage <- STAGE_LBL[[st]]; d$weather <- w
    if (common) d <- d[, intersect(COMMON_RATING_COLS, names(d))]
    rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}

# --- load all per-battle results. dir defaults to MEGA. ---
load_results <- function(dir=MEGA) {
  rows <- list()
  for (st in STAGES) for (w in WEATHERS) {
    f <- file.path(dir, sprintf("results_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE)
    d$stage <- STAGE_LBL[[st]]; d$weather <- w
    rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}

# piece_id -> tier lookup (from any ratings file)
piece_tier <- function(R) {
  u <- unique(R[,c("piece_id","tier")])
  setNames(u$tier, u$piece_id)
}

# sum power of a "|"-joined team string given tier lookup
team_power <- function(teamstr, tmap) {
  vapply(strsplit(teamstr, "\\|"), function(ids) {
    sum(power(tmap[ids]), na.rm=TRUE)
  }, numeric(1))
}

cat("loaded helpers: power(), load_ratings(), load_results(), team_power()\n")
