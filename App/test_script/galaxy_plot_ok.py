import os
import glob
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize, root_scalar
import plotly.express as px

G_grav = 4.30091e-6
rho_crit_local = 2.775e2
def create_galaxy_grid(output_folder, cols=3, rows_per_page=4):
    """
    Crea griglie di immagini multiple. 
    Con cols=3 e rows_per_page=4, avrai un massimo di 12 grafici per immagine/pagina.
    """
    import math
    from PIL import Image

    # Trova tutti i plot combinati
    search_pattern = os.path.join(output_folder, "*_combined.png")
    image_files = sorted(glob.glob(search_pattern))
    
    if not image_files:
        print("Nessun plot trovato per creare la griglia.")
        return

    # Quanti plot ci stanno su una pagina?
    plots_per_page = cols * rows_per_page
    total_pages = math.ceil(len(image_files) / plots_per_page)
    
    # Prende le dimensioni della prima immagine
    first_img = Image.open(image_files[0])
    img_width, img_height = first_img.size
    
    for page in range(total_pages):
        # Seleziona i file per questa specifica pagina
        start_idx = page * plots_per_page
        end_idx = min(start_idx + plots_per_page, len(image_files))
        current_files = image_files[start_idx:end_idx]
        
        # Calcola quante righe servono davvero per questa pagina (l'ultima potrebbe essere mezza vuota)
        current_rows = math.ceil(len(current_files) / cols)
        
        # Crea la tela bianca
        grid_width = cols * img_width
        grid_height = current_rows * img_height
        grid_image = Image.new('RGB', (grid_width, grid_height), color='white')
        
        # Incolla le immagini
        for idx, file in enumerate(current_files):
            img = Image.open(file)
            row = idx // cols
            col = idx % cols
            x_offset = col * img_width
            y_offset = row * img_height
            grid_image.paste(img, (x_offset, y_offset))
            img.close()
            
        # Salva la pagina
        grid_filename = os.path.join(output_folder, f"FINAL_Galaxy_Grid_Page_{page+1}.png")
        grid_image.save(grid_filename)
        print(f"Griglia salvata: {grid_filename}")
def create_galaxy_grid2(output_folder, cols=4):
    """Stitches individual galaxy plots into a single grid image."""
    import math
    from PIL import Image

    # Find all combined rotation curve plots
    search_pattern = os.path.join(output_folder, "*_combined.png")
    image_files = sorted(glob.glob(search_pattern))
    
    if not image_files:
        print("No galaxy plots found to create a grid.")
        return

    # Calculate grid dimensions
    rows = math.ceil(len(image_files) / cols)
    
    # Open the first image to get dimensions (assuming all are the same size)
    first_img = Image.open(image_files[0])
    img_width, img_height = first_img.size
    
    # Create a blank white canvas for the grid
    grid_width = cols * img_width
    grid_height = rows * img_height
    grid_image = Image.new('RGB', (grid_width, grid_height), color='white')
    
    # Paste each image into the grid
    for idx, file in enumerate(image_files):
        img = Image.open(file)
        row = idx // cols
        col = idx % cols
        x_offset = col * img_width
        y_offset = row * img_height
        grid_image.paste(img, (x_offset, y_offset))
        img.close()
        
    # Save the final composite image
    grid_filename = os.path.join(output_folder, "FINAL_Galaxy_Grid.png")
    grid_image.save(grid_filename)
    print(f"Galaxy grid successfully saved to {grid_filename}")
def M_nfw_enclosed(r, rho_s, r_s):
    x = r / r_s
    return 4.0 * np.pi * rho_s * (r_s**3) * (np.log(1.0 + x) - x / (1.0 + x))

def M_burkert_enclosed(r, rho_s, r_s):
    x = r / r_s
    return 2.0 * np.pi * rho_s * (r_s**3) * (0.5 * np.log(1.0 + x**2) + np.log(1.0 + x) - np.arctan(x))

def observed_rho_from_RC(r, Vobs, Vgas, Vdisk, Vbul, y):
    V_bar_sq = Vgas * np.abs(Vgas) + y * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
    V_DM_sq = np.maximum(Vobs**2 - V_bar_sq, 0) 
    q = r**2 * (V_DM_sq / r)
    dq_dr = np.gradient(q, r)
    rho_DM = (1.0 / (4.0 * np.pi * G_grav * r**2)) * dq_dr
    return rho_DM

