# 12_mega7_plots.R — headline figures for the mega9 (results/mega/mega9) report.
# Base R graphics only. Run after 11_mega7.R. Writes plots/m9_*.png.
# Run from repo root: Rscript reviews/mega_sim/12_mega7_plots.R

source("reviews/mega_sim/00_load.R")
OUTDIR <- "reviews/mega_sim"; PLOTS <- file.path(OUTDIR,"plots")
dir.create(PLOTS, showWarnings=FALSE)
C  <- readRDS(file.path(OUTDIR,"cache_mega9.rds"))
R9 <- C$R9; CB <- C$CB; ORD <- C$ORD9_pres; SIZE <- C$SIZE9[ORD]
px <- function(f) file.path(PLOTS, f)
mn <- function(x) mean(x, na.rm=TRUE)

# 9-role palette for the re-axed mega9 roster (mega8's warrior/hybrid are gone;
# tank/spellblade/spellslinger/swashbuckler are new — keep all so role figures
# colour every piece instead of falling back to grey).
ROLE_COLS <- c(mage="#d62728", marksman="#2ca02c", assassin="#9467bd",
               bruiser="#ff7f0e", support="#17becf", tank="#7f7f7f",
               spellblade="#e377c2", spellslinger="#bcbd22", swashbuckler="#1f77b4")
WX_COLS <- c(clear="#f6c90e", cloudy="#7f7f7f", mist="#bcbd22",
             rain="#1f77b4", snow="#aec7e8", thunder="#9467bd")
sizes <- as.numeric(SIZE)

# ---- 1. ROLE wr_delta by team size -----------------------------------------
png(px("m9_01_role_wrdelta_vs_size.png"), 1050, 660, res=120)
par(mar=c(4,4,3,7))
rd <- C$role_wd9; cols <- ROLE_COLS[rownames(rd)]
matplot(sizes, t(rd), type="o", pch=19, lty=1, lwd=2, col=cols, xaxt="n",
        xlab="team size", ylab="wr_delta (tuning residual)",
        main="Role tuning residuals by team size (mega9)",
        ylim=range(rd, na.rm=TRUE)+c(-0.02,0.02))
axis(1, sizes, ORD); abline(h=0, lty=2, col="grey50")
legend("topright", rownames(rd), col=cols, lwd=2, pch=19, bty="n", cex=.8,
       xpd=TRUE, inset=c(-0.16,0))
dev.off()

# ---- 2. VARIANCE + timeout vs size (dual axis) ------------------------------
png(px("m9_02_variance_timeout_vs_size.png"), 1000, 600, res=120)
par(mar=c(4,4.5,3,4.5))
plot(C$bal9$size, C$bal9$sd_wr, type="o", pch=19, col="#1f77b4", lwd=2,
     xlab="team size", ylab="sd(per-piece win_rate)", ylim=c(0,0.30),
     main="Win-rate spread and timeout rate vs team size (mega9)")
par(new=TRUE)
plot(C$bal9$size, C$bal9$timeout, type="o", pch=17, col="#d62728", lwd=2,
     axes=FALSE, xlab="", ylab="", ylim=c(0,0.55))
axis(4, col.axis="#d62728"); mtext("timeout rate", 4, 2.8, col="#d62728")
legend("right", c("sd(win_rate)","timeout rate"), col=c("#1f77b4","#d62728"),
       lwd=2, pch=c(19,17), bty="n")
dev.off()

# ---- 3. MAGE DEFICIT by size: mega8 vs mega9 --------------------------------
png(px("m9_03_mage_deficit_by_size.png"), 1000, 620, res=120)
par(mar=c(4,4,3,1))
wtd9 <- C$mt9$within_tier_def
R8 <- C$R8
wtdf <- function(d) {
  tiers <- sort(unique(d$tier)); diffs <- c()
  for (t in tiers) { a <- d$win_rate[d$tier==t & d$role=="mage"]
    b <- d$win_rate[d$tier==t & d$role!="mage"]
    if (length(a)&length(b)) diffs <- c(diffs, mn(b)-mn(a)) }
  mn(diffs)
}
m8sizes <- c("2v2"=2,"3v3"=3,"4v4"=4,"5v5"=5,"6v6"=6,"7v7"=7,"8v8"=8,"9v9"=9,"10v10"=10)
wtd8 <- if(!is.null(R8)) sapply(names(m8sizes), function(s) wtdf(R8[as.character(R8$stage)==s,])) else NULL
plot(sizes, wtd9, type="o", pch=19, col="#d62728", lwd=2,
     xlab="team size", ylab="within-tier mage deficit (non-mage − mage wr)",
     main="Mage deficit by team size (mega8 vs mega9)", xaxt="n",
     ylim=range(c(wtd9, wtd8, 0), na.rm=TRUE)+c(-0.01,0.01))
