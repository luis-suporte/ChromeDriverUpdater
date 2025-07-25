import os
import requests
import subprocess
import hashlib
from contextlib import contextmanager
from datetime import datetime
from dotenv import load_dotenv
from plyer import notification

# === CONFIGURAÇÃO ===
load_dotenv()
DESKTOP_PATH = os.getenv('CHROMEDRIVER_PATH')
ZIP_NAME = 'chromedriver-win64.zip'
VERSION_FILE = 'version.txt'
JSON_URL = 'https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json'
CHUNK_SIZE = 1024 * 1024  # 1MB

# === UTILS ===
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

@contextmanager
def change_dir(path):
    original = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)

def calcular_sha256(caminho_arquivo):
    sha256 = hashlib.sha256()
    with open(caminho_arquivo, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

# === MAIN FLOW ===
def obter_ultima_versao_e_url():
    resposta = requests.get(JSON_URL, timeout=10)
    resposta.raise_for_status()
    dados = resposta.json()
    canal_estavel = dados["channels"]["Stable"]
    versao = canal_estavel["version"]
    downloads = canal_estavel["downloads"]["chromedriver"]
    url = next((item["url"] for item in downloads if item["platform"] == "win64"), None)
    if not url:
        raise ValueError("URL do chromedriver-win64.zip não encontrada!")
    return versao, url

def ler_versao_salva(caminho):
    if os.path.exists(caminho):
        with open(caminho, 'r') as f:
            return f.read().strip()
    return None

def salvar_versao(caminho, versao):
    with open(caminho, 'w') as f:
        f.write(versao)

def baixar_arquivo_com_progresso(url, caminho):
    resposta = requests.get(url, stream=True, timeout=60)
    resposta.raise_for_status()
    total_size = int(resposta.headers.get('Content-Length', 0))
    downloaded_size = 0

    with open(caminho, 'wb') as f:
        for chunk in resposta.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)
                downloaded_size += len(chunk)
                percent = (downloaded_size / total_size) * 100
                print(f"\rBaixando: {percent:.2f}% ({downloaded_size / (1024 * 1024):.2f} MB / {total_size / (1024 * 1024):.2f} MB)", end='', flush=True)
    print("\nDownload concluído.")

def git_push_tag(caminho, arquivos, mensagem, tag):
    with change_dir(caminho):
        status = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if not status.stdout.strip():
            log("Nenhuma alteração detectada para subir no repositório.")
            return
        subprocess.run(['git', 'add'] + arquivos, check=True)
        subprocess.run(['git', 'commit', '-m', mensagem], check=True)
        subprocess.run(['git', 'push'], check=True)
        subprocess.run(['git', 'tag', tag], check=True)
        subprocess.run(['git', 'push', '--tags'], check=True)
        log(f"Arquivos enviados e tag {tag} criada no repositório.")

def notificar(titulo, mensagem):
    notification.notify(
        title=titulo,
        message=mensagem,
        timeout=5
    )

def main():
    os.makedirs(DESKTOP_PATH, exist_ok=True)
    caminho_zip = os.path.join(DESKTOP_PATH, ZIP_NAME)
    caminho_version = os.path.join(DESKTOP_PATH, VERSION_FILE)

    log("Verificando última versão estável do ChromeDriver...")
    versao_atual, url_chromedriver = obter_ultima_versao_e_url()
    log(f"Última versão estável: {versao_atual}")

    versao_salva = ler_versao_salva(caminho_version)
    if versao_salva == versao_atual and os.path.exists(caminho_zip):
        log("Você já possui a última versão. Nenhuma ação necessária.")
        return

    log(f"Iniciando download de: {url_chromedriver}")
    baixar_arquivo_com_progresso(url_chromedriver, caminho_zip)

    sha256 = calcular_sha256(caminho_zip)
    log(f"SHA256 do arquivo baixado: {sha256}")

    salvar_versao(caminho_version, versao_atual)

    git_push_tag(DESKTOP_PATH, [ZIP_NAME, VERSION_FILE], f'Atualização ChromeDriver {versao_atual}', f'v{versao_atual}')

    notificar("ChromeDriver Atualizado", f"Versão {versao_atual} baixada e enviada ao GitHub.")

if __name__ == "__main__":
    main()