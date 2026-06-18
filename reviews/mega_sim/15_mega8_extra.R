# 15_mega8_extra.R — supplementary analyses for the mega8 report:
#   (A) Roster health index  — wr_delta balance bands (Riot-style) + Gini.
#   (B) Combat pacing         — mean_duration_ticks vs power / level / timeout.
#   (C) Behavioral archetypes — k-means clustering of pieces on outcome features
#       ("beyond win rates", arXiv 2502.01250), checked against designer roles.
# Base R only. Run from repo root after 13_mega8.R:
#   Rscript reviews/mega_sim/15_mega8_extra.R
# Writes plots/m8_13..m8_15.png + tables/m8_health.csv, m8_archetypes.csv.

OUTDIR <- "reviews/mega_sim"; PLOTS <- file.path(OUTDIR,"plots")
TABLES <- file.path(OUTDIR,"tables")
dir.create(PLOTS, showWarnings=FALSE); dir.create(TABLES, showWarnings=FALSE)
px <- function(f) file.path(PLOTS, f)
CB <- read.csv("results/mega/mega8/ratings_combined.csv", stringsAsFactors=FALSE)
CB <- CB[is.finite(CB$expected_power) & CB$expected_power > 0, ]
ROLE_COLS <- c(mage="#d62728", warrior="#1f77b4", marksman="#2ca02c",
               assassin="#9467bd", bruiser="#ff7f0e", hybrid="#8c564b",
               support="#17becf", tank="#7f7f7f", spellblade="#e377c2",
               spellslinger="#bcbd22", swashbuckler="#2ca0aa")

# ---- (A) ROSTER HEALTH: wr_delta balance bands -----------------------------
wd <- CB$wr_delta
gini <- function(x){x<-sort(x);n<-length(x);2*sum((1:n)*x)/(n*sum(x))-(n+1)/n}
health <- data.frame(
  metric=c("within +/-0.05 (tuned)","within +/-0.10 (acceptable)",
           "beyond +/-0.10 (outlier)","sd(wr_delta)","sd(win_rate)","Gini(win_rate)"),
  value=c(sprintf("%.1f%%",100*mean(abs(wd)<=0.05)),
          sprintf("%.1f%%",100*mean(abs(wd)<=0.10)),
          sprintf("%.1f%% (%d pieces)",100*mean(abs(wd)>0.10),sum(abs(wd)>0.10)),
          sprintf("%.3f",sd(wd)), sprintf("%.3f",sd(CB$win_rate)),
          sprintf("%.3f",gini(CB$win_rate))))
write.csv(health, file.path(TABLES,"m8_health.csv"), row.names=FALSE)
cat("=== (A) ROSTER HEALTH ===\n"); print(health, row.names=FALSE)

png(px("m8_13_health_band.png"), 1100, 560, res=120)
par(mar=c(4,4,3,1))
h <- hist(wd, breaks=40, col="grey85", border="white",
          xlab="pooled wr_delta (power-adjusted residual)", ylab="pieces",
          main="Roster health: power-adjusted residual vs balance bands (mega8)")
# Riot-style bands translated to residual space: tuned / acceptable / outlier
abline(v=c(-0.05,0.05), col="#2ca02c", lwd=2, lty=2)
abline(v=c(-0.10,0.10), col="#ff7f0e", lwd=2, lty=3)
abline(v=0, col="grey40")
legend("topright", c("+/-0.05 tuned (84%)","+/-0.10 acceptable (97%)"),
       col=c("#2ca02c","#ff7f0e"), lwd=2, lty=c(2,3), bty="n", cex=.85)
dev.off()

# ---- (B) COMBAT PACING: mean_duration_ticks --------------------------------
cat("\n=== (B) PACING ===\n")
cat(sprintf("duration: median %d ticks (cap 12000); range %d-%d\n",
   round(median(CB$mean_duration_ticks)), round(min(CB$mean_duration_ticks)),
   round(max(CB$mean_duration_ticks))))
cat(sprintf("cor(power,duration)=%.3f  cor(win_rate,duration)=%.3f  cor(timeout,duration)=%.3f\n",
   cor(CB$expected_power,CB$mean_duration_ticks), cor(CB$win_rate,CB$mean_duration_ticks),
   cor(CB$timeout_rate,CB$mean_duration_ticks)))
dur_by_lv <- tapply(CB$mean_duration_ticks, CB$level, mean)
cat("mean duration by level:", paste(sprintf("L%d=%d",1:3,round(dur_by_lv)),collapse="  "),"\n")

png(px("m8_14_pacing.png"), 1200, 560, res=120)
par(mfrow=c(1,2), mar=c(4,4,3,1))
lvcol <- c("#2ca02c","#ff7f0e","#d62728")[CB$level]
plot(CB$expected_power, CB$mean_duration_ticks, log="x", pch=19, cex=0.7,
     col=adjustcolor(lvcol,0.6), xlab="expected_power (log)", ylab="mean fight duration (ticks)",
     main="Pacing: median flat, high-power fans out (finishers vs grinders)")
