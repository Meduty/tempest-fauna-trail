# 04_mega4.R — analyze mega4 (deterministic WR model, 5x sample) + mega3 vs mega4.
# mega4 incomplete: team3 missing snow+thunder at runtime. Loaders skip missing files.
source("reviews/mega_sim/00_load.R")
TAB<-file.path(OUTDIR,"tables"); P<-file.path(OUTDIR,"plots"); say<-function(...)cat(...,"\n")
M4<-"results/mega4"; M3<-"results/mega3"
stages<-c("1v1","2v2","3v3"); scol<-c("1v1"="#2c7fb8","2v2"="#41ab5d","3v3"="#d95f0e")

R4<-load_ratings(M4); R3<-load_ratings(M3)
say("mega4 rated rows:",nrow(R4)," cols:",ncol(R4))
say("mega4 coverage (rows per stage x weather):"); print(table(R4$stage,R4$weather))
say("mega3 has beta cols:", "beta" %in% names(R3), " | mega4 has beta cols:", "beta" %in% names(R4))

# ---- A. aggregate balance mega4 ----
say("\n=== A. mega4 aggregate balance (champ vs enemy) ===")
print(aggregate(win_rate~stage+kind,R4,mean),row.names=FALSE)
for(s in stages){x<-R4$win_rate[R4$stage==s]
  say(sprintf("stage %-3s mean=%.3f sd=%.3f min=%.3f max=%.3f",s,mean(x),sd(x),min(x),max(x)))}

# ---- B. role balance mega4 vs mega3 (1v1, all weathers; 1v1 fully done in both) ----
say("\n=== B. role win_rate mega3 -> mega4 (1v1, all 6 weathers) ===")
r3<-aggregate(win_rate~role,R3[R3$stage=="1v1",],mean)
r4<-aggregate(win_rate~role,R4[R4$stage=="1v1",],mean)
cmp<-merge(r3,r4,by="role",suffixes=c("_m3","_m4")); cmp$delta<-cmp$win_rate_m4-cmp$win_rate_m3
cmp<-cmp[order(cmp$delta),]; print(cmp,row.names=FALSE)
write.csv(cmp,file.path(TAB,"mega3_vs_mega4_role.csv"),row.names=FALSE)

# ---- C. tier curve + scaling calibration: did deterministic model fix wr_delta drift? ----
say("\n=== C. scaling calibration: cor(tier, wr_delta) mega3 vs mega4 (matched coverage) ===")
# restrict both to same stage/weather cells present in mega4
key4<-unique(paste(R4$stage,R4$weather))
R3m<-R3[paste(R3$stage,R3$weather) %in% key4,]
for(s in stages){
  d3<-R3m[R3m$stage==s,]; d4<-R4[R4$stage==s,]
  say(sprintf("stage %-3s  cor(tier,wrdelta): m3=%+.3f m4=%+.3f | sd(wrdelta): m3=%.3f m4=%.3f | cor(tier,winrate) m4=%.3f",
    s, cor(d3$tier,d3$wr_delta), cor(d4$tier,d4$wr_delta),
    sd(d3$wr_delta), sd(d4$wr_delta), cor(d4$tier,d4$win_rate)))}

# ---- D. mage crisis: still broken under bigger sample? ----
say("\n=== D. role overall mega4 (matched cells) vs mega3 ===")
ro4<-aggregate(win_rate~role,R4,mean); ro3<-aggregate(win_rate~role,R3m,mean)
rc<-merge(ro3,ro4,by="role",suffixes=c("_m3","_m4")); rc$delta<-rc$win_rate_m4-rc$win_rate_m3
print(rc[order(rc$win_rate_m4),],row.names=FALSE)
say(sprintf("\nmage within-tier deficit (1v1) mega4: %.3f",{
  d<-R4[R4$stage=="1v1",]
  tt<-merge(aggregate(win_rate~tier,d[d$role=="mage",],mean),
            aggregate(win_rate~tier,d[d$role!="mage",],mean),by="tier")
  mean(tt$win_rate.y-tt$win_rate.x)}))

# ---- E. weather effect: did the model change wake weather up? ----
say("\n=== E. own-weather advantage mega4 vs mega3 ===")
owncalc<-function(R){R$m<-R$weather==R$affinity
  sub<-R[R$affinity %in% intersect(unique(R$affinity),WEATHERS),]
  o<-aggregate(win_rate~m,sub,mean); o$win_rate[o$m]-o$win_rate[!o$m]}
ws_range<-function(R){a<-aggregate(win_rate~piece_id+stage,R,function(x)max(x)-min(x)); mean(a$win_rate)}
say(sprintf("own-weather delta: mega3=%.4f  mega4=%.4f",owncalc(R3m),owncalc(R4)))
say(sprintf("mean per-piece wr range across weathers: mega3=%.4f  mega4=%.4f (note: mega4 team3 only 4 wx)",ws_range(R3m),ws_range(R4)))

# ---- F. outliers mega4 ----
say("\n=== F. mega4 outliers (per-piece mean, matched cells) ===")
pp4<-aggregate(cbind(win_rate,wr_delta,timeout_rate)~piece_id+name+role+tier+affinity,R4,mean)
pp4<-pp4[order(pp4$win_rate),]
write.csv(pp4,file.path(TAB,"mega4_piece_overall.csv"),row.names=FALSE)
say("-- 8 weakest --"); print(head(pp4[,c("name","role","tier","win_rate","wr_delta")],8),row.names=FALSE)
say("-- 8 strongest --"); print(head(pp4[order(-pp4$win_rate),c("name","role","tier","win_rate","wr_delta")],8),row.names=FALSE)

# join mega3 & mega4 per-piece win_rate to find biggest movers
say("\n=== G. biggest per-piece movers mega3 -> mega4 (1v1) ===")
p3<-aggregate(win_rate~piece_id+name+role+tier,R3[R3$stage=="1v1",],mean)
p4<-aggregate(win_rate~piece_id+name+role+tier,R4[R4$stage=="1v1",],mean)
mv<-merge(p3,p4,by=c("piece_id","name","role","tier"),suffixes=c("_m3","_m4"))
mv$delta<-mv$win_rate_m4-mv$win_rate_m3
say("-- 6 biggest risers --");print(head(mv[order(-mv$delta),c("name","role","tier","win_rate_m3","win_rate_m4","delta")],6),row.names=FALSE)
say("-- 6 biggest fallers --");print(head(mv[order(mv$delta),c("name","role","tier","win_rate_m3","win_rate_m4","delta")],6),row.names=FALSE)
say(sprintf("\nmedian |per-piece shift| m3->m4 (1v1): %.4f  (sample 10x bigger -> less noise)",median(abs(mv$delta))))

saveRDS(list(R4=R4,R3m=R3m,cmp=cmp,pp4=pp4,mv=mv),file.path(OUTDIR,"cache_mega4.rds"))
say("\n[done]")
