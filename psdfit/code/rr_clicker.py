"""
Bi-Rosin-Rammler TGSD fit, click-picked starting guess.

A plot window will open and pause the script, waiting for you to
click. Click the COARSE mode peak first, then the FINE mode peak
(2 clicks total). The window closes itself once both clicks are in,
and the fit continues.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

from psdfit.code.models import bi_rr_density, rr_density_phi, entropy_of_info
from psdfit.code.load_dataset import DatasetLoader
from psdfit.code.results_store import save_fit_result

matplotlib.use("TkAgg")


def main():
    # ---------------------------------------------------------------
    # Load data
    # ---------------------------------------------------------------
    loader = DatasetLoader(need_size=False, need_weight=True)
    data = loader.load()
    phi_data = data["phi"]
    wt_pct_norm = data["weight_pct"]  # already normalized to sum to 100
    phi_bin_width = data["phi_bin_width"]
    DATASET_LABEL = loader.dataset_label

    # ---------------------------------------------------------------
    # Interactive picker: click coarse mode, then fine mode
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(phi_data, wt_pct_norm, width=0.85, color='lightgray',
           edgecolor='k', zorder=2)
    ax.set_xlabel(r'$\phi = -\log_2$(diameter in mm)')
    ax.set_ylabel('wt.% per phi bin')
    ax.set_title('Click COARSE mode peak, then FINE mode peak (in that order)')
    ax.grid(alpha=0.3)
    plt.tight_layout()

    print("\nClick the COARSE mode peak first, then the FINE mode peak.")
    picked_points = plt.ginput(n=2, timeout=0)
    plt.close(fig)

    if len(picked_points) < 2:
        raise RuntimeError(
            "Only got {} click(s). Re-run the script and click twice "
            "(coarse mode, then fine mode).".format(len(picked_points))
        )

    print(f"\nBoth points picked:")
    print(f"  coarse: phi={picked_points[0][0]:.3f}, wt%={picked_points[0][1]:.3f}")
    print(f"  fine:   phi={picked_points[1][0]:.3f}, wt%={picked_points[1][1]:.3f}")

    # ---------------------------------------------------------------
    # Build p0 from clicks and fit
    # ---------------------------------------------------------------
    (phi_coarse_pick, y_coarse_pick), (phi_fine_pick, y_fine_pick) = picked_points

    sigma1_guess = 2.0 ** (-phi_coarse_pick)
    sigma2_guess = 2.0 ** (-phi_fine_pick)
    amp_guess = max(y_coarse_pick, y_fine_pick) * 2.0
    w_guess = y_coarse_pick / (y_coarse_pick + y_fine_pick)

    p0 = [w_guess, sigma1_guess, 4.0, sigma2_guess, 4.0, amp_guess]
    lower = [0.0, 1e-4, 0.3, 1e-4, 0.3, 1]
    upper = [1.0, 50.0, 15.0, 50.0, 15.0, 500]
    p0 = list(np.clip(p0, lower, upper))

    print(f"Initial guess built from clicks: {[round(x, 4) for x in p0]}")

    ss_tot = np.sum((wt_pct_norm - wt_pct_norm.mean()) ** 2)

    popt_bi, pcov_bi = curve_fit(
        bi_rr_density, phi_data, wt_pct_norm,
        p0=p0, bounds=(lower, upper), maxfev=50000
    )
    w_fit, sigma1_fit, k1_fit, sigma2_fit, k2_fit, amp_fit = popt_bi
    fit_bi = bi_rr_density(phi_data, *popt_bi)
    r2_bi = 1 - np.sum((wt_pct_norm - fit_bi) ** 2) / ss_tot

    perr = np.sqrt(np.diag(pcov_bi))
    w_err, s1_err, k1_err, s2_err, k2_err, amp_err = perr

    if sigma1_fit < sigma2_fit:
        w_fit = 1 - w_fit
        sigma1_fit, sigma2_fit = sigma2_fit, sigma1_fit
        k1_fit, k2_fit = k2_fit, k1_fit
        s1_err, s2_err = s2_err, s1_err
        k1_err, k2_err = k2_err, k1_err

    phi1_mode = -np.log2(sigma1_fit)
    phi2_mode = -np.log2(sigma2_fit)
    phi1_err = s1_err / (sigma1_fit * np.log(2))
    phi2_err = s2_err / (sigma2_fit * np.log(2))

    print("\nBi-Rosin-Rammler fit (from clicked starting guess):")
    print(f"  w (coarse mass fraction) = {w_fit:.4f} +/- {w_err:.4f}")
    print(f"  sigma_coarse             = {sigma1_fit:.5f} +/- {s1_err:.5f} mm"
          f"   (phi = {phi1_mode:.3f} +/- {phi1_err:.3f})")
    print(f"  k_coarse                 = {k1_fit:.4f} +/- {k1_err:.4f}")
    print(f"  sigma_fine                = {sigma2_fit:.5f} +/- {s2_err:.5f} mm"
          f"   (phi = {phi2_mode:.3f} +/- {phi2_err:.3f})")
    print(f"  k_fine                   = {k2_fit:.4f} +/- {k2_err:.4f}")
    print(f"  amp                      = {amp_fit:.4f} +/- {amp_err:.4f}")
    print(f"  R^2                      = {r2_bi:.4f}")

    # ---------------------------------------------------------------
    # Plot the fit result (mass density + two cumulative views)
    # ---------------------------------------------------------------
    phi_smooth = np.linspace(phi_data.min() - 0.5, phi_data.max() + 0.5, 500)
    fit_bi_smooth = bi_rr_density(phi_smooth, w_fit, sigma1_fit, k1_fit, sigma2_fit, k2_fit, amp_fit)
    fit_coarse_smooth = amp_fit * w_fit * rr_density_phi(phi_smooth, sigma1_fit, k1_fit)
    fit_fine_smooth = amp_fit * (1 - w_fit) * rr_density_phi(phi_smooth, sigma2_fit, k2_fit)

    fig2, axes2 = plt.subplots(3, 1, figsize=(8, 14))

    # --- Mass density view (wt.% per phi bin) ---
    ax2 = axes2[0]
    ax2.bar(phi_data, wt_pct_norm, width=0.85, color='lightgray',
            edgecolor='k', label='data', zorder=2)
    ax2.plot(phi_smooth, fit_bi_smooth, '-', color='crimson', lw=2,
             label=f'Bi-Rosin-Rammler ($R^2$={r2_bi:.3f})', zorder=4)
    ax2.plot(phi_smooth, fit_coarse_smooth, '--', color='steelblue', label='Coarse mode')
    ax2.plot(phi_smooth, fit_fine_smooth, '--', color='seagreen', label='Fine mode')
    ax2.set_xlabel(r'$\phi = -\log_2$(diameter in mm)')
    ax2.set_ylabel('wt.% per phi bin')
    ax2.set_title('mass-density fit')
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    # --- Cumulative M(>l)/M_T view vs diameter (log scale) ---
    diam_mm = 2.0 ** (-phi_data)
    order_diam = np.argsort(diam_mm)[::-1]
    diam_sorted = diam_mm[order_diam]
    wt_sorted = wt_pct_norm[order_diam]
    tot = wt_sorted.sum()
    M_gt_l_data = 1 - np.cumsum(wt_sorted) / tot + wt_sorted / tot

    l_smooth = 2.0 ** (-phi_smooth)
    order = np.argsort(phi_smooth)
    cum_from_fine_end = np.cumsum(fit_bi_smooth[order])
    cum_from_fine_end /= cum_from_fine_end[-1]
    M_gt_l_fit_sorted = 1 - cum_from_fine_end

    ax2 = axes2[1]
    ax2.semilogx(diam_sorted, M_gt_l_data, 'o', color='k',
                 label='data (empirical)', zorder=5)
    ax2.semilogx(l_smooth[order], M_gt_l_fit_sorted, '-', color='crimson', lw=2,
                 label='Bi-Rosin-Rammler (from fitted density)')
    ax2.set_xlabel('Particle diameter, $l$ (mm, log scale)')
    ax2.set_ylabel(r'$M(>l)/M_T$')
    ax2.set_title('cumulative view (vs diameter)')
    ax2.invert_xaxis()
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3, which='both')

    # --- Cumulative M(>l)/M_T view vs phi ---
    phi_sorted = phi_data[order_diam]
    ax2 = axes2[2]
    ax2.plot(phi_sorted, M_gt_l_data, 'o', color='k',
             label='data (empirical)', zorder=5)
    ax2.plot(phi_smooth[order], M_gt_l_fit_sorted, '-', color='crimson', lw=2,
             label='Bi-Rosin-Rammler (from fitted density)')
    ax2.set_xlabel(r'$\phi = -\log_2$(diameter in mm)')
    ax2.set_ylabel(r'$M(>l)/M_T$')
    ax2.set_title('cumulative view (vs phi)')
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3, which='both')

    plt.tight_layout()
    print("\nShowing fit plots -- close the window to finish.")
    plt.show()

    print("\nBi-Rosin-Rammler fit (from clicked starting guess):")
    print(f"  w (coarse mass fraction) = {w_fit:.4f} +/- {w_err:.4f}")
    print(f"  sigma_coarse             = {sigma1_fit:.5f} +/- {s1_err:.5f} mm"
          f"   (phi = {phi1_mode:.3f} +/- {phi1_err:.3f})")
    print(f"  k_coarse                 = {k1_fit:.4f} +/- {k1_err:.4f}")
    print(f"  sigma_fine                = {sigma2_fit:.5f} +/- {s2_err:.5f} mm"
          f"   (phi = {phi2_mode:.3f} +/- {phi2_err:.3f})")
    print(f"  k_fine                   = {k2_fit:.4f} +/- {k2_err:.4f}")
    print(f"  amp                      = {amp_fit:.4f} +/- {amp_err:.4f}")
    print(f"  R^2                      = {r2_bi:.4f}")

    # ---------------------------------------------------------------
    # Shannon entropy of the mass distribution
    # ---------------------------------------------------------------
    mass_frac = wt_pct_norm / wt_pct_norm.sum()
    H, H_norm = entropy_of_info(mass_frac, bin_width=phi_bin_width)
    print(f"Shannon entropy: {H:.3f} bits (normalized: {H_norm:.3f})")

    # ---------------------------------------------------------------
    # Save this fit to the shared results store
    # ---------------------------------------------------------------
    save_fit_result(
        dataset=DATASET_LABEL,
        model="bi_rr",
        params={
            "w": w_fit, "sigma_coarse_mm": sigma1_fit, "k_coarse": k1_fit,
            "sigma_fine_mm": sigma2_fit, "k_fine": k2_fit,
            "amp": amp_fit, "R2": r2_bi,
        },
        rmse=None,
        entropy_bits=H,
        entropy_norm=H_norm,
        phi_bin_width=phi_bin_width,
    )

if __name__ == "__main__":
    main()
