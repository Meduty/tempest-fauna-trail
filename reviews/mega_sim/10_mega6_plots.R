# 10_mega6_plots.R — headline figures for the mega6 (results/mega_10v10_2) report.
# Base R graphics only. Run after 09_mega6.R. Writes plots/m6_*.png.
# Run from repo root: Rscript reviews/mega_sim/10_mega6_plots.R

source("reviews/mega_sim/00_load.R")
OUTDIR <- "reviews/mega_sim"; PLOTS <- file.path(OUTDIR,"plots")
dir.create(PLOTS, showWarnings=FALSE)
C <- readRDS(file.path(OUTDIR,"cache_mega6.rds"))
R6 <- C$R6; ORD <- C$ORD6_pres; SIZE <- C$SIZE6[ORD]
px <- function(f) file.path(PLOTS, f)
mn <- function(x) mean(x, na.rm=TRUE)

ROLE_COLS <- c(mage="#d62728", warrior="#1f77b4", marksman="#2ca02c",
               assassin="#9467bd", bruiser="#ff7f0e", hybrid="#8c564b",
               support="#17becf")
WX_COLS <- c(clear="#f6c90e", cloudy="#7f7f7f", mist="#bcbd22",
             rain="#1f77b4", snow="#aec7e8", thunder="#9467bd")

# ---- 1. ROLE wr_delta by team size (compression / divergence) ---------------
png(px("m6_01_role_wrdelta_vs_size.png"), 1050, 660, res=120)
par(mar=c(4,4,3,7))
rd <- C$role_wd6
cols <- ROLE_COLS[rownames(rd)]
sizes <- as.numeric(SIZE)
matplot(sizes, t(rd), type="o", pch=19, lty=1, lwd=2, col=cols,
        xaxt="n", xlab="team size", ylab="wr_delta (tuning residual)",
        main="Role tuning residuals by team size (mega6, post INT-fix)",
        ylim=range(rd, na.rm=TRUE) + c(-0.02, 0.02))
axis(1, sizes, ORD); abline(h=0, lty=2, col="grey50")
legend("topright", rownames(rd), col=cols, lwd=2, pch=19, bty="n", cex=.8,
       xpd=TRUE, inset=c(-0.18,0))
dev.off()

# ---- 2. VARIANCE shrink + timeout by size (dual axis) -----------------------
png(px("m6_02_variance_timeout_vs_size.png"), 1000, 600, res=120)
par(mar=c(4,4.5,3,4.5))
plot(C$bal6$size, C$bal6$sd_wr, type="o", pch=19, col="#1f77b4", lwd=2,
     xlab="team size", ylab="sd(per-piece win_rate)", ylim=c(0,0.28),
     main="Win-rate spread and timeout rate vs team size")
par(new=TRUE)
plot(C$bal6$size, C$bal6$timeout, type="o", pch=17, col="#d62728", lwd=2,
     axes=FALSE, xlab="", ylab="", ylim=c(0, 0.55))
axis(4, col.axis="#d62728"); mtext("timeout rate", 4, 2.8, col="#d62728")
legend("right", c("sd(win_rate)","timeout rate"), col=c("#1f77b4","#d62728"),
       lwd=2, pch=c(19,17), bty="n")
dev.off()

# ---- 3. MAGE DEFICIT: mega5 L1 vs mega6 L1 (before/after INT-fix) -----------
# Anchors from mega5 analysis (from 06_mega5.R cache / report)
# mega5 within-tier deficit: 2v2≈0.119, 3v3≈0.084, 4v4≈0.068 (post-buff but pre-fix)
# mega4 pre-buff anchors: 1v1=0.198, 2v2=0.105, 3v3=0.070 (from mega3 report)
m5_anchors <- data.frame(
  size=c(2,3,4), stage=c("2v2","3v3","4v4"),
  deficit=sapply(c("2v2","3v3","4v4"), function(s) {
    d <- C$R5c[C$R5c$stage==s & C$R5c$level==1,]
    if (!nrow(d)) return(NA)
    tiers <- sort(unique(d$tier)); diffs <- c()
    for (t in tiers) { a <- d$win_rate[d$tier==t & d$role=="mage"]
      b <- d$win_rate[d$tier==t & d$role!="mage"]
      if (length(a) & length(b)) diffs <- c(diffs, mn(b)-mn(a)) }
    mn(diffs)
  })
)

m6_def <- C$mt6[C$mt6$stage %in% c("2v2","3v3","4v4"), c("size","within_tier_def")]

