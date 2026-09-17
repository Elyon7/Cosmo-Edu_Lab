import os
import glob
import io
import math
import warnings
import numpy as np
import pandas as pd
from PIL import Image
from scipy.optimize import minimize, root_scalar
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore', category=RuntimeWarning)

# --- COSTANTI FISICHE ---
G_grav = 4.30091e-6
rho_crit_local = 2.775e2

# --- NOMI DEI FILE SPARC ORIGINALI (.mrt) ---
SPARC_FILES = {
    'nfw': 'parameter_NFW_Flat.txt',
    'iso': 'parameter_pISO.txt',
    'burkert': 'parameter_Burkert.txt'
}

def clean_name(name):
    """Pulisce i nomi delle galassie per farli combaciare perfettamente tra i nostri file e quelli SPARC."""
    return name.replace("_rotmod", "").replace(" ", "").replace("-", "").replace("_", "").strip().upper()

def create_galaxy_grid(output_folder, cols=3, rows_per_page=4):
    search_pattern = os.path.join(output_folder, "*_combined.png")
    image_files = sorted(glob.glob(search_pattern))
    if not image_files: return

    plots_per_page = cols * rows_per_page
    total_pages = math.ceil(len(image_files) / plots_per_page)
    first_img = Image.open(image_files[0])
    img_width, img_height = first_img.size
    
    for page in range(total_pages):
        start_idx = page * plots_per_page
        end_idx = min(start_idx + plots_per_page, len(image_files))
        current_files = image_files[start_idx:end_idx]
        current_rows = math.ceil(len(current_files) / cols)
        
        grid_width = cols * img_width
        grid_height = current_rows * img_height
        grid_image = Image.new('RGB', (grid_width, grid_height), color='white')
        
        for idx, file in enumerate(current_files):
            img = Image.open(file)
            row = idx // cols
            col = idx % cols
            grid_image.paste(img, (col * img_width, row * img_height))
            img.close()
            
        grid_filename = os.path.join(output_folder, f"FINAL_Galaxy_Grid_Page_{page+1}.png")
        grid_image.save(grid_filename)

# --- FUNZIONI MASSA DEI PROFILI ---
def M_nfw(r, rho_s, r_s):
    x = r / r_s
    return 4.0 * np.pi * rho_s * (r_s**3) * (np.log(1.0 + x) - x / (1.0 + x))

def M_iso(r, rho_s, r_s):
    x = r / r_s
    return 4.0 * np.pi * rho_s * (r_s**3) * (x - np.arctan(x))

def M_burkert(r, rho_s, r_s):
    x = r / r_s
    return 2.0 * np.pi * rho_s * (r_s**3) * (0.5 * np.log(1.0 + x**2) + np.log(1.0 + x) - np.arctan(x))

# --- LIMITI E CALCOLI COSMOLOGICI ---
def get_rs_rhos_bounds(profile):
    v200_min, v200_max = 10.0, 500.0   
    c_min, c_max = 0.1, 100.0          
    
    costante_vir = np.sqrt((800.0 * np.pi / 3.0) * G_grav * rho_crit_local)
    R200_min, R200_max = v200_min / costante_vir, v200_max / costante_vir
    rs_min, rs_max = R200_min / c_max, R200_max / c_min
    
    def calc_rhos(v200, c):
        R200 = v200 / costante_vir
        r_s = R200 / c
        M200 = (4.0/3.0) * np.pi * 200.0 * rho_crit_local * R200**3
        if profile == 'nfw': return M200 / (4.0 * np.pi * r_s**3 * (np.log(1.0 + c) - c / (1.0 + c)))
        elif profile == 'iso': return M200 / (4.0 * np.pi * r_s**3 * (c - np.arctan(c)))
        elif profile == 'burkert': return M200 / (2.0 * np.pi * r_s**3 * (0.5 * np.log(1.0 + c**2) + np.log(1.0 + c) - np.arctan(c)))

    rhos_corners = [calc_rhos(v200_min, c_min), calc_rhos(v200_min, c_max),
                    calc_rhos(v200_max, c_min), calc_rhos(v200_max, c_max)]
    return (np.log10(rs_min), np.log10(rs_max)), (np.log10(min(rhos_corners)), np.log10(max(rhos_corners)))

