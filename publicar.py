"""Publica en Instagram la historia que toca según calendario.csv.

Corre cada 30 min desde GitHub Actions. Publica cualquier franja (8:00, 12:00,
16:00, 20:00 hora de Venezuela) que ya llegó, tiene menos de 3 h de atraso y
no aparece en publicados.txt.
"""
import csv, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

VE = timezone(timedelta(hours=-4))
API = "https://graph.facebook.com/v25.0"
IG_ID = os.environ["IG_USER_ID"]
TOKEN = os.environ["IG_TOKEN"]
BASE = os.environ["MEDIA_BASE_URL"].rstrip("/")
HORAS = ["08:00", "12:00", "16:00", "20:00"]
VENTANA = timedelta(hours=3)
LOG = "publicados.txt"


def api(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path}: {e.read().decode()}") from None


def url_de(nombre):
    ext = "mp4" if nombre.startswith("buenosdias_") else "jpg"
    return f"{BASE}/media/{nombre}.{ext}", ext


def crear_contenedor(nombre):
    url, ext = url_de(nombre)
    campo = "video_url" if ext == "mp4" else "image_url"
    cid = api("POST", f"{IG_ID}/media", media_type="STORIES", **{campo: url})["id"]
    for _ in range(40):
        st = api("GET", cid, fields="status_code,status").get("status_code")
        if st == "FINISHED":
            return cid
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"contenedor {nombre}: {st}")
        time.sleep(6)
    raise RuntimeError(f"contenedor {nombre}: tiempo agotado")


def publicar(nombre):
    cid = crear_contenedor(nombre)
    return api("POST", f"{IG_ID}/media_publish", creation_id=cid)["id"]


def main():
    prueba = os.environ.get("PRUEBA", "").strip()
    if prueba:  # crea el contenedor sin publicar: valida token, permisos y URL
        print("Contenedor OK:", crear_contenedor(prueba))
        return
    ahora_pieza = os.environ.get("PUBLICAR_AHORA", "").strip()
    if ahora_pieza:  # publica de verdad una pieza fuera del calendario
        print("Publicada ahora:", ahora_pieza, publicar(ahora_pieza))
        return

    hechos = set(open(LOG).read().split("\n")) if os.path.exists(LOG) else set()
    ahora = datetime.now(VE)
    filas = list(csv.reader(open("calendario.csv")))[1:]
    errores = 0
    for fila in filas:
        for hora, nombre in zip(HORAS, fila[1:]):
            franja = datetime.fromisoformat(f"{fila[0]}T{hora}").replace(tzinfo=VE)
            clave = f"{fila[0]} {hora} {nombre}"
            if clave in hechos or not (franja <= ahora <= franja + VENTANA):
                continue
            try:
                mid = publicar(nombre)
                print("Publicada", clave, mid)
                with open(LOG, "a") as f:
                    f.write(clave + "\n")
            except Exception as e:
                errores += 1
                print("ERROR", clave, e, file=sys.stderr)
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()