png(px("m6_03_mage_deficit_before_after.png"), 1000, 620, res=120)
par(mar=c(4,4,3,1))
ymax <- max(c(m5_anchors$deficit, m6_def$within_tier_def), na.rm=TRUE) + 0.02
plot(m6_def$size, m6_def$within_tier_def, type="o", pch=19, col="#d62728", lwd=2,
     xlab="team size", ylab="within-tier mage deficit (non-mage wr − mage wr)",
     main="Mage deficit: INT-fix effect (mega5 pre-fix vs mega6 post-fix)",
     xlim=c(1.5,4.5), ylim=c(0, ymax))
points(m5_anchors$size, m5_anchors$deficit, pch=4, col="grey30", lwd=2, cex=1.4)
lines(m5_anchors$size, m5_anchors$deficit, col="grey30", lty=3, lwd=2)
abline(h=0, lty=2, col="grey60")
legend("topright",
       c("mega6 L1 (post INT-fix)","mega5 L1 (post-initial-buff, pre-fix)"),
       col=c("#d62728","grey30"), pch=c(19,4), lwd=2, lty=c(1,3), bty="n")
dev.off()

# ---- 4. ROLE WIN-RATE HEATMAP by size (mega6) -------------------------------
png(px("m6_04_role_wr_heatmap.png"), 1050, 520, res=120)
par(mar=c(5,6,3,5))
wr <- C$role_wr6
nr <- nrow(wr); nc <- ncol(wr)
image(1:nc, 1:nr, t(wr), col=colorRampPalette(c("#d73027","#fee08b","#1a9850"))(64),
      axes=FALSE, xlab="team size", ylab="",
      main="Role win_rate by size (mega6)", zlim=c(0.3,0.7))
axis(1, 1:nc, colnames(wr))
axis(2, 1:nr, rownames(wr), las=2)
for (i in 1:nc) for (j in 1:nr)
  text(i, j, sprintf("%.2f", wr[j,i]), cex=0.75,
       col=ifelse(abs(wr[j,i]-0.5)>0.10,"white","black"))
image.plot <- function(z, col, ...) {
  rng <- range(z); steps <- seq(rng[1], rng[2], length=5)
  legend("right", legend=round(steps,2), fill=colorRampPalette(col)(5), bty="n",
         title="win_rate", xpd=TRUE)
}
# simple scale bar via segments
usr <- par("usr")
xr <- usr[2]+0.3; ys <- seq(usr[3],usr[4],length=64)
rect(xr, ys[-64], xr+0.25, ys[-1], col=colorRampPalette(c("#d73027","#fee08b","#1a9850"))(63),
     border=NA, xpd=TRUE)
text(xr+0.4, usr[3], "0.3", cex=0.7, xpd=TRUE, adj=c(0,0))
text(xr+0.4, usr[4], "0.7", cex=0.7, xpd=TRUE, adj=c(0,1))
dev.off()

# ---- 5. LEVEL EFFECT (L1/L2/L3) win_rate and wr_delta ----------------------
png(px("m6_05_level_effect.png"), 1100, 560, res=120)
par(mfrow=c(1,2), mar=c(4,4,3,1))
lv_wr <- sapply(ORD, function(s) {
  d <- R6[R6$stage==s,]; sapply(1:3, function(l) mn(d$win_rate[d$level==l]))
})
lv_wd <- sapply(ORD, function(s) {
  d <- R6[R6$stage==s,]; sapply(1:3, function(l) mn(d$wr_delta[d$level==l]))
})
lcol <- c("#2ca02c","#ff7f0e","#d62728")
sizes2 <- as.numeric(SIZE)
matplot(sizes2, t(lv_wr), type="o", pch=19, lty=1, lwd=2, col=lcol, xaxt="n",
        xlab="team size", ylab="win_rate", main="Win rate by champion level")
axis(1,sizes2,ORD); abline(h=.5,lty=2,col="grey60")
legend("topright",paste0("L",1:3),col=lcol,lwd=2,pch=19,bty="n",cex=.9)
matplot(sizes2, t(lv_wd), type="o", pch=19, lty=1, lwd=2, col=lcol, xaxt="n",
        xlab="team size", ylab="wr_delta", main="Level tuning residual (on-budget)")
axis(1,sizes2,ORD); abline(h=0,lty=2,col="grey60")
legend("topright",paste0("L",1:3),col=lcol,lwd=2,pch=19,bty="n",cex=.9)
dev.off()

