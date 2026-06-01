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

# --- load all ratings (per-piece, per stage+weather) ---
load_ratings <- function() {
  rows <- list()
  for (st in STAGES) for (w in WEATHERS) {
    f <- file.path(MEGA, sprintf("ratings_%s_%s.csv", st, w))
    if (!file.exists(f)) next
    d <- read.csv(f, stringsAsFactors=FALSE)
    d$stage <- STAGE_LBL[[st]]; d$weather <- w
    rows[[paste(st,w)]] <- d
  }
  do.call(rbind, rows)
}

# --- load all per-battle results ---
load_results <- function() {
  rows <- list()
  for (st in STAGES) for (w in WEATHERS) {
    f <- file.path(MEGA, sprintf("results_%s_%s.csv", st, w))
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
