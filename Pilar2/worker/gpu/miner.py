import subprocess, re, logging
from common.consumer import run_worker

EXE = "/app/limites_gpu"

log = logging.getLogger("worker")

def minar(cadena, prefijo, nonce_min, nonce_max):
    proc = subprocess.run([EXE, cadena, prefijo, str(nonce_min), str(nonce_max)],
                          capture_output=True, text=True)
    if proc.stderr:
        # aca viaja el diagnostico "[GPU] <nombre> SM x.y ..." y cualquier error de CUDA
        # (ej. "no se detecta GPU CUDA") - antes se descartaba en silencio.
        log.info(proc.stderr.strip())
    m_nonce = re.search(r"Nonce\s*:\s*(\d+)", proc.stdout)
    m_hash  = re.search(r"MD5\s*:\s*([0-9a-f]+)", proc.stdout)
    if m_nonce and m_hash:
        return int(m_nonce.group(1)), m_hash.group(1)
    return None, None

if __name__ == "__main__":
    run_worker(minar)
