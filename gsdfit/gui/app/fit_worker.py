"""
gui/fit_worker.py
==================
Runs curve_fit in a background QThread so clicking doesn't freeze the
UI while scipy works.
"""

import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
import warnings
from PyQt6.QtCore import QThread, pyqtSignal

from gsdfit.gui.models import (
    bi_gaussian, bi_weibull, weibull_component,
    bi_power_law, log_bi_power_law,
    bi_rr_density, rr_density_phi,
    bimodality_B,
)


# ---------------------------------------------------------------------
# Bi-Gaussian
# ---------------------------------------------------------------------
def _fit_bi_gaussian(arrays, clicks):
    phi_labels = arrays["phi"]
    mass_pct = arrays["weight_pct"]
    mass_frac = mass_pct / mass_pct.sum()
    phi_bin_width = arrays["phi_bin_width"]

    (phi1, y1), (phi2, y2) = sorted(clicks, key=lambda pt: pt[0])

    mu1_guess, mu2_guess = phi1, phi2
    default_sigma = 1.0
    y1_frac = max(y1 / mass_pct.sum() if mass_pct.sum() > 0 else 0, 1e-6)
    y2_frac = max(y2 / mass_pct.sum() if mass_pct.sum() > 0 else 0, 1e-6)
    w_guess = y1 / (y1 + y2) if (y1 + y2) > 0 else 0.5

    sigma1_guess = max(w_guess / (y1_frac * np.sqrt(2 * np.pi)), 0.3) if y1_frac > 0 else default_sigma
    sigma2_guess = max((1 - w_guess) / (y2_frac * np.sqrt(2 * np.pi)), 0.3) if y2_frac > 0 else default_sigma
    sigma1_guess = float(np.clip(sigma1_guess, 0.3, 6.0))
    sigma2_guess = float(np.clip(sigma2_guess, 0.3, 6.0))

    p0 = [mu1_guess, sigma1_guess, mu2_guess, sigma2_guess, w_guess]
    phi_span = float(phi_labels.max() - phi_labels.min())
    lb = [phi_labels.min() - phi_span, 0.05, phi_labels.min() - phi_span, 0.05, 0.01]
    ub = [phi_labels.max() + phi_span, phi_span, phi_labels.max() + phi_span, phi_span, 0.99]
    p0 = list(np.clip(p0, lb, ub))

    def bi_gaussian_binned(phi, mu1, sigma1, mu2, sigma2, p):
        return bi_gaussian(phi, mu1, sigma1, mu2, sigma2, p) * phi_bin_width

    popt, pcov = curve_fit(
        bi_gaussian_binned, phi_labels, mass_frac,
        p0=p0, bounds=(lb, ub), maxfev=30000
    )
    perr = np.sqrt(np.diag(pcov))
    mu1, sig1, mu2, sig2, p = popt
    y_fit = bi_gaussian_binned(phi_labels, *popt)
    rmse = float(np.sqrt(np.mean((mass_frac - y_fit) ** 2)) * 100)
    BI = (np.sqrt(2) * abs(mu2 - mu1) / np.sqrt(sig1 ** 2 + sig2 ** 2)
          * np.sqrt(p * (1.0 - p)))
    B = bimodality_B(mu1, mu2, sig1, sig2, p)

    phi_smooth = np.linspace(phi_labels.min() - 1.0, phi_labels.max() + 1.0, 1000)
    y_total = bi_gaussian(phi_smooth, *popt) * phi_bin_width * 100
    y_pop1 = (p / (sig1 * np.sqrt(2 * np.pi))
              * np.exp(-0.5 * ((phi_smooth - mu1) / sig1) ** 2) * phi_bin_width * 100)
    y_pop2 = ((1 - p) / (sig2 * np.sqrt(2 * np.pi))
              * np.exp(-0.5 * ((phi_smooth - mu2) / sig2) ** 2) * phi_bin_width * 100)

    summary = (
        f"BI-GAUSSIAN FIT\n"
        f"  mu1    = {mu1:+.3f} Phi   +/- {perr[0]:.3f}\n"
        f"  sigma1 = {sig1:.3f} Phi   +/- {perr[1]:.3f}\n"
        f"  mu2    = {mu2:+.3f} Phi   +/- {perr[2]:.3f}\n"
        f"  sigma2 = {sig2:.3f} Phi   +/- {perr[3]:.3f}\n"
        f"  p      = {p:.4f}        +/- {perr[4]:.4f}\n"
        f"  BI     = {BI:.3f}  ({'bimodal' if BI > 1.1 else 'unimodal'})\n"
        f"  B      = {B:.3f}\n"
        f"  RMSE   = {rmse:.4f} wt.%"
    )

    return {
        "params": {"mu1": mu1, "sigma1": sig1, "mu2": mu2, "sigma2": sig2,
                    "p": p, "BI": BI, "B": B},
        "rmse": rmse,
        "phi_smooth": phi_smooth,
        "y_total": y_total,
        "y_pop1": y_pop1,
        "y_pop2": y_pop2,
        "total_label": "Bi-Gaussian fit",
        "pop1_label": f"Coarse Pop.  $\\mu_1$ = {mu1:.2f} $\\phi$, $\\sigma_1$ = {sig1:.3f}",
        "pop2_label": f"Fine Pop.  $\\mu_2$ = {mu2:.2f} $\\phi$, $\\sigma_2$ = {sig2:.3f}",
        "summary_text": summary,
    }


