import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.integrate import quad

G_grav = 4.30091e-6
c_light = 3e5
H0 = 70.0
def create_cluster_grid(output_dir, cols=3):
    """Stitches individual cluster histograms into a single grid image."""
    import math
    from PIL import Image

    # Find all histogram plots
    search_pattern = os.path.join(output_dir, "*_histogram.png")
    image_files = sorted(glob.glob(search_pattern))
    
    if not image_files:
        print("No cluster histograms found to create a grid.")
        return

    # Calculate grid dimensions
    rows = math.ceil(len(image_files) / cols)
    
    # Open first image to get dimensions
    first_img = Image.open(image_files[0])
    img_width, img_height = first_img.size
    
    # Create canvas
    grid_width = cols * img_width
    grid_height = rows * img_height
    grid_image = Image.new('RGB', (grid_width, grid_height), color='white')
    
    # Paste images
    for idx, file in enumerate(image_files):
        img = Image.open(file)
        row = idx // cols
        col = idx % cols
        x_offset = col * img_width
        y_offset = row * img_height
        grid_image.paste(img, (x_offset, y_offset))
        img.close()
        
    # Save the final composite image
    grid_filename = os.path.join(output_dir, "FINAL_Cluster_Grid.png")
    grid_image.save(grid_filename)
    print(f"Cluster histogram grid successfully saved to {grid_filename}")
def comoving_distance_Mpc(z, Om=0.3):
    integrand = lambda zp: 1.0 / np.sqrt(Om*(1.0+zp)**3 + (1.0-Om))
    chi, _ = quad(integrand, 0.0, z)
    return (c_light / H0) * chi

def angular_diameter_distance_Mpc(z, Om=0.3):
    return comoving_distance_Mpc(z, Om) / (1.0 + z)

def rho_crit_Msunkpc3():
    H0_kpc = H0 / 1000.0
    return 3.0 * (H0_kpc**2) / (8.0 * np.pi * G_grav)

def angsep_rad(ra1_deg, dec1_deg, ra2_deg, dec2_deg):
    ra1 = np.deg2rad(ra1_deg); dec1 = np.deg2rad(dec1_deg)
    ra2 = np.deg2rad(ra2_deg); dec2 = np.deg2rad(dec2_deg)
    cos_theta = np.clip(np.sin(dec1)*np.sin(dec2) + np.cos(dec1)*np.cos(dec2)*np.cos(ra1 - ra2), -1.0, 1.0)
    return np.arccos(cos_theta)

def estimate_M200_R200_from_sigma(sigma_obs, rho_crit_local):
    if sigma_obs <= 0: return 1e14, 1000.0
    R200 = np.sqrt((9.0 * sigma_obs**2) / (4.0 * np.pi * G_grav * 200.0 * rho_crit_local))
    M200 = (4.0/3.0) * np.pi * 200.0 * rho_crit_local * R200**3
    return M200, R200