# ---- 6. WEATHER OWN-ADVANTAGE by size + by affinity (2v2) -------------------
png(px("m6_06_weather_effects.png"), 1100, 560, res=120)
par(mfrow=c(1,2), mar=c(4,4,3,1))
# 6a: own minus counter by size
plot(C$wx6$size, C$wx6$own_minus_counter, type="o", pch=19, col="#1f77b4", lwd=2,
     xlab="team size", ylab="own-weather wr − counter-weather wr",
     main="Own-weather advantage by team size", ylim=c(-0.02,0.08))
abline(h=0, lty=2, col="grey50")
points(C$wx6$size, C$wx6$sensitivity, type="o", pch=17, col="#ff7f0e", lwd=2)
legend("topright", c("own - counter wr","mean sensitivity"), col=c("#1f77b4","#ff7f0e"),
       lwd=2, pch=c(19,17), bty="n")
# 6b: per-affinity in 2v2
aff6 <- C$aff6
if (!is.null(aff6) && nrow(aff6)) {
  bp <- barplot(aff6$delta, names.arg=aff6$affinity,
               col=WX_COLS[aff6$affinity], ylim=c(-0.03,0.1),
               ylab="own wr − counter wr", main="Per-affinity own-weather delta (2v2 L1)")
  abline(h=0); abline(h=mn(aff6$delta), lty=2, col="grey50")
  text(bp, aff6$delta+0.004, sprintf("%.3f",aff6$delta), cex=0.75)
}
dev.off()

# ---- 7. OUTLIER SCATTER: wr_delta vs win_rate (mega6) ----------------------
png(px("m6_07_outlier_scatter.png"), 1000, 650, res=120)
par(mar=c(4,4,3,1))
agg6 <- C$agg6
rcol <- ROLE_COLS[agg6$role]
rcol[is.na(rcol)] <- "grey50"
plot(agg6$win_rate, agg6$wr_delta,
     col=adjustcolor(rcol, alpha.f=0.55), pch=19, cex=0.7,
     xlab="pooled win_rate", ylab="pooled wr_delta",
     main="Piece outliers: win_rate vs wr_delta (mega6, all sizes pooled)")
abline(h=0, lty=2, col="grey40"); abline(v=0.5, lty=2, col="grey40")
# label extremes
extreme <- agg6[agg6$wr_delta < -0.25 | agg6$wr_delta > 0.25 |
                agg6$win_rate < 0.25  | agg6$win_rate > 0.75, ]
text(extreme$win_rate, extreme$wr_delta, extreme$name, cex=0.55, pos=3)
legend("topright", names(ROLE_COLS), col=ROLE_COLS, pch=19, bty="n", cex=.75)
dev.off()

# ---- 8. MAGE COMPARISON: individual wr_delta mega5 vs mega6 (2v2 L1) -------
m5m <- C$R5c[C$R5c$stage=="2v2" & C$R5c$level==1 & C$R5c$role=="mage",]
m6m <- C$R6[C$R6$stage=="2v2" & C$R6$level==1 & C$R6$role=="mage",]
a5 <- aggregate(wr_delta~name+tier, m5m, mn)
a6 <- aggregate(wr_delta~name+tier, m6m, mn)
mcmp <- merge(a5, a6, by=c("name","tier"), suffixes=c("_m5","_m6"))
mcmp <- mcmp[order(mcmp$wr_delta_m5),]

png(px("m6_08_mage_individual_shift.png"), 1100, 700, res=120)
par(mar=c(5,9,3,2))
n <- nrow(mcmp)
y <- seq_len(n)
plot(NA, xlim=c(min(c(mcmp$wr_delta_m5,mcmp$wr_delta_m6))-0.02,
                max(c(mcmp$wr_delta_m5,mcmp$wr_delta_m6))+0.02),
     ylim=c(0.5,n+0.5), yaxt="n", xlab="wr_delta",
     main="Mage wr_delta per piece: mega5 (grey) vs mega6 (red) — 2v2 L1")
axis(2, y, sprintf("%s T%d", mcmp$name, mcmp$tier), las=2, cex.axis=0.7)
segments(mcmp$wr_delta_m5, y, mcmp$wr_delta_m6, y, col="grey60", lwd=1.5)
points(mcmp$wr_delta_m5, y, pch=4, col="grey40", cex=0.8, lwd=1.5)
points(mcmp$wr_delta_m6, y, pch=19, col="#d62728", cex=0.8)
abline(v=0, lty=2, col="grey40")
legend("bottomright", c("mega5 (pre INT-fix)","mega6 (post INT-fix)"),
       col=c("grey40","#d62728"), pch=c(4,19), lwd=c(1.5,NA), bty="n")
dev.off()

cat("[plots] wrote m6_01..m6_08 to", PLOTS, "\n")