def fit_galaxy_parameters(r, Vobs, errV, Vgas, Vdisk, Vbul):
    dof = max(1, len(r) - 3) 
    
    # 1. Griglia basata sugli intervalli diretti di rs e rhos convertiti
    # DOPO
    log_rs_grid = np.linspace(np.log10(0.01), np.log10(5000.0), 15)
    log_rhos_grid = np.linspace(np.log10(6.0e4), np.log10(3.02e12), 15)
    y_grid = [0.5] # Fissato a 0.5
    
    verr_safe = np.maximum(errV, 5.0)
    best_chi2 = np.inf
    best_p = (None, None) # Rimosso il terzo parametro
    
    # Ciclo di Grid Search iniziale
    for log_rs in log_rs_grid:
        rs = 10**log_rs
        for log_rhos in log_rhos_grid:
            rho_s = 10**log_rhos
            
            x_arr = r / rs
            M_dm_arr = 2.0 * np.pi * rho_s * (rs**3) * (0.5 * np.log(1.0 + x_arr**2) + np.log(1.0 + x_arr) - np.arctan(x_arr))
            V_dm_sq_arr = (G_grav * M_dm_arr) / r
            
            for y in y_grid:
                V_bar_sq = Vgas * np.abs(Vgas) + y * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
                V_tot = np.sqrt(np.maximum(V_bar_sq + V_dm_sq_arr, 0))
                
                chi2 = np.sum(((Vobs - V_tot) / verr_safe)**2) / dof
                if chi2 < best_chi2:
                    best_chi2 = chi2
                    best_p = (log_rs, log_rhos)

    # 2. Funzione obiettivo diretta su rs e rhos
    def objective(params):
        log_rs, log_rhos = params # y_val rimosso da params
        y_val = 0.5 # Fissato a 0.5
        rs = 10**log_rs
        rho_s = 10**log_rhos
        
        V_bar_sq_opt = Vgas * np.abs(Vgas) + y_val * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
        x_opt = r / rs
        
        M_dm_opt = 2.0 * np.pi * rho_s * (rs**3) * (0.5 * np.log(1.0 + x_opt**2) + np.log(1.0 + x_opt) - np.arctan(x_opt))
        V_tot_opt = np.sqrt(np.maximum(V_bar_sq_opt + (G_grav * M_dm_opt) / r, 0))
        return np.sum(((Vobs - V_tot_opt) / verr_safe)**2) / dof

    # 3. Limiti indipendenti convertiti (solo per rs e rhos)
    limiti = [
        (np.log10(0.01), np.log10(5000.0)),
        (np.log10(6.0e4), np.log10(3.02e12))
    ]
   
    best_p_clipped = (
        np.clip(best_p[0], limiti[0][0], limiti[0][1]), 
        np.clip(best_p[1], limiti[1][0], limiti[1][1])        
    )

    # 4. Ottimizzazione SLSQP
    res = minimize(objective, best_p_clipped, method='SLSQP', bounds=limiti, tol=1e-8)

    # Estrazione risultati
    # DOPO
    # Estrazione risultati
    log_rs_fin, log_rhos_fin = res.x
    y_fin = 0.5 # Reinserito fisso per la compatibilità in uscita
    r_s_fin = 10**log_rs_fin
    rho_s_fin = 10**log_rhos_fin

    hit_bound = False
    tolleranza_bordo = 1e-3
    for i in range(2): # Cambiato da 3 a 2
        if np.isclose(res.x[i], limiti[i][0], rtol=tolleranza_bordo) or np.isclose(res.x[i], limiti[i][1], rtol=tolleranza_bordo):
            hit_bound = True

    # --- INIZIO CALCOLO M200 ---
    def find_c200(c):
        term = 0.5 * np.log(1.0 + c**2) + np.log(1.0 + c) - np.arctan(c)
        rho_s_teorica = (400.0 / 3.0) * rho_crit_local * (c**3) / term
        return rho_s_teorica - rho_s_fin

    try:
        res_c = root_scalar(find_c200, bracket=[1e-2, 1e5], method='brentq')
        c200_calc = res_c.root
        r200_calc = c200_calc * r_s_fin
        M200_fin = (800.0 / 3.0) * np.pi * rho_crit_local * (r200_calc**3)
    except ValueError:
        M200_fin = 0.0 # Caso limite in cui la radice non converge
    # --- FINE CALCOLO M200 ---

    # Controllo manuale ultra-sicuro SUI VALORI REALI
    hit_bound_str = "NO"
    if r_s_fin >= 4900.0 or r_s_fin <= 0.011:
        hit_bound_str = "SÌ"
    if rho_s_fin >= 3.0e12 or rho_s_fin <= 6.1e4:
        hit_bound_str = "SÌ"

    print(f"\n--- DIAGNOSTICA MINIMIZZAZIONE ---")
    print(f"Convergenza raggiunta : {res.success}")
    print(f"Messaggio di uscita   : {res.message}")
    print(f"Iterazioni effettuate : {res.nit}")
    print(f"Parametri Profilo     : (rho_s={rho_s_fin:.2e}, r_s={r_s_fin:.2f}, Y={y_fin:.2f})")
    print(f"Ha toccato un bordo?  : {hit_bound_str}")
    print(f"----------------------------------\n")
    
    if res.success and res.fun < best_chi2:
        # Nota: aggiunto hit_bound_str in fondo!
        return res.fun, rho_s_fin, r_s_fin, y_fin, M200_fin, hit_bound_str  
    
    # Nota: aggiunto hit_bound_str in fondo!
    return best_chi2, rho_s_fin, r_s_fin, y_fin, M200_fin, hit_bound_str

