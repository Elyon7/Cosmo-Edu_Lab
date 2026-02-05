import PyInstaller.__main__
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

APP_NAME = "Cosmo-Edu_Lab"

print("🔍 Analisi dipendenze complesse...")

# --- 1. RACCOLTA DATI LIBRERIE (Fix per FileNotFoundError) ---
# Astroquery e Astropy: Configurazione e citazioni
astroquery_datas = collect_data_files('astroquery')
astropy_datas = collect_data_files('astropy')
# Plotly: Schemi JSON per i grafici
plotly_datas = collect_data_files('plotly')
# NiceGUI Toolkit: File JS/CSS aggiuntivi
toolkit_datas = collect_data_files('nicegui_toolkit')
# Latex2MathML: Mappature XML/JSON
latex_datas = collect_data_files('latex2mathml')
# Imageio: Plugin e risorse
imageio_datas = collect_data_files('imageio')

# --- 2. LE TUE CARTELLE ---
my_datas = [
    ('static', 'static'),           
    ('images', 'images'),           
    ('data', 'data'),               
    ('dataset', 'dataset'), 
    ('galaxy_data', 'galaxy_data'), 
    ('cluster_data', 'cluster_data'),
    ('cluster_tables', 'cluster_tables'),
    ('iso_fe0.01', 'iso_fe0.01'),
    ('pages', 'pages'),
    ('galaxy_spectra', 'galaxy_spectra'),
    ('planet_image', 'planet_image'),
    ('galaxy_img', 'galaxy_img'),
    ('cluster_img', 'cluster_img'),
    ('galaxy_tables', 'galaxy_tables'),
    ('slides', 'slides'),
    ('discovery_images', 'discovery_images'),
    ('cosmic_epochs', 'cosmic_epochs'),
]

# Uniamo tutto
all_datas = my_datas + astroquery_datas + astropy_datas + plotly_datas + toolkit_datas + latex_datas + imageio_datas

# --- 3. HIDDEN IMPORTS (Fix per ModuleNotFoundError) ---
hidden_imports = [
    # Scipy (Critico)
    'scipy.special.cython_special',
    'scipy.spatial.transform._rotation_groups',
    'scipy.stats._stats',
    
    # Astropy/Astroquery
    'astropy.coordinates',
    'astroquery.simbad',
    'astroquery.mast',
    
    # Plotly/NetworkX
    'plotly.validators',
    'plotly.graph_objs',
    'networkx',
    'PIL',
    
    # Matplotlib Backends (CRITICO per i tuoi grafici)
    'matplotlib.backends.backend_svg',
    'matplotlib.backends.backend_agg',
    'matplotlib.backends.backend_pdf',
    'matplotlib.backends.backend_ps',
    
    # Altro
    'pages', # Il tuo pacchetto
    'latex2mathml',
    'imageio',
    'nicegui_toolkit',
]
# Aggiungiamo i sottomoduli automatici
hidden_imports += collect_submodules('astroquery')
hidden_imports += collect_submodules('nicegui_toolkit')

# --- 4. COSTRUZIONE ARGOMENTI ---
add_data_args = []
separator = ';' if os.name == 'nt' else ':' 

for source, dest in all_datas:
    if os.path.exists(source):
        add_data_args.append(f'--add-data={source}{separator}{dest}')
    elif os.path.isabs(source) and os.path.exists(source):
        add_data_args.append(f'--add-data={source}{separator}{dest}')

hidden_import_args = [f'--hidden-import={mod}' for mod in hidden_imports]

args = [
    'main.py',                  
    f'--name={APP_NAME}',       
    '--onefile',                
    '--windowed',  # <--- RIMESSO WINDOWED (Togli se vuoi fare debug)             
    '--clean',                  
    '--optimize=1',
    
    # --- COLLEZIONI SPECIALI ---
    '--collect-all=nicegui',          # Essenziale
    '--collect-all=nicegui_toolkit',  # Essenziale per il toolkit
    '--collect-all=xyz_services',     # Spesso usato da Plotly/Map
    
] + add_data_args + hidden_import_args

print(f"\n🚀 Avvio build completo con supporto per {len(hidden_imports)} librerie critiche...")

try:
    PyInstaller.__main__.run(args)
    print(f"\n✅ SUCCESSO! Trovi il file in: dist/{APP_NAME}.exe")
except Exception as e:
    print(f"\n❌ ERRORE: {e}")