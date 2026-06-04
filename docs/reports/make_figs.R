#!/usr/bin/env Rscript
# Generates vector PDF figures for the weather-impact report from the sim runs.
# Data is the deterministic output of tools/simulation/weather_impact.py
# (size 8; A/B/AB matrices @30 samples, density curves @40 samples, --both-sides).

suppressPackageStartupMessages(library(ggplot2))

outdir <- file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(), value = TRUE))), "figs")
if (length(outdir) == 0 || is.na(outdir)) outdir <- "figs"
dir.create(outdir, showWarnings = FALSE, recursive = TRUE)

own <- c(0, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100)

# --- marginal effect (delta) of own-affinity density, per mechanism -----------
favor_dm   <- c(0, 0.283, 0.300, 0.517, 0.350, 0.617, 0.517, 0.850, 0.983)  # A, control-subtracted
clash_dm   <- c(0, 0.145, 0.313, 0.313, 0.375, 0.440, 0.467, 0.497, 0.508)  # Bd, vs j=0
compound_dm<- c(0, 0.175, 0.272, 0.300, 0.328, 0.333, 0.333, 0.333, 0.333)  # ABd, vs j=0

dm <- rbind(
  data.frame(own = own, dmargin = favor_dm,    sys = "Weather Favor (A)"),
  data.frame(own = own, dmargin = clash_dm,    sys = "Affinity Clash (B)"),
  data.frame(own = own, dmargin = compound_dm, sys = "Favor + Clash (AB)")
)
dm$sys <- factor(dm$sys, levels = c("Weather Favor (A)", "Affinity Clash (B)", "Favor + Clash (AB)"))

pal <- c("Weather Favor (A)" = "#1b7837",
         "Affinity Clash (B)" = "#2166ac",
         "Favor + Clash (AB)" = "#b2182b")

p1 <- ggplot(dm, aes(own, dmargin, colour = sys)) +
  geom_line(linewidth = 1) + geom_point(size = 1.8) +
  scale_colour_manual(values = pal, name = NULL) +
  scale_x_continuous(breaks = seq(0, 100, 25)) +
  labs(x = "Own-affinity pieces in team (%)",
       y = expression(Delta * " mean HP margin")) +
  theme_minimal(base_size = 11) +
  theme(legend.position = c(0.02, 0.98), legend.justification = c(0, 1),
        legend.background = element_rect(fill = "white", colour = NA),
        panel.grid.minor = element_blank())
ggsave(file.path(outdir, "density_dmargin.pdf"), p1, width = 6.2, height = 3.4)

# --- absolute win% vs density -------------------------------------------------
favor_w    <- c(50.0, 60.0, 65.0, 63.3, 56.7, 78.3, 68.3, 80.0, 68.3)  # A favor%
clash_w    <- c(74.0, 81.2, 89.8, 89.8, 92.8, 96.0, 97.2, 99.0, 99.5)  # Bd win%
compound_w <- c(83.0, 92.2, 97.0, 98.2, 99.8, 100.0, 100.0, 100.0, 100.0)  # ABd win%

w <- rbind(
  data.frame(own = own, win = favor_w,    sys = "Weather Favor (A)"),
  data.frame(own = own, win = clash_w,    sys = "Affinity Clash (B)"),
  data.frame(own = own, win = compound_w, sys = "Favor + Clash (AB)")
)
w$sys <- factor(w$sys, levels = names(pal))

p2 <- ggplot(w, aes(own, win, colour = sys)) +
  geom_hline(yintercept = 50, linetype = "dashed", colour = "grey60") +
  geom_line(linewidth = 1) + geom_point(size = 1.8) +
  scale_colour_manual(values = pal, name = NULL) +
  scale_x_continuous(breaks = seq(0, 100, 25)) +
  scale_y_continuous(limits = c(40, 100), breaks = seq(40, 100, 10)) +
  labs(x = "Own-affinity pieces in team (%)", y = "Player win rate (%)") +
  theme_minimal(base_size = 11) +
  theme(legend.position = c(0.98, 0.02), legend.justification = c(1, 0),
        legend.background = element_rect(fill = "white", colour = NA),
        panel.grid.minor = element_blank())
ggsave(file.path(outdir, "density_winrate.pdf"), p2, width = 6.2, height = 3.4)

# --- System B: win% by ring relation (mono-stack saturation) ------------------
rel <- data.frame(
  relation = c("primary\npredator", "secondary\npredator",
               "secondary\nprey", "primary\nprey"),
  win = c(99.0, 81.7, 17.3, 3.7)
)
rel$relation <- factor(rel$relation, levels = rel$relation)

p3 <- ggplot(rel, aes(relation, win, fill = win)) +
  geom_col(width = 0.66) +
  geom_hline(yintercept = 50, linetype = "dashed", colour = "grey50") +
  geom_text(aes(label = sprintf("%.0f%%", win)), vjust = -0.4, size = 3.4) +
  scale_fill_gradient2(low = "#b2182b", mid = "#f7f7f7", high = "#2166ac",
                       midpoint = 50, guide = "none") +
  scale_y_continuous(limits = c(0, 108), breaks = seq(0, 100, 25)) +
  labs(x = NULL, y = "Player win rate (%)",
       title = NULL) +
  theme_minimal(base_size = 11) +
  theme(panel.grid.major.x = element_blank(), panel.grid.minor = element_blank())
ggsave(file.path(outdir, "clash_ring.pdf"), p3, width = 6.2, height = 3.0)

cat("figures written to", outdir, "\n")
