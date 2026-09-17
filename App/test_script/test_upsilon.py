import os
import glob
import io
import sys
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize, root_scalar
from PIL import Image
import warnings

warnings.filterwarnings('ignore', category=RuntimeWarning)

G_grav = 4.30091e-6
rho_crit_local = 2.775e2

class Logger(object):
    def __init__(self, log_filepath):
        self.terminal = sys.stdout
        self.log = open(log_filepath, "w", encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)  

    def flush(self):
        self.terminal.flush()
        self.log.flush()

def create_galaxy_grid(output_folder, cols=4):
    search_pattern = os.path.join(output_folder, "*_combined.png")
    image_files = sorted(glob.glob(search_pattern))
    
    if not image_files: return

    rows = math.ceil(len(image_files) / cols)
    first_img = Image.open(image_files[0])
    img_width, img_height = first_img.size
    
    grid_width = cols * img_width
    grid_height = rows * img_height
    grid_image = Image.new('RGB', (grid_width, grid_height), color='white')
    
    for idx, file in enumerate(image_files):
        img = Image.open(file)
        row = idx // cols
        col = idx % cols
        grid_image.paste(img, (col * img_width, row * img_height))
        img.close()
        
    grid_filename = os.path.join(output_folder, "FINAL_Galaxy_Grid.png")
    grid_image.save(grid_filename)

def M_burkert_enclosed(r, rho_s, r_s):
    x = r / r_s
    return 2.0 * np.pi * rho_s * (r_s**3) * (0.5 * np.log(1.0 + x**2) + np.log(1.0 + x) - np.arctan(x))

def get_rs_rhos_bounds():
    """
    Ricava i limiti rs e rhos mappando l'intera griglia V200, C200 
    esattamente come nello script plot_parameters.py per avere perfetta 
    coerenza tra le mediane.
    """
    v200_vals = np.linspace(10.0, 500.0, 100)
    c200_vals = np.linspace(0.1, 1000.0, 100)
    
    denominatore = np.sqrt((4.0/3.0) * np.pi * G_grav * (200.0 * rho_crit_local))
    
    rs_list = []
    rhos_list = []
    
    for v in v200_vals:
        for c in c200_vals:
            R200 = v / denominatore
            M200 = (v**2 * R200) / G_grav
            rs = R200 / c
            term = 0.5 * np.log(1.0 + c**2) + np.log(1.0 + c) - np.arctan(c)
            rho_s = M200 / (2.0 * np.pi * (rs**3) * term)
            rs_list.append(rs)
            rhos_list.append(rho_s)
            
    return (np.log10(np.min(rs_list)), np.log10(np.max(rs_list))), (np.log10(np.min(rhos_list)), np.log10(np.max(rhos_list)))

def calc_m200_from_profile(rho_s, r_s):
    def find_c200(c):
        term = 0.5 * np.log(1.0 + c**2) + np.log(1.0 + c) - np.arctan(c)
        rho_teorica = (400.0 / 3.0) * rho_crit_local * (c**3) / term
        return rho_teorica - rho_s

    try:
        res_c = root_scalar(find_c200, bracket=[1e-3, 1e5], method='brentq')
        c200_calc = res_c.root
        return (800.0 / 3.0) * np.pi * rho_crit_local * ((c200_calc * r_s)**3)
    except ValueError:
        return 0.0

