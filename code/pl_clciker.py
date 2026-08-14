"""
Bi-power-law TGSD fit (cumulative number distribution),
click-picked starting guess.

A plot window will open and pause the script, waiting for you to
click. Click each visible crossover/kink -- 1 or 2 clicks:
  - Left-click to place a point.
  - Middle-click (or press Enter) to finish early after just 1 click.
  - Right-click to undo the last click.
The window closes itself once you finish (2 clicks, or middle-click/
Enter after 1), and the fit continues.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, OptimizeWarning
from scipy.signal import find_peaks
import warnings

from models import bi_power_law, log_bi_power_law, entropy_of_info
from load_dataset import DatasetLoader
from results_store import save_fit_result

matplotlib.use("TkAgg")
np.seterr(over="ignore", divide="ignore", invalid="ignore")


def main():
    # ---------------------------------------------------------------
    # Load data -- this fit needs a physical particle diameter (to
    # build the number distribution N ~ mass/d^3) as well as phi and
    # a weight column.
    # ---------------------------------------------------------------
    loader = DatasetLoader(need_size=True, need_weight=True)
    data = loader.load()
    Phi = data["phi"]
    d_mm = data["size_mm"]
    massp = data["weight_pct"]
    phi_bin_width = data["phi_bin_width"]
    DATASET_LABEL = loader.dataset_label

    valid = ~np.isnan(d_mm) & ~np.isnan(massp) & ~np.isnan(Phi) & (d_mm > 0)
    Phi, d_mm, massp = Phi[valid], d_mm[valid], massp[valid]

    order = np.argsort(Phi)
    Phi, d_mm, massp = Phi[order], d_mm[order], massp[order]

    num_raw = massp / (d_mm ** 3)
    num_raw[~np.isfinite(num_raw)] = 0.0
    no_data = num_raw / np.sum(num_raw)

    N_cum = np.cumsum(no_data)
    N_cum = N_cum / N_cum[-1]

    mask = N_cum > 0
    phi_masked = Phi[mask]
    N_masked = N_cum[mask]
    logN_masked = np.log10(N_masked)

    print(f"Loaded {DATASET_LABEL}: {len(Phi)} points, "
          f"Phi range [{Phi.min():.2f}, {Phi.max():.2f}]")

    # ---------------------------------------------------------------
    # Interactive picker: click 1 or 2 visible crossovers
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.semilogy(Phi, N_cum, 'ok', markersize=6, label='Data')
    ax.set_xlabel(r'$\Phi$', fontsize=13)
    ax.set_ylabel(r'$N(\geq z)/N_0$', fontsize=13)
    ax.set_title('Click each visible crossover/kink (1 or 2).\n'
                  'Middle-click or Enter to finish after 1 click.')
    ax.set_xlim(Phi.min() - 4, Phi.max() + 4)
    ax.invert_xaxis()
    ax.set_ylim(N_cum[N_cum > 0].min() * 1e-2, 100)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='lower right', fontsize=8)
    plt.tight_layout()

    print("\nClick each visible crossover/kink on the plot (1 or 2 clicks).")
    print("Middle-click or press Enter to finish after just 1 click.")
    raw_points = plt.ginput(n=2, timeout=0)  # left click=add, mid/Enter=stop early
    plt.close(fig)
    picked_points = [pt[0] for pt in raw_points]  # keep phi (x) values only

    if len(picked_points) < 1:
        raise RuntimeError(
            "No click registered. Re-run the script and click at least "
            "once at a visible crossover."
        )

    for i, phi_click in enumerate(picked_points):
        print(f"Crossover {i + 1} picked: Phi={phi_click:.3f}")

    # ---------------------------------------------------------------
    # Build p0 from clicks and fit (multistart)
    # ---------------------------------------------------------------
    offset_phi = 2.0

    if len(picked_points) == 1:
        phi_crossover_click = picked_points[0]
        lamc_guess = phi_crossover_click - offset_phi
        lamf_guess = phi_crossover_click + offset_phi
        print(f"1 crossover clicked at Phi={phi_crossover_click:.3f}")
    else:
        phi_left, phi_right = sorted(picked_points)
        lamc_guess = phi_left - offset_phi
        lamf_guess = phi_right + offset_phi
        print(f"2 crossovers clicked at Phi={phi_left:.3f} and Phi={phi_right:.3f}")

    Df0_guess = 3.0
    Dc0_guess = 3.0

    p0 = [lamf_guess, lamc_guess, Df0_guess, Dc0_guess]
    print(f"Initial guess: lambda_f={p0[0]:.3f}, lambda_c={p0[1]:.3f}, "
          f"Df={p0[2]:.3f}, Dc={p0[3]:.3f}")

    lower = [-20, -20, 0.1, 0.1]
    upper = [20, 20, 15, 15]
    p0 = list(np.clip(p0, lower, upper))

    rng = np.random.default_rng(0)
    n_trials = 20
    best_fval = np.inf
    p_fit = None

    for trial in range(n_trials):
        if trial == 0:
            p0_trial = p0
        else:
            factors = rng.uniform(0.5, 1.8, size=2)
            offset_trial = offset_phi * rng.uniform(0.4, 2.0)
            if len(picked_points) == 1:
                lamc_t = np.clip(phi_crossover_click - offset_trial, lower[1], upper[1])
                lamf_t = np.clip(phi_crossover_click + offset_trial, lower[0], upper[0])
            else:
                lamc_t = np.clip(phi_left - offset_trial, lower[1], upper[1])
                lamf_t = np.clip(phi_right + offset_trial, lower[0], upper[0])
            Df_t = np.clip(Df0_guess * factors[0], lower[2], upper[2])
            Dc_t = np.clip(Dc0_guess * factors[1], lower[3], upper[3])
            p0_trial = [lamf_t, lamc_t, Df_t, Dc_t]

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", OptimizeWarning)
                popt_trial, pcov_trial = curve_fit(
                    log_bi_power_law, phi_masked, logN_masked,
                    p0=p0_trial, method="lm", maxfev=10000,
                )
        except (RuntimeError, OptimizeWarning):
            continue

        resid_trial = log_bi_power_law(phi_masked, *popt_trial) - logN_masked
        if not np.all(np.isfinite(resid_trial)):
            continue
        fval_trial = np.sum(resid_trial ** 2)

        if fval_trial < best_fval:
            best_fval = fval_trial
            p_fit = popt_trial

    if p_fit is None:
        raise RuntimeError(
            "All multistart attempts failed to converge from this click. "
            "Re-run and click closer to the visible bend(s), or increase "
            "offset_phi / n_trials in the script."
        )

    fval = best_fval
    lambda_f, lambda_c, Df, Dc = p_fit
    print(f"\nBi-power-law fit (best of {n_trials} multistart attempts from your click(s)):")
    print(f"  lambda_f = {lambda_f:.4g} Phi")
    print(f"  lambda_c = {lambda_c:.4g} Phi")
    print(f"  Df       = {Df:.3f}")
    print(f"  Dc       = {Dc:.3f}")
    print(f"  log10 RMSE^2 = {fval:.4f}")

    # ---------------------------------------------------------------
    # Plot the fit result
    # ---------------------------------------------------------------
    Phi_fine = np.linspace(Phi.min() - 1, Phi.max() + 1, 500)
    N_fit = bi_power_law(Phi_fine, *p_fit)

    fig2, ax2 = plt.subplots(figsize=(6, 6), facecolor="w")

    ax2.semilogy(Phi_fine, N_fit, "-r", linewidth=1.5, label="Bi-power-law fit")
    ax2.semilogy(Phi, N_cum, "ok", markerfacecolor="k", markersize=6,
                 linewidth=1, label="Data")

    logN_fit = np.log10(np.clip(N_fit, 1e-300, None))
    dlogN = np.gradient(logN_fit, Phi_fine)
    d2logN = np.gradient(dlogN, Phi_fine)

    peaks, properties = find_peaks(
        np.abs(d2logN), prominence=np.max(np.abs(d2logN)) * 0.05
    )

    if len(peaks) >= 2:
        top2 = peaks[np.argsort(properties["prominences"])[-2:]]
        top2 = np.sort(top2)
        phi_crossover1, phi_crossover2 = Phi_fine[top2]
        ax2.axvline(phi_crossover1, color="purple", linestyle=":", linewidth=1.5,
                    label=fr"crossover 1: $\Phi$={phi_crossover1:.2f}")
        ax2.axvline(phi_crossover2, color="orange", linestyle=":", linewidth=1.5,
                    label=fr"crossover 2: $\Phi$={phi_crossover2:.2f}")
    elif len(peaks) == 1:
        phi_crossover1 = Phi_fine[peaks[0]]
        ax2.axvline(phi_crossover1, color="purple", linestyle=":", linewidth=1.5,
                    label=fr"crossover: $\Phi$={phi_crossover1:.2f}")

    ax2.axvline(lambda_c, color="blue", linestyle="--", linewidth=1, alpha=0.6,
                label=fr"$\lambda_c$={lambda_c:.2f}")
    ax2.axvline(lambda_f, color="green", linestyle="--", linewidth=1, alpha=0.6,
                label=fr"$\lambda_f$={lambda_f:.2f}")

    ax2.set_xlabel(r"$\Phi$", fontsize=14)
    ax2.set_ylabel(r"$N(\geq z)/N_0$", fontsize=14)
    ax2.set_title(f"{DATASET_LABEL} (click-picked starting guess)", fontsize=12)
    ax2.legend(loc="lower right", fontsize=8)
    ax2.grid(True)

    ax2.set_xlim(Phi.min() - 4, Phi.max() + 4)
    ax2.invert_xaxis()
    ax2.set_ylim(N_cum[N_cum > 0].min() * 1e-2, 100)

    plt.tight_layout()
    print("\nShowing fit plot -- close the window to finish.")
    plt.show()

    print(DATASET_LABEL)
    print(f"\nBi-power-law fit (best of {n_trials} multistart attempts from your click(s)):")
    print(f"  lambda_f = {lambda_f:.4g} Phi")
    print(f"  lambda_c = {lambda_c:.4g} Phi")
    print(f"  Df       = {Df:.3f}")
    print(f"  Dc       = {Dc:.3f}")
    print(f"  log10 RMSE^2 = {fval:.4f}")

    # ---------------------------------------------------------------
    # Shannon entropy of the mass distribution
    # ---------------------------------------------------------------
    # Uses the raw wt.% data (massp, pre-filtering) renormalized to
    # fractions -- same quantity the other clicker scripts compute.
    mass_frac = massp / massp.sum()
    H, H_norm = entropy_of_info(mass_frac, bin_width=phi_bin_width)
    print(f"Shannon entropy: {H:.3f} bits (normalized: {H_norm:.3f})")

    # ---------------------------------------------------------------
    # Save this fit to the shared results store
    # ---------------------------------------------------------------
    save_fit_result(
        dataset=DATASET_LABEL,
        model="bi_power_law",
        params={
            "lambda_f": lambda_f, "lambda_c": lambda_c,
            "Df": Df, "Dc": Dc,
        },
        rmse=None,
        entropy_bits=H,
        entropy_norm=H_norm,
        phi_bin_width=phi_bin_width,
    )
  
if __name__ == "__main__":
    main()
