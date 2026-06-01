# 02_results.R — per-battle win-curve, duration, decisiveness. + mega2 comparison.
source("reviews/mega_sim/00_load.R")
TAB <- file.path(OUTDIR,"tables"); say <- function(...) cat(...,"\n")
R <- load_ratings(); tmap <- piece_tier(R)
D <- load_results()
say("total battles:", nrow(D))

# power ratio for side A
D$Pa <- team_power(D$team_a, tmap)
D$Pb <- team_power(D$team_b, tmap)
D$pr <- D$Pa/(D$Pa+D$Pb)
D$winA <- ifelse(D$outcome=="win",1, ifelse(D$outcome=="loss",0, 0.5)) # draw=0.5

say("\n=== WIN-CURVE: P(win A) by power-ratio bin (all stages) ===")
br <- seq(0,1,by=0.05); D$bin <- cut(D$pr, br, include.lowest=TRUE)
wc <- aggregate(winA ~ bin + stage, D, function(x) c(p=mean(x), n=length(x)))
wc <- do.call(data.frame, wc)
write.csv(wc, file.path(TAB,"wincurve.csv"), row.names=FALSE)
# show parity region
mid <- aggregate(winA ~ stage, D[abs(D$pr-0.5)<0.025,], function(x) c(p=mean(x),n=length(x)))
say("-- near-parity (|pr-.5|<.025) win prob --"); print(do.call(data.frame,mid), row.names=FALSE)

# decisiveness: how wide is the contested band (win prob 0.2..0.8)?
say("\n=== CONTESTED BAND width (pr where 0.2<P(win)<0.8), 1v1 ===")
w1 <- wc[wc$stage=="1v1" & wc$winA.n>30,]
cb <- w1[w1$winA.p>0.2 & w1$winA.p<0.8,]
print(cb[,c("bin","winA.p","winA.n")], row.names=FALSE)

# draws / timeouts by stage
say("\n=== DRAWS & TIMEOUTS by stage ===")
dt <- aggregate(cbind(draw=outcome=="draw", timed=timed_out) ~ stage, D, mean)
print(dt, row.names=FALSE)

# duration distribution by stage
say("\n=== DURATION ticks by stage ===")
du <- aggregate(duration_ticks ~ stage, D, function(x) round(c(mean=mean(x), med=median(x), p90=quantile(x,.9), max=max(x))))
print(do.call(data.frame,du), row.names=FALSE)

# HP-remaining of winner = decisiveness (stomp index)
D$win_hp <- ifelse(D$outcome=="win", D$hp_remaining_a, ifelse(D$outcome=="loss", D$hp_remaining_b, NA))
say("\nmean winner HP remaining (stomp proxy) by stage:")
print(aggregate(win_hp ~ stage, D, mean), row.names=FALSE)

# ---------- MEGA2 vs MEGA3 role comparison (kit impact) ----------
say("\n=== MEGA2 vs MEGA3 role win_rate (1v1, all weathers) ===")
load_role <- function(dir){
  rows<-list()
  for(w in WEATHERS){f<-file.path(dir,sprintf("ratings_1v1_%s.csv",w)); if(file.exists(f)){d<-read.csv(f);rows[[w]]<-d}}
  d<-do.call(rbind,rows); aggregate(win_rate~role,d,mean)
}
m2<-load_role("results/mega2"); m3<-load_role("results/mega3")
cmp<-merge(m2,m3,by="role",suffixes=c("_m2","_m3")); cmp$delta<-cmp$win_rate_m3-cmp$win_rate_m2
print(cmp[order(cmp$delta),], row.names=FALSE)
write.csv(cmp, file.path(TAB,"mega2_vs_mega3_role.csv"), row.names=FALSE)

saveRDS(list(D=D, wc=wc), file.path(OUTDIR,"cache_results.rds"))
say("\n[done]")
