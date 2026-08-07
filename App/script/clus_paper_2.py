import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.integrate import quad
from scipy.stats import norm

G_grav = 4.30091e-6
c_light = 3e5
H0 = 70.0

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

def r200_from_M200(M200, rho_crit_local):
    return (3.0 * M200 / (4.0 * np.pi * 200.0 * rho_crit_local))**(1.0/3.0)

def delta_c_of_c(c):
    return (200.0 / 3.0) * c**3 / (np.log(1.0 + c) - c / (1.0 + c))

def concentration_duffy2008(M200_msun, z):
    M_safe = min(M200_msun, 5e15)
    c = 5.71 * (M_safe / (2e12 / 0.7))**(-0.084) * (1 + z)**(-0.47)
    return max(c, 3.5)

def rho_s_from_M200_and_c(M200, c, rho_crit_local):
    r200 = r200_from_M200(M200, rho_crit_local)
    r_s = r200 / c
    return delta_c_of_c(c) * rho_crit_local, r_s, r200

def estimate_M200_R200_from_sigma(sigma_obs, rho_crit_local):
    if sigma_obs <= 0: return 1e14, 1000.0
    R200 = np.sqrt((9.0 * sigma_obs**2) / (4.0 * np.pi * G_grav * 200.0 * rho_crit_local))
    M200 = (4.0/3.0) * np.pi * 200.0 * rho_crit_local * R200**3
    return M200, R200