def fit_galaxy_parameters(r, Vobs, errV, Vgas, Vdisk, Vbul, y_mode, y_bounds):
    dof = max(1, len(r) - 3) 
    verr_safe = np.maximum(errV, 5.0)
    
    rs_bounds, rhos_bounds = get_rs_rhos_bounds()
    
    log_rs_grid = np.linspace(rs_bounds[0], rs_bounds[1], 15)
    log_rhos_grid = np.linspace(rhos_bounds[0], rhos_bounds[1], 15)
    
    if y_mode == "fixed":
        y_grid = [0.5]
        limiti = [rs_bounds, rhos_bounds]
        best_p = (np.mean(rs_bounds), np.mean(rhos_bounds))
    else:
        y_grid = [y_bounds[0], np.mean(y_bounds), y_bounds[1]]
        limiti = [rs_bounds, rhos_bounds, y_bounds]
        best_p = (np.mean(rs_bounds), np.mean(rhos_bounds), np.mean(y_bounds))

    best_chi2 = np.inf
    
    for log_rs in log_rs_grid:
        rs = 10**log_rs
        for log_rhos in log_rhos_grid:
            rho_s = 10**log_rhos
            M_dm_arr = M_burkert_enclosed(r, rho_s, rs)
            V_dm_sq_arr = (G_grav * M_dm_arr) / r
            
            for y in y_grid:
                V_bar_sq = Vgas * np.abs(Vgas) + y * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
                V_tot = np.sqrt(np.maximum(V_bar_sq + V_dm_sq_arr, 0))
                
                chi2 = np.sum(((Vobs - V_tot) / verr_safe)**2) / dof
                if chi2 < best_chi2:
                    best_chi2 = chi2
                    best_p = (log_rs, log_rhos) if y_mode == "fixed" else (log_rs, log_rhos, y)

    def objective_fixed(params):
        log_rs, log_rhos = params
        y_val = 0.5
        rs = 10**log_rs
        rho_s = 10**log_rhos
        V_bar_sq_opt = Vgas * np.abs(Vgas) + y_val * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
        M_dm_opt = M_burkert_enclosed(r, rho_s, rs)
        V_tot_opt = np.sqrt(np.maximum(V_bar_sq_opt + (G_grav * M_dm_opt) / r, 0))
        return np.sum(((Vobs - V_tot_opt) / verr_safe)**2) / dof

    def objective_free(params):
        log_rs, log_rhos, y_val = params
        rs = 10**log_rs
        rho_s = 10**log_rhos
        V_bar_sq_opt = Vgas * np.abs(Vgas) + y_val * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
        M_dm_opt = M_burkert_enclosed(r, rho_s, rs)
        V_tot_opt = np.sqrt(np.maximum(V_bar_sq_opt + (G_grav * M_dm_opt) / r, 0))
        return np.sum(((Vobs - V_tot_opt) / verr_safe)**2) / dof

    obj_func = objective_fixed if y_mode == "fixed" else objective_free
    
    res = minimize(obj_func, best_p, method='SLSQP', bounds=limiti, tol=1e-8)

    if y_mode == "fixed":
        log_rs_fin, log_rhos_fin = res.x
        y_fin = 0.5
    else:
        log_rs_fin, log_rhos_fin, y_fin = res.x

    r_s_fin = 10**log_rs_fin
    rho_s_fin = 10**log_rhos_fin

    # Controllo dettagliato dei bordi
    hit_bounds_info = []
    tolleranza_bordo = 1e-3
    
    for i in range(len(res.x)):
        val = res.x[i]
        b_min, b_max = limiti[i]
        
        if np.isclose(val, b_min, rtol=tolleranza_bordo):
            if i == 0: hit_bounds_info.append(f"r_s al MIN ({10**b_min:.2e} kpc)")
            elif i == 1: hit_bounds_info.append(f"rho_s al MIN ({10**b_min:.2e} M_sun/kpc^3)")
            else: hit_bounds_info.append(f"Upsilon al MIN ({b_min:.2f})")
        elif np.isclose(val, b_max, rtol=tolleranza_bordo):
            if i == 0: hit_bounds_info.append(f"r_s al MAX ({10**b_max:.2e} kpc)")
            elif i == 1: hit_bounds_info.append(f"rho_s al MAX ({10**b_max:.2e} M_sun/kpc^3)")
            else: hit_bounds_info.append(f"Upsilon al MAX ({b_max:.2f})")
            
    hit_bound_str = "SÌ -> " + " | ".join(hit_bounds_info) if hit_bounds_info else "NO"

    m200_fin = calc_m200_from_profile(rho_s_fin, r_s_fin)
    chi2_fin = res.fun if res.success else best_chi2

    return chi2_fin, rho_s_fin, r_s_fin, y_fin, m200_fin, hit_bound_str, res.success, res.message

