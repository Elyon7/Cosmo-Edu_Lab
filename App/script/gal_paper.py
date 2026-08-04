import os
import glob
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize


G_grav = 4.30091e-6
rho_crit_local = 2.775e2

def M_nfw_enclosed(r, rho_s, r_s):
   
    x = r / r_s
    return 4.0 * np.pi * rho_s * (r_s**3) * (np.log(1.0 + x) - x / (1.0 + x))

def observed_rho_from_RC(r, Vobs, Vgas, Vdisk, Vbul, y):
   
    V_bar_sq = Vgas * np.abs(Vgas) + y * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
    V_DM_sq = np.maximum(Vobs**2 - V_bar_sq, 0) 
    q = r**2 * (V_DM_sq / r)
    dq_dr = np.gradient(q, r)
    rho_DM = (1.0 / (4.0 * np.pi * G_grav * r**2)) * dq_dr
    return rho_DM

def fit_galaxy_parameters(r, Vobs, errV, Vgas, Vdisk, Vbul):
 
    dof = max(1, len(r) - 3) 
    
    i_vals = np.arange(1.0, 9.25, 0.25)
    j_vals = np.arange(0, 5, 1)
    base_scan = np.array([i * (10**j) for j in j_vals for i in i_vals])
    
    rho_s_grid = base_scan * rho_crit_local
    r_s_grid = base_scan
    y_grid = np.arange(0.01, 5.01, 0.05)

    verr_safe = np.maximum(errV, 5.0)

    x = r[np.newaxis, :] / r_s_grid[:, np.newaxis] 
    M_dm_rs = 4.0 * np.pi * (r_s_grid[:, np.newaxis]**3) * (np.log(1.0 + x) - x / (1.0 + x))
    
    rho_3d = rho_s_grid[:, np.newaxis, np.newaxis]
    M_3d = M_dm_rs[np.newaxis, :, :]
    r_3d = r[np.newaxis, np.newaxis, :]
    V_dm_sq_grid = G_grav * (rho_3d * M_3d) / r_3d 
    
    best_chi2 = np.inf
    best_p = (None, None, None)
    
    for y in y_grid:
        V_bar_sq = Vgas * np.abs(Vgas) + y * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
        V_bar_sq_3d = V_bar_sq[np.newaxis, np.newaxis, :]
        
        V_tot = np.sqrt(np.maximum(V_bar_sq_3d + V_dm_sq_grid, 0))
        
        chi2_grid = np.sum(((Vobs[np.newaxis, np.newaxis, :] - V_tot) / verr_safe[np.newaxis, np.newaxis, :])**2, axis=2) / dof
        
        min_idx = np.unravel_index(np.argmin(chi2_grid), chi2_grid.shape)
        if chi2_grid[min_idx] < best_chi2:
            best_chi2 = chi2_grid[min_idx]
            best_p = (rho_s_grid[min_idx[0]], r_s_grid[min_idx[1]], y)

    def objective(params):
        rho, rs, y_val = params
        V_bar_sq_opt = Vgas * np.abs(Vgas) + y_val * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
        x_opt = r / rs
        M_dm_opt = 4.0 * np.pi * rho * (rs**3) * (np.log(1.0 + x_opt) - x_opt / (1.0 + x_opt))
        V_tot_opt = np.sqrt(np.maximum(V_bar_sq_opt + (G_grav * M_dm_opt) / r, 0))
        return np.sum(((Vobs - V_tot_opt) / verr_safe)**2) / dof

    res = minimize(objective, best_p, bounds=[(min(rho_s_grid), max(rho_s_grid)), 
                                              (min(r_s_grid), max(r_s_grid)), 
                                              (0.01, 5.0)]) 
    
    if res.success and res.fun < best_chi2:
        return res.fun, res.x[0], res.x[1], res.x[2]
    
    return best_chi2, best_p[0], best_p[1], best_p[2]