axis(1, sizes, ORD)
if(!is.null(wtd8)) { lines(m8sizes, wtd8, type="o", pch=4, col="grey40", lty=3, lwd=2) }
abline(h=0, lty=2, col="grey60")
legend("topright", c("mega9","mega8"), col=c("#d62728","grey40"),
       pch=c(19,4), lwd=2, lty=c(1,3), bty="n")
dev.off()

# ---- 4. ROLE WIN-RATE HEATMAP by size --------------------------------------
png(px("m9_04_role_wr_heatmap.png"), 1100, 520, res=120)
par(mar=c(5,6,3,5))
wr <- C$role_wr9; nr <- nrow(wr); nc <- ncol(wr)
image(1:nc, 1:nr, t(wr), col=colorRampPalette(c("#d73027","#fee08b","#1a9850"))(64),
      axes=FALSE, xlab="team size", ylab="", zlim=c(0.3,0.7),
      main="Role win_rate by size (mega9)")
axis(1,1:nc,colnames(wr)); axis(2,1:nr,rownames(wr),las=2)
for (i in 1:nc) for (j in 1:nr)
  text(i,j,sprintf("%.2f",wr[j,i]),cex=0.7,
       col=ifelse(abs(wr[j,i]-0.5)>0.10,"white","black"))
usr <- par("usr"); xr <- usr[2]+0.3; ys <- seq(usr[3],usr[4],length=64)
rect(xr, ys[-64], xr+0.25, ys[-1],
     col=colorRampPalette(c("#d73027","#fee08b","#1a9850"))(63), border=NA, xpd=TRUE)
text(xr+0.4, usr[3], "0.3", cex=0.7, xpd=TRUE, adj=c(0,0))
text(xr+0.4, usr[4], "0.7", cex=0.7, xpd=TRUE, adj=c(0,1))
dev.off()

# ---- 5. LEVEL EFFECT (L1/L2/L3) --------------------------------------------
png(px("m9_05_level_effect.png"), 1100, 560, res=120)
par(mfrow=c(1,2), mar=c(4,4,3,1))
lv_wr <- sapply(ORD, function(s){d<-R9[R9$stage==s,];sapply(1:3,function(l)mn(d$win_rate[d$level==l]))})
lv_wd <- sapply(ORD, function(s){d<-R9[R9$stage==s,];sapply(1:3,function(l)mn(d$wr_delta[d$level==l]))})
lcol <- c("#2ca02c","#ff7f0e","#d62728")
matplot(sizes,t(lv_wr),type="o",pch=19,lty=1,lwd=2,col=lcol,xaxt="n",
        xlab="team size",ylab="win_rate",main="Win rate by champion level")
axis(1,sizes,ORD); abline(h=.5,lty=2,col="grey60")
legend("topright",paste0("L",1:3),col=lcol,lwd=2,pch=19,bty="n",cex=.9)
matplot(sizes,t(lv_wd),type="o",pch=19,lty=1,lwd=2,col=lcol,xaxt="n",
        xlab="team size",ylab="wr_delta",main="Level tuning residual")
axis(1,sizes,ORD); abline(h=0,lty=2,col="grey60")
legend("topright",paste0("L",1:3),col=lcol,lwd=2,pch=19,bty="n",cex=.9)
dev.off()

# ---- 6. WEATHER own-advantage by size + per-affinity (2v2) -----------------
png(px("m9_06_weather_effects.png"), 1100, 560, res=120)
par(mfrow=c(1,2), mar=c(4,4,3,1))
rng <- range(c(C$wx9$own_minus_counter, C$wx9$own_minus_clear, 0), na.rm=TRUE)
plot(C$wx9$size, C$wx9$own_minus_counter, type="o", pch=19, col="#1f77b4", lwd=2,
     xlab="team size", ylab="win-rate advantage", xaxt="n",
     main="Own-weather advantage by size (RAW)", ylim=rng+c(-0.01,0.02))
axis(1, C$wx9$size)
points(C$wx9$size, C$wx9$own_minus_clear, type="o", pch=15, col="#2ca02c", lwd=2)
abline(h=0,lty=2,col="grey50")
legend("topright", c("own − counter","own − clear(baseline)"),
       col=c("#1f77b4","#2ca02c"), lwd=2, pch=c(19,15), bty="n", cex=.85)