def run_pipeline():
    input_folder = "Rotmod_LTG"
    output_folder = "barke_rs_rhos_upsilon0.5"
    export_file = "barke_original.csv"
 
    
    os.makedirs(output_folder, exist_ok=True)
    q_dict = {}
    mrt_file = "Table.txt"
    if os.path.exists(mrt_file):
        with open(mrt_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                sline = line.strip()
               
                if not sline or sline.startswith('-') or sline.startswith('=') or "Byte" in sline or "Note" in sline:
                    continue
                
                parts = sline.split()
                
                if len(parts) >= 18 and parts[0].upper() != "GALAXY":
                    name = parts[0].strip().upper()
                    inc_str = parts[5].strip()
                    vflat_str = parts[15].strip()
                    q_str = parts[17].strip()
                    
                    if q_str.isdigit():
                        q_dict[name] = {
                            "Q": int(q_str),
                            "Inc": float(inc_str) if inc_str else 0.0,
                            "Vflat": float(vflat_str) if vflat_str else 0.0
                        }
                        
        print(f"\n>>> SUCCESSO: Trovati {len(q_dict)} valori Q nel file '{mrt_file}'! <<<\n")
    else:
        print(f"\n>>> ERRORE CRITICO: Il file '{mrt_file}' NON ESISTE in questa cartella! <<<\n")
    
    all_files = glob.glob(os.path.join(input_folder, "*"))
    files = [f for f in all_files ]
    if not files:
        print(f"Nessun file trovato in {input_folder}")
        return

    print("-" * 116)
    print(f"{'Galassia':<15} | {'Q':<3} | {'\u03C7\u00B2 Min':<8} | {'\u03C1_s':<9} | {'r_s':<6} | {'\u03A5':<5} | {'M_bar_edg':<9} | {'M_DM_edg':<9} | {'M_tot_edg':<9} | {'% DM':<6}")
    print(f"{'':<15} | {'':<3} | {'':<8} | {'(M_s/kpc\u00B3)':<9} | {'(kpc)':<6} | {'(M/L)':<5} | {'(M_sun)':<9} | {'(M_sun)':<9} | {'(M_sun)':<9} | {'(bordo)':<6}")
    print("-" * 116)

    results_data = []

    for file in sorted(files):
        gal_name = os.path.splitext(os.path.basename(file))[0]
        gal_name_clean = gal_name.replace("_rotmod", "").strip().upper()
        
        gal_info = q_dict.get(gal_name_clean, {"Q": "?", "Inc": 0.0})
        Q_val = gal_info["Q"]
        Inc_val = gal_info["Inc"]
        Vflat_val = gal_info["Vflat"]
       
        if Q_val == 2:
            print(f"{gal_name:<15} | SCARTATA: Quality Flag Q=2 ")
            continue
       
        if Q_val == 3:
            print(f"{gal_name:<15} | SCARTATA: Quality Flag Q=3")
            continue
       
        if isinstance(Inc_val, float) and Inc_val < 30.0:
            print(f"{gal_name:<15} | SCARTATA: Face-on (Incl={Inc_val}° < 30°)")
            continue
        if isinstance(Vflat_val, float) and Vflat_val == 0.0:
            print(f"{gal_name:<15} | SCARTATA: Non raggiunge il plateau (Vflat=0)")
            continue
        
        
        try:
            with open(file, 'r') as f:
                lines = f.readlines()
            
            header_line = None
            data_lines = []
            
            for line in lines:
                sline = line.strip()
                if not sline:
                    continue
                if sline.startswith('#'):
                    if 'Rad' in sline and 'Vobs' in sline:
                        header_line = sline.replace('#', '').strip() + '\n'
                else:
                    data_lines.append(line)
            
            if header_line is None or not data_lines:
                print(f"{gal_name:<15} | error: header 'Rad' o dati non trovati")
                continue
                
            full_data_str = header_line + "".join(data_lines)
            df = pd.read_csv(io.StringIO(full_data_str), sep=r'\s+')
            
            if 'Rad' not in df.columns:
                print(f"{gal_name:<15} | error: colonna Rad mancante")
                continue
                
            r = df['Rad'].values.astype(float)
            Vobs = df['Vobs'].values.astype(float)
            errV = df['errV'].values.astype(float) if 'errV' in df.columns else np.ones_like(Vobs) * 5.0
            Vgas = df['Vgas'].values.astype(float) if 'Vgas' in df.columns else np.zeros_like(Vobs)
            Vdisk = df['Vdisk'].values.astype(float) if 'Vdisk' in df.columns else np.zeros_like(Vobs)
            Vbul = df['Vbul'].values.astype(float) if 'Vbul' in df.columns else np.zeros_like(Vobs)
         
            R_max = r[-1]  
            
            mid_mask = (r >= 0.4 * R_max) & (r <= 0.6 * R_max)
            out_mask = (r >= 0.8 * R_max)
            
            if np.sum(mid_mask) > 0 and np.sum(out_mask) > 0:
                v_mid = np.mean(Vobs[mid_mask])
                v_end = np.mean(Vobs[out_mask])
                delta_v_perc = ((v_end - v_mid) / v_mid) * 100.0
                
                if delta_v_perc > 5.0:
                    print(f"{gal_name:<15} | SCARTATA: Curva in salita (+{delta_v_perc:.1f}% a grandi raggi)")
                    continue
            else:
                if len(Vobs) >= 6:
                    v_mid = np.mean(Vobs[len(Vobs)//2 : len(Vobs)//2 + 2])
                    v_end = np.mean(Vobs[-2:])
                    delta_v_perc = ((v_end - v_mid) / v_mid) * 100.0
                    
                    if delta_v_perc > 5.0:
                        print(f"{gal_name:<15} | SCARTATA: Curva in salita (Fallback: +{delta_v_perc:.1f}%)")
                        continue
                else:
                    print(f"{gal_name:<15} | SCARTATA: Troppi pochi dati per cercare un plateau")
                    continue
                    
            chi2_min, rho_s, r_s, y_opt, m200, hit_bound_str = fit_galaxy_parameters(r, Vobs, errV, Vgas, Vdisk, Vbul)
            if hit_bound_str == "SÌ":
                print(f"{gal_name:<15} | SCARTATA: Parametro (rs o rhos) ha raggiunto il bordo")
                continue
            V_bar_sq = Vgas * np.abs(Vgas) + y_opt * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
            V_bar = np.sqrt(np.maximum(V_bar_sq, 0))
            M_dm_grid = M_burkert_enclosed(r, rho_s, r_s)
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
            ratio_dm = M_dm_edge / M_tot_edge if M_tot_edge > 0 else 0.0
            
            results_data.append({
                "Galaxy": gal_name, 
                "Chi2_min": chi2_min, 
                "rho_s": rho_s, 
                "r_s": r_s, 
                "Upsilon": y_opt,
                "M200": m200,
                "M_bar_edge": M_bar_edge,
                "M_DM_edge": M_dm_edge,
                "M_tot_edge": M_tot_edge,
                "DM_Fraction_Edge": ratio_dm,
                "r_edge": r_edge
            })
            
            print(f"{gal_name:<15} | {Q_val:<3} | {chi2_min:<8.2f} | {rho_s:<9.2e} | {r_s:<6.2f} | {y_opt:<5.2f} | {M_bar_edge:<9.2e} | {M_dm_edge:<9.2e} | {M_tot_edge:<9.2e} | {ratio_dm*100:>5.1f}%")
            
            # --- CURVA DI ROTAZIONE ---
            rho_burkert_array = rho_s / ((1.0 + r / r_s) * (1.0 + (r / r_s)**2))
            fig, ax1 = plt.subplots(figsize=(10, 6))
            fig.suptitle(f'{gal_name.replace("_rotmod", "")}', fontsize=16, fontweight='bold')
            
            ax1.errorbar(r, Vobs, yerr=errV, fmt='o', color='blue', ecolor='gray', label='Observations')
            ax1.plot(r, V_bar, '-', color='red', linewidth=2, label=f'Baryonic')
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
            print(f"{gal_name:<15} | error: {str(e)}")

    # Salvataggio CSV
    df_results = pd.DataFrame(results_data)
    df_results.to_csv(export_file, index=False, float_format='%.4f')
    df_params = pd.DataFrame(results_data)[['Galaxy', 'Upsilon', 'r_s', 'rho_s']]
    df_params.to_csv("galaxy_best_parameters.csv", index=False)
    print("Salvataggio 'galaxy_best_parameters.csv' per l'App completato!")
  
    print("-" * 110)
   
    # --- SCATTER PLOT FINALE (Matplotlib) ---
    if len(results_data) > 0:
        m_tots = [res["M_tot_edge"] for res in results_data]
        dm_percs = [res["DM_Fraction_Edge"] * 100 for res in results_data]
        
        plt.figure(figsize=(8, 6))
        plt.scatter(m_tots, dm_percs, color='blue', s=60, alpha=0.7, edgecolor='black')
        plt.xscale('log')
        plt.xlabel(r'Total Mass ($M_\odot$)', fontsize=12)
        plt.ylabel(r'Dark Matter Fraction ($\%$)', fontsize=12)
        plt.grid(True, which="both", linestyle='--', alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(output_folder, "galaxies_DM_vs_Mtot_scatter.png"), dpi=300, bbox_inches='tight')
        plt.close()

    # --- SCATTER PLOT INTERATTIVO (Plotly) ---
    if len(results_data) > 0:
        df_results["DM_Perc"] = df_results["DM_Fraction_Edge"] * 100.0

        fig1 = px.scatter(df_results, x="M_tot_edge", y="DM_Perc", hover_name="Galaxy",
                          log_x=True, color_discrete_sequence=['royalblue'],
                          labels={"M_tot_edge": "Total Mass (M_sun)", "DM_Perc": "Dark Matter Fraction (%)"})
        fig1.update_traces(marker=dict(size=10, line=dict(width=1, color='black')))
        fig1.write_html(os.path.join(output_folder, "1_DM_vs_Mtot_scatter_Interactive.html"))
    
    print("\n" + "="*80)
    print(" Table:")
    print("="*80)
    print(r"\begin{longtable}{lccccc}") # Cambiato da 5 a 6 colonne
    print(r"\caption{Best-fit structural parameters ($r_s$, $\rho_s$), minimum $\chi^2$, total mass ($M_{\text{tot}}$) and DM fraction for each galaxy.}")
    print(r"\label{tab:galaxy_params} \\")
    print(r"\hline")
    print(r"Galaxy & $r_s$ [kpc] & $\rho_s$ [$M_\odot/\text{kpc}^3$] & $\chi^2_{\text{min}}$ & $M_{\text{tot}}$ [$M_\odot$] & $\% \text{DM}/M_{\text{tot}}$ \\")
    print(r"\hline")
    print(r"\endfirsthead")
    print(r"\multicolumn{6}{c}%") # Aggiornato per 6 colonne
    print(r"{{\bfseries \tablename\ \thetable{} -- continued from previous page}} \\")
    print(r"\hline")
    print(r"Galaxy & $r_s$ [kpc] & $\rho_s$ [$M_\odot/\text{kpc}^3$] & $\chi^2_{\text{min}}$ & $M_{\text{tot}}$ [$M_\odot$] & $\% \text{DM}/M_{\text{tot}}$ \\")
    print(r"\hline")
    print(r"\endhead")
    print(r"\hline \multicolumn{6}{r}{{Continued on next page}} \\") # Aggiornato per 6 colonne
    print(r"\endfoot")
    print(r"\hline")
    print(r"\endlastfoot")
    
    for res in results_data:
        gal = res["Galaxy"].replace("_rotmod", "").replace("_", r"\_")
        perc_dm = res["DM_Fraction_Edge"] * 100
        rs = res["r_s"]
        rhos = res["rho_s"]
        chi2 = res["Chi2_min"]
        m_tot = res["M_tot_edge"]
        
        # Formattazione densità in notazione scientifica LaTeX
        base_rhos, exp_rhos = f"{rhos:.2e}".split("e")
        rhos_latex = f"{base_rhos} \\times 10^{{{int(exp_rhos)}}}"
        
        # Formattazione Massa Totale in notazione scientifica LaTeX
        base_mtot, exp_mtot = f"{m_tot:.2e}".split("e")
        mtot_latex = f"{base_mtot} \\times 10^{{{int(exp_mtot)}}}"
        
        # Stampa riga con la nuova colonna per m_tot
        print(f"{gal} & {rs:.2f} & ${rhos_latex}$ & {chi2:.2f} & ${mtot_latex}$ & {perc_dm:.1f}\\% \\\\")
        
    print(r"\end{longtable}")
    print("="*80 + "\n")
 

    create_galaxy_grid(output_folder, cols=4)
if __name__ == "__main__":
    run_pipeline()