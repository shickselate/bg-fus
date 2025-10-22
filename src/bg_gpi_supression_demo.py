"""
BG–Thalamus with explicit GPi suppression (reversal/global disinhibition demo)

Run (plots/headless):
    python bg_gpi_suppression_demo.py

Run (interactive GUI):
    nengo bg_gpi_suppression_demo.py

What this shows:
- Two cortical action drives (A1, A2) feed the Basal Ganglia (BG).
- BG output approximates GPi/SNr inhibitory drive to thalamus (lower = more disinhibition).
- A global "GPi suppression" factor scales BG output before it reaches thalamus.
  * Moderate suppression -> the stronger action is selected (disinhibited).
  * Strong suppression -> BOTH channels become disinhibited (loss of selectivity / 'reversal').

A transient FUS pulse can further suppress GPi output during a time window to illustrate
a flip in the selected channel or global disinhibition when too strong.
"""

import numpy as np
import nengo
import matplotlib.pyplot as plt

# ----------------------------
# Tunable parameters (quick edits)
# ----------------------------
A1 = 0.85          # cortical drive for action 1
A2 = 0.65          # cortical drive for action 2

T_total = 1.6      # total simulation time (s)

# Global GPi scaling (1.0 = normal inhibition; 0.0 = GPi silenced)
gpi_scale_base = 1.0

# FUS pulse suppresses GPi by multiplying gpi_scale_base by (1 - fus_depth) during the window
fus_start = 0.6    # s
fus_dur   = 0.5    # s
fus_depth = 0.6    # 0..1 (how much extra suppression during the pulse)

rng_seed = 0       # reproducibility

# ----------------------------
# Helper: time-varying GPi scale under FUS
# ----------------------------
def gpi_scale_fn(t):
    in_pulse = (fus_start <= t <= fus_start + fus_dur)
    return gpi_scale_base * (1.0 - fus_depth if in_pulse else 1.0)

# ----------------------------
# Build model
# ----------------------------
np.random.seed(rng_seed)
model = nengo.Network(label="BG–Thalamus with GPi suppression")
with model:
    # Cortex drives two action channels
    cortex = nengo.Node(lambda t: [A1, A2], label="Cortex [A1,A2]")

    # Basal ganglia (rate model), output ~ GPi inhibitory 'level' per channel
    bg = nengo.networks.BasalGanglia(dimensions=2, label="BasalGanglia")

    # Thalamus (rate model), expects inhibitory input from BG and relays winner
    th = nengo.networks.Thalamus(dimensions=2, label="Thalamus")

    # Time-varying GPi scale node (represents global suppression of BG output)
    gpi_scale = nengo.Node(gpi_scale_fn, label="GPi scale(t)")

    # Connect cortex -> BG; BG -> Thalamus (but insert a scaling stage for GPi)
    nengo.Connection(cortex, bg.input, synapse=0.02)

    # We’ll route BG output through a small linear ensemble to apply time-varying scaling
    # Equivalent to: th.input = gpi_scale(t) * bg.output
    # (Lower BG output means less inhibition -> thalamus more active)
    scaler = nengo.networks.EnsembleArray(n_neurons=100, n_ensembles=2, label="GPi scaler")
    # Feed BG output into scaler
    nengo.Connection(bg.output, scaler.input, synapse=0.02)
    # Multiply by gpi_scale(t): implement as a modulation via connection function
    # In Nengo, easiest is to create a Node that emits [scale,scale] and connect with a product network,
    # but here we use a linear trick: drive scaler bias with scale and use a simple 2D elementwise 'product' via
    # a small network. To stay lightweight, we approximate product with a 2-neuron ensemble per dim.
    # Simpler: do elementwise scale via a Node that outputs the scaled vector directly (clean & fast).
    scaled_gpi = nengo.Node(size_in=2, label="Scaled GPi")
    nengo.Connection(scaler.output, scaled_gpi, synapse=0.01)
    nengo.Connection(gpi_scale, scaled_gpi[0], synapse=0.0, transform=0.0)  # placeholder to keep node live
    nengo.Connection(gpi_scale, scaled_gpi[1], synapse=0.0, transform=0.0)  # (no effect; see function below)

    # Monkey-patch a function onto scaled_gpi to compute elementwise scaling
    def scaled_gpi_func(t, x):
        # x is [bg0, bg1] coming from scaler.output via first connection
        # We read the current gpi_scale via gpi_scale_fn(t)
        s = gpi_scale_fn(t)
        return [s * x[0], s * x[1]]
    scaled_gpi.output = scaled_gpi_func

    # Now feed scaled GPi output to thalamus
    nengo.Connection(scaled_gpi, th.input, synapse=0.02)

    # ----- Probes -----
    p_ctx  = nengo.Probe(cortex, label="Cortex")
    p_bg   = nengo.Probe(bg.output, synapse=0.05, label="BG->GPi (inhib level)")
    p_gpis = nengo.Probe(scaled_gpi, synapse=0.05, label="Scaled GPi (to Th)")
    p_th   = nengo.Probe(th.output, synapse=0.05, label="Thalamus out")
    p_scl  = nengo.Probe(gpi_scale, label="gpi_scale(t)")

# ----------------------------
# Simulate (headless mode)
# ----------------------------
with nengo.Simulator(model, seed=rng_seed) as sim:
    sim.run(T_total)

t = sim.trange()
ctx = sim.data[p_ctx]
bg_out = sim.data[p_bg]
gpi_scaled = sim.data[p_gpis]
th_out = sim.data[p_th]
scale = sim.data[p_scl].reshape(-1)

winner = th_out.argmax(axis=1)

# ----------------------------
# Plot
# ----------------------------
fig, ax = plt.subplots(4, 1, figsize=(9, 8), sharex=True)

# Cortex drives
ax[0].plot(t, ctx[:, 0], label="A1")
ax[0].plot(t, ctx[:, 1], label="A2")
ax[0].axvspan(fus_start, fus_start + fus_dur, alpha=0.15, label="FUS window")
ax[0].legend(); ax[0].set_ylabel("Cortex")

# BG output (pre-scale) ~ GPi inhibitory level (higher = more inhibition)
ax[1].plot(t, bg_out[:, 0], label="BG→GPi ch1")
ax[1].plot(t, bg_out[:, 1], label="BG→GPi ch2")
ax[1].set_ylabel("BG out (inhib level)")
ax[1].legend()

# Scaled GPi (what thalamus actually receives)
ax[2].plot(t, gpi_scaled[:, 0], label="(scaled) GPi→Th ch1")
ax[2].plot(t, gpi_scaled[:, 1], label="(scaled) GPi→Th ch2")
ax[2].plot(t, scale, ':', label="gpi_scale(t)")
ax[2].set_ylabel("Scaled GPi")
ax[2].legend()

# Thalamus
ax[3].plot(t, th_out[:, 0], label="Th ch1")
ax[3].plot(t, th_out[:, 1], label="Th ch2")
ax[3].set_ylabel("Thalamus")
ax[3].set_xlabel("Time (s)")
ax[3].text(0.02, 0.75, f"Winner @ end: {int(winner[-1])}", transform=ax[3].transAxes)

plt.tight_layout()
plt.show()