# ---------------------------------------------------------------------
# Bi-Weibull
# ---------------------------------------------------------------------
def _fit_bi_weibull(arrays, clicks):
    phi_labels = arrays["phi"]
    mass_pct = arrays["weight_pct"]
    mass_frac = mass_pct / mass_pct.sum()
    phi_bin_width = arrays["phi_bin_width"]

    (phi1, y1), (phi2, y2) = sorted(clicks, key=lambda pt: pt[0])

    lam1_guess = 2.0 ** (-phi1)
    lam2_guess = 2.0 ** (-phi2)
    n1_guess = 1.0
    n2_guess = 1.0
    q_guess = y1 / (y1 + y2) if (y1 + y2) > 0 else 0.5

    p0 = [lam1_guess, n1_guess, lam2_guess, n2_guess, q_guess]
    lb = [1e-4, 0.05, 1e-7, 0.05, 0.01]
    ub = [500., 5.0, 10., 5.0, 0.99]
    p0 = list(np.clip(p0, lb, ub))

    def bi_weibull_binned(phi, lam1, n1, lam2, n2, q):
        return bi_weibull(phi, lam1, n1, lam2, n2, q) * phi_bin_width

    popt, pcov = curve_fit(
        bi_weibull_binned, phi_labels, mass_frac,
        p0=p0, bounds=(lb, ub), maxfev=30000
    )
    perr = np.sqrt(np.diag(pcov))
    lam1, n1, lam2, n2, q = popt
    y_fit = bi_weibull_binned(phi_labels, *popt)
    rmse = float(np.sqrt(np.mean((mass_frac - y_fit) ** 2)) * 100)
    lam1_phi = -np.log2(lam1)
    lam2_phi = -np.log2(lam2)

    phi_smooth = np.linspace(phi_labels.min() - 1.0, phi_labels.max() + 1.0, 1000)
    y_total = bi_weibull(phi_smooth, *popt) * phi_bin_width * 100
    y_pop1 = q * weibull_component(phi_smooth, lam1, n1) * phi_bin_width * 100
    y_pop2 = (1 - q) * weibull_component(phi_smooth, lam2, n2) * phi_bin_width * 100

    summary = (
        f"BI-LENGTH BIASED WEIBULL FIT\n"
        f"  lambda1 = {lam1:.4f} mm ({lam1_phi:+.3f} Phi)  +/- {perr[0]:.4f}\n"
        f"  n1      = {n1:.4f}  +/- {perr[1]:.4f}\n"
        f"  lambda2 = {lam2:.6f} mm ({lam2_phi:+.3f} Phi)  +/- {perr[2]:.6f}\n"
        f"  n2      = {n2:.4f}  +/- {perr[3]:.4f}\n"
        f"  q       = {q:.4f}  +/- {perr[4]:.4f}\n"
        f"  RMSE    = {rmse:.4f} wt.%"
    )

    return {
        "params": {"lambda1_mm": lam1, "n1": n1, "lambda2_mm": lam2,
                    "n2": n2, "q": q},
        "rmse": rmse,
        "phi_smooth": phi_smooth,
        "y_total": y_total,
        "y_pop1": y_pop1,
        "y_pop2": y_pop2,
        "total_label": "Bi-Length Biased Weibull fit",
        "pop1_label": f"Coarse Pop.  $\\lambda_1$ = {lam1:.3f} mm, $n_1$= {n1:.3f}",
        "pop2_label": f"Fine Pop.  $\\lambda_2$ = {lam2:.5f} mm, $n_2$ = {n2:.3f}",
        "summary_text": summary,
    }


# ---------------------------------------------------------------------
# Bi-Rosin-Rammler -- PDF (density fit only; no cumulative here)
# ---------------------------------------------------------------------
def _fit_bi_rr(arrays, clicks):
    phi_data = arrays["phi"]
    wt_pct_norm = arrays["weight_pct"]
    phi_bin_width = arrays["phi_bin_width"]

    # rr_clicker.py expects (coarse_click, fine_click) IN ORDER, unsorted --
    # coarse first, fine second. Our clicks come in whatever order the user
    # clicked, so sort by phi (fine phi is numerically larger) to guarantee
    # coarse-then-fine regardless of click order.

    (phi_coarse, y_coarse), (phi_fine, y_fine) = sorted(clicks, key=lambda pt: pt[0])

    sigma1_guess = 2.0 ** (-phi_coarse)
    sigma2_guess = 2.0 ** (-phi_fine)
    amp_guess = max(y_coarse, y_fine) * 2.0
    w_guess = y_coarse / (y_coarse + y_fine) if (y_coarse + y_fine) > 0 else 0.5

    p0 = [w_guess, sigma1_guess, 4.0, sigma2_guess, 4.0, amp_guess]
    lower = [0.0, 1e-4, 0.3, 1e-4, 0.3, 1]
    upper = [1.0, 50.0, 15.0, 50.0, 15.0, 500]
    p0 = list(np.clip(p0, lower, upper))

    ss_tot = np.sum((wt_pct_norm - wt_pct_norm.mean()) ** 2)

    popt, pcov = curve_fit(
        bi_rr_density, phi_data, wt_pct_norm,
        p0=p0, bounds=(lower, upper), maxfev=50000
    )
    w_fit, lambda1_fit, n1_fit, lambda2_fit, n2_fit, amp_fit = popt
    fit_vals = bi_rr_density(phi_data, *popt)
    r2 = float(1 - np.sum((wt_pct_norm - fit_vals) ** 2) / ss_tot)
    perr = np.sqrt(np.diag(pcov))
    w_err, s1_err, k1_err, s2_err, k2_err, amp_err = perr

    if lambda1_fit < lambda2_fit:
        w_fit = 1 - w_fit
        lambda1_fit, lambda2_fit = lambda2_fit, lambda1_fit
        n1_fit, n2_fit = n2_fit, n1_fit
        s1_err, s2_err = s2_err, s1_err
        k1_err, k2_err = k2_err, k1_err

    phi1_mode = -np.log2(lambda1_fit)
    phi2_mode = -np.log2(lambda2_fit)

    phi_smooth = np.linspace(phi_data.min() - 0.5, phi_data.max() + 0.5, 1000)
    y_total = bi_rr_density(phi_smooth, w_fit, lambda1_fit, n1_fit, lambda2_fit, n2_fit, amp_fit)
    y_pop1 = amp_fit * w_fit * rr_density_phi(phi_smooth, lambda1_fit, n1_fit)
    y_pop2 = amp_fit * (1 - w_fit) * rr_density_phi(phi_smooth, lambda2_fit, n2_fit)

    summary = (
        f"BI-ROSIN-RAMMLER FIT (PDF)\n"
        f"  w (coarse mass fraction) = {w_fit:.4f} +/- {w_err:.4f}\n"
        f"  lambda_coarse = {lambda1_fit:.5f} mm (phi={phi1_mode:.3f})  +/- {s1_err:.5f}\n"
        f"  n_coarse     = {n1_fit:.4f}  +/- {k1_err:.4f}\n"
        f"  lambda_fine   = {lambda2_fit:.5f} mm (phi={phi2_mode:.3f})  +/- {s2_err:.5f}\n"
        f"  k_fine       = {n2_fit:.4f}  +/- {k2_err:.4f}\n"
        f"  amp          = {amp_fit:.4f}  +/- {amp_err:.4f}\n"
        f"  R^2          = {r2:.4f}"
    )

    return {
        "params": {"w": w_fit, "sigma_coarse_mm": lambda1_fit, "n_coarse": n1_fit,
                    "lambda_fine_mm": lambda2_fit, "k_fine": n2_fit,
                    "amp": amp_fit, "R2": r2},
        "rmse": None,
        "phi_smooth": phi_smooth,
        "y_total": y_total,
        "y_pop1": y_pop1,
        "y_pop2": y_pop2,
        "total_label": f"Bi-Rosin-Rammler fit (R\u00b2={r2:.3f})",
        "pop1_label": f"Coarse Pop.  $d'_c$={lambda1_fit:.3f} mm, $k_c$={n1_fit:.3f}",
        "pop2_label": f"Fine Pop.  $d'_f$={lambda2_fit:.3f} mm, $k_f$={n2_fit:.3f}",
        "summary_text": summary,
    }


# ---------------------------------------------------------------------
# Bi-Rosin-Rammler -- Cumulative (independent fit against M(>l)/M_T)
# ---------------------------------------------------------------------
def _bi_rr_cdf(phi, w, sigma1, k1, sigma2, k2):
    """
    Cumulative 'coarser than' curve M(>l)/M_T for the bi-Rosin-Rammler
    distribution, in closed form -- the Rosin-Rammler density
    integrates analytically, so this is fit directly rather than by
    numerically integrating a separately-fitted density.
    """
    l = 2.0 ** (-phi)
    surv1 = 1.0 - np.exp(-(l / sigma1) ** k1)
    surv2 = 1.0 - np.exp(-(l / sigma2) ** k2)
    return w * surv1 + (1.0 - w) * surv2


def _fit_bi_rr_cdf(arrays, clicks=None):
    """
    Independently fits the bi-Rosin-Rammler cumulative curve M(>l)/M_T
    directly against the empirical cumulative data. Fully automatic --
    no clicks needed. `clicks` is accepted (and ignored) only to keep
    the same call signature as every other MODEL_FIT_FUNCS entry.
    """
    phi_data = arrays["phi"]
    wt_pct_norm = arrays["weight_pct"]

    # Empirical cumulative "coarser than" curve, M(>l)/M_T. Diameter
    # l = 2^-phi is a DECREASING function of phi, so the coarse end of
    # the sample sits at very NEGATIVE phi (huge l) and the fine end at
    # very POSITIVE phi (tiny l). Confirmed against a reference plot:
    # M(>l)/M_T -> 1 at the coarse (low-phi) end and -> 0 at the fine
    # (high-phi) end -- i.e. the curve DECREASES as phi increases. This
    # is 1 minus the cumulative mass fraction from the fine end, i.e.
    # the cumulative mass fraction STRICTLY COARSER than the current
    # bin, shifted by one bin so a bin's own mass isn't counted as
    # "coarser than itself".
    order = np.argsort(phi_data)
    phi_data_sorted = phi_data[order]
    mass_frac_sorted = wt_pct_norm[order] / wt_pct_norm.sum()
    M_gt_l_data = 1.0 - np.cumsum(mass_frac_sorted)
    M_gt_l_data = np.concatenate(([1.0], M_gt_l_data[:-1]))
    diam_mm_data = 2.0 ** (-phi_data_sorted)

    phi_span = float(phi_data.max() - phi_data.min())

    def _phi_at_quantile(q):
        """phi where the empirical M(>l)/M_T curve crosses value q.
        The curve is DECREASING in phi, so reverse both arrays before
        np.interp, which requires increasing x."""
        m_rev = M_gt_l_data[::-1]
        phi_rev = phi_data_sorted[::-1]
        return float(np.interp(q, m_rev, phi_rev))

    # Since the curve FALLS with phi, the coarse component's
    # characteristic scale sits nearer the HIGH-quantile crossing
    # (large M, low/negative phi) and the fine component's nearer the
    # LOW-quantile crossing (small M, high/positive phi).
    phi_75 = _phi_at_quantile(0.75)
    phi_25 = _phi_at_quantile(0.25)
    phi_50 = _phi_at_quantile(0.50)

    # local steepness near each crossing, from the empirical curve's
    # own slope -- steeper => higher k. Guard against zero/negative
    # dphi from duplicate or unsorted points.
    def _local_slope(phi_at, window=None):
        window = window or max(phi_span * 0.05, 1e-6)
        mask = np.abs(phi_data_sorted - phi_at) <= window
        if mask.sum() < 2:
            return 1.0
        xs = phi_data_sorted[mask]
        ys = M_gt_l_data[mask]
        dphi = xs.max() - xs.min()
        if dphi <= 1e-9:
            return 1.0
        return float(abs((ys[np.argmax(xs)] - ys[np.argmin(xs)]) / dphi))

    slope_75 = _local_slope(phi_75)
    slope_25 = _local_slope(phi_25)
    k_guess_coarse = float(np.clip(1.0 + slope_75 * 2.0, 0.5, 10.0))
    k_guess_fine = float(np.clip(1.0 + slope_25 * 2.0, 0.5, 10.0))

    # coarse component (subscript 1) -> high-M/low-phi crossing;
    # fine component (subscript 2) -> low-M/high-phi crossing
    sigma1_guess = float(np.clip(2.0 ** (-phi_75), 1e-6, 1e6))
    sigma2_guess = float(np.clip(2.0 ** (-phi_25), 1e-6, 1e6))

    # w guess from the curve's value at its flattest (lowest-slope)
    # point in the middle of the phi range -- approximates the
    # plateau height, i.e. the coarse population's mass fraction.
    # Falls back to 0.5 if no clear interior plateau exists.
    interior = (phi_data_sorted > phi_data_sorted.min() + 0.1 * phi_span) & \
               (phi_data_sorted < phi_data_sorted.max() - 0.1 * phi_span)
    if interior.sum() >= 3:
        interior_phi = phi_data_sorted[interior]
        interior_m = M_gt_l_data[interior]
        grad = np.abs(np.gradient(interior_m, interior_phi))
        w_guess = float(np.clip(interior_m[np.argmin(grad)], 0.05, 0.95))
    else:
        w_guess = 0.5

    p0_base = [w_guess, sigma1_guess, k_guess_coarse, sigma2_guess, k_guess_fine]

    # Bounds scaled to the dataset's own phi range rather than a fixed
    # mm window -- fixed bounds let sigma/k collapse onto an arbitrary
    # wall far from any physically sensible value for datasets whose
    # actual size range sits elsewhere.
    sigma_lo = float(np.clip(2.0 ** (-(phi_data.max() + phi_span)), 1e-6, 1e-3))
    sigma_hi = float(np.clip(2.0 ** (-(phi_data.min() - phi_span)), 1e3, 1e6))
    lower = [0.0, sigma_lo, 0.3, sigma_lo, 0.3]
    upper = [1.0, sigma_hi, 15.0, sigma_hi, 15.0]
    p0_base = list(np.clip(p0_base, lower, upper))

    ss_tot = np.sum((M_gt_l_data - M_gt_l_data.mean()) ** 2)

    rng = np.random.default_rng(0)
    n_trials = 20
    best_r2 = -np.inf
    best_popt = None
    best_pcov = None

    for trial in range(n_trials):
        if trial == 0:
            p0_trial = p0_base
        else:
            factors = rng.uniform(0.5, 1.8, size=5)
            p0_trial = list(np.clip(np.array(p0_base) * factors, lower, upper))

        try:
            popt_trial, pcov_trial = curve_fit(
                _bi_rr_cdf, phi_data_sorted, M_gt_l_data,
                p0=p0_trial, bounds=(lower, upper), maxfev=50000
            )
        except RuntimeError:
            continue

        fit_vals_trial = _bi_rr_cdf(phi_data_sorted, *popt_trial)
        if not np.all(np.isfinite(fit_vals_trial)):
            continue
        ss_res_trial = np.sum((M_gt_l_data - fit_vals_trial) ** 2)
        r2_trial = float(1 - ss_res_trial / ss_tot) if ss_tot > 0 else float("nan")

        if r2_trial > best_r2:
            best_r2 = r2_trial
            best_popt = popt_trial
            best_pcov = pcov_trial

    if best_popt is None:
        raise RuntimeError(
            "All multistart attempts failed to converge for the "
            "Bi-Rosin-Rammler Cumulative fit."
        )

    popt, pcov, r2 = best_popt, best_pcov, best_r2
    w_fit, sigma1_fit, k1_fit, sigma2_fit, k2_fit = popt
    perr = np.sqrt(np.diag(pcov))
    w_err, s1_err, k1_err, s2_err, k2_err = perr

    if sigma1_fit < sigma2_fit:
        w_fit = 1 - w_fit
        sigma1_fit, sigma2_fit = sigma2_fit, sigma1_fit
        k1_fit, k2_fit = k2_fit, k1_fit
        s1_err, s2_err = s2_err, s1_err
        k1_err, k2_err = k2_err, k1_err

    phi1_mode = -np.log2(sigma1_fit)
    phi2_mode = -np.log2(sigma2_fit)

    phi_smooth = np.linspace(phi_data.min() - 0.5, phi_data.max() + 0.5, 1000)
    M_gt_l_fit = _bi_rr_cdf(phi_smooth, *popt)
    diam_mm_fit = 2.0 ** (-phi_smooth)

    rr_cumulative = {
        "phi_data_sorted": phi_data_sorted,
        "diam_mm_data": diam_mm_data,
        "M_gt_l_data": M_gt_l_data,
        "phi_fit_sorted": phi_smooth,
        "diam_mm_fit": diam_mm_fit,
        "M_gt_l_fit": M_gt_l_fit,
    }

    summary = (
        f"BI-ROSIN-RAMMLER FIT (CUMULATIVE, automatic, best of {n_trials} attempts)\n"
        f"  w (coarse mass fraction) = {w_fit:.4f} +/- {w_err:.4f}\n"
        f"  sigma_coarse = {sigma1_fit:.5f} mm (phi={phi1_mode:.3f})  +/- {s1_err:.5f}\n"
        f"  k_coarse     = {k1_fit:.4f}  +/- {k1_err:.4f}\n"
        f"  sigma_fine   = {sigma2_fit:.5f} mm (phi={phi2_mode:.3f})  +/- {s2_err:.5f}\n"
        f"  k_fine       = {k2_fit:.4f}  +/- {k2_err:.4f}\n"
        f"  R^2          = {r2:.4f}"
    )

    return {
        "params": {"w": w_fit, "sigma_coarse_mm": sigma1_fit, "k_coarse": k1_fit,
                    "sigma_fine_mm": sigma2_fit, "k_fine": k2_fit, "R2": r2},
        "rmse": None,
        "cum_label": f"$\\sigma_1$={sigma1_fit:.3f} mm, $k_1$={k1_fit:.3f}, "
                     f"$\\sigma_2$={sigma2_fit:.3f} mm, $k_2$={k2_fit:.3f}",
        "summary_text": summary,
        "rr_cumulative": rr_cumulative,
    }


