import os
import glob
import pandas as pd
import numpy as np


c_light = 3e5         # km/s
H0_kmsMpc = 70.0
M_sun_r = 4.67
M_to_L_ratio = 5.0  


def stellar_mass_from_r_mag(app_mag_r, extinction_r, z, M_to_L_ratio=5.0):
    """
    Calcola la massa stellare (barionica) in masse solari.
    """
    mag_corrected = app_mag_r - extinction_r
    
    # Calcolo della distanza di luminosità
    D_L_Mpc = (c_light * z) / H0_kmsMpc
    dist_mod = 5 * np.log10(D_L_Mpc * 1e6) - 5
    
    # Magnitudine assoluta
    M_galaxy_r = mag_corrected - dist_mod
    
    # Luminosità in unità solari
    L_galaxy_solar = 10.0**(0.4 * (M_sun_r - M_galaxy_r))
    
    # Massa in masse solari
    stellar_mass_msun = L_galaxy_solar * M_to_L_ratio
    return stellar_mass_msun

def crea_dataset_excel(input_folder, output_excel):
    """
    Legge tutti i file .txt nella cartella, calcola la massa barionica, 
    rimuove le prime due colonne e salva tutto in un unico file Excel multi-foglio.
    """

    file_list = glob.glob(os.path.join(input_folder, "*.txt"))
    
    if not file_list:
        print(f"Nessun file .txt trovato nella cartella '{input_folder}'!")
        return

    print(f"Trovati {len(file_list)} dataset. Inizio l'elaborazione...")

   
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        for file_path in file_list:
      
            nome_file = os.path.basename(file_path)
            nome_cluster = os.path.splitext(nome_file)[0][:31] 
            
            try:
            
                df = pd.read_csv(file_path, sep=r"\s+", header=None)
                
               
                df = df.iloc[:, :8]
                df.columns = ["Cluster", "ID", "RAdeg", "DEdeg", "RV", "e_RV", "q_RV", "bmag"]
                
             
                for col in ["RAdeg", "DEdeg", "RV", "bmag"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df.dropna(subset=["RAdeg", "DEdeg", "RV", "bmag"])
                
            
                if df.empty:
                    print(f"  [Avviso] Il file {nome_file} è vuoto dopo la pulizia dei dati.")
                    continue

             
                z_cluster = np.nanmedian(df["RV"].values / c_light)
                
              
                df["Luminous_Mass_Msun"] = stellar_mass_from_r_mag(
                    app_mag_r=df["bmag"].values, 
                    extinction_r=0.0, 
                    z=z_cluster, 
                    M_to_L_ratio=M_to_L_ratio
                )
                
                
                df_finale = df.drop(columns=["Cluster", "ID"])
                
              
                df_finale = df_finale.rename(columns={
                    "RAdeg": "Radeg",
                    "DEdeg": "Dedeg",
                    "e_RV": "err_RV"
                })
                
              
                df_finale.to_excel(writer, sheet_name=nome_cluster, index=False)
                print(f"  ✓ {nome_cluster} elaborato e salvato correttamente.")
                
            except Exception as e:
                print(f"  [Errore] Impossibile elaborare il file {nome_file}: {e}")

    print(f"\nOperazione completata! File salvato come: {output_excel}")


if __name__ == "__main__":
   
    CARTELLA_DATI = "cluster_data" 
    
   
    NOME_FILE_OUTPUT = "Cluster_Datasets.xlsx"
    
   
    if not os.path.exists(CARTELLA_DATI):
        print(f"Attenzione: La cartella '{CARTELLA_DATI}' non esiste. Assicurati che il percorso sia corretto.")
    else:
        crea_dataset_excel(CARTELLA_DATI, NOME_FILE_OUTPUT)