abline(lm(CB$mean_duration_ticks~log(CB$expected_power)), col="#08519c", lwd=2)
legend("topright", paste0("L",1:3), col=c("#2ca02c","#ff7f0e","#d62728"), pch=19, bty="n", cex=.8)
plot(CB$mean_duration_ticks, CB$timeout_rate, pch=19, cex=0.7, col=adjustcolor("#1f77b4",0.5),
     xlab="mean fight duration (ticks)", ylab="timeout rate",
     main="Duration is the timeout driver (r=0.92)")
abline(v=12000, lty=3, col="grey50")
dev.off()

# ---- (C) BEHAVIORAL ARCHETYPES: k-means beyond designer roles --------------
cat("\n=== (C) ARCHETYPE CLUSTERING ===\n")
feat <- scale(CB[, c("win_rate","wr_delta","timeout_rate","weather_sensitivity",
                     "mean_duration_ticks","expected_power")])
set.seed(42)
K <- 6
km <- kmeans(feat, centers=K, nstart=25)
CB$cluster <- km$cluster
# dominant designer role per cluster + purity
arche <- do.call(rbind, lapply(sort(unique(CB$cluster)), function(k){
  d <- CB[CB$cluster==k,]
  tt <- sort(table(d$role), decreasing=TRUE)
  data.frame(cluster=k, n=nrow(d),
             win_rate=round(mean(d$win_rate),3), wr_delta=round(mean(d$wr_delta),3),
             timeout=round(mean(d$timeout_rate),3),
             dur=round(mean(d$mean_duration_ticks)),
             power=round(mean(d$expected_power),1),
             top_role=names(tt)[1], purity=round(tt[1]/nrow(d),2))
}))
write.csv(arche, file.path(TABLES,"m8_archetypes.csv"), row.names=FALSE)
print(arche, row.names=FALSE)
# role->cluster spread: does one designer role split across behavior clusters?
cat("\nrole x cluster contingency (how designer roles map to behavior):\n")
print(table(CB$role, CB$cluster))

# PCA projection for the cluster plot
pc <- prcomp(feat)
png(px("m8_15_archetypes.png"), 1100, 720, res=120)
par(mar=c(4,4,3,1))
ccol <- c("#1f77b4","#d62728","#2ca02c","#9467bd","#ff7f0e","#17becf")[CB$cluster]
plot(pc$x[,1], pc$x[,2], col=adjustcolor(ccol,0.7), pch=19, cex=0.9,
     xlab=sprintf("PC1 (%.0f%% var)",100*summary(pc)$importance[2,1]),
     ylab=sprintf("PC2 (%.0f%% var)",100*summary(pc)$importance[2,2]),
     main="Behavioral archetypes: k-means on outcome features (mega8)")
# cluster centroids labelled by dominant role
for(k in 1:K){ cen <- colMeans(pc$x[CB$cluster==k,1:2,drop=FALSE])
  text(cen[1],cen[2], sprintf("C%d:%s",k,arche$top_role[arche$cluster==k]),
       font=2, cex=0.8) }
dev.off()

# ---- (D) BOXPLOT FLIERS: named outliers under each boxplot ------------------
# R's boxplot draws fliers (beyond 1.5*IQR per group) as unlabelled dots. These
# are the pieces deviating most from their cohort = prime tuning candidates.
# Recover them for all four report boxplots (m8_12 power x2, m8_09 role + tier).
cat("\n=== (D) BOXPLOT FLIERS ===\n")
flier_rows <- function(v, g){
  out <- integer(0)
  for(lvl in unique(g)){
    idx <- which(g==lvl); st <- boxplot.stats(v[idx])$out
    for(o in st){ out <- c(out, idx[which(v[idx]==o)[1]]) }
  }
  out
}
collect <- function(plot_id, panel, v, g){
  fi <- flier_rows(v, g); if(!length(fi)) return(NULL)
  data.frame(plot=plot_id, panel=panel, group=as.character(g[fi]),
             name=CB$name[fi], tier=CB$tier[fi], level=CB$level[fi],
             role=CB$role[fi], value=round(v[fi],4), win_rate=round(CB$win_rate[fi],3))
}
pbin <- factor(round(CB$expected_power,4))
flo <- rbind(
  collect("m8_12","win_rate~power", CB$win_rate, pbin),
  collect("m8_12","wr_delta~power", CB$wr_delta, pbin),
  collect("m8_09","wr_delta~role",  CB$wr_delta, CB$role),
  collect("m8_09","wr_delta~tier",  CB$wr_delta, factor(CB$tier)))
write.csv(flo, file.path(TABLES,"m8_boxplot_outliers.csv"), row.names=FALSE)
cat(sprintf("wrote %d named fliers across 4 boxplots -> tables/m8_boxplot_outliers.csv\n", nrow(flo)))
print(table(flo$plot, flo$panel))

cat("\n[extra] wrote m8_13/14/15 + tables/m8_health.csv, m8_archetypes.csv, m8_boxplot_outliers.csv\n")
