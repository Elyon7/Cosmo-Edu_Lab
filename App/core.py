import os
import json
from functools import lru_cache
import pandas as pd
from dotenv import load_dotenv
from fastapi import Request
from groq import Groq
#from ipywidgets import interact, FloatSlider
import nicegui
from nicegui import ui, app, run , client
#from nicegui_toolkit import inject_layout_tool
import asyncio           
import logging
from huggingface_hub import HfApi, hf_hub_download
import io
from io import BytesIO
import json
import re
import uuid
import base64
import datetime
import threading
import random
from fractions import Fraction
from math import isfinite
#inject_layout_tool()
import numpy as np
import matplotlib.pyplot as plt
from google import genai
DATASET_REPO_ID = "Elyon7/Cosmo_login" 
DATASET_FILENAME = "app_data.json"
LOCAL_DATA_FILE = "app_data.json"
_rho_rs_cache = {}
_cluster_calc_cache = {}

load_dotenv()


    
@app.get('/.well-known/appspecific/com.chrome.devtools.json')
async def chrome_devtools_stub():
    return {}

logging.getLogger("nicegui").setLevel(logging.ERROR)
client.Client.DEFAULT_JS_TIMEOUT = 3600

def fig_to_base64(fig):
    """Converts a matplotlib figure to a base64 encoded string."""
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig) 
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')


HF_API_TOKEN = os.getenv("HF_API_TOKEN")



_data_lock = threading.Lock()

_local_generator = None
_local_lock = threading.Lock()
#LOCAL_MODEL_NAME = "google/flan-t5-large"

#HUGGINGFACE_MODEL = "tiiuae/falcon-7b-instruct"

GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


DATA_FILE = 'app_data.json'

app_data = {'users': {}, 'reflection_log': []}


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GALAXY_DATA_PATH = os.path.join(BASE_DIR, "galaxy_data")
GALAXY_IMG_PATH = os.path.join(BASE_DIR, "galaxy_img")
GALAXY_TABLES_PATH = os.path.join(BASE_DIR, "galaxy_tables")
CLUSTER_DATA_PATH = os.path.join(BASE_DIR, "cluster_data")
CLUSTER_IMG_PATH = os.path.join(BASE_DIR, "cluster_img")
CLUSTER_TABLES_PATH = os.path.join(BASE_DIR, "cluster_tables")
GALAXY_SPECTRA_PATH = os.path.join(BASE_DIR, "galaxy_spectra/csv_converted")
GALAXY_LINE_PATH = os.path.join(BASE_DIR, "galaxy_spectra/lambda_obs")
#GALAXY_FITS_PATH = os.path.join(BASE_DIR, "galaxy_fits")
PLANETS_IMG_PATH = os.path.join(BASE_DIR, "planet_image")
GAL_SDSS_PATH = os.path.join(DATA_DIR, "SDSS_30.csv")
STAR_GAIA_PATH = os.path.join(DATA_DIR, "Gaia_20000.csv")
#GALAXY_ZOO_PATH = os.path.join(DATA_DIR, "galaxy_zoo_classifications.csv")
MIST_PATH = os.path.join(BASE_DIR, "iso_fe0.01")
SDSS_MORPHO_PATH = os.path.join(DATA_DIR, "sdss_gal_morfo.txt")
#cluster_gif_path = os.path.join(BASE_DIR, 'cluster_gif')

if os.path.exists('/data'):
    DATA_FILE = '/data/app_data.json'
else:
    DATA_FILE = 'app_data.json'

def load_data():
    """
    Strategia Ibrida:
    1. Prova a scaricare dal Cloud (è la fonte di verità).
    2. Se fallisce (offline/no token), carica dal file locale.
    """
    global app_data
    
    # TENTATIVO 1: CLOUD
    if HF_API_TOKEN:
        try:
            print("☁️ Tentativo download dati dal Cloud...", end=" ")
            file_path = hf_hub_download(
                repo_id=DATASET_REPO_ID,
                filename=DATASET_FILENAME,
                repo_type="dataset",
                token=HF_API_TOKEN,
                local_dir="." # Scarica nella cartella corrente
            )
            with open(file_path, 'r') as f:
                app_data = json.load(f)
            print("✅ Successo!")
            return # Se ha funzionato, usciamo
        except Exception as e:
            print(f"⚠️ Fallito ({e}). Passo al locale.")
    
    # TENTATIVO 2: LOCALE (Fallback)
    if os.path.exists(LOCAL_DATA_FILE):
        try:
            with open(LOCAL_DATA_FILE, 'r') as f:
                app_data = json.load(f)
            print("🏠 Dati caricati dal disco locale.")
        except Exception as e:
            print(f"❌ Errore caricamento locale: {e}")

def save_data():
    """
    Salva SEMPRE in locale, e se possibile sincronizza col Cloud.
    """
    global app_data
    
    # 1. SALVATAGGIO LOCALE (Immediato)
    try:
        with open(LOCAL_DATA_FILE, 'w') as f:
            json.dump(app_data, f, indent=4)
    except Exception as e:
        print(f"❌ Errore salvataggio locale: {e}")

    # 2. SALVATAGGIO CLOUD (Background Sync)
    if HF_API_TOKEN:
        # Eseguiamo l'upload in un thread separato per non bloccare l'app
        def _upload_task():
            try:
                api = HfApi(token=HF_API_TOKEN)
                json_bytes = json.dumps(app_data, indent=4).encode('utf-8')
                bio = BytesIO(json_bytes)
                
                api.upload_file(
                    path_or_fileobj=bio,
                    path_in_repo=DATASET_FILENAME,
                    repo_id=DATASET_REPO_ID,
                    repo_type="dataset",
                    commit_message="Sync data"
                )
                print("☁️ Dati sincronizzati col Cloud.")
            except Exception as e:
                print(f"⚠️ Errore sync Cloud: {e}")
        
        threading.Thread(target=_upload_task).start()