def calc_m200_from_profile(profile, rho_s, r_s):
    def find_c200(c):
        if profile == 'nfw': rho_teorica = (200.0 / 3.0) * rho_crit_local * (c**3) / (np.log(1.0 + c) - c / (1.0 + c))
        elif profile == 'iso': rho_teorica = (200.0 / 3.0) * rho_crit_local * (c**3) / (c - np.arctan(c))
        elif profile == 'burkert': rho_teorica = (400.0 / 3.0) * rho_crit_local * (c**3) / (0.5 * np.log(1.0 + c**2) + np.log(1.0 + c) - np.arctan(c))
        return rho_teorica - rho_s

    try:
        res_c = root_scalar(find_c200, bracket=[1e-3, 1e5], method='brentq')
        c200_calc = res_c.root
        return (800.0 / 3.0) * np.pi * rho_crit_local * ((c200_calc * r_s)**3)
    except ValueError:
        return 0.0

# --- MOTORE DI OTTIMIZZAZIONE ---
def fit_profile(profile, r, Vobs, errV, Vgas, Vdisk, Vbul):
    dof = max(1, len(r) - 3)
    verr_safe = np.maximum(errV, 5.0)
    rs_bounds, rhos_bounds = get_rs_rhos_bounds(profile)
    bounds = [rs_bounds, rhos_bounds, (0.4, 0.6)]
    
    log_rs_grid, log_rhos_grid = np.linspace(bounds[0][0], bounds[0][1], 10), np.linspace(bounds[1][0], bounds[1][1], 10)
    y_grid = [0.4, 0.5, 0.6]
    best_chi2, best_p = np.inf, (np.mean(bounds[0]), np.mean(bounds[1]), 0.5)
    
    for log_rs in log_rs_grid:
        rs = 10**log_rs
        for log_rhos in log_rhos_grid:
            rho_s = 10**log_rhos
            if profile == 'nfw': M_dm = M_nfw(r, rho_s, rs)
            elif profile == 'iso': M_dm = M_iso(r, rho_s, rs)
            else: M_dm = M_burkert(r, rho_s, rs)
            
            V_dm_sq = (G_grav * M_dm) / r
            for y in y_grid:
                V_bar_sq = Vgas * np.abs(Vgas) + y * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
                V_tot = np.sqrt(np.maximum(V_bar_sq + V_dm_sq, 0))
                chi2 = np.sum(((Vobs - V_tot) / verr_safe)**2) / dof
                if chi2 < best_chi2:
                    best_chi2, best_p = chi2, (log_rs, log_rhos, y)

    def objective(params):
        rs, rho_s, y_val = 10**params[0], 10**params[1], params[2]
        V_bar_sq = Vgas * np.abs(Vgas) + y_val * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
        if profile == 'nfw': M_dm = M_nfw(r, rho_s, rs)
        elif profile == 'iso': M_dm = M_iso(r, rho_s, rs)
        else: M_dm = M_burkert(r, rho_s, rs)
        return np.sum(((Vobs - np.sqrt(np.maximum(V_bar_sq + (G_grav * M_dm) / r, 0))) / verr_safe)**2) / dof

    res = minimize(objective, best_p, method='SLSQP', bounds=bounds, tol=1e-8)
    rs_fin, rho_s_fin, y_fin = 10**res.x[0], 10**res.x[1], res.x[2]
    chi2_fin = res.fun if res.success else best_chi2
    m200_fin = calc_m200_from_profile(profile, rho_s_fin, rs_fin)
    
    return chi2_fin, rho_s_fin, rs_fin, y_fin, m200_fin

# --- UTILS E PARSER SPARC ---
def load_sparc_references():
    sparc_data = {'nfw': {}, 'iso': {}, 'burkert': {}}
    for profile, filename in SPARC_FILES.items():
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip(): continue
                    parts = line.split()
                    if len(parts) >= 20:
                        raw_name = parts[0].strip()
                        gal_clean_name = clean_name(raw_name)
                        
                        try:
                            chi2_val = float(parts[19])
                        except ValueError:
                            chi2_val = np.nan
                            
                        sparc_data[profile][gal_clean_name] = {
                            'upsilon': float(parts[1]), 'rs': float(parts[13]), 
                            'rhos': 10**(float(parts[15]) + 9.0), 'm200': 10**float(parts[17]), 'chi2': chi2_val
                        }
            print(f"✅ CARICATO: '{filename}' ({len(sparc_data[profile])} galassie).")
        else:
            print(f"⚠️ File '{filename}' NON TROVATO.")
    return sparc_data

