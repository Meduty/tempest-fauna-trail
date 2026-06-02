# 05_mega4_plots.R — plots for the corrected-model (mega4) integration.
source("reviews/mega_sim/00_load.R")
P<-file.path(OUTDIR,"plots"); C<-readRDS(file.path(OUTDIR,"cache_mega4.rds"))
R4<-C$R4; R3m<-C$R3m; pp4<-C$pp4
png_<-function(f,w=1100,h=750)png(file.path(P,f),width=w,height=h,res=130)
stages<-c("1v1","2v2","3v3"); scol<-c("1v1"="#2c7fb8","2v2"="#41ab5d","3v3"="#d95f0e")

# 11. expected_wr bug fix: wr_delta vs tier, mega3 (buggy BT) vs mega4 (deterministic)
png_("11_wrdelta_calibration_fix.png",1300,650)
par(mfrow=c(1,2))
for(tag in c("m3","m4")){
  D<-if(tag=="m3") R3m else R4
  ttl<-if(tag=="m3")"mega3: BT model (buggy)\ncor(tier,wr_delta)=+0.55" else "mega4: power-threshold (fixed)\ncor(tier,wr_delta)=-0.40"
  plot(jitter(D$tier),D$wr_delta,pch=19,col=adjustcolor(scol[D$stage],0.3),cex=.5,
       ylim=c(-0.5,0.5),xlab="tier",ylab="wr_delta",main=ttl)
  abline(h=0,lty=2); abline(lm(wr_delta~tier,D),col="black",lwd=2)
}
dev.off()

# 12. role win_rate mega3 vs mega4 (robustness: 10x sample, ~identical)
png_("12_role_m3_vs_m4.png")
cmp<-aggregate(win_rate~role,R4,mean); c3<-aggregate(win_rate~role,R3m,mean)
m<-merge(c3,cmp,by="role",suffixes=c("_m3","_m4"))
roles<-c("mage","assassin","warrior","marksman","bruiser","hybrid")
m<-m[match(roles,m$role),]
mat<-rbind(m3=m$win_rate_m3,m4=m$win_rate_m4)
barplot(mat,beside=TRUE,names.arg=roles,las=2,col=c("#9ecae1","#08519c"),
        legend.text=c("mega3","mega4 (5x sample)"),args.legend=list(x="topleft"),
        ylab="mean win_rate",main="Role balance robust to 5x sample\n(deltas < 0.002 -- mega3 was converged)")
abline(h=0.5,lty=2)
dev.off()

# 13. mage wr_delta under fixed model: low-by-design vs genuine underperformers
png_("13_mage_fixed_model.png",1100,800)
mg<-pp4[pp4$role=="mage",]; mg<-mg[order(mg$wr_delta),]
cols<-ifelse(mg$wr_delta < -0.08,"#d7301f", ifelse(mg$wr_delta>0.08,"#1a9850","#bdbdbd"))
bp<-barplot(mg$wr_delta,horiz=TRUE,col=cols,las=1,names.arg=mg$name,cex.names=0.55,
        xlab="wr_delta (corrected model)",main="Mages under fixed expected_wr:\nred = genuine underperformer, grey = just low-power (expected)")
abline(v=0,lwd=1); abline(v=c(-0.08,0.08),lty=3,col="grey50")
dev.off()
cat("mega4 plots written\n"); print(grep("^1[123]",list.files(P),value=TRUE))