def run_pipeline():
    input_folder = "galaxy_data"
    output_folder = "galaxy_plot_paper"
    export_file = "galaxy_best_parameters.csv"
    
    os.makedirs(output_folder, exist_ok=True)
    files = glob.glob(os.path.join(input_folder, "*.txt"))
    
    if not files:
        print(f"Nessun file trovato in {input_folder}")
        return

    
    print("-" * 110)
    print(f"{'Galassia':<10} | {'\u03C7\u00B2 Min':<8} | {'\u03C1_s':<9} | {'r_s':<6} | {'\u03A5':<5} | {'M_bar_edg':<9} | {'M_DM_edg':<9} | {'M_tot_edg':<9} | {'% DM':<6}")
    print(f"{'':<10} | {'':<8} | {'(M_s/kpc\u00B3)':<9} | {'(kpc)':<6} | {'(M/L)':<5} | {'(M_sun)':<9} | {'(M_sun)':<9} | {'(M_sun)':<9} | {'(bordo)':<6}")
    print("-" * 110)

    results_data = []

    for file in sorted(files):
        gal_name = os.path.basename(file).replace('.txt', '')
        
        try:
            with open(file, 'r') as f:
                lines = f.readlines()
            
            cleaned_lines = [line.replace('#', '').strip() + '\n' if line.strip().startswith('#') and 'Rad' in line else line for line in lines if not line.strip().startswith('#') or 'Rad' in line]
                    
            df = pd.read_csv(io.StringIO("".join(cleaned_lines)), sep=r'\s+')
            if 'Rad' not in df.columns:
                print(f"{gal_name:<10} | error")
                continue
                
            r = df['Rad'].values
            Vobs = df['Vobs'].values
            errV = df['errV'].values if 'errV' in df.columns else np.ones_like(Vobs) * 5.0
            Vgas = df['Vgas'].values
            Vdisk = df['Vdisk'].values 
            Vbul = df['Vbul'].values 
            
            chi2_min, rho_s, r_s, y_opt = fit_galaxy_parameters(r, Vobs, errV, Vgas, Vdisk, Vbul)
            
            V_bar_sq = Vgas * np.abs(Vgas) + y_opt * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
            V_bar = np.sqrt(np.maximum(V_bar_sq, 0))
            
            M_dm_grid = M_nfw_enclosed(r, rho_s, r_s)
            V_dm_sq = (G_grav * M_dm_grid) / r
            V_dm = np.sqrt(np.maximum(V_dm_sq, 0))
            
            V_sim = np.sqrt(np.maximum(V_bar_sq + V_dm_sq, 0))
            
            M_bar = (r * V_bar_sq) / G_grav
            M_dm = M_dm_grid
            M_tot = M_bar + M_dm
            
            r_edge = r[-1]
            M_bar_edge = M_bar[-1]
            M_dm_edge = M_dm[-1]
            M_tot_edge = M_tot[-1]
            ratio_dm = M_dm_edge / M_tot_edge
            
            results_data.append({
                "Galaxy": gal_name, 
                "Chi2_min": chi2_min, 
                "rho_s": rho_s, 
                "r_s": r_s, 
                "Upsilon": y_opt,
                "M_bar_edge": M_bar_edge,
                "M_DM_edge": M_dm_edge,
                "M_tot_edge": M_tot_edge,
                "DM_Fraction_Edge": ratio_dm
            })
            
            print(f"{gal_name:<10} | {chi2_min:<8.2f} | {rho_s:<9.2e} | {r_s:<6.2f} | {y_opt:<5.2f} | {M_bar_edge:<9.2e} | {M_dm_edge:<9.2e} | {M_tot_edge:<9.2e} | {ratio_dm*100:>5.1f}%")

            rho_nfw_array = rho_s / ((r / r_s) * (1.0 + r / r_s)**2)
            
           
            fig, axs = plt.subplots(1, 2, figsize=(14, 6))
            fig.suptitle(f'Galaxy - {gal_name}', fontsize=18, fontweight='bold')
            
        
            axs[0].errorbar(r, Vobs, yerr=errV, fmt='o', color='blue', ecolor='gray',label='Observed Data')
            axs[0].plot(r, V_bar, '-', color='red', linewidth=2, label=f'Baryonic (\u03A5={y_opt:.2f})')
            axs[0].plot(r, V_dm, '-', color='purple', linewidth=2, label='Dark Matter (NFW)')
            axs[0].plot(r, V_sim, '-', color='green', linewidth=2.5, label=' Total ')
            axs[0].set(title='Velocity Profile', xlabel='Radius (kpc)', ylabel='Velocity (km/s)')
            axs[0].set_ylim(0, max(max(Vobs), max(V_sim)) * 1.15)
            axs[0].grid(True, linestyle='--', alpha=0.6)
            axs[0].legend()
            
           
            axs[1].plot(r, rho_nfw_array, '-', color='purple', linewidth=2.5, label='NFW Density')
            
            info_text = f'$r_s = {r_s:.2f}$ kpc\n$\\rho_s = {rho_s:.2e}$ $M_\\odot/kpc^3$'
            axs[1].plot([], [], ' ', label=info_text)
            axs[1].set(title='Dark Matter Density Profile', xlabel='Radius (kpc)', ylabel='Density ($M_\odot / kpc^3$)')
            axs[1].set_yscale('log')
            axs[1].set_xscale('log') 
            axs[1].grid(True, which="both", linestyle='--', alpha=0.6)
            axs[1].legend()
            
            plt.tight_layout(rect=[0, 0, 1, 0.95])
            plt.savefig(os.path.join(output_folder, f"{gal_name}.png"), dpi=300, bbox_inches='tight')
            plt.close() 
            
        except Exception as e:
            print(f"{gal_name:<10} | error: {str(e)}")

    df_results = pd.DataFrame(results_data)
    df_results.to_csv(export_file, index=False, float_format='%.4f')
    print("-" * 110)
   
   
    print("\n" + "="*50)
    print(" Table:")
    print("="*50)
    print(r"\begin{table}[h!]")
    print(r"\centering")
    print(r"\begin{tabular}{lcc}")
    print(r"\hline")
    print(r"Galaxy & $M_{\text{tot}} \ [M_\odot]$ & $\% \text{DM}/\text{tot}$ \\")
    print(r"\hline")
    
    for res in results_data:
        gal = res["Galaxy"].replace("_", r"\_") 
        mtot = res["M_tot_edge"]
        perc_dm = res["DM_Fraction_Edge"] * 100
        
       
        base, exp = f"{mtot:.2e}".split("e")
        exp = int(exp) 
        mtot_latex = f"{base} \\times 10^{{{exp}}}"
        
        print(f"{gal} & ${mtot_latex}$ & {perc_dm:.1f}\\% \\\\")
        
    print(r"\hline")
    print(r"\end{tabular}")
    print(r"\caption{Total mass and DM fraction for each galaxy.}")
    print(r"\label{tab:galaxy}")
    print(r"\end{table}")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_pipeline()