def pct_diff(val, ref):
    if np.isnan(val) or np.isnan(ref) or ref == 0: return np.nan
    return abs(val - ref) / abs(ref) * 100.0

def compact_num(num):
    if np.isnan(num): return "--"
    if num == 0: return "0"
    if num > 9999 or num < 0.01:
        base, exp = f"{num:.1e}".split("e")
        return f"{float(base):.1f} \\times 10^{{{int(exp)}}}"
    return f"{num:.2f}"

def format_val_delta(val, ref, delta):
    val_str = compact_num(val)
    if np.isnan(ref) or ref == 0: 
        return rf"\shortstack[c]{{${val_str}$ / -- \\ (--)\%}}"
    
    ref_str = compact_num(ref)
    d_str = f"{delta:.1f}\\%" if not np.isnan(delta) else "--"
    return rf"\shortstack[c]{{${val_str}$ / ${ref_str}$ \\ ({d_str})}}"

def format_sci(val):
    if val == 0: return "N/A"
    base, exp = f"{val:.2e}".split("e")
    return f"{base} \\times 10^{{{int(exp)}}}"

# --- MAIN PIPELINE ---
def run_all_profiles():
    input_folder = "Rotmod_LTG"
    output_folder = "Profiles_Comparison_Output"
    os.makedirs(output_folder, exist_ok=True)
    
    print("\n[1] Lettura File SPARC in corso...")
    sparc_data = load_sparc_references()
    q_dict = {}
    
    # L'ESTRAZIONE ORIGINALE DEI FILTRI DA TABLE.TXT
    if os.path.exists("Table.txt"):
        with open("Table.txt", 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 18 and parts[0].upper() != "GALAXY":
                    name = clean_name(parts[0])
                    inc_str = parts[5].strip()
                    vflat_str = parts[15].strip()
                    q_str = parts[17].strip()
                    if q_str.isdigit():
                        q_dict[name] = {
                            "Q": int(q_str),
                            "Inc": float(inc_str) if inc_str else 0.0,
                            "Vflat": float(vflat_str) if vflat_str else 0.0
                        }

    files = glob.glob(os.path.join(input_folder, "*"))
    results = {'nfw': [], 'iso': [], 'burkert': []}
    
    print("\n[2] Inizio ottimizzazione curve di rotazione con FILTRI ATTIVI...")
    for file in sorted(files):
        raw_gal_name = os.path.splitext(os.path.basename(file))[0]
        gal_name = clean_name(raw_gal_name)
        
        # --- APPLICAZIONE DEI FILTRI ORIGINALI ---
        gal_info = q_dict.get(gal_name, {"Q": "?", "Inc": 0.0, "Vflat": 0.0})
        Q_val = gal_info.get("Q", "?")
        Inc_val = gal_info.get("Inc", 0.0)
        Vflat_val = gal_info.get("Vflat", 0.0)
       
        if Q_val == 2: continue
        if Q_val == 3: continue
        if isinstance(Inc_val, float) and Inc_val < 30.0: continue
        if isinstance(Vflat_val, float) and Vflat_val == 0.0: continue
        
        try:
            with open(file, 'r') as f: lines = f.readlines()
            header_line, data_lines = None, []
            for line in lines:
                if line.startswith('#') and 'Rad' in line: header_line = line.replace('#', '').strip() + '\n'
                elif line.strip() and not line.startswith('#'): data_lines.append(line)
                    
            if not header_line: continue
            df = pd.read_csv(io.StringIO(header_line + "".join(data_lines)), sep=r'\s+')
            if 'Rad' not in df.columns: continue
            
            r, Vobs = df['Rad'].values.astype(float), df['Vobs'].values.astype(float)
            errV = df['errV'].values.astype(float) if 'errV' in df.columns else np.ones_like(Vobs)*5.0
            Vgas = df['Vgas'].values.astype(float) if 'Vgas' in df.columns else np.zeros_like(Vobs)
            Vdisk = df['Vdisk'].values.astype(float) if 'Vdisk' in df.columns else np.zeros_like(Vobs)
            Vbul = df['Vbul'].values.astype(float) if 'Vbul' in df.columns else np.zeros_like(Vobs)
            
            # --- FILTRO CURVA IN SALITA ORIGINALE ---
            R_max = r[-1]  
            mid_mask = (r >= 0.4 * R_max) & (r <= 0.6 * R_max)
            out_mask = (r >= 0.8 * R_max)
            
            if np.sum(mid_mask) > 0 and np.sum(out_mask) > 0:
                v_mid = np.mean(Vobs[mid_mask])
                v_end = np.mean(Vobs[out_mask])
                delta_v_perc = ((v_end - v_mid) / v_mid) * 100.0
                if delta_v_perc > 5.0: continue
            else:
                if len(Vobs) >= 6:
                    v_mid = np.mean(Vobs[len(Vobs)//2 : len(Vobs)//2 + 2])
                    v_end = np.mean(Vobs[-2:])
                    delta_v_perc = ((v_end - v_mid) / v_mid) * 100.0
                    if delta_v_perc > 5.0: continue
                else: continue
            
            fig, ax1 = plt.subplots(figsize=(10, 6))
            ax1.errorbar(r, Vobs, yerr=errV, fmt='o', color='black', alpha=0.5, label='Observations')
            colors = {'nfw': 'red', 'iso': 'blue', 'burkert': 'green'}
            
            for profile in ['nfw', 'iso', 'burkert']:
                chi2, rhos, rs, upsilon, m200 = fit_profile(profile, r, Vobs, errV, Vgas, Vdisk, Vbul)
                
                V_bar_sq = Vgas * np.abs(Vgas) + upsilon * (Vdisk * np.abs(Vdisk) + Vbul * np.abs(Vbul))
                if profile == 'nfw': M_dm_arr = M_nfw(r, rhos, rs)
                elif profile == 'iso': M_dm_arr = M_iso(r, rhos, rs)
                else: M_dm_arr = M_burkert(r, rhos, rs)
                
                M_tot_edge = ((r[-1] * V_bar_sq[-1]) / G_grav) + M_dm_arr[-1]
                dm_frac = (M_dm_arr[-1] / M_tot_edge) * 100 if M_tot_edge > 0 else 0
                
                V_sim = np.sqrt(np.maximum(V_bar_sq + (G_grav * M_dm_arr) / r, 0))
                ax1.plot(r, V_sim, '-', color=colors[profile], linewidth=2, label=f'{profile.upper()} Fit')
                
                results[profile].append({
                    "Galaxy_Raw": raw_gal_name.replace("_rotmod", ""),
                    "Galaxy": gal_name, "Upsilon": upsilon, "r_s": rs, "rho_s": rhos,
                    "chi2": chi2, "M_tot": M_tot_edge, "DM_perc": dm_frac, "M200": m200, "R_edge": r[-1]
                })
                
            ax1.set_xlabel('Radius (kpc)')
            ax1.set_ylabel('Velocity (km/s)')
            ax1.set_title(f'{raw_gal_name.replace("_rotmod", "")} - Profile Comparison')
            ax1.legend()
            plt.savefig(os.path.join(output_folder, f"{gal_name}_combined.png"))
            plt.close()
            
        except Exception as e:
            continue

    # --- CALCOLO MEDIANE DELTA % E COSTRUZIONE RIGHE MEGA-TABELLA ---
    print("\n[3] Calcolo delle statistiche e stampa tabelle LaTeX...")
    medians = {p: {'ups': [], 'rs': [], 'rhos': [], 'chi2': [], 'm200': []} for p in ['nfw', 'iso', 'burkert']}
    galaxy_rows = []
    
    # Nomi abbreviati per far stringere la colonna in LaTeX!
    prof_names_short = {'nfw': 'NFW', 'iso': 'ISO', 'burkert': 'Bur'}
    prof_names_long = {'nfw': 'NFW', 'iso': 'ISO', 'burkert': 'Burkert'}
    
    all_gals_raw = sorted(set(res["Galaxy_Raw"] for res in results['nfw']))
    
    for raw_gal in all_gals_raw:
        gal_clean = clean_name(raw_gal)
        display_name = raw_gal.replace("_", r"\_")
        
        gal_chunk = [rf"\multirow{{3}}{{*}}{{\textbf{{{display_name}}}}}"]
        for profile in ['nfw', 'iso', 'burkert']:
            res = next((item for item in results[profile] if item["Galaxy"] == gal_clean), None)
            ref = sparc_data[profile].get(gal_clean, {})
            
            if not res or not ref:
                pref = " & " if profile == 'nfw' else " & "
                gal_chunk.append(f"{pref}{prof_names_short[profile]} & -- & -- & -- & -- & -- & {res['DM_perc']:.1f}\\% \\\\")
                continue
                
            d_ups = pct_diff(res['Upsilon'], ref.get('upsilon', np.nan))
            d_rs = pct_diff(res['r_s'], ref.get('rs', np.nan))
            d_rhos = pct_diff(res['rho_s'], ref.get('rhos', np.nan))
            d_chi2 = pct_diff(res['chi2'], ref.get('chi2', np.nan))
            d_m200 = pct_diff(res['M200'], ref.get('m200', np.nan))
            
            if not np.isnan(d_ups): medians[profile]['ups'].append(d_ups)
            if not np.isnan(d_rs): medians[profile]['rs'].append(d_rs)
            if not np.isnan(d_rhos): medians[profile]['rhos'].append(d_rhos)
            if not np.isnan(d_chi2): medians[profile]['chi2'].append(d_chi2)
            if not np.isnan(d_m200): medians[profile]['m200'].append(d_m200)
            
            row_str = (f"{prof_names_short[profile]} & "
                       f"{format_val_delta(res['Upsilon'], ref.get('upsilon', np.nan), d_ups)} & "
                       f"{format_val_delta(res['r_s'], ref.get('rs', np.nan), d_rs)} & "
                       f"{format_val_delta(res['rho_s'], ref.get('rhos', np.nan), d_rhos)} & "
                       f"{format_val_delta(res['chi2'], ref.get('chi2', np.nan), d_chi2)} & "
                       f"{format_val_delta(res['M200'], ref.get('m200', np.nan), d_m200)} & "
                       f"{res['DM_perc']:.1f}\\% \\\\")
            
            pref = " & " if profile == 'nfw' else " & "
            gal_chunk.append(pref + row_str)
            
        galaxy_rows.extend(gal_chunk)
        galaxy_rows.append(r"\hline")

    # --- 1. STAMPA DELLE 3 TABELLE ASSOLUTE ---
    for profile in ['nfw', 'iso', 'burkert']:
        print(f"\n\n% ================= TABELLA: {prof_names_long[profile]} =================")
        print(r"\begin{longtable}{@{}lccccccc@{}}")
        print(rf"\caption{{Best-fit parameters and DM fraction for the \textbf{{{prof_names_long[profile]}}} profile.}}")
        print(rf"\label{{tab:results_{profile}}} \\")
        print(r"\hline")
        print(r"Galaxy & $\Upsilon$ & $r_s$ [kpc] & $\rho_s$ [$M_\odot/\text{kpc}^3$] & $\chi^2_{\text{min}}$ & $R_{\text{edge}}$ [kpc] & $M_{\text{tot}}$ [$M_\odot$] & $\% \text{DM}$ \\")
        print(r"\hline")
        print(r"\endfirsthead")
        print(r"\multicolumn{8}{c}%")
        print(r"{{\bfseries \tablename\ \thetable{} -- continued from previous page}} \\")
        print(r"\hline")
        print(r"Galaxy & $\Upsilon$ & $r_s$ [kpc] & $\rho_s$ [$M_\odot/\text{kpc}^3$] & $\chi^2_{\text{min}}$ & $R_{\text{edge}}$ [kpc] & $M_{\text{tot}}$ [$M_\odot$] & $\% \text{DM}$ \\")
        print(r"\hline")
        print(r"\endhead")
        print(r"\hline \multicolumn{8}{r}{{Continued on next page}} \\")
        print(r"\endfoot")
        print(r"\hline")
        print(r"\endlastfoot")
        
        for res in results[profile]:
            gal = res["Galaxy_Raw"].replace("_", r"\_")
            rhos_tex = f"${format_sci(res['rho_s'])}$"
            mtot_tex = f"${format_sci(res['M_tot'])}$"
            print(f"{gal} & {res['Upsilon']:.2f} & {res['r_s']:.2f} & {rhos_tex} & {res['chi2']:.2f} & {res['R_edge']:.1f} & {mtot_tex} & {res['DM_perc']:.1f}\\% \\\\")
        print(r"\end{longtable}")

    # --- 2. STAMPA MEGA-TABELLA LATEX (SALVA-SPAZIO A4) ---
    print("\n\n% ================= MEGA-TABELLA: CONFRONTO PROFILI VS SPARC =================")
    print(r"{\scriptsize") # Dimensione font ancora più ridotta
    print(r"\setlength{\tabcolsep}{2pt}") # Comprime la distanza orizzontale tra colonne
    print(r"\begin{longtable}{@{}llcccccc@{}}")
    print(r"\caption{Comparison of best-fit parameters across DM profiles. Values are formatted as \textit{Our Fit / SPARC MCMC}, with the absolute percentage difference $\Delta\%$ below. Medians of $\Delta\%$ are reported at the top.}")
    print(r"\label{tab:mega_comparison} \\")
    print(r"\hline")
    print(r"\textbf{Galaxy} & \textbf{Prof} & \textbf{$\Upsilon$} & \textbf{$r_s$ [kpc]} & \textbf{$\rho_s$ [$M_\odot/\text{kpc}^3$]} & \textbf{$\chi^2_{\text{min}}$} & \textbf{$M_{200}$ [$M_\odot$]} & \textbf{\%DM} \\")
    print(r"\hline")
    print(r"\endfirsthead")
    print(r"\hline")
    print(r"\textbf{Galaxy} & \textbf{Prof} & \textbf{$\Upsilon$} & \textbf{$r_s$ [kpc]} & \textbf{$\rho_s$ [$M_\odot/\text{kpc}^3$]} & \textbf{$\chi^2_{\text{min}}$} & \textbf{$M_{200}$ [$M_\odot$]} & \textbf{\%DM} \\")
    print(r"\hline")
    print(r"\endhead")
    print(r"\hline")
    print(r"\endlastfoot")
    
    print(r"\multicolumn{8}{c}{\textbf{OVERALL MEDIAN $\Delta\%$ (LOWER IS BETTER)}} \\")
    print(r"\hline")
    for p in ['nfw', 'iso', 'burkert']:
        m_ups = f"{np.nanmedian(medians[p]['ups']):.1f}\\%" if medians[p]['ups'] else "--"
        m_rs = f"{np.nanmedian(medians[p]['rs']):.1f}\\%" if medians[p]['rs'] else "--"
        m_rhos = f"{np.nanmedian(medians[p]['rhos']):.1f}\\%" if medians[p]['rhos'] else "--"
        m_chi2 = f"{np.nanmedian(medians[p]['chi2']):.1f}\\%" if medians[p]['chi2'] else "--"
        m_m200 = f"{np.nanmedian(medians[p]['m200']):.1f}\\%" if medians[p]['m200'] else "--"
        print(rf"\multicolumn{{2}}{{l}}{{\textbf{{Median $\Delta\%$ {prof_names_long[p]}}}}} & \textbf{{{m_ups}}} & \textbf{{{m_rs}}} & \textbf{{{m_rhos}}} & \textbf{{{m_chi2}}} & \textbf{{{m_m200}}} & -- \\")
    
    print(r"\hline")
    print(r"\multicolumn{8}{c}{\textbf{DETAILED BREAKDOWN BY GALAXY}} \\")
    print(r"\hline")
    for row in galaxy_rows:
        print(row)
    print(r"\end{longtable}")
    print(r"}") # Chiude scriptsize
    
    create_galaxy_grid(output_folder, cols=3, rows_per_page=4)

if __name__ == "__main__":
    run_all_profiles()