def run_cluster_analysis():
    coma_files = glob.glob("data/Abell1656(Coma).csv") + glob.glob("Abell1656(Coma).csv")
    abell_files = glob.glob("cluster_data/Abell*.txt") + glob.glob("Abell*.txt")
    all_files = list(set(coma_files + abell_files))
    
    # --- CREAZIONE DELLE TRE CARTELLE ---
    output_dir_original = "cluster_plot_unified2"
    output_dir_comparison = "cluster_plot_methods_comparison2"
    output_dir_mass_density = "cluster_plot_mass_density"
    
    os.makedirs(output_dir_original, exist_ok=True)
    os.makedirs(output_dir_comparison, exist_ok=True)
    os.makedirs(output_dir_mass_density, exist_ok=True)
    
    rho_crit = rho_crit_Msunkpc3()

    print(f"{'Cluster':<12} | {'M_tot (M_sun)':<12} | {'% DM (Meth 1)':<14} | {'% DM (Meth 2)':<14}")
    print("-" * 60)
    results_data = []
    
    for file in sorted(all_files):
        cluster_name = os.path.basename(file).replace('.txt', '').replace('.csv', '')
        try:
            if "coma" in cluster_name.lower():
                df = pd.read_csv(file, skiprows=1)
                df.columns = ['objid','ra','dec','modelmag_r','modelmagerr_r','extinction_r','redshift','zErr']
                observed_vel = c_light * df['redshift'].dropna().values
                z_cluster = np.nanmedian(df['redshift'].dropna().values)
                
                center_ra = np.nanmedian(df['ra'].dropna().values)
                center_dec = np.nanmedian(df['dec'].dropna().values)
                
                D_A_kpc = angular_diameter_distance_Mpc(z_cluster) * 1000.0
                theta_rad = angsep_rad(df['ra'].values, df['dec'].values, center_ra, center_dec)
                r = np.maximum(theta_rad * D_A_kpc, 1e-3)
                
                M_sun_r = 4.67
                mag = df['modelmag_r'].values - df['extinction_r'].values
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
                members = members[members["r_kpc"] <= 3000]
                
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
            
            if "coma" in cluster_name.lower():
                sigma_global = np.std(observed_vel_sorted)
            else:
                sigma_global = np.std(observed_vel_sorted - np.median(observed_vel_sorted))
                
            # --- CALCOLO MASSE ---
            M_tot_r_virial = (3.0 * sigma_global**2 * r_sorted) / G_grav
            f_gas_r = 0.093 * (((0.7 * M_tot_r_virial) / 2e14)**0.21)
            m_gas_r = (0.7 * M_tot_r_virial) * f_gas_r
            M_baryonic_r = M_lum_r + m_gas_r
            
            def positive_floor(arr):
                pos = arr[np.isfinite(arr) & (arr > 0)]
                if pos.size == 0: return arr + 1e-6
                return np.where(arr <= 0, np.nanmin(pos) * 1e-3, arr)

            M_tot_r_virial = positive_floor(M_tot_r_virial)
            M_baryonic_r = positive_floor(M_baryonic_r)
            M_bar_tot = M_baryonic_r[-1]
            
            # Arrays per Metodo 1
            M_DM_m1_r = np.maximum(0.0, M_tot_r_virial - M_baryonic_r)
            M_tot_1 = M_tot_r_virial[-1]
            M_DM_1 = M_tot_1 - M_bar_tot
            perc_DM_1 = (M_DM_1 / M_tot_1) * 100
            
            # Arrays per Metodo 2
            M200, R200 = estimate_M200_R200_from_sigma(sigma_global, rho_crit)
            c_val = concentration_duffy2008(M200, z_cluster)
            rho_s, r_s, r200_nfw = rho_s_from_M200_and_c(M200, c_val, rho_crit)
            x = r_sorted / r_s
            M_DM_NFW_r = 4.0 * np.pi * rho_s * (r_s**3) * (np.log(1.0 + x) - x / (1.0 + x))
            M_tot_model_r = M_baryonic_r + M_DM_NFW_r
            
            M_tot_2 = M_tot_model_r[-1]
            M_DM_2 = M_DM_NFW_r[-1]
            perc_DM_2 = (M_DM_2 / M_tot_2) * 100
            
            # --- CALCOLO DENSITÀ ---
            Vol = (4.0 / 3.0) * np.pi * r_sorted**3
            rho_bar = M_baryonic_r / Vol
            rho_tot_m1 = M_tot_r_virial / Vol
            rho_DM_m1 = M_DM_m1_r / Vol
            rho_tot_m2 = M_tot_model_r / Vol
            rho_DM_m2 = M_DM_NFW_r / Vol
            
            results_data.append({
                "Cluster": cluster_name,
                "M_tot_1": M_tot_1,
                "Perc_DM_1": perc_DM_1,
                "Perc_DM_2": perc_DM_2
            })
            
            print(f"{cluster_name:<12} | {M_tot_1:<12.2e} | {perc_DM_1:<12.1f}% | {perc_DM_2:.1f}%")
            
            # --- GENERAZIONE VELOCITÀ ---
            v_mean_obs = np.mean(observed_vel_sorted)
            sigma_mean_obs = np.std(observed_vel_sorted)
            rng = np.random.default_rng(seed=42)
            
            sigma_bar_local = np.sqrt(np.maximum(1e-6, G_grav * M_baryonic_r / (3.0 * r_sorted)))
            v_bar = rng.normal(loc=sigma_bar_local, scale=sigma_mean_obs, size=len(r_sorted))
            
            v_sim_m1 = rng.normal(loc=v_mean_obs, scale=sigma_global, size=len(r_sorted))
            
            sigma_tot_nfw_local = np.sqrt(np.maximum(0.0, G_grav * M_tot_model_r / (3.0 * r_sorted)))
            v_sim_m2 = rng.normal(loc=v_mean_obs, scale=sigma_tot_nfw_local, size=len(r_sorted))
            
            x_max = observed_vel_sorted.max()
            padding = 0.15 * x_max
            bins = np.linspace(0, x_max + padding, 50)
            
            fig1, axs1 = plt.subplots(1, 2, figsize=(14, 6))
            fig1.suptitle(f"Cluster: {cluster_name}", fontsize=18, fontweight='bold')
            
            axs1[0].hist(observed_vel_sorted, bins=bins, alpha=0.4, color='blue', label='Observed Data')
            axs1[0].hist(v_bar, bins=bins, histtype='step', linewidth=2, color='red', label='Baryonic Component')
            axs1[0].hist(v_sim_m1, bins=bins, histtype='step', linewidth=3, color='green', label='Total (M1)')
            axs1[0].hist(v_sim_m2, bins=bins, histtype='step', linewidth=3, color='purple', label='Total (NFW M2)')
            axs1[0].set_title('Velocity Distribution', fontsize=14, fontweight='bold')
            axs1[0].set_xlabel('Velocity (km/s)')
            axs1[0].set_ylabel('Number of Galaxies')
            axs1[0].set_xlim(0, x_max + padding)
            axs1[0].legend()
            axs1[0].grid(True, axis='y', linestyle='--', alpha=0.5)
            
            axs1[1].scatter(r_sorted, observed_vel_sorted, color='blue', s=15, alpha=0.6, label='Observed Data')
            axs1[1].scatter(r_sorted, v_bar, color='red', s=15, alpha=0.6, label='Baryonic Component')
            axs1[1].scatter(r_sorted, v_sim_m1, color='green', s=15, alpha=0.6, label='Total (M1)')
            axs1[1].scatter(r_sorted, v_sim_m2, color='purple', s=15, alpha=0.6, label='Total (NFW M2)')
            axs1[1].set_title('Cluster Galaxies Velocities', fontsize=14, fontweight='bold')
            axs1[1].set_xlabel('Radius (kpc)')
            axs1[1].set_ylabel('Velocity (km/s)')
            axs1[1].set_ylim(0, x_max + padding)
            axs1[1].set_xlim(0, r_sorted.max() * 1.1)
            axs1[1].legend()
            axs1[1].grid(True, linestyle='--', alpha=0.5)
            
            for ax in axs1:
                ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                ax.ticklabel_format(style='sci', axis='both', scilimits=(0,0))
                
            plt.tight_layout(rect=[0, 0, 1, 0.95])
            plt.savefig(os.path.join(output_dir_original, f"{cluster_name}_unified.png"), dpi=300)
            plt.close(fig1)

         
            fig1, axs1 = plt.subplots(1, 2, figsize=(14, 6))
            fig1.suptitle(f"Cluster: {cluster_name}", fontsize=18, fontweight='bold')
            
            
            axs1[0].hist(observed_vel_sorted, bins=bins, alpha=0.5, color='blue', label='Observed Data')
            axs1[0].hist(v_bar, bins=bins, alpha=0.5, color='red', label='Baryonic Component')
            axs1[0].hist(v_sim_m1, bins=bins, alpha=0.5, color='green', label='Total (M1)')
            axs1[0].hist(v_sim_m2, bins=bins, alpha=0.5, color='purple', label='Total (NFW M2)')
            axs1[0].set_title('Velocity Distribution', fontsize=14, fontweight='bold')
            axs1[0].set_xlabel('Velocity (km/s)')
            axs1[0].set_ylabel('Number of Galaxies')
            axs1[0].set_xlim(0, x_max + padding)
            axs1[0].legend()
            axs1[0].grid(True, axis='y', linestyle='--', alpha=0.5)
            
            axs1[1].scatter(r_sorted, observed_vel_sorted, color='blue', s=15, alpha=0.6, label='Observed Data')
            axs1[1].scatter(r_sorted, v_bar, color='red', s=15, alpha=0.6, label='Baryonic Component')
            axs1[1].scatter(r_sorted, v_sim_m1, color='green', s=15, alpha=0.6, label='Total (M1)')
            axs1[1].scatter(r_sorted, v_sim_m2, color='purple', s=15, alpha=0.6, label='Total (NFW M2)')
            axs1[1].set_title('Cluster Galaxies Velocities', fontsize=14, fontweight='bold')
            axs1[1].set_xlabel('Radius (kpc)')
            axs1[1].set_ylabel('Velocity (km/s)')
            axs1[1].set_ylim(0, x_max + padding)
            axs1[1].set_xlim(0, r_sorted.max() * 1.1)
            axs1[1].legend()
            axs1[1].grid(True, linestyle='--', alpha=0.5)
            
            for ax in axs1:
                ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                ax.ticklabel_format(style='sci', axis='both', scilimits=(0,0))
                
            plt.tight_layout(rect=[0, 0, 1, 0.95])
            plt.savefig(os.path.join(output_dir_original, f"{cluster_name}_unified.png"), dpi=300)
            plt.close(fig1)

          
            fig2, axs2 = plt.subplots(2, 2, figsize=(16, 12))
            fig2.suptitle(f"Cluster: {cluster_name} - Velocities Comparison", fontsize=18, fontweight='bold')
            
         
            axs2[0,0].hist(observed_vel_sorted, bins=bins, alpha=0.5, color='blue', label='Observed Data')
            axs2[0,0].hist(v_bar, bins=bins, alpha=0.5, color='red', label='Baryonic Component')
            axs2[0,0].hist(v_sim_m1, bins=bins, alpha=0.5, color='green', label='Sim. Total (Method 1)')
            axs2[0,0].set_title('Velocity Distribution (Method 1)', fontsize=14, fontweight='bold')
            axs2[0,0].set_xlabel('Velocity (km/s)')
            axs2[0,0].set_ylabel('Number of Galaxies')
            axs2[0,0].set_xlim(0, x_max + padding)
            axs2[0,0].legend()
            axs2[0,0].grid(True, axis='y', linestyle='--', alpha=0.5)
            
            axs2[0,1].scatter(r_sorted, observed_vel_sorted, color='blue', s=15, alpha=0.4, label='Observed Data')
            axs2[0,1].scatter(r_sorted, v_bar, color='red', s=15, alpha=0.4, label='Baryonic Component')
            axs2[0,1].scatter(r_sorted, v_sim_m1, color='green', s=15, alpha=0.6, label='Sim. Total (Method 1)')
            axs2[0,1].set_title('Cluster Galaxies Velocities (Method 1)', fontsize=14, fontweight='bold')
            axs2[0,1].set_xlabel('Radius (kpc)')
            axs2[0,1].set_ylabel('Velocity (km/s)')
            axs2[0,1].set_ylim(0, x_max + padding)
            axs2[0,1].set_xlim(0, r_sorted.max() * 1.1)
            axs2[0,1].legend()
            axs2[0,1].grid(True, linestyle='--', alpha=0.5)

         
            axs2[1,0].hist(observed_vel_sorted, bins=bins, alpha=0.5, color='blue', label='Observed Data')
            axs2[1,0].hist(v_bar, bins=bins, alpha=0.5, color='red', label='Baryonic Component')
            axs2[1,0].hist(v_sim_m2, bins=bins, alpha=0.5, color='purple', label='Sim. Total (Method 2 NFW)')
            axs2[1,0].set_title('Velocity Distribution (Method 2 NFW)', fontsize=14, fontweight='bold')
            axs2[1,0].set_xlabel('Velocity (km/s)')
            axs2[1,0].set_ylabel('Number of Galaxies')
            axs2[1,0].set_xlim(0, x_max + padding)
            axs2[1,0].legend()
            axs2[1,0].grid(True, axis='y', linestyle='--', alpha=0.5)
            
            axs2[1,1].scatter(r_sorted, observed_vel_sorted, color='blue', s=15, alpha=0.4, label='Observed Data')
            axs2[1,1].scatter(r_sorted, v_bar, color='red', s=15, alpha=0.4, label='Baryonic Component')
            axs2[1,1].scatter(r_sorted, v_sim_m2, color='purple', s=15, alpha=0.6, label='Sim. Total (Method 2 NFW)')
            axs2[1,1].set_title('Cluster Galaxies Velocities (Method 2 NFW)', fontsize=14, fontweight='bold')
            axs2[1,1].set_xlabel('Radius (kpc)')
            axs2[1,1].set_ylabel('Velocity (km/s)')
            axs2[1,1].set_ylim(0, x_max + padding)
            axs2[1,1].set_xlim(0, r_sorted.max() * 1.1)
            axs2[1,1].legend()
            axs2[1,1].grid(True, linestyle='--', alpha=0.5)
            
            for ax_row in axs2:
                for ax in ax_row:
                    ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                    ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                    ax.ticklabel_format(style='sci', axis='both', scilimits=(0,0))
                
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            plt.savefig(os.path.join(output_dir_comparison, f"{cluster_name}_comparison.png"), dpi=300)
            plt.close(fig2)

            fig_md, axs_md = plt.subplots(1, 2, figsize=(14, 6))
            fig_md.suptitle(f"Cluster: {cluster_name} - Mass & Density Profiles", fontsize=18, fontweight='bold')
            
          
            axs_md[0].plot(r_sorted, M_baryonic_r, 'r-', lw=2, label='Baryonic Mass')
            axs_md[0].plot(r_sorted, M_DM_NFW_r, 'purple', lw=2.5, label='DM Mass (NFW)')
            axs_md[0].plot(r_sorted, M_tot_model_r, 'c--', lw=2.5, label='Total Mass')
            axs_md[0].set_title('Mass Profile', fontsize=14, fontweight='bold')
            axs_md[0].set_xlabel('Radius (kpc)')
            axs_md[0].set_ylabel('Mass ($M_\odot$)')
            axs_md[0].set_yscale('log')
            axs_md[0].set_xscale('log')
            axs_md[0].grid(True, which="both", linestyle='--', alpha=0.5)
            axs_md[0].legend()

         
            axs_md[1].plot(r_sorted, rho_bar, 'r-', lw=2, label='Baryonic Density')
            axs_md[1].plot(r_sorted, rho_DM_m2, 'purple', lw=2.5, label='DM Density (NFW)')
            axs_md[1].plot(r_sorted, rho_tot_m2, 'c--', lw=2.5, label='Total Density')
            axs_md[1].set_title('Density Profile', fontsize=14, fontweight='bold')
            axs_md[1].set_xlabel('Radius (kpc)')
            axs_md[1].set_ylabel('Density ($M_\odot / kpc^3$)')
            axs_md[1].set_yscale('log')
            axs_md[1].set_xscale('log')
            axs_md[1].grid(True, which="both", linestyle='--', alpha=0.5)
            axs_md[1].legend()
            
            for ax in axs_md:
                ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                ax.ticklabel_format(style='sci', axis='both', scilimits=(0,0))
            
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            plt.savefig(os.path.join(output_dir_mass_density, f"{cluster_name}_mass_density.png"), dpi=300)
            plt.close(fig_md)
            
        except Exception as e:
            print(f"Error on {cluster_name}: {str(e)}")

    df_results = pd.DataFrame(results_data)
    export_file = "cluster_best_parameters_combined.csv"
    df_results.to_csv(export_file, index=False, float_format='%.4f')
   
    print("\n" + "="*60)
    print("  TABLE :")
    print("="*60)
    print(r"\begin{table}[h!]")
    print(r"\centering")
    print(r"\begin{tabular}{lccc}")
    print(r"\hline")
    print(r"Cluster & $M_{\text{tot}} \ [M_\odot]$ & $\% M_{\text{DM}}/\text{tot}_1$ & $\% M_{\text{DM}}/\text{tot}_2$ \\")
    print(r"\hline")
    
    for res in results_data:
        cluster = res["Cluster"].replace("_", r"\_")
        mtot = res["M_tot_1"]
        perc1 = res["Perc_DM_1"]
        perc2 = res["Perc_DM_2"]
        
        base, exp = f"{mtot:.2e}".split("e")
        mtot_latex = f"{base} \\times 10^{{{int(exp)}}}"
        
        print(f"{cluster} & ${mtot_latex}$ & {perc1:.1f}\\% & {perc2:.1f}\\% \\\\")
        
    print(r"\hline")
    print(r"\end{tabular}")
    print(r"\caption{Total mass and DM fraction (Method 1: Virial subtraction, Method 2: NFW profile) for each cluster.}")
    print(r"\label{tab:clusters_dm}")
    print(r"\end{table}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_cluster_analysis()