"""
Bi-Gaussian TGSD fit, click-picked starting guess.

A plot window will open and pause the script, waiting for you to
click. Click the peak of each mode (2 clicks), then close the plot
window (or just wait -- it closes itself once both clicks are in) to
continue to the fit.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

from models import bi_gaussian, entropy_of_info
from load_dataset import DatasetLoader
from results_store import save_fit_result

matplotlib.use("TkAgg")  # interactive GUI backend for a plain script


def main():
    # ---------------------------------------------------------------
    # Load data (file picker, header confirmation, column mapping)
    # ---------------------------------------------------------------
    loader = DatasetLoader(need_size=False, need_weight=True)
    data = loader.load()
    phi_labels = data["phi"]
    mass_pct = data["weight_pct"]
    mass_frac = mass_pct / mass_pct.sum()
    phi_bin_width = data["phi_bin_width"]
    DATASET_LABEL = loader.dataset_label

    # ---------------------------------------------------------------
    # Interactive picker: click each mode's peak
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(phi_labels, mass_pct, width=0.90, color='#c0392b', alpha=0.55,
           edgecolor='grey', linewidth=0.5, label='Data')
    ax.set_xlabel('Φ', fontsize=11)
    ax.set_ylabel('Mass (wt.%)', fontsize=11)
    ax.set_title("Click the peak of each mode (2 clicks), order doesn't matter")
    ax.set_xlim(phi_labels.min() - 1, phi_labels.max() + 1)
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    plt.tight_layout()

    print("\nClick the peak of each mode on the plot window (2 clicks total).")
    picked_points = plt.ginput(n=2, timeout=0)  # blocks until 2 clicks
    plt.close(fig)

    if len(picked_points) < 2:
        raise RuntimeError(
            "Only got {} click(s). Re-run the script and click twice "
            "(one per mode peak).".format(len(picked_points))
        )

    for i, (phi_click, y_click) in enumerate(picked_points):
        print(f"Peak {i + 1} picked: Phi={phi_click:.3f}, wt%={y_click:.3f}")

    # ---------------------------------------------------------------
    # Build p0 from clicks and fit
    # ---------------------------------------------------------------
    (phi1, y1), (phi2, y2) = sorted(picked_points, key=lambda pt: pt[0])

    mu1_guess = phi1
    mu2_guess = phi2

    default_sigma = 1.0
    y1_frac = max(y1 / mass_pct.sum() if mass_pct.sum() > 0 else 0, 1e-6)
    y2_frac = max(y2 / mass_pct.sum() if mass_pct.sum() > 0 else 0, 1e-6)

    w_guess = y1 / (y1 + y2) if (y1 + y2) > 0 else 0.5

    sigma1_guess = max(w_guess / (y1_frac * np.sqrt(2 * np.pi)), 0.3) if y1_frac > 0 else default_sigma
    sigma2_guess = max((1 - w_guess) / (y2_frac * np.sqrt(2 * np.pi)), 0.3) if y2_frac > 0 else default_sigma

    sigma1_guess = float(np.clip(sigma1_guess, 0.3, 6.0))
    sigma2_guess = float(np.clip(sigma2_guess, 0.3, 6.0))

    p0_g = [mu1_guess, sigma1_guess, mu2_guess, sigma2_guess, w_guess]
    phi_span = float(phi_labels.max() - phi_labels.min())
    lb_g = [phi_labels.min() - phi_span, 0.05, phi_labels.min() - phi_span, 0.05, 0.01]
    ub_g = [phi_labels.max() + phi_span, phi_span, phi_labels.max() + phi_span, phi_span, 0.99]
    p0_g = list(np.clip(p0_g, lb_g, ub_g))

    print(f"Initial guess from clicks: mu1={p0_g[0]:.3f}, sigma1={p0_g[1]:.3f}, "
          f"mu2={p0_g[2]:.3f}, sigma2={p0_g[3]:.3f}, p={p0_g[4]:.3f}")

    # bi_gaussian() is a probability DENSITY in phi -- it integrates to
    # 1 over phi, so sum(bi_gaussian(phi, ...)) approx 1/phi_bin_width,
    # not 1. mass_frac, on the other hand, always sums to exactly 1
    # regardless of resolution. Fitting the raw density directly
    # against mass_frac is only correct by coincidence at 1.0-phi
    # spacing; at any other bin width (e.g. 0.5-phi) it silently
    # forces curve_fit to distort mu1/mu2/sigma1/sigma2/p to compensate
    # for the mismatched scale. Scaling the model by phi_bin_width
    # before fitting fixes this at any resolution.
    def bi_gaussian_binned(phi, mu1, sigma1, mu2, sigma2, p):
        return bi_gaussian(phi, mu1, sigma1, mu2, sigma2, p) * phi_bin_width

    gauss_ok = False
    try:
        popt_g, pcov_g = curve_fit(
            bi_gaussian_binned, phi_labels, mass_frac,
            p0=p0_g, bounds=(lb_g, ub_g), maxfev=30000
        )
        perr_g = np.sqrt(np.diag(pcov_g))
        mu1_g, sig1_g, mu2_g, sig2_g, p_g = popt_g
        yg_fit = bi_gaussian_binned(phi_labels, *popt_g)
        rmse_g = np.sqrt(np.mean((mass_frac - yg_fit) ** 2)) * 100
        BI = (np.sqrt(2) * abs(mu2_g - mu1_g)
              / np.sqrt(sig1_g**2 + sig2_g**2)
              * np.sqrt(p_g * (1.0 - p_g)))
        gauss_ok = True
    except Exception as e:
        print(f"Bi-Gaussian fit failed from clicked guess: {e}")
        print("Try re-running and clicking closer to each peak's true "
              "center, or widen lb_g/ub_g in the script.")

    if not gauss_ok:
        raise RuntimeError("Cannot continue: the fit did not converge.")

    print(f"\nBi-Gaussian fit (from clicked starting guess):")
    print(f"  mu1    = {mu1_g:+.3f} Phi  +/- {perr_g[0]:.3f}")
    print(f"  sigma1 = {sig1_g:.3f} Phi  +/- {perr_g[1]:.3f}")
    print(f"  mu2    = {mu2_g:+.3f} Phi  +/- {perr_g[2]:.3f}")
    print(f"  sigma2 = {sig2_g:.3f} Phi  +/- {perr_g[3]:.3f}")
    print(f"  p      = {p_g:.4f}       +/- {perr_g[4]:.4f}")
    print(f"  BI     = {BI:.3f}  ({'bimodal' if BI > 1.1 else 'unimodal'})")
    print(f"  RMSE   = {rmse_g:.4f} wt.%")

    # ---------------------------------------------------------------
    # Plot the fit result
    # ---------------------------------------------------------------
    phi_smooth = np.linspace(phi_labels.min() - 1.0, phi_labels.max() + 1.0, 1000)
    CDATA, CFIT, CPOP1, CPOP2 = '#c0392b', '#2c3e50', '#2980b9', '#27ae60'

    fig2 = plt.figure(figsize=(7, 5.4))
    fig2.suptitle(f"{DATASET_LABEL} (click-picked starting guess)",
                  fontsize=12, y=1.02, fontweight='bold')
    ax2 = fig2.add_subplot(111)

    ax2.bar(phi_labels, mass_pct, width=0.90, color=CDATA, alpha=0.55,
            edgecolor='grey', linewidth=0.5, label='Data')

    # Scale by phi_bin_width for the same reason as the fit itself:
    # bi_gaussian() is a density (integrates to 1 over phi), but the
    # bars being plotted are per-bin wt.%, so the overlay must be
    # converted to per-bin terms the same way to actually line up with
    # the data at any phi resolution.
    yg_tot = bi_gaussian(phi_smooth, *popt_g) * phi_bin_width * 100
    yg_c = p_g / (sig1_g * np.sqrt(2 * np.pi)) \
           * np.exp(-0.5 * ((phi_smooth - mu1_g) / sig1_g) ** 2) * phi_bin_width * 100
    yg_f = (1 - p_g) / (sig2_g * np.sqrt(2 * np.pi)) \
           * np.exp(-0.5 * ((phi_smooth - mu2_g) / sig2_g) ** 2) * phi_bin_width * 100

    ax2.plot(phi_smooth, yg_tot, color=CFIT, lw=2.0, label='Bi-Gaussian fit')
    ax2.plot(phi_smooth, yg_c, color=CPOP1, lw=1.2, ls='--',
              label=f'Pop. 1  μ₁ = {mu1_g:.2f} Φ')
    ax2.plot(phi_smooth, yg_f, color=CPOP2, lw=1.2, ls='--',
              label=f'Pop. 2  μ₂ = {mu2_g:.2f} Φ')

    ax2.set_xlabel('Φ', fontsize=11)
    ax2.set_ylabel('Mass (wt.%)', fontsize=11)
    ax2.set_title('Bi-Gaussian', fontsize=11, fontweight='bold')
    ax2.set_xlim(phi_labels.min() - 1, phi_labels.max() + 1)
    ax2.set_ylim(bottom=0)
    ax2.legend(fontsize=8)
    ax2.tick_params(labelsize=9)
    plt.tight_layout()
    print("\nShowing fit plot -- close the window to continue.")
    plt.show()

    SEP = "=" * 62
    print(f"\n{SEP}")
    print(f"  TGSD FIT RESULTS (click-picked starting guess)")
    print(f"  {DATASET_LABEL}")
    print(f"{SEP}")
    print("\n  BI-GAUSSIAN")
    print(f"    mu1    = {mu1_g:+8.3f} Phi   +/- {perr_g[0]:.3f}")
    print(f"    sigma1 = {sig1_g:8.3f} Phi   +/- {perr_g[1]:.3f}")
    print(f"    mu2    = {mu2_g:+8.3f} Phi   +/- {perr_g[2]:.3f}")
    print(f"    sigma2 = {sig2_g:8.3f} Phi   +/- {perr_g[3]:.3f}")
    print(f"    p      = {p_g:8.4f}       +/- {perr_g[4]:.4f}")
    print(f"    BI     = {BI:8.3f}       ({'bimodal' if BI > 1.1 else 'unimodal'})")
    print(f"    RMSE   = {rmse_g:.4f} wt.%")

    # ---------------------------------------------------------------
    # Shannon entropy of the mass distribution
    # ---------------------------------------------------------------
    H, H_norm = entropy_of_info(mass_frac)
    print(f"\nShannon entropy: {H:.3f} bits (normalized: {H_norm:.3f})")

    
    # ---------------------------------------------------------------
    # Save this fit to the shared results store
    # ---------------------------------------------------------------
    save_fit_result(
        dataset=DATASET_LABEL,
        model="bi_gaussian",
        params={
            "mu1": mu1_g, "sigma1": sig1_g,
            "mu2": mu2_g, "sigma2": sig2_g,
            "p": p_g, "BI": BI,
        },
        rmse=rmse_g,
        entropy_bits=H,
        entropy_norm=H_norm,
        phi_bin_width=phi_bin_width,
    )
if __name__ == "__main__":
    main()