def run_cluster_analysis():
    coma_files = glob.glob("data/Abell1656(Coma).csv") + glob.glob("Abell1656(Coma).csv")
    abell_files = glob.glob("cluster_data_tot/Abell*.txt") + glob.glob("Abell*.txt")
    all_files = list(set(coma_files + abell_files))
    
    output_dir = "cluster_plots_tot_dataset_filter"
    os.makedirs(output_dir, exist_ok=True)
    
    rho_crit = rho_crit_Msunkpc3()

    print(f"{'Cluster':<15} | {'M_tot (M_sun)':<12} | {'% DM':<8} | {'% Gas':<8} | {'% Star':<8}")
    print("-" * 65)
    results_data = []
   
    debug_data = []
    for file in sorted(all_files):
        cluster_name = os.path.basename(file).replace('.txt', '').replace('.csv', '')
        try:
            if "coma" in cluster_name.lower():
                df = pd.read_csv(file, skiprows=1)
                df.columns = ['objid','ra','dec','modelmag_r','modelmagerr_r','extinction_r','redshift','zErr']
                df = df.dropna(subset=['ra', 'dec', 'redshift', 'modelmag_r'])
                df['RV'] = c_light * df['redshift']
                n_iniziale = len(df)
                counts, bin_edges = np.histogram(df["RV"], bins=50)
                v_peak = (bin_edges[np.argmax(counts)] + bin_edges[np.argmax(counts) + 1]) / 2.0
                df = df[(df["RV"] >= v_peak - 6000) & (df["RV"] <= v_peak + 6000)]
                members = df.copy()
                for _ in range(5):
                    v_rel = members["RV"] - np.median(members["RV"])
                    mad = np.median(np.abs(v_rel))
                    sigma_clip = 1.4826 * mad if mad > 0 else np.std(v_rel)
                    mask = np.abs(v_rel) <= 3 * sigma_clip
                    new_members = members[mask]
                    if len(new_members) == len(members): break
                    members = new_members
                    
                if len(members) < 5:
                    print(f"{cluster_name:<15} | SCARTATO: Solo {len(members)} membri post-filtro (ne servono almeno 5)")
                    continue
                observed_vel = members['RV'].values
                z_cluster = np.nanmedian(members['redshift'].values)
                center_ra = np.nanmedian(members['ra'].values)
                center_dec = np.nanmedian(members['dec'].values)
                
                D_A_kpc = angular_diameter_distance_Mpc(z_cluster) * 1000.0
                theta_rad = angsep_rad(members['ra'].values, members['dec'].values, center_ra, center_dec)
                r = np.maximum(theta_rad * D_A_kpc, 1e-3)
                
                M_sun_r = 4.67
                mag = members['modelmag_r'].values - members['extinction_r'].values
                D_L_Mpc = (c_light * z_cluster) / H0
                dist_mod = 5 * np.log10(D_L_Mpc * 1e6) - 5
                M_abs = mag - dist_mod
                L_B = 10.0**(0.4 * (M_sun_r - M_abs))
                MLR = 2.0
                
            else:
                df = pd.read_csv(file, sep=r"\s+", header=None)
                if df.shape[1] == 7: df[7] = np.nan
                df = df.iloc[:, :8]
                df.columns = ["Cluster", "ID", "RAdeg", "DEdeg", "RV", "e_RV", "q_RV", "bmag"]
                for col in ["RAdeg", "DEdeg", "RV", "bmag"]: df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df.dropna(subset=["RAdeg", "DEdeg", "RV", "bmag"])
                df = df[df["bmag"] > 0.0]
                n_iniziale = len(df)
                counts, bin_edges = np.histogram(df["RV"], bins=50)
                v_peak = (bin_edges[np.argmax(counts)] + bin_edges[np.argmax(counts) + 1]) / 2.0
                df = df[(df["RV"] >= v_peak - 6000) & (df["RV"] <= v_peak + 6000)]
                
               
                members = df.copy()
                for _ in range(5):
                    v_rel = members["RV"] - np.median(members["RV"])
                    mad = np.median(np.abs(v_rel))
                    sigma_clip = 1.4826 * mad if mad > 0 else np.std(v_rel)
                    mask = np.abs(v_rel) <= 3 * sigma_clip
                    new_members = members[mask]
                    if len(new_members) == len(members): break
                    members = new_members
                    
                if len(members) < 5: continue
                cluster_distance = np.median(members["RV"]) / H0
                z_cluster = np.nanmedian(members["RV"] / c_light)
                
                mean_ra, mean_dec = members["RAdeg"].mean(), members["DEdeg"].mean()
                ang_sep = np.sqrt(((members["RAdeg"] - mean_ra) * np.cos(np.radians(mean_dec)))**2 + (members["DEdeg"] - mean_dec)**2)
                r = cluster_distance * 1000 * np.radians(ang_sep)
                members = members.assign(r_kpc=r).dropna(subset=["r_kpc"])
                #members = members[members["r_kpc"] <= 3000]
                
                r = members["r_kpc"].values
                observed_vel = members["RV"].values
                bmag = members["bmag"].values
                
                D_pc = cluster_distance * 1e6
                dist_mod = 5*np.log10(D_pc) - 5
                M_abs = bmag - dist_mod
                L_B = 10**(-0.4*(M_abs - 5.48))
                MLR = 5.0 
            
            order = np.argsort(r)
            r_sorted = r[order]
            observed_vel_sorted = observed_vel[order]
            
            L_cum = np.cumsum(L_B[order])
            M_lum_r = MLR * L_cum
            M_star_tot = M_lum_r[-1]
            
            if "coma" in cluster_name.lower():
                sigma_global = np.std(observed_vel_sorted)
            else:
                sigma_global = np.std(observed_vel_sorted - np.median(observed_vel_sorted))
                
            M200, R200 = estimate_M200_R200_from_sigma(sigma_global, rho_crit)
            M_tot = M200
            
            
            n_finale = len(observed_vel_sorted)
            v_mean_obs = np.mean(observed_vel_sorted) 

           
            
            debug_data.append({
                "Cluster": cluster_name,
                "N_iniziale": n_iniziale,
                "N_finale": n_finale,
                "V_mean": v_mean_obs,
                "Sigma": sigma_global
            })
            if M_tot > 5e15:
                print(f"{cluster_name:<15} | SCARTATO: Massa M_tot esagerata ({M_tot:.2e} M_sun > 5e15)")
                continue
            elif M_tot < 1e13:
                print(f"{cluster_name:<15} | SCARTATO: Massa M_tot irrisoria ({M_tot:.2e} M_sun < 1e13)")
                continue
            
            f_gas_global = 0.093 * (((0.7 * M_tot) / 2e14)**0.21)
            M_gas_tot = (0.7 * M_tot) * f_gas_global
            
            M_DM_tot = np.maximum(0.0, M_tot - M_star_tot - M_gas_tot)
            
            perc_dm = (M_DM_tot / M_tot) * 100.0
            perc_gas = (M_gas_tot / M_tot) * 100.0
            perc_star = (M_star_tot / M_tot) * 100.0
            
           
            results_data.append({
                "Cluster": cluster_name,
                "M_tot": M_tot,
                "Perc_DM": perc_dm,
                "Perc_Gas": perc_gas,
                "Perc_Star": perc_star,
                "M_DM": M_DM_tot,
                "M_Gas": M_gas_tot,
                "M_Star": M_star_tot
            })
            
            print(f"{cluster_name:<15} | {M_tot:<12.2e} | {perc_dm:<8.3f}% | {perc_gas:<8.3f}% | {perc_star:<8.3f}%")
            
            v_mean_obs = np.mean(observed_vel_sorted)
            sigma_mean_obs = np.std(observed_vel_sorted)
            rng = np.random.default_rng(seed=42)
            
            m_gas_r_local = (0.7 * (3.0 * sigma_global**2 * r_sorted) / G_grav) * f_gas_global
            M_baryonic_r = M_lum_r + m_gas_r_local
            sigma_bar_local = np.sqrt(np.maximum(1e-6, G_grav * M_baryonic_r / (3.0 * r_sorted)))
            
            v_bar = rng.normal(loc=sigma_bar_local, scale=sigma_mean_obs, size=len(r_sorted))
            v_sim_tot = rng.normal(loc=v_mean_obs, scale=sigma_global, size=len(r_sorted))
            
            x_max = observed_vel_sorted.max()
            padding = 0.15 * x_max
            bins = np.linspace(0, x_max + padding, 50)

            fig, ax = plt.subplots(figsize=(8, 6))
            ax.hist(observed_vel_sorted, bins=bins, alpha=0.4, color='blue', label='Observations')
            ax.hist(v_bar, bins=bins, histtype='step', linewidth=2, color='red', label='Baryonic')
            ax.hist(v_sim_tot, bins=bins, histtype='step', linewidth=3, color='green', label='Total Simulated')
            
            ax.set_title(f"{cluster_name} ", fontsize=14, fontweight='bold')
            ax.set_xlabel('Velocity (km/s)', fontsize=12)
            ax.set_ylabel('Number of Galaxies', fontsize=12)
            ax.set_xlim(0, x_max + padding)
            ax.legend(fontsize=11)
            ax.grid(True, axis='y', linestyle='--', alpha=0.5)
            
            ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
            ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
            ax.ticklabel_format(style='sci', axis='x', scilimits=(0,0))
            
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f"{cluster_name}_histogram.png"), dpi=300)
            plt.close(fig)
            
        except Exception as e:
            print(f"Error on {cluster_name}: {str(e)}")

  
    m_tots = [res["M_tot"] for res in results_data]
    dm_percs = [res["Perc_DM"] for res in results_data]
    
    plt.figure(figsize=(8, 6))
    plt.scatter(m_tots, dm_percs, color='forestgreen', s=80, alpha=0.8, marker='o', edgecolor='black')
    plt.xscale('log')
    plt.xlabel('Total Mass ($M_\odot$)', fontsize=12)
    plt.ylabel('Dark Matter Fraction (%)', fontsize=12)
    #plt.title('Clusters: Dark Matter Fraction vs Total Mass', fontsize=14, fontweight='bold')
    plt.grid(True, which="both", linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "clusters_DM_vs_Mtot_scatter.png"), dpi=300, bbox_inches='tight')
    plt.close()
    

    print("\n" + "="*80)
    print("  LaTeX TABLE 1 (Absolute Masses) :")
    print("="*80)
    print(r"\begin{table}[htbp]")
    print(r"\centering")
    #print(r"\scalebox{0.65}{%")
    print(r"\begin{tabular}{lcccc}")
    print(r"\hline")
    print(r"Cluster & $M_{\text{tot}} \ [M_\odot]$ & $M_{\text{DM}} \ [M_\odot]$ & $M_{\text{gas}} \ [M_\odot]$ & $M_{\text{star}} \ [M_\odot]$ \\")
    print(r"\hline")
    
    def to_latex_sci(val):
        if val == 0:
            return "0.00"
        base, exp = f"{val:.2e}".split("e")
        return f"{base} \\times 10^{{{int(exp)}}}"

   
    results_data_sorted = sorted(results_data, key=lambda x: x["M_tot"])
    
  
    for res in results_data_sorted:
        cluster = res["Cluster"].replace("_", r"\_")
        mtot = res["M_tot"]
        p_dm = res["Perc_DM"]
        p_gas = res["Perc_Gas"]
        p_star = res["Perc_Star"]
        
        base_m, exp_m = f"{mtot:.2e}".split("e")
        mtot_latex = f"{base_m} \\times 10^{{{int(exp_m)}}}"
        
      
        print(f"{cluster} & ${mtot_latex}$ & {p_dm:.2f}\\% & {p_gas:.2f}\\% & {p_star:.2f}\\% \\\\")
        
    print(r"\hline")
    print(r"\end{tabular}%")
    print(r"}") 
    print(r"\caption{Absolute mass budget of analyzed clusters.}")
    print(r"\label{tab:clusters_absolute_mass}")
    print(r"\end{table}")
    print("="*80 + "\n")


    print("\n" + "="*65)
    print("  LaTeX TABLE 2 (Percentages) :")
    print("="*65)
    print(r"\begin{table}[htbp]")
    print(r"\centering")
   # print(r"\scalebox{0.65}{%")
    print(r"\begin{tabular}{lcccc}")
    print(r"\hline")
    print(r"Cluster & $M_{\text{tot}} \ [M_\odot]$ & $\% M_{\text{DM}}$ & $\% M_{\text{gas}}$ & $\% M_{\text{star}}$ \\")
    print(r"\hline")
    
    for res in results_data:
        cluster = res["Cluster"].replace("_", r"\_")
        mtot = res["M_tot"]
        p_dm = res["Perc_DM"]
        p_gas = res["Perc_Gas"]
        p_star = res["Perc_Star"]
        
        base_m, exp_m = f"{mtot:.2e}".split("e")
        mtot_latex = f"{base_m} \\times 10^{{{int(exp_m)}}}"
        
        print(f"{cluster} & ${mtot_latex}$ & {p_dm:.4f}\\% & {p_gas:.4f}\\% & {p_star:.4f}\\% \\\\")
        
    print(r"\hline")
    print(r"\end{tabular}%")
    print(r"}") 
    print(r"\caption{ Total mass ($M_{200}$) of analyzed clusters, alongside decomposed fractions for dark matter, estimated intra-cluster gas, and stellar mass.}")
    print(r"\label{tab:clusters_mass_budget}")
    print(r"\end{table}")
    print("="*65 + "\n")
    
    
 
    print("\n" + "="*80)
    print(f"{'Cluster':<15} | {'N_iniziale':<12} | {'N_finale':<10} | {'V_mean (km/s)':<15} | {'Sigma (km/s)':<15}")
    print("-" * 80)
    
    
    debug_data_sorted = sorted(debug_data, key=lambda x: x["Cluster"])
    
    for d in debug_data_sorted:
        print(f"{d['Cluster']:<15} | {d['N_iniziale']:<12} | {d['N_finale']:<10} | {d['V_mean']:<15.2f} | {d['Sigma']:<15.2f}")
    print("="*80 + "\n")
    create_cluster_grid(output_dir, cols=4)
if __name__ == "__main__":
    run_cluster_analysis()