# ---------------------------------------------------------------------
# Bi-power-law
# ---------------------------------------------------------------------
def _fit_bi_power_law(arrays, clicks):
    Phi = arrays["phi"]
    d_mm = arrays["size_mm"]
    massp = arrays["weight_pct"]
    density = arrays["density"]

    valid = ~np.isnan(d_mm) & ~np.isnan(massp) & ~np.isnan(Phi) & (d_mm > 0)
    Phi, d_mm, massp = Phi[valid], d_mm[valid], massp[valid]
    order = np.argsort(Phi)
    Phi, d_mm, massp = Phi[order], d_mm[order], massp[order]

    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        num_raw = massp / (density*(d_mm ** 3))
    num_raw[~np.isfinite(num_raw)] = 0.0
    no_data = num_raw / np.sum(num_raw)

    N_cum = np.cumsum(no_data)
    N_cum = N_cum / N_cum[-1]

    mask = N_cum > 0
    phi_masked = Phi[mask]
    N_masked = N_cum[mask]
    logN_masked = np.log10(N_masked)

    # Derive a crossover guess from the two peak clicks (offset outward
    # from each) since we only get peak clicks here, not hand-picked
    # crossovers as in the original pl_clciker.py.
    (phi_coarse, _), (phi_fine, _) = sorted(clicks, key=lambda pt: pt[0])
    offset_phi = 2.0
    lamc_guess = phi_coarse - offset_phi
    lamf_guess = phi_fine + offset_phi

    Df0_guess = 3.0
    Dc0_guess = 3.0
    p0 = [lamf_guess, lamc_guess, Df0_guess, Dc0_guess]
    lower = [-20, -20, 0.1, 0.1]
    upper = [20, 20, 15, 15]
    p0 = list(np.clip(p0, lower, upper))

    rng = np.random.default_rng(0)
    n_trials = 20
    best_fval = np.inf
    p_fit = None

    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        for trial in range(n_trials):
            if trial == 0:
                p0_trial = p0
            else:
                factors = rng.uniform(0.5, 1.8, size=2)
                offset_trial = offset_phi * rng.uniform(0.4, 2.0)
                lamc_t = np.clip(phi_coarse - offset_trial, lower[1], upper[1])
                lamf_t = np.clip(phi_fine + offset_trial, lower[0], upper[0])
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
            fval_trial = float(np.sum(resid_trial ** 2))

            if fval_trial < best_fval:
                best_fval = fval_trial
                p_fit = popt_trial

    if p_fit is None:
        raise RuntimeError(
            "All multistart attempts failed to converge from these clicks. "
            "Try clicking closer to each mode's peak."
        )

    lambda_f, lambda_c, Df, Dc = p_fit

    phi_smooth = np.linspace(Phi.min() - 1, Phi.max() + 1, 1000)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        y_total = bi_power_law(phi_smooth, *p_fit)

    summary = (
        f"BI-POWER-LAW FIT (best of {n_trials} multistart attempts)\n"
        f"  Constant Density? {len(density)==1}\n"
        f"  lambda_f = {lambda_f:.4g} Phi\n"
        f"  lambda_c = {lambda_c:.4g} Phi\n"
        f"  Df       = {Df:.3f}\n"
        f"  Dc       = {Dc:.3f}\n"
        f"  log10 RMSE^2 = {best_fval:.4f}"
    )

    return {
        "params": {"lambda_f": lambda_f, "lambda_c": lambda_c, "Df": Df, "Dc": Dc},
        "rmse": None,
        "phi_smooth": phi_smooth,
        "y_total": y_total,
        "total_label": "Bi-power-law fit (cumulative N)",
        "summary_text": summary,
        # bi-power-law's natural axes (cumulative N vs phi, log-y) differ
        # from the other three models' mass-density bars -- plot_tab
        # checks this flag to draw it on its own semilog panel.
        "is_cumulative": True,
        "cumulative_data": {"phi": Phi, "N_cum": N_cum},
    }


