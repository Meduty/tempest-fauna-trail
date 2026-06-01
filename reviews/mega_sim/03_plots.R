# 03_plots.R — base-R PNG plots into reviews/mega_sim/plots/
source("reviews/mega_sim/00_load.R")
P <- file.path(OUTDIR,"plots")
C <- readRDS(file.path(OUTDIR,"cache.rds"));        R<-C$R; pp<-C$pp; ws<-C$ws
CR<- readRDS(file.path(OUTDIR,"cache_results.rds")); D<-CR$D; wc<-CR$wc
stages <- c("1v1","2v2","3v3"); scol <- c("1v1"="#2c7fb8","2v2"="#41ab5d","3v3"="#d95f0e")
png_ <- function(f,w=1100,h=750) png(file.path(P,f), width=w, height=h, res=130)

# 1. win_rate distribution by stage (boxplot)
png_("01_winrate_dist_by_stage.png")
boxplot(win_rate~stage, R, col=scol[stages], ylab="win_rate", xlab="stage",
        main="Win-rate distribution by team size\n(spread shrinks as team averaging smooths imbalance)")
abline(h=0.5, lty=2, col="grey40"); grid(nx=NA, ny=NULL)
dev.off()

# 2. role balance — grouped bars by stage
png_("02_role_balance.png", 1200)
ro <- aggregate(win_rate~role+stage, R, mean)
roles <- c("mage","assassin","warrior","marksman","bruiser","hybrid")
m <- sapply(stages, function(s){d<-ro[ro$stage==s,]; d$win_rate[match(roles,d$role)]})
rownames(m)<-roles
barplot(t(m), beside=TRUE, col=scol[stages], legend.text=stages,
        args.legend=list(x="topleft"), ylab="mean win_rate", las=2,
        main="Role balance by team size  (mage broken low, hybrid runaway)")
abline(h=0.5, lty=2)
dev.off()

# 3. tier curve
png_("03_tier_curve.png")
plot(NA, xlim=c(1,10), ylim=c(0.1,1), xlab="tier", ylab="mean win_rate",
     main="Tier curve: the cliff (parity at tier ~6)")
for(s in stages){ d<-aggregate(win_rate~tier,R[R$stage==s,],mean)
  lines(d$tier,d$win_rate,col=scol[s],lwd=2,type="o",pch=19)}
abline(h=0.5,lty=2,col="grey40"); abline(v=6,lty=3,col="grey60")
legend("topleft",stages,col=scol[stages],lwd=2,pch=19)
dev.off()

# 4. win-curve (decisiveness cliff) from per-battle
png_("04_wincurve_powerratio.png")
plot(NA, xlim=c(0.2,0.8), ylim=c(0,1), xlab="power ratio  Pa/(Pa+Pb)",
     ylab="P(team A wins)", main="Win-curve vs power ratio: near step-function")
for(s in stages){ w<-wc[wc$stage==s & wc$winA.n>50,]
  x<-(as.numeric(sub("\\((.+),.*","\\1",w$bin))+as.numeric(sub(".*,(.+)]","\\1",w$bin)))/2
  lines(x,w$winA.p,col=scol[s],lwd=2,type="o",pch=19)}
abline(h=0.5,lty=2);abline(v=0.5,lty=3,col="grey60")
legend("topleft",stages,col=scol[stages],lwd=2,pch=19)
dev.off()

# 5. mega2 vs mega3 role delta
png_("05_mega2_vs_mega3_role.png")
cmp<-read.csv(file.path(OUTDIR,"tables","mega2_vs_mega3_role.csv"))
cmp<-cmp[order(cmp$delta),]
cols<-ifelse(cmp$delta<0,"#d7301f","#1a9850")
bp<-barplot(cmp$delta, names.arg=cmp$role, col=cols, las=2, ylab="Δ win_rate (mega3 - mega2)",
            main="Kit implementation impact on roles (1v1)\nmarksman/warrior recovered, mage crashed")