aff9 <- C$aff9
bp <- barplot(aff9$own_minus_counter, names.arg=aff9$affinity, col=WX_COLS[aff9$affinity],
              ylim=range(c(aff9$own_minus_counter, aff9$own_minus_clear,0))+c(-0.01,0.02),
              ylab="own − counter wr", main="Per-affinity own-weather edge (RAW, pooled)")
abline(h=0); text(bp, aff9$own_minus_counter+0.003,
                  sprintf("%.3f",aff9$own_minus_counter), cex=0.7)
dev.off()

# ---- 7. OUTLIER SCATTER: wr_delta vs win_rate (combined) -------------------
png(px("m9_07_outlier_scatter.png"), 1050, 680, res=120)
par(mar=c(4,4,3,1))
rcol <- ROLE_COLS[CB$role]; rcol[is.na(rcol)] <- "grey50"
plot(CB$win_rate, CB$wr_delta, col=adjustcolor(rcol,alpha.f=0.6), pch=19, cex=0.8,
     xlab="pooled win_rate (combined)", ylab="pooled wr_delta",
     main="Piece outliers: win_rate vs wr_delta (mega9 combined, all stages+wx)")
abline(h=0,lty=2,col="grey40"); abline(v=0.5,lty=2,col="grey40")
ex <- CB[CB$wr_delta < -0.17 | CB$wr_delta > 0.18 | CB$win_rate<0.27 | CB$win_rate>0.85,]
text(ex$win_rate, ex$wr_delta, ex$name, cex=0.52, pos=3)
legend("bottomright", names(ROLE_COLS)[names(ROLE_COLS) %in% CB$role],
       col=ROLE_COLS[names(ROLE_COLS) %in% CB$role], pch=19, bty="n", cex=.8)
dev.off()

# ---- 8. MAGE per-piece wr_delta (combined), sorted -------------------------
mc <- CB[CB$role=="mage",]
mc <- aggregate(wr_delta~name+tier, mc, mn)  # pool levels for readability
mc <- mc[order(mc$wr_delta),]
png(px("m9_08_mage_wrdelta.png"), 1100, 900, res=120)
par(mar=c(4,9,3,2))
n <- nrow(mc); y <- seq_len(n)
cols <- ifelse(mc$wr_delta<0, "#d62728", "#2ca02c")
plot(mc$wr_delta, y, pch=19, col=cols, yaxt="n", xlab="wr_delta (level-pooled)",
     ylab="", main="Mage wr_delta per piece (mega9 combined)",
     xlim=range(mc$wr_delta)+c(-0.02,0.02))
axis(2, y, sprintf("%s T%d", mc$name, mc$tier), las=2, cex.axis=0.55)
segments(0, y, mc$wr_delta, y, col=adjustcolor(cols,alpha.f=0.5))
abline(v=0, lty=2, col="grey40")
dev.off()

# ---- 9. wr_delta BOXPLOTS by role and by tier (combined) -------------------
# How odd are the residuals? Boxplots show the full per-piece spread, not just
# the mean — the IQR/whiskers/outlier dots make the distribution legible.
png(px("m9_09_wrdelta_boxplots.png"), 1200, 560, res=120)
par(mfrow=c(1,2), mar=c(5,4,3,1))
rd_ord <- names(sort(tapply(CB$wr_delta, CB$role, mn)))
bcol <- ROLE_COLS[rd_ord]
boxplot(wr_delta~factor(role, levels=rd_ord), data=CB, col=bcol, las=2,
        ylab="pooled wr_delta", xlab="", outpch=19, outcex=0.5, outcol="grey30",
        main="wr_delta distribution by role (mega9 combined)")
abline(h=0, lty=2, col="grey40")
boxplot(wr_delta~tier, data=CB, col="#9ecae1", outpch=19, outcex=0.5,
        outcol="grey30", xlab="tier", ylab="pooled wr_delta",
        main="wr_delta distribution by tier")
abline(h=0, lty=2, col="grey40")
dev.off()

# ---- 10. wr_delta DISTRIBUTION: histogram+density + per-piece spread --------
png(px("m9_10_wrdelta_distribution.png"), 1200, 560, res=120)
par(mfrow=c(1,2), mar=c(4,4,3,1))
wd <- CB$wr_delta
h <- hist(wd, breaks=30, col="#c6dbef", border="white", freq=FALSE,
          xlab="pooled wr_delta", main="wr_delta distribution (combined)")
lines(density(wd, na.rm=TRUE), col="#08519c", lwd=2)
xs <- seq(min(wd), max(wd), length=200)
lines(xs, dnorm(xs, mean(wd), sd(wd)), col="#d62728", lwd=2, lty=2)  # normal ref
abline(v=0, lty=3, col="grey40")
legend("topright", c("density","normal ref"), col=c("#08519c","#d62728"),
       lwd=2, lty=c(1,2), bty="n", cex=.85)