def run_scenario(y_mode, y_bounds, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    
    log_file = os.path.join(output_folder, "terminal_output.txt")
    sys.stdout = Logger(log_file)
    
    input_folder = "Rotmod_LTG"
    export_file = os.path.join(output_folder, "barke_original.csv")
    latex_file = os.path.join(output_folder, "latex_table.txt")

    q_dict = {}
    mrt_file = "Table.txt"
    if os.path.exists(mrt_file):
        with open(mrt_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                sline = line.strip()
                if not sline or sline.startswith('-') or sline.startswith('='): continue
                parts = sline.split()
                if len(parts) >= 18 and parts[0].upper() != "GALAXY":
                    if parts[17].strip().isdigit():
                        q_dict[parts[0].strip().upper()] = {
                            "Q": int(parts[17].strip()),
                            "Inc": float(parts[5].strip()) if parts[5].strip() else 0.0,
                            "Vflat": float(parts[15].strip()) if parts[15].strip() else 0.0
                        }

    all_files = glob.glob(os.path.join(input_folder, "*"))
    if not all_files: return

    print(f"\n{'='*80}")
    print(f" SCENARIO: Upsilon {y_mode} {y_bounds if y_mode != 'fixed' else '0.5'}")
    print(f"{'='*80}")
    
    results_data = []

    for file in sorted(all_files):
        gal_name = os.path.splitext(os.path.basename(file))[0]
        gal_name_clean = gal_name.replace("_rotmod", "").strip().upper()
        
        gal_info = q_dict.get(gal_name_clean, {"Q": "?", "Inc": 0.0, "Vflat": 0.0})
        if gal_info.get("Q", "?") in [2, 3]: continue
        if gal_info.get("Inc", 0.0) < 30.0: continue
        if gal_info.get("Vflat", 0.0) == 0.0: continue
        
        try:
            with open(file, 'r') as f: lines = f.readlines()
            header_line, data_lines = None, []
            for line in lines:
                if line.startswith('#') and 'Rad' in line: header_line = line.replace('#', '').strip() + '\n'
                elif line.strip() and not line.startswith('#'): data_lines.append(line)
            
            if not header_line: continue
            df = pd.read_csv(io.StringIO(header_line + "".join(data_lines)), sep=r'\s+')
            if 'Rad' not in df.columns: continue
                
            r = df['Rad'].values.astype(float)
            Vobs = df['Vobs'].values.astype(float)
            errV = df['errV'].values.astype(float) if 'errV' in df.columns else np.ones_like(Vobs)*5.0
            Vgas = df['Vgas'].values.astype(float) if 'Vgas' in df.columns else np.zeros_like(Vobs)
            Vdisk = df['Vdisk'].values.astype(float) if 'Vdisk' in df.columns else np.zeros_like(Vobs)
            Vbul = df['Vbul'].values.astype(float) if 'Vbul' in df.columns else np.zeros_like(Vobs)
         
            R_max = r[-1]  
            mid_mask = (r >= 0.4 * R_max) & (r <= 0.6 * R_max)
            out_mask = (r >= 0.8 * R_max)
            
            if np.sum(mid_mask) > 0 and np.sum(out_mask) > 0:
                if ((np.mean(Vobs[out_mask]) - np.mean(Vobs[mid_mask])) / np.mean(Vobs[mid_mask])) * 100.0 > 5.0: continue
            elif len(Vobs) >= 6:
                if ((np.mean(Vobs[-2:]) - np.mean(Vobs[len(Vobs)//2 : len(Vobs)//2 + 2])) / np.mean(Vobs[len(Vobs)//2 : len(Vobs)//2 + 2])) * 100.0 > 5.0: continue
            else: continue
                    
            chi2_min, rho_s, r_s, y_opt, m200, hit_bound_str, success, msg = fit_galaxy_parameters(r, Vobs, errV, Vgas, Vdisk, Vbul, y_mode, y_bounds)
            
            print(f"\n--- {gal_name} ---")
            print(f"Convergenza  : {success} ({msg})")
            print(f"Bordi        : {hit_bound_str}")
            print(f"Parametri    : rho_s={rho_s:.2e}, r_s={r_s:.2f}, Y={y_opt:.2f}")
            print(f"Chi2 Minimo  : {chi2_min:.2f}")
            
            V_bar_sq = Vgas * np.abs(Vgas) + y_opt * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
            V_bar = np.sqrt(np.maximum(V_bar_sq, 0))
            M_dm_grid = M_burkert_enclosed(r, rho_s, r_s)
            V_dm = np.sqrt(np.maximum((G_grav * M_dm_grid) / r, 0))
            V_sim = np.sqrt(np.maximum(V_bar_sq + (G_grav * M_dm_grid) / r, 0))
            
            M_bar_mass = (r * V_bar_sq) / G_grav
            M_tot_mass = M_bar_mass + M_dm_grid
            ratio_dm = M_dm_grid[-1] / M_tot_mass[-1] if M_tot_mass[-1] > 0 else 0.0
            
            results_data.append({
                "Galaxy": gal_name, "Chi2_min": chi2_min, "rho_s": rho_s, "r_s": r_s, 
                "Upsilon": y_opt, "M200": m200, "M_bar_edge": M_bar_mass[-1], "M_DM_edge": M_dm_grid[-1], 
                "M_tot_edge": M_tot_mass[-1], "DM_Fraction_Edge": ratio_dm, "r_edge": r[-1]
            })
            
            rho_burkert_array = rho_s / ((1.0 + r / r_s) * (1.0 + (r / r_s)**2))
            fig, ax1 = plt.subplots(figsize=(10, 6))
            fig.suptitle(f'{gal_name.replace("_rotmod", "")}', fontsize=16, fontweight='bold')
            ax1.errorbar(r, Vobs, yerr=errV, fmt='o', color='blue', ecolor='gray', label='Observations')
            ax1.plot(r, V_bar, '-', color='red', linewidth=2, label='Baryonic')
            ax1.plot(r, V_dm, '-', color='purple', linewidth=2, label='Dark Matter')
            ax1.plot(r, V_sim, '-', color='green', linewidth=2.5, label='Total Simulated')
            ax1.set_xlabel('Radius (kpc)', fontsize=12)
            ax1.set_ylabel('Velocity (km/s)', fontsize=12)
            ax1.set_ylim(0, max(max(Vobs), max(V_sim)) * 1.15)
            ax1.grid(True, linestyle='--', alpha=0.6)
            
            ax2 = ax1.twinx()
            ax2.plot(r, rho_burkert_array, '-', color='darkorange', linewidth=2.5, label='Burkert Density')
            ax2.set_ylabel(r'DM Density ($M_\odot / kpc^3$)', fontsize=12, color='darkorange')
            ax2.set_yscale('log')
            ax2.tick_params(axis='y', labelcolor='darkorange')
            
            lines_1, labels_1 = ax1.get_legend_handles_labels()
            lines_2, labels_2 = ax2.get_legend_handles_labels()
            ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='center right', fontsize=10)
            
            plt.tight_layout()
            plt.savefig(os.path.join(output_folder, f"{gal_name}_combined.png"), dpi=300, bbox_inches='tight')
            plt.close()
            
        except Exception as e:
            pass

    df_results = pd.DataFrame(results_data)
    df_results.to_csv(export_file, index=False, float_format='%.4f')
    
    df_params = pd.DataFrame(results_data)[['Galaxy', 'Upsilon', 'r_s', 'rho_s']]
    df_params.to_csv(os.path.join(output_folder, "galaxy_best_parameters.csv"), index=False)
    
    create_galaxy_grid(output_folder, cols=4)

    with open(latex_file, "w") as f:
        f.write(r"\begin{longtable}{lcccccccc}" + "\n")
        f.write(rf"\caption{{Best-fit parameters for scenario: $\Upsilon$ {y_mode} {y_bounds if y_mode != 'fixed' else '0.5'}}}\\" + "\n")
        f.write(r"\hline" + "\n")
        f.write(r"Galaxy & $\Upsilon$ & $r_s$ [kpc] & $\rho_s$ [$M_\odot/\text{kpc}^3$] & $\chi^2_{\text{min}}$ & $R_{\text{edge}}$ [kpc] & $M_{\text{tot}}$ [$M_\odot$] & $\% \text{DM}$ & $M_{200}$ [$M_\odot$] \\" + "\n")
        f.write(r"\hline" + "\n")
        for res in results_data:
            gal = res["Galaxy"].replace("_rotmod", "").replace("_", r"\_")
            mtot = res["M_tot_edge"]
            perc_dm = res["DM_Fraction_Edge"] * 100
            
            def format_sci(val):
                if val == 0: return "N/A"
                base, exp = f"{val:.2e}".split("e")
                return f"{base} \\times 10^{{{int(exp)}}}"
                
            rhos_latex = format_sci(res["rho_s"])
            mtot_latex = format_sci(mtot)
            m200_latex = format_sci(res["M200"]) if res["M200"] > 0 else "N/A"
            
            f.write(f"{gal} & {res['Upsilon']:.2f} & {res['r_s']:.2f} & ${rhos_latex}$ & {res['Chi2_min']:.2f} & {res['r_edge']:.1f} & ${mtot_latex}$ & {perc_dm:.1f}\\% & ${m200_latex}$ \\\\\n")
        f.write(r"\end{longtable}" + "\n")

    sys.stdout = sys.__stdout__

if __name__ == "__main__":
    run_scenario("fixed", None, "Output_Burkert_Fixed_0.5")
    run_scenario("free", (0.1, 0.9), "Output_Burkert_Free_0.1_0.9")
    run_scenario("free", (0.4, 0.6), "Output_Burkert_Free_0.4_0.6")