MODEL_FIT_FUNCS = {
    "bi_gaussian": _fit_bi_gaussian,
    "bi_lb_weibull": _fit_bi_weibull,
    "bi_rr_pdf": _fit_bi_rr,
    "bi_rr_cdf": _fit_bi_rr_cdf,
    "bi_power_law": _fit_bi_power_law,
}

MODEL_LABELS = {
    "bi_gaussian": "Bi-Gaussian",
    "bi_lb_weibull": "Bi-Length Biased Weibull",
    "bi_rr_pdf": "Bi-Rosin-Rammler (PDF)",
    "bi_rr_cdf": "Bi-Rosin-Rammler (Cumulative)",
    "bi_power_law": "Bi-power-law",
}


class FitWorker(QThread):
    """
    Fits every model in model_keys from the same set of clicks (pass
    an empty list for click-free models like bi_rr_cdf, which derives
    its own starting guess automatically). Emits progress per-model as
    each finishes (so partial results show up even if one model
    fails), then a final all_finished signal.
    """
    model_done = pyqtSignal(str, dict)     # (model_key, result)
    model_failed = pyqtSignal(str, str)    # (model_key, message)
    all_finished = pyqtSignal()

    def __init__(self, model_keys, arrays, clicks, parent=None):
        super().__init__(parent)
        self.model_keys = list(model_keys)
        self.arrays = arrays
        self.clicks = list(clicks)

    def run(self):
        for model_key in self.model_keys:
            fit_func = MODEL_FIT_FUNCS.get(model_key)
            if fit_func is None:
                self.model_failed.emit(model_key, f"Unknown model '{model_key}'.")
                continue
            try:
                result = fit_func(self.arrays, self.clicks)
            except Exception as e:
                self.model_failed.emit(model_key, f"{type(e).__name__}: {e}")
                continue
            self.model_done.emit(model_key, result)
        if "cd_bi_power" in self.model_keys:
            print("fitting constant density aswell")
            self.arrays["density"]=[1.0]
            result = _fit_bi_power_law(self.arrays,self.clicks)
            self.model_done.emit("cd_bi_power",result)

        self.all_finished.emit()
