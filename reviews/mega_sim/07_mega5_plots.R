# 07_mega5_plots.R — headline figures for the mega5 (results/mega_10v10) report.
# Base R graphics only. Run after 06_mega5.R. Writes plots/m5_*.png.

source("reviews/mega_sim/00_load.R")
OUTDIR <- "reviews/mega_sim"; PLOTS <- file.path(OUTDIR,"plots")
dir.create(PLOTS, showWarnings=FALSE)
C <- readRDS(file.path(OUTDIR,"cache_mega5.rds"))
R5 <- C$R5; ORD <- levels(R5$stage); SIZE <- seq_along(ORD)
px <- function(f) file.path(PLOTS, f)

# --- 1. role wr_delta compression vs team size ---
png(px("m5_01_role_wrdelta_vs_size.png"), 1000, 640, res=120)
par(mar=c(4,4,3,7))
rd <- C$role_wd  # roles x sizes
cols <- c(mage="#d62728", warrior="#1f77b4", marksman="#2ca02c",
          assassin="#9467bd", bruiser="#ff7f0e", hybrid="#8c564b", support="#17becf")
matplot(SIZE, t(rd), type="o", pch=19, lty=1, lwd=2,
        col=cols[rownames(rd)], xaxt="n", xlab="team size", ylab="wr_delta (tuning residual)",
        main="Role imbalance compresses with team size")
axis(1, SIZE, ORD); abline(h=0, lty=2, col="grey50")
legend("topright", rownames(rd), col=cols[rownames(rd)], lwd=2, pch=19, bty="n", cex=.8)
dev.off()

# --- 2. variance shrink + timeout rise vs size (dual axis) ---
png(px("m5_02_variance_timeout_vs_size.png"), 1000, 600, res=120)
par(mar=c(4,4,3,4))
plot(C$bal$size, C$bal$sd_wr, type="o", pch=19, col="#1f77b4", lwd=2,
     xlab="team size", ylab="sd(per-piece win_rate)", ylim=c(0,0.28),
     main="Win-rate spread collapses — but timeouts explain part of it")
par(new=TRUE)
plot(C$bal$size, C$bal$timeout, type="o", pch=17, col="#d62728", lwd=2,
     axes=FALSE, xlab="", ylab="", ylim=c(0,0.4))
axis(4, col="#d62728", col.axis="#d62728"); mtext("timeout (draw) rate", 4, 2.5, col="#d62728")
legend("right", c("sd(win_rate)","timeout rate"), col=c("#1f77b4","#d62728"),
       lwd=2, pch=c(19,17), bty="n")
dev.off()

# --- 3. level effect (win_rate + wr_delta) across sizes ---
png(px("m5_03_level_effect.png"), 1100, 560, res=120)
par(mfrow=c(1,2), mar=c(4,4,3,1))
lv_wr <- sapply(ORD, function(s){ d<-R5[R5$stage==s,]; sapply(1:3, function(l) mean(d$win_rate[d$level==l],na.rm=TRUE)) })
lv_wd <- sapply(ORD, function(s){ d<-R5[R5$stage==s,]; sapply(1:3, function(l) mean(d$wr_delta[d$level==l],na.rm=TRUE)) })
lcol <- c("#2ca02c","#ff7f0e","#d62728")
matplot(SIZE, t(lv_wr), type="o", pch=19, lty=1, lwd=2, col=lcol, xaxt="n",
        xlab="team size", ylab="win_rate", main="Win rate by champion level")
axis(1,SIZE,ORD); abline(h=.5,lty=2,col="grey60"); legend("topright",paste0("L",1:3),col=lcol,lwd=2,pch=19,bty="n")
matplot(SIZE, t(lv_wd), type="o", pch=19, lty=1, lwd=2, col=lcol, xaxt="n",
        xlab="team size", ylab="wr_delta", main="Level on-budget residual")
axis(1,SIZE,ORD); abline(h=0,lty=2,col="grey60"); legend("topright",paste0("L",1:3),col=lcol,lwd=2,pch=19,bty="n")
dev.off()

# --- 4. mage deficit vs size + before/after ---
png(px("m5_04_mage_deficit.png"), 1000, 600, res=120)
par(mar=c(4,4,3,1))
plot(C$mt$size, C$mt$within_tier_def, type="o", pch=19, col="#d62728", lwd=2,
     xlab="team size", ylab="within-tier mage deficit (non-mage wr - mage wr)",
     main="Mage deficit: shrinks with team size; halved vs pre-buff", ylim=c(0,0.21))
# mega4 pre-buff anchors (from 06 digest): 1v1 .198, 2v2 .105, 3v3 .070
points(1:3, c(.198,.105,.070), pch=4, col="grey30", lwd=2, cex=1.4)
lines(1:3, c(.198,.105,.070), col="grey30", lty=3)
abline(h=0,lty=2,col="grey60")
legend("topright", c("mega5 (post-buff, all levels)","mega4 (pre-buff, L1)"),
       col=c("#d62728","grey30"), pch=c(19,4), lwd=2, lty=c(1,3), bty="n")
dev.off()

# --- 5. weather still inert: own-off advantage by affinity, mega4 vs mega5 ---
png(px("m5_05_weather_inert.png"), 1000, 600, res=120)
WEA <- c("clear","cloudy","mist","rain","snow","thunder")
weff <- function(dir){
  rows<-list(); for(w in WEA){f<-file.path(dir,sprintf("ratings_1v1_%s.csv",w)); if(file.exists(f)){d<-read.csv(f);d$weather<-w;rows[[w]]<-d}}
  R<-do.call(rbind,rows); ps<-unique(R$piece_id); o<-data.frame()
  for(p in ps){s<-R[R$piece_id==p,];aff<-s$affinity[1];wr<-setNames(s$win_rate,s$weather)
    if(!(aff%in%names(wr)))next; o<-rbind(o,data.frame(affinity=aff,adv=wr[[aff]]-mean(wr[names(wr)!=aff])))}
  aggregate(adv~affinity,o,mean)
}
a4<-weff("results/mega4"); a5<-weff("results/mega_10v10")
m<-merge(a4,a5,by="affinity",suffixes=c("4","5")); m<-m[match(WEA,m$affinity),]
par(mar=c(4,4,3,1)); bp<-barplot(t(as.matrix(m[,c("adv4","adv5")])), beside=TRUE,
   names.arg=m$affinity, col=c("grey60","#d62728"), ylim=c(-0.01,0.04),
   ylab="own-weather advantage (own wr - off wr)",
   main="Weather still inert: +0.015 own-advantage, unchanged by the buff")
abline(h=0); abline(h=mean(a5$adv), lty=2, col="#d62728")
legend("topleft", c("mega4 (pre-buff)","mega5 (post-buff)"), fill=c("grey60","#d62728"), bty="n")
dev.off()

cat("[plots] wrote m5_01..m5_05 to", PLOTS, "\n")
