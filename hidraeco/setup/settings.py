import os
import json
from pathlib import Path
import firebase_admin
from firebase_admin import credentials

# import dj_database_url


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Criar diretório de logs se não existir
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-s%5w70mp^bo0#9vc5pm2(s10pwinu*0$nle3nh88-a#sr87lj7'

# SECURITY WARNING: don't run with debug turned on in production!
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/


# ==============================================================================
# CONFIGURAÇÕES BASE
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get(
    'SECRET_KEY', 'django-insecure-s%5w70mp^bo0#9vc5pm2(s10pwinu*0$nle3nh88-a#sr87lj7')
ROOT_URLCONF = 'setup.urls'
WSGI_APPLICATION = 'setup.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# DETECÇÃO AUTOMÁTICA DE AMBIENTE (LOCAL vs. RENDER)
# ==============================================================================
IS_RENDER_ENV = 'RENDER' in os.environ
DEBUG = not IS_RENDER_ENV

if IS_RENDER_ENV:
    print("A carregar configurações de PRODUÇÃO (Render)...")
else:
    print("A carregar configurações de desenvolvimento (Local)...")
    FIREBASE_CREDENTIALS_PATH = BASE_DIR / \
        'hidra-eco-firebase-adminsdk-fbsvc-e8d6447316.json'
    FIREBASE_CREDENTIALS_JSON = None

    if not os.path.exists(FIREBASE_CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"O ficheiro de credenciais local não foi encontrado em: {FIREBASE_CREDENTIALS_PATH}")

# ==============================================================================
# CONFIGURAÇÕES DE APLICAÇÃO E SEGURANÇA
# ==============================================================================
# --- Configurações de Hosts Permitidos ---
ALLOWED_HOSTS = []

# A Render define esta variável de ambiente automaticamente com a sua URL principal
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    # Adiciona a URL padrão da Render (ex: hidra-eco.onrender.com)
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

    # --- ADICIONE OS SEUS DOMÍNIOS PERSONALIZADOS AQUI ---
    # Adicione o seu domínio principal e a versão com 'www'
    ALLOWED_HOSTS.extend(['hidra-eco.com.br', 'www.hidra-eco.com.br'])

else:
    # Se não estiver na Render, assume ambiente local
    ALLOWED_HOSTS.extend(['localhost', '127.0.0.1'])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'iotmonitor.apps.IotmonitorConfig',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ==============================================================================
# BANCO DE DADOS (DATABASE)
# ==============================================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ==============================================================================
# FIREBASE - LÓGICA FINAL E CONSOLIDADA
# ==============================================================================

# 1. Defina as suas URLs/IDs estáticas aqui
FIREBASE_DATABASE_URL = 'https://hidra-eco-default-rtdb.firebaseio.com'
# FIREBASE_STORAGE_BUCKET = 'hidra-eco-default-rtdb.appspot.com'
FIREBASE_STORAGE_BUCKET = 'hidra-eco.firebasestorage.app'

# 2. Lógica de inicialização que só corre uma vez
if not firebase_admin._apps:
    cred = None
    if IS_RENDER_ENV:
        # Na Render, carrega a partir da variável de ambiente
        firebase_credentials_json_str = os.environ.get('FIREBASE_CREDENTIALS')
        if firebase_credentials_json_str:
            cred_dict = json.loads(firebase_credentials_json_str)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_DATABASE_URL,
            'storageBucket': FIREBASE_STORAGE_BUCKET
            })
            print("Conexão com Firebase inicializada com sucesso. Dentro do Render")
            
        
        else:
            raise ValueError(
                "A variável de ambiente FIREBASE_CREDENTIALS não foi configurada na Render.")
        
        
    else:
        # Localmente, carrega a partir do ficheiro
        cred_path = BASE_DIR / 'hidra-eco-firebase-adminsdk-fbsvc-e8d6447316.json'
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_DATABASE_URL,
            'storageBucket': FIREBASE_STORAGE_BUCKET
            })
            print("Conexão com Firebase inicializada com sucesso. Dentro do Local")
        else:
            # Esta verificação pára o servidor local se o ficheiro não for encontrado
            raise FileNotFoundError(
                f"Ficheiro de credenciais não encontrado localmente: {cred_path}")

    #  inicializa a aplicação Firebase com as credenciais carregadas
    '''firebase_admin.initialize_app(cred, {
        'databaseURL': FIREBASE_DATABASE_URL,
        'storageBucket': FIREBASE_STORAGE_BUCKET
    })
    print("Conexão com Firebase inicializada com sucesso.")'''

# ==============================================================================
# TEMPLATES, I18N, STATICFILES
# ==============================================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [], 'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Recife'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ==============================================================================
# REDIRECIONAMENTOS E CORS
# ==============================================================================
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/login/'

if IS_RENDER_ENV:
    CORS_ALLOWED_ORIGINS = [
        f"https://{RENDER_EXTERNAL_HOSTNAME}",
    ]
else:
    CORS_ALLOW_ALL_ORIGINS = True

# ==============================================================================
# CONFIGURAÇÕES DE EMAIL (Mantidas como no seu original)
# ==============================================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'hidrateams@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get(
    'EMAIL_HOST_PASSWORD', 'qyhc pbkd nbgp wpbf')
DEFAULT_FROM_EMAIL = f'HIDRA <{EMAIL_HOST_USER}>'