abline(h=0,lwd=1); text(bp, cmp$delta, sprintf("%+.2f",cmp$delta), pos=ifelse(cmp$delta<0,1,3),cex=.8)
dev.off()

# 6. wr_delta vs tier (scaling under-reward): high tier overperforms BT expectation
png_("06_wrdelta_vs_tier.png")
plot(jitter(R$tier), R$wr_delta, pch=19, col=adjustcolor(scol[R$stage],0.35), cex=.5,
     xlab="tier", ylab="wr_delta (actual - BT-expected)",
     main="Scaling mis-calibration: high tiers beat their power budget")
abline(h=0,lty=2); abline(lm(wr_delta~tier,R), col="black", lwd=2)
legend("topleft",stages,col=scol[stages],pch=19)
dev.off()

# 7. timeouts by role
png_("07_timeout_by_role.png")
tor<-aggregate(timeout_rate~role,R,mean); tor<-tor[order(tor$timeout_rate),]
barplot(tor$timeout_rate, names.arg=tor$role, las=2, col="#7570b3",
        ylab="mean timeout_rate", main="Stalemate risk by role\n(tanks can't close, mages can't kill)")
dev.off()

# 8. affinity balance + own-weather effect
png_("08_affinity.png", 1200)
par(mfrow=c(1,2))
aff<-aggregate(win_rate~affinity,R,mean); aff<-aff[order(aff$win_rate),]
barplot(aff$win_rate, names.arg=aff$affinity, las=2, col="#66c2a5", ylim=c(0,0.7),
        ylab="mean win_rate", main="Affinity balance"); abline(h=0.5,lty=2)
R$match<-R$weather==R$affinity; sub<-R[R$affinity %in% intersect(unique(R$affinity),WEATHERS),]
mm<-aggregate(win_rate~match+affinity,sub,mean)
affs<-unique(mm$affinity); mt<-sapply(affs,function(a)c(no=mm$win_rate[mm$affinity==a&!mm$match],yes=mm$win_rate[mm$affinity==a&mm$match]))
barplot(mt, beside=TRUE, col=c("#bdbdbd","#fc8d59"), legend.text=c("other wx","own wx"),
        las=2, ylab="win_rate", main="Own-weather advantage (tiny: +0.011)"); abline(h=0.5,lty=2)
dev.off()

# 9. mage deep-dive: win_rate vs tier, mage vs rest
png_("09_mage_deepdive.png")
d1<-R[R$stage=="1v1",]
mg<-aggregate(win_rate~tier,d1[d1$role=="mage",],mean)
rest<-aggregate(win_rate~tier,d1[d1$role!="mage",],mean)
plot(rest$tier,rest$win_rate,type="o",pch=19,col="#2c7fb8",lwd=2,ylim=c(0.1,1),
     xlab="tier",ylab="win_rate (1v1)",main="Mage role is broken at every tier")
lines(mg$tier,mg$win_rate,type="o",pch=17,col="#d7301f",lwd=2)
abline(h=0.5,lty=2); legend("topleft",c("non-mage","mage"),col=c("#2c7fb8","#d7301f"),lwd=2,pch=c(19,17))
dev.off()

# 10. piece scatter: win_rate vs tier, label extreme outliers
png_("10_piece_outliers.png", 1200, 800)
plot(jitter(pp$tier), pp$win_rate, pch=19, cex=0.7,
     col=adjustcolor(ifelse(pp$role=="mage","#d7301f","#3182bd"),0.6),
     xlab="tier", ylab="mean win_rate (all stages/weathers)",
     main="Per-piece outliers (red=mage)")
abline(h=0.5,lty=2)
ext<-pp[pp$win_rate>0.83 | pp$win_rate<0.21 | abs(pp$wr_delta)>0.24,]
text(ext$tier, ext$win_rate, ext$name, cex=0.6, pos=3)
dev.off()

cat("plots written:\n"); print(list.files(P))
