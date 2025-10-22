"""
BG action selection with FUS attenuation (BasalGanglia + Thalamus)

Run (plots/headless):
    python bg_fus_interactive.py --A1 0.8 --A2 0.6 --kappa 0.6 --fus_start 0.5 --fus_dur 0.3 --T 1.2

Run (interactive GUI):
    nengo bg_fus_interactive.py
(When launched via nengo-gui, this file is imported; it will find `model` and won't run the __main__ block.)
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
import nengo

# ----------------------------
# Defaults (can be overridden via CLI)
# ----------------------------
DEFAULTS = dict(
    A1=0.8,          # cortical drive for action 1
    A2=0.6,          # cortical drive for action 2
    kappa=0.6,       # FUS attenuation strength (0..1) applied to A1 during the pulse
    fus_start=0.5,   # s
    fus_dur=0.3,     # s
    T=1.2,           # total simulation time (s)
    seed=1,          # simulator seed
)

# ----------------------------
# Time-varying attenuation for A1
# ----------------------------
def make_fus_scale(kappa, fus_start, fus_dur):
    def scale_fn(t):
        return (1.0 - kappa) if (fus_start <= t <= (fus_start + fus_dur)) else 1.0
    return scale_fn

# ----------------------------
# Build the model (this stays at module level so nengo-gui can import it)
# Note: we initialise with DEFAULTS; the __main__ block can rebuild with CLI args.
# ----------------------------
_fus_scale = make_fus_scale(DEFAULTS["kappa"], DEFAULTS["fus_start"], DEFAULTS["fus_dur"])
model = nengo.Network(label="BG + Thalamus with FUS attenuation")
with model:
    # Two cortical action drives; A1 gets attenuated during FUS window
    cortex = nengo.Node(lambda t: [DEFAULTS["A1"] * _fus_scale(t), DEFAULTS["A2"]],
                        label="Cortex [A1,A2]")

    # Basal ganglia & thalamus (rate models)
    bg = nengo.networks.BasalGanglia(dimensions=2, label="BasalGanglia")
    th = nengo.networks.Thalamus(dimensions=2, label="Thalamus")

    # Wiring
    nengo.Connection(cortex, bg.input, synapse=0.02)
    nengo.Connection(bg.output, th.input, synapse=0.02)

    # Probes (used when running headless)
    p_ctx = nengo.Probe(cortex)
    p_bg  = nengo.Probe(bg.output, synapse=0.05)
    p_th  = nengo.Probe(th.output, synapse=0.05)

# ----------------------------
# Headless runner + plotting
# ----------------------------
def run_and_plot(A1, A2, kappa, fus_start, fus_dur, T, seed):
    np.random.seed(seed)
    fus_scale = make_fus_scale(kappa, fus_start, fus_dur)

    # Rebuild a fresh model with chosen params (so GUI import stays untouched)
    net = nengo.Network(label="BG + Thalamus with FUS attenuation (headless)")
    with net:
        cortex = nengo.Node(lambda t: [A1 * fus_scale(t), A2], label="Cortex [A1,A2]")
        bg = nengo.networks.BasalGanglia(dimensions=2, label="BasalGanglia")
        th = nengo.networks.Thalamus(dimensions=2, label="Thalamus")
        nengo.Connection(cortex, bg.input, synapse=0.02)
        nengo.Connection(bg.output, th.input, synapse=0.02)
        p_ctx = nengo.Probe(cortex)
        p_bg  = nengo.Probe(bg.output, synapse=0.05)
        p_th  = nengo.Probe(th.output, synapse=0.05)

    with nengo.Simulator(net, seed=seed) as sim:
        sim.run(T)

    t = sim.trange()
    ctx = sim.data[p_ctx]
    bg_out = sim.data[p_bg]
    th_out = sim.data[p_th]

    # --- Plots (one chart per figure) ---
    plt.figure(figsize=(8, 3))
    plt.plot(t, ctx[:, 0], label="A1 (FUS-attenuated)")
    plt.plot(t, ctx[:, 1], label="A2")
    plt.axvspan(fus_start, fus_start + fus_dur, alpha=0.15, label="FUS window")
    plt.ylabel("Cortex"); plt.xlabel("Time (s)"); plt.legend()
    plt.show()

    plt.figure(figsize=(8, 3))
    plt.plot(t, bg_out)
    plt.ylabel("BG out (lower = disinhib.)"); plt.xlabel("Time (s)")
    plt.show()

    plt.figure(figsize=(8, 3))
    plt.plot(t, th_out)
    plt.ylabel("Thalamus"); plt.xlabel("Time (s)")
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BG action selection with FUS attenuation (headless run).")
    parser.add_argument("--A1", type=float, default=DEFAULTS["A1"])
    parser.add_argument("--A2", type=float, default=DEFAULTS["A2"])
    parser.add_argument("--kappa", type=float, default=DEFAULTS["kappa"])
    parser.add_argument("--fus_start", type=float, default=DEFAULTS["fus_start"])
    parser.add_argument("--fus_dur", type=float, default=DEFAULTS["fus_dur"])
    parser.add_argument("--T", type=float, default=DEFAULTS["T"])
    parser.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    args = parser.parse_args()

    run_and_plot(**vars(args))
