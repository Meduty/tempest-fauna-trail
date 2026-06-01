# 01_analysis.R — core statistics + tables. Base R. Writes tables/*.csv, prints summary.
source("reviews/mega_sim/00_load.R")
R <- load_ratings()
TAB <- file.path(OUTDIR, "tables")
wr <- function(x) round(x, 4)
say <- function(...) cat(..., "\n")

R$stage <- factor(R$stage, levels=c("1v1","2v2","3v3"))
R$kind  <- factor(R$kind)

say("================ A. AGGREGATE BALANCE ================")
# champion vs enemy mean win_rate per stage (each piece appears in mixed teams)
agg_kind <- aggregate(win_rate ~ stage + kind, R, function(x) c(mean=mean(x), sd=sd(x), n=length(x)))
print(do.call(data.frame, agg_kind))
say("")
# overall win_rate distribution per stage
for (s in levels(R$stage)) {
  x <- R$win_rate[R$stage==s]
  say(sprintf("stage %-3s  mean=%.3f  sd=%.3f  IQR=[%.3f,%.3f]  min=%.3f max=%.3f",
              s, mean(x), sd(x), quantile(x,.25), quantile(x,.75), min(x), max(x)))
}

say("\n================ B. ROLE BALANCE ================")
role_tab <- aggregate(cbind(win_rate, wr_delta) ~ role + stage, R, mean)
role_tab <- role_tab[order(role_tab$stage, role_tab$win_rate),]
print(role_tab, row.names=FALSE)
write.csv(role_tab, file.path(TAB,"role_balance.csv"), row.names=FALSE)
# role mean collapsed over stage+weather
say("\n-- role overall (all stages/weathers) --")
ro <- aggregate(cbind(win_rate, wr_delta, beta_deviation_pct) ~ role, R, mean)
print(ro[order(ro$win_rate),], row.names=FALSE)

say("\n================ C. AFFINITY BALANCE ================")
aff <- aggregate(cbind(win_rate, wr_delta) ~ affinity, R, mean)
print(aff[order(aff$win_rate),], row.names=FALSE)
write.csv(aff, file.path(TAB,"affinity_balance.csv"), row.names=FALSE)

say("\n================ D. TIER CURVE ================")
tier_tab <- aggregate(cbind(win_rate, wr_delta, mean_duration_ticks) ~ tier + stage, R, mean)
print(tier_tab, row.names=FALSE)
write.csv(tier_tab, file.path(TAB,"tier_curve.csv"), row.names=FALSE)
# correlation tier vs win_rate per stage
for (s in levels(R$stage)) {
  d <- R[R$stage==s,]
  say(sprintf("stage %-3s  cor(tier,win_rate)=%.3f  cor(tier,wr_delta)=%.3f",
              s, cor(d$tier,d$win_rate), cor(d$tier,d$wr_delta)))
}

say("\n================ E. WEATHER SENSITIVITY ================")
# per-piece win_rate spread across 6 weathers, within each stage
ws <- aggregate(win_rate ~ piece_id + name + affinity + role + tier + stage, R,
                function(x) max(x)-min(x))
names(ws)[ncol(ws)] <- "wr_range"
ws <- ws[order(-ws$wr_range),]
say("-- top 15 most weather-sensitive (win_rate range across weathers) --")
print(head(ws,15), row.names=FALSE)
write.csv(ws, file.path(TAB,"weather_sensitivity.csv"), row.names=FALSE)
say(sprintf("\nmean wr_range across pieces: %.3f   median: %.3f", mean(ws$wr_range), median(ws$wr_range)))

# affinity x weather: does a piece do better when weather matches its affinity?
say("\n-- own-weather advantage: mean win_rate when weather==affinity vs not --")
R$match_wx <- R$weather == R$affinity
# only affinities that are also weather states
wxset <- intersect(unique(R$affinity), WEATHERS)
sub <- R[R$affinity %in% wxset,]
mm <- aggregate(win_rate ~ match_wx + affinity, sub, mean)
print(mm, row.names=FALSE)
ov <- aggregate(win_rate ~ match_wx, sub, mean)
say(sprintf("OVERALL match=%.3f  nomatch=%.3f  delta=%+.3f",
            ov$win_rate[ov$match_wx], ov$win_rate[!ov$match_wx],
            ov$win_rate[ov$match_wx]-ov$win_rate[!ov$match_wx]))

say("\n================ F. OUTLIER PIECES ================")
# collapse to per-piece across weathers within stage, then overall
pp <- aggregate(cbind(win_rate, wr_delta, beta_deviation_pct, timeout_rate, mean_duration_ticks) ~
                  piece_id + name + affinity + role + tier + kind, R, mean)
pp <- pp[order(pp$win_rate),]
write.csv(pp, file.path(TAB,"piece_overall.csv"), row.names=FALSE)
say("-- 12 WEAKEST (mean win_rate, all stages/weathers) --")
print(head(pp[,c("name","affinity","role","tier","win_rate","wr_delta","timeout_rate")],12), row.names=FALSE)
say("\n-- 12 STRONGEST --")
print(head(pp[order(-pp$win_rate),c("name","affinity","role","tier","win_rate","wr_delta","timeout_rate")],12), row.names=FALSE)
say("\n-- 12 most OVERPERFORMING vs BT expectation (wr_delta) --")
print(head(pp[order(-pp$wr_delta),c("name","affinity","role","tier","win_rate","wr_delta")],12), row.names=FALSE)
say("\n-- 12 most UNDERPERFORMING vs BT expectation --")
print(head(pp[order(pp$wr_delta),c("name","affinity","role","tier","win_rate","wr_delta")],12), row.names=FALSE)

say("\n================ G. TIMEOUTS ================")
say(sprintf("pieces with timeout_rate>0: %d / %d (per stage/weather rows)",
            sum(R$timeout_rate>0), nrow(R)))
to <- aggregate(timeout_rate ~ stage, R, mean); print(to, row.names=FALSE)
tor <- aggregate(timeout_rate ~ role, R, mean); say("-- by role --"); print(tor[order(-tor$timeout_rate),], row.names=FALSE)
tot <- pp[order(-pp$timeout_rate),c("name","role","tier","timeout_rate","mean_duration_ticks")]
say("-- top 10 timeout pieces --"); print(head(tot,10), row.names=FALSE)

say("\n================ H. wr_delta dispersion per stage (balance health) ================")
for (s in levels(R$stage)) {
  d <- R[R$stage==s,]
  say(sprintf("stage %-3s  sd(wr_delta)=%.4f  mean|wr_delta|=%.4f  RMS=%.4f",
              s, sd(d$wr_delta), mean(abs(d$wr_delta)), sqrt(mean(d$wr_delta^2))))
}
saveRDS(list(R=R, pp=pp, ws=ws), file.path(OUTDIR,"cache.rds"))
say("\n[done] tables written to", TAB)
