"""
Bi-Weibull TGSD fit, click-picked starting guess.

A plot window will open and pause the script, waiting for you to
click. Click the peak of each mode (2 clicks), then the window closes
itself and the fit continues.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

from psdfit.code.models import bi_weibull, weibull_component, entropy_of_info
from psdfit.code.load_dataset import DatasetLoader
from psdfit.code.results_store import save_fit_result

matplotlib.use("TkAgg")


def main():
    # ---------------------------------------------------------------
    # Load data
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
    picked_points = plt.ginput(n=2, timeout=0)
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

    lam1_guess = 2.0 ** (-phi1)  # coarse -> larger lambda
    lam2_guess = 2.0 ** (-phi2)  # fine   -> smaller lambda

    n1_guess = 1.0
    n2_guess = 1.0

    q_guess = y1 / (y1 + y2) if (y1 + y2) > 0 else 0.5

    p0_w = [lam1_guess, n1_guess, lam2_guess, n2_guess, q_guess]
    lb_w = [1e-4, 0.05, 1e-7, 0.05, 0.01]
    ub_w = [500., 5.0, 10.,  5.0,  0.99]
    p0_w = list(np.clip(p0_w, lb_w, ub_w))

    print(f"Initial guess from clicks: lambda1={p0_w[0]:.4f} mm, n1={p0_w[1]:.3f}, "
          f"lambda2={p0_w[2]:.5f} mm, n2={p0_w[3]:.3f}, q={p0_w[4]:.3f}")

    # bi_weibull() is a probability DENSITY in phi (integrates to 1),
    # so it only matches mass_frac directly by coincidence at 1.0-phi
    # spacing. Scaling by phi_bin_width before fitting keeps the fit
    # correct at any resolution -- see the identical note in
    # bg_clicker.py for the full explanation.
    def bi_weibull_binned(phi, lam1, n1, lam2, n2, q):
        return bi_weibull(phi, lam1, n1, lam2, n2, q) * phi_bin_width

    weib_ok = False
    try:
        popt_w, pcov_w = curve_fit(
            bi_weibull_binned, phi_labels, mass_frac,
            p0=p0_w, bounds=(lb_w, ub_w), maxfev=30000
        )
        perr_w    = np.sqrt(np.diag(pcov_w))
        lam1_w, n1_w, lam2_w, n2_w, q_w = popt_w
        yw_fit    = bi_weibull_binned(phi_labels, *popt_w)
        rmse_w    = np.sqrt(np.mean((mass_frac - yw_fit) ** 2)) * 100
        lam1_phi_w = -np.log2(lam1_w)
        lam2_phi_w = -np.log2(lam2_w)
        weib_ok   = True
    except Exception as e:
        print(f"Bi-Weibull fit failed from clicked guess: {e}")
        print("Try re-running and clicking closer to each peak's true "
              "center, or widen lb_w/ub_w in the script.")

    if not weib_ok:
        raise RuntimeError("Cannot continue: the fit did not converge.")

    print(f"\nBi-Weibull fit (from clicked starting guess):")
    print(f"  lambda1 = {lam1_w:.4f} mm ({lam1_phi_w:+.3f} Phi)  +/- {perr_w[0]:.4f}")
    print(f"  n1      = {n1_w:.4f}  +/- {perr_w[1]:.4f}")
    print(f"  lambda2 = {lam2_w:.6f} mm ({lam2_phi_w:+.3f} Phi)  +/- {perr_w[2]:.6f}")
    print(f"  n2      = {n2_w:.4f}  +/- {perr_w[3]:.4f}")
    print(f"  q       = {q_w:.4f}  +/- {perr_w[4]:.4f}")
    print(f"  RMSE    = {rmse_w:.4f} wt.%")

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

    # Scaled by phi_bin_width to match the bars (per-bin wt.%) at any
    # phi resolution -- same reasoning as the fit itself above.
    yw_tot = bi_weibull(phi_smooth, *popt_w) * phi_bin_width * 100
    yw_c   = q_w     * weibull_component(phi_smooth, lam1_w, n1_w) * phi_bin_width * 100
    yw_f   = (1-q_w) * weibull_component(phi_smooth, lam2_w, n2_w) * phi_bin_width * 100

    ax2.plot(phi_smooth, yw_tot, color=CFIT, lw=2.0, label='Bi-Weibull fit')
    ax2.plot(phi_smooth, yw_c, color=CPOP1, lw=1.2, ls='--',
             label=f'Pop. 1  λ₁ = {lam1_w:.3f} mm')
    ax2.plot(phi_smooth, yw_f, color=CPOP2, lw=1.2, ls='--',
             label=f'Pop. 2  λ₂ = {lam2_w:.5f} mm')

    ax2.set_xlabel('Φ', fontsize=11)
    ax2.set_ylabel('Mass (wt.%)', fontsize=11)
    ax2.set_title('Bi-Weibull (click-picked)', fontsize=11, fontweight='bold')
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
    print("\n  BI-WEIBULL")
    print(f"    lambda1 = {lam1_w:9.4f} mm  ({lam1_phi_w:+.3f} Phi)   +/- {perr_w[0]:.4f}")
    print(f"    n1      = {n1_w:9.4f}             +/- {perr_w[1]:.4f}")
    print(f"    lambda2 = {lam2_w:9.6f} mm  ({lam2_phi_w:+.3f} Phi)   +/- {perr_w[2]:.6f}")
    print(f"    n2      = {n2_w:9.4f}             +/- {perr_w[3]:.4f}")
    print(f"    q       = {q_w:9.4f}               +/- {perr_w[4]:.4f}")
    print(f"    RMSE    = {rmse_w:.4f} wt.%")
    print(f"\n{SEP}\n")

    # ---------------------------------------------------------------
    # Shannon entropy of the mass distribution
    # ---------------------------------------------------------------
    H, H_norm = entropy_of_info(mass_frac, bin_width=phi_bin_width)
    print(f"Shannon entropy: {H:.3f} bits (normalized: {H_norm:.3f})")

    # ---------------------------------------------------------------
    # Save this fit to the shared results store
    # ---------------------------------------------------------------
    save_fit_result(
        dataset=DATASET_LABEL,
        model="bi_weibull",
        params={
            "lambda1_mm": lam1_w, "n1": n1_w,
            "lambda2_mm": lam2_w, "n2": n2_w, "q": q_w,
        },
        rmse=rmse_w,
        entropy_bits=H,
        entropy_norm=H_norm,
        phi_bin_width=phi_bin_width,
    )
if __name__ == "__main__":
    main()