qqnorm(wd, pch=19, cex=0.5, col=adjustcolor("#08519c",alpha.f=0.5),
       main="Normal Q-Q of wr_delta")
qqline(wd, col="#d62728", lwd=2)
dev.off()

# ---- 11. CONTEXT-VOLATILITY (excess wr_delta sd) lollipop, top 25 ----------
sp <- C$spread9
if (!is.null(sp) && nrow(sp)) {
  top <- head(sp[order(-sp$excess_sd),], 25)
  top <- top[order(top$excess_sd),]              # ascending for bottom-up bars
  png(px("m9_11_spread_outliers.png"), 1100, 900, res=120)
  par(mar=c(4,11,3,2))
  y <- seq_len(nrow(top))
  cols <- ROLE_COLS[top$role]; cols[is.na(cols)] <- "grey50"
  plot(top$excess_sd, y, pch=19, col=cols, yaxt="n",
       xlab="excess wr_delta sd (observed - binomial-noise sd)", ylab="",
       main="Most context-volatile pieces (mega9)",
       xlim=c(0, max(top$excess_sd)*1.05))
  axis(2, y, sprintf("%s T%d", top$name, top$tier), las=2, cex.axis=0.55)
  segments(0, y, top$excess_sd, y, col=adjustcolor(cols, alpha.f=0.5))
  legend("bottomright", names(ROLE_COLS)[names(ROLE_COLS) %in% top$role],
         col=ROLE_COLS[names(ROLE_COLS) %in% top$role], pch=19, bty="n", cex=.8)
  dev.off()
}

# ---- 12. WIN-RATE & wr_delta vs QUANTIZED POWER (rowed boxplots) ------------
# Default mega draws teams at random, so high-P pieces meet low-P pieces and
# win_rate(P) SHOULD climb — that climb is the deterministic power model, not a
# finding. Left panel overlays expected_wr (the power-threshold prediction) so
# the boxes can be read against the curve they're supposed to track. Right panel
# is wr_delta = win_rate - expected_wr: the residual after removing that curve,
# so it should sit flat on 0 across every P bin if scaling is tuned.
pdat <- CB[is.finite(CB$expected_power) & CB$expected_power > 0, ]
# One box per DISTINCT expected_power. P = power(tier,level) = 1.5^((T-1)/2+(L-1)),
# so tier and level COLLIDE onto shared powers (T3/L1 == T1/L2 == 2.0, etc): the
# 30 (tier,level) combos map to only ~19 distinct P. That natural quantization is
# the right x-axis — no arbitrary binning.
pdat$pbin <- factor(round(pdat$expected_power, 4))
lvls <- levels(pdat$pbin); at <- seq_along(lvls)
# Per-bin mean of the model prediction + the bin's exact P, for the overlay.
exp_by_bin <- tapply(pdat$expected_wr, pdat$pbin, mn)[lvls]
blab <- sprintf("%.1f", as.numeric(lvls))

png(px("m9_12_wr_vs_power.png"), 1250, 560, res=120)
par(mfrow=c(1,2), mar=c(5,4,3,1))

# Left: win_rate boxes + expected_wr curve
boxplot(win_rate~pbin, data=pdat, at=at, col="#c6dbef", xaxt="n",
        outpch=19, outcex=0.4, outcol="grey40",
        xlab="expected_power (one box per distinct tier/level power)", ylab="win_rate",
        main="win_rate vs power, with expected_wr curve (mega9 combined)")
axis(1, at, blab, las=2, cex.axis=0.6)
lines(at, exp_by_bin, col="#d62728", lwd=2, type="o", pch=19)
abline(h=0.5, lty=3, col="grey50")
legend("topleft", c("expected_wr (power model)","0.5 ref"),
       col=c("#d62728","grey50"), lwd=2, lty=c(1,3), pch=c(19,NA), bty="n", cex=.8)

# Right: wr_delta boxes — residual after removing the curve, want flat on 0
boxplot(wr_delta~pbin, data=pdat, at=at, col="#9ecae1", xaxt="n",
        outpch=19, outcex=0.4, outcol="grey40",
        xlab="expected_power (one box per distinct tier/level power)",
        ylab="wr_delta (residual)",
        main="wr_delta vs power (residual after expected_wr)")
axis(1, at, blab, las=2, cex.axis=0.6)
abline(h=0, lty=2, col="#d62728", lwd=2)
dev.off()

cat("[plots] wrote m9_01..m9_12 to", PLOTS, "\n")
