import subprocess, re
from common.consumer import run_worker

EXE = "/app/limites_gpu"   

def minar(cadena, prefijo, nonce_min, nonce_max):
    out = subprocess.run([EXE, cadena, prefijo, str(nonce_min), str(nonce_max)],
                         capture_output=True, text=True).stdout
    m_nonce = re.search(r"Nonce\s*:\s*(\d+)", out)
    m_hash  = re.search(r"MD5\s*:\s*([0-9a-f]+)", out)
    if m_nonce and m_hash:
        return int(m_nonce.group(1)), m_hash.group(1)
    return None, None

if __name__ == "__main__":
    run_worker(minar)
