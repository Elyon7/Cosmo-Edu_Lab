import PyInstaller.__main__
import os
import platform
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys

# La cartella in cui si trovano main.py e tutte le sottocartelle (images, static, ecc.)
APP_DIR = "App"
sys.path.append(os.path.abspath(APP_DIR))

from astropy.utils import iers

os.environ['ASTROPY_SKIP_INTERNET_DOWNLOADS'] = '1'
os.environ['ASTROPY_ALLOW_INTERNET'] = 'False'
iers.conf.auto_download = False
APP_NAME = "Cosmo-Edu_Lab"

# Riconoscimento del Sistema Operativo
current_os = platform.system()
if current_os == 'Windows':
    ext = '.exe'
    os_suffix = '_Windows'
elif current_os == 'Darwin':
    ext = ''
    os_suffix = '_Mac'
elif current_os == 'Linux':
    ext = ''
    os_suffix = '_Linux'
else:
    ext = ''
    os_suffix = '_Other'

FINAL_OUTPUT_NAME = f"{APP_NAME}{os_suffix}"

print(f"🔍 Analisi dipendenze complesse per {current_os}...")

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

# FIX: Aggiungiamo 'App/' (o APP_DIR) davanti a ogni cartella locale
my_datas = [
    (os.path.join(APP_DIR, 'static'), 'static'),           
    (os.path.join(APP_DIR, 'images'), 'images'),           
    (os.path.join(APP_DIR, 'data'), 'data'),               
    (os.path.join(APP_DIR, 'dataset'), 'dataset'), 
    (os.path.join(APP_DIR, 'galaxy_data'), 'galaxy_data'), 
    (os.path.join(APP_DIR, 'cluster_data'), 'cluster_data'),
    (os.path.join(APP_DIR, 'cluster_tables'), 'cluster_tables'),
    (os.path.join(APP_DIR, 'iso_fe0.01'), 'iso_fe0.01'),
    (os.path.join(APP_DIR, 'pages'), 'pages'),
    (os.path.join(APP_DIR, 'galaxy_spectra'), 'galaxy_spectra'),
    (os.path.join(APP_DIR, 'planet_image'), 'planet_image'),
    (os.path.join(APP_DIR, 'galaxy_img'), 'galaxy_img'),
    (os.path.join(APP_DIR, 'cluster_img'), 'cluster_img'),
    (os.path.join(APP_DIR, 'galaxy_tables'), 'galaxy_tables'),
    (os.path.join(APP_DIR, 'slides'), 'slides'),
    (os.path.join(APP_DIR, 'discovery_images'), 'discovery_images'),
    (os.path.join(APP_DIR, 'cosmic_epochs'), 'cosmic_epochs'),
]

all_datas = my_datas + astroquery_datas + astropy_datas + plotly_datas + toolkit_datas + latex_datas + imageio_datas

hidden_imports = [
    # Scipy 
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
    
    # Matplotlib Backends 
    'matplotlib.backends.backend_svg',
    'matplotlib.backends.backend_agg',
    'matplotlib.backends.backend_pdf',
    'matplotlib.backends.backend_ps',
    
    # Altro
    'pages', 
    'latex2mathml',
    'imageio',
    'nicegui_toolkit',
]

hidden_imports += collect_submodules('astroquery')
hidden_imports += collect_submodules('nicegui_toolkit')

add_data_args = []

# Gestione sicura del separatore in base al sistema operativo (Windows usa ';', Unix usa ':')
separator = ';' if current_os == 'Windows' else ':' 

for source, dest in all_datas:
    if os.path.exists(source):
        add_data_args.append(f'--add-data={source}{separator}{dest}')
    elif os.path.isabs(source) and os.path.exists(source):
        add_data_args.append(f'--add-data={source}{separator}{dest}')
    else:
        # Se una cartella manca, ce lo segnala nei log di GitHub invece di ignorarla!
        print(f"⚠️ WARNING: Data source not found and skipped: {source}")

hidden_import_args = [f'--hidden-import={mod}' for mod in hidden_imports]

args = [
    os.path.join(APP_DIR, 'main.py'),                  
    f'--name={FINAL_OUTPUT_NAME}',       
    '--onefile',                
    '--windowed',      
    '--clean',                  
    '--optimize=1',
    '--collect-all=nicegui',          
    '--collect-all=nicegui_toolkit', 
    '--collect-all=xyz_services',
    '--collect-all=astropy',
    '--collect-all=astroquery',
    '--collect-all=pyvo',
] + add_data_args + hidden_import_args

print(f"\n🚀 Avvio build completo con supporto per {len(hidden_imports)} librerie critiche su {current_os}...")

try:
    PyInstaller.__main__.run(args)
    print(f"\n✅ SUCCESSO! Trovi il file in: dist/{FINAL_OUTPUT_NAME}{ext}")
except Exception as e:
    print(f"\n❌ ERRORE: {e}")