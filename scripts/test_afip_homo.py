#!/usr/bin/env python3
"""
test_afip_homo.py
─────────────────
Script STANDALONE para validar la conexión con AFIP/ARCA en homologación.
NO modifica ni importa nada del proyecto. Solo prueba:

  1. WSAA  — Obtener Token/Sign (con caché para evitar bloqueos)
  2. WSFE  — FEParamGetPtosVenta
  3. WSFE  — FECompUltimoAutorizado
  4. WSFE  — FECAESolicitar (Factura C, $1000, consumidor final)

Dependencias (pip install zeep cryptography):
  zeep==4.3.3          — cliente SOAP
  cryptography>=3.2    — firma CMS/PKCS#7

Uso:
  python scripts/test_afip_homo.py
"""

import base64
import json
import os
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Forzar UTF-8 en la consola de Windows (cp1252 no soporta los símbolos del script)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ── firma CMS con la lib `cryptography` (Python-puro, robusto en Windows) ──────
# Alternativa con OpenSSL subprocess al final del archivo (comentada).
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7, load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate

import zeep
from zeep.transports import Transport

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
CUIT      = 27287927490
CERT_PATH = Path(r"C:\Users\Rodri\bejas-afip-certs\bejas_homo2.crt")
KEY_PATH  = Path(r"C:\Users\Rodri\bejas-afip-certs\bejas_homo2.key")

# Caché por CUIT — evita pisarse si se alterna entre certificados
CACHE_PATH = Path(__file__).parent / f"ta_cache_{CUIT}.json"

# URLs de HOMOLOGACIÓN (nunca las de producción en este script)
WSAA_WSDL = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"
WSFE_WSDL = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

SERVICE = "wsfe"
AR_TZ   = ZoneInfo("America/Argentina/Buenos_Aires")


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════════
def sep(title: str) -> None:
    print(f"\n{'─' * 62}")
    print(f"  {title}")
    print("─" * 62)


def abort(msg: str) -> None:
    print(f"\n⛔  {msg}", file=sys.stderr)
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 1 — WSAA: Autenticación
# ═══════════════════════════════════════════════════════════════════════════════
def _build_ltr(service: str) -> bytes:
    """Construye el XML LoginTicketRequest."""
    now = datetime.now(tz=AR_TZ)
    gen = now.strftime("%Y-%m-%dT%H:%M:%S-03:00")
    exp = (now + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S-03:00")
    uid = int(now.timestamp()) & 0xFFFFFFFF          # uint32 único por ventana
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<loginTicketRequest version="1.0">'
        f'<header>'
        f'<uniqueId>{uid}</uniqueId>'
        f'<generationTime>{gen}</generationTime>'
        f'<expirationTime>{exp}</expirationTime>'
        f'</header>'
        f'<service>{service}</service>'
        '</loginTicketRequest>'
    )
    return xml.encode("utf-8")


def _sign_cms(data: bytes) -> str:
    """
    Firma `data` con CMS/PKCS#7 (data adjunta, DER, SHA-256).
    Devuelve el resultado en base64.

    Se usa la lib `cryptography` (puro Python).  Alternativa con subprocess
    de OpenSSL al final del archivo si hubiera problemas con la lib.
    """
    with open(KEY_PATH, "rb") as f:
        priv_key = load_pem_private_key(f.read(), password=None)
    with open(CERT_PATH, "rb") as f:
        cert = load_pem_x509_certificate(f.read())

    # pkcs7.PKCS7Options.DetachedSignature NO se incluye → datos adjuntos.
    # AFIP/WSAA necesita que el XML quede dentro del CMS (no detached).
    cms_der = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(data)
        .add_signer(cert, priv_key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [])
    )
    return base64.b64encode(cms_der).decode("ascii")


def _load_cached_ta() -> dict | None:
    """Devuelve el TA cacheado si todavía es válido (margen de 10 min)."""
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text())
        exp_raw = data.get("expiration", "")
        # AFIP puede devolver offset con milisegundos: 2026-06-28T22:00:00.000-03:00
        exp_raw = exp_raw.split(".")[0] + "-03:00" if "." in exp_raw else exp_raw
        exp = datetime.fromisoformat(exp_raw).astimezone(timezone.utc)
        if datetime.now(tz=timezone.utc) < exp - timedelta(minutes=10):
            return data
    except Exception:
        pass
    return None


def _save_ta_cache(token: str, sign: str, expiration: str) -> None:
    CACHE_PATH.write_text(
        json.dumps({"token": token, "sign": sign, "expiration": expiration}, indent=2)
    )


def get_token_sign() -> tuple[str, str]:
    sep("PASO 1 — WSAA: Autenticación")

    cached = _load_cached_ta()
    if cached:
        print("✓  Token/Sign reutilizado del caché (aún válido)")
        print(f"   Token[:20]: {cached['token'][:20]}…")
        print(f"   Expira:     {cached['expiration']}")
        return cached["token"], cached["sign"]

    print("→  Generando nuevo Ticket de Acceso…")

    ltr_bytes = _build_ltr(SERVICE)
    print(f"   LoginTicketRequest: {ltr_bytes.decode()[:100]}…")

    cms_b64 = _sign_cms(ltr_bytes)
    print(f"   CMS firmado base64 (primeros 40 chars): {cms_b64[:40]}…")

    # Llamada SOAP a WSAA
    transport = Transport(timeout=30, operation_timeout=30)
    wsaa = zeep.Client(wsdl=WSAA_WSDL, transport=transport)
    raw_resp = wsaa.service.loginCms(in0=cms_b64)

    # La respuesta es un XML como string
    from xml.etree import ElementTree as ET
    root = ET.fromstring(raw_resp)

    token      = root.findtext(".//token")
    sign       = root.findtext(".//sign")
    expiration = root.findtext(".//expirationTime")

    if not token or not sign:
        abort(f"WSAA no devolvió token/sign. Respuesta completa:\n{raw_resp}")

    _save_ta_cache(token, sign, expiration or "")

    print("✓  Login exitoso")
    print(f"   Token[:20]:  {token[:20]}…")
    print(f"   Sign[:20]:   {sign[:20]}…")
    print(f"   Expira:      {expiration}")
    return token, sign


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 2 — WSFEv1: Puntos de venta
# ═══════════════════════════════════════════════════════════════════════════════
def _afip_errors(resp) -> list[str]:
    """Extrae errores de una respuesta AFIP (si los hay)."""
    msgs: list[str] = []
    try:
        for e in resp.Errors.Err:
            msgs.append(f"[{e.Code}] {e.Msg}")
    except (AttributeError, TypeError):
        pass
    return msgs


def get_pv(client, auth: dict) -> int:
    sep("PASO 2 — WSFEv1: Puntos de venta habilitados")
    resp = client.service.FEParamGetPtosVenta(Auth=auth)

    errs = _afip_errors(resp)
    # Error 602 = "Sin Resultados" — ocurre en homo aunque el CUIT pueda facturar.
    # En ese caso continuamos con PV=1 por defecto sin abortar.
    if errs:
        codigos = [e.split("]")[0].lstrip("[") for e in errs]
        for e in errs:
            print(f"   AFIP respondió: {e}")
        if "602" in codigos:
            print("⚠   Error 602 (Sin Resultados) — normal en homologación.")
            print("   → Continuando con PV=1 por defecto.")
            return 1
        # Cualquier otro error sí aborta
        abort("AFIP devolvió error inesperado al listar puntos de venta.")

    pvs = []
    try:
        pvs = resp.ResultGet.PtoVenta or []
    except (AttributeError, TypeError):
        pass

    if not pvs:
        print("⚠   Lista de PVs vacía — continuando con PV=1 por defecto.")
        return 1

    print("   Puntos de venta encontrados:")
    elegido: int | None = None
    for pv in pvs:
        activo = pv.FchBaja is None
        estado = "ACTIVO" if activo else f"baja: {pv.FchBaja}"
        print(f"     PV {pv.Nro:>4}  |  {str(pv.EmisionTipo):<14}  |  {estado}")
        if elegido is None and activo:
            elegido = pv.Nro

    if elegido is None:
        print("⚠   Todos los PVs están dados de baja — continuando con PV=1 por defecto.")
        return 1

    print(f"\n   → Usaremos el PV {elegido}")
    return elegido


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 3 — WSFEv1: Último comprobante autorizado
# ═══════════════════════════════════════════════════════════════════════════════
def get_ultimo(client, auth: dict, pv: int, cbte_tipo: int) -> int:
    sep(f"PASO 3 — WSFEv1: Último comprobante (PV={pv}, Tipo={cbte_tipo} Factura C)")
    resp = client.service.FECompUltimoAutorizado(
        Auth=auth, PtoVta=pv, CbteTipo=cbte_tipo
    )

    errs = _afip_errors(resp)
    if errs:
        for e in errs:
            print(f"   ERROR AFIP: {e}")
        abort("Error al consultar último comprobante.")

    ultimo = resp.CbteNro
    print(f"   Último número autorizado: {ultimo}")
    print(f"   Próximo a emitir:         {ultimo + 1}")
    return ultimo


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 4 — WSFEv1: Emitir Factura C de prueba
# ═══════════════════════════════════════════════════════════════════════════════
def emitir_factura_c(client, auth: dict, pv: int, ultimo: int) -> dict:
    sep("PASO 4 — WSFEv1: Emitir Factura C de prueba ($1000, consumidor final)")

    CBTE_TIPO = 11   # Factura C — no discrimina IVA
    cbte_nro  = ultimo + 1
    fecha_hoy = datetime.now(tz=AR_TZ).strftime("%Y%m%d")

    print(f"   PV={pv}  |  Tipo=11 (Factura C)  |  Número={cbte_nro}  |  Fecha={fecha_hoy}")
    print(f"   DocTipo=99 (consumidor final), DocNro=0, ImpTotal=1000")

    body = {
        "Auth": auth,
        "FeCAEReq": {
            "FeCabReq": {
                "CantReg":  1,
                "PtoVta":   pv,
                "CbteTipo": CBTE_TIPO,
            },
            "FeDetReq": {
                "FECAEDetRequest": [
                    {
                        "Concepto":   1,       # Productos
                        "DocTipo":    99,      # Consumidor final
                        "DocNro":     0,
                        "CbteDesde":  cbte_nro,
                        "CbteHasta":  cbte_nro,
                        "CbteFch":    fecha_hoy,
                        "ImpTotal":   1000.00,
                        "ImpTotConc": 0.00,
                        "ImpNeto":    1000.00,
                        "ImpOpEx":    0.00,
                        "ImpIVA":     0.00,
                        "ImpTrib":    0.00,
                        "MonId":      "PES",
                        "MonCotiz":   1.00,
                    }
                ]
            },
        },
    }

    resp = client.service.FECAESolicitar(**body)

    result: dict = {"PtoVta": pv, "CbteTipo": CBTE_TIPO, "CbteNro": cbte_nro}

    # ── Cabecera de respuesta ────────────────────────────────────────────────
    try:
        cab = resp.FeCabResp
        print(f"\n   Resultado global:  {cab.Resultado}")
        print(f"   Reproceso:         {cab.Reproceso}")
        print(f"   FchProceso:        {cab.FchProceso}")
    except AttributeError:
        pass

    # ── Detalle del comprobante ──────────────────────────────────────────────
    try:
        det = resp.FeDetResp.FECAEDetResponse[0]
        result["Resultado"] = det.Resultado
        result["CAE"]       = det.CAE
        result["CAEFchVto"] = det.CAEFchVto

        aprobado = det.Resultado == "A"
        marca    = "✓" if aprobado else "✗"
        estado   = "APROBADO" if aprobado else "RECHAZADO"
        print(f"\n   Resultado:     {det.Resultado}  — {estado} {marca}")
        print(f"   CAE:           {det.CAE}")
        print(f"   Vto. CAE:      {det.CAEFchVto}")

        # Observaciones (avisos no fatales)
        try:
            obs_list = det.Observaciones.Obs
            if obs_list:
                print("\n   Observaciones:")
                for obs in obs_list:
                    print(f"     [{obs.Code}] {obs.Msg}")
        except (AttributeError, TypeError):
            pass

    except (AttributeError, TypeError, IndexError) as exc:
        print(f"\n   ⚠  No se pudo leer FeDetResp: {exc}")

    # ── Errores a nivel de solicitud ─────────────────────────────────────────
    errs = _afip_errors(resp)
    if errs:
        print("\n   ERRORES AFIP (texto literal):")
        for e in errs:
            print(f"     {e}")

    # ── Eventos informativos ─────────────────────────────────────────────────
    try:
        for ev in resp.Events.Evt:
            print(f"\n   Evento [{ev.Code}]: {ev.Msg}")
    except (AttributeError, TypeError):
        pass

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    print("=" * 62)
    print("  TEST AFIP/ARCA — ENTORNO DE HOMOLOGACIÓN (testing)")
    print("=" * 62)
    print(f"  CUIT:    {CUIT}")
    print(f"  Cert:    {CERT_PATH}")
    print(f"  Caché:   {CACHE_PATH}")
    print(f"  WSAA:    {WSAA_WSDL}")
    print(f"  WSFEv1:  {WSFE_WSDL}")

    # Verificar que existen los archivos de certificado
    for p in (CERT_PATH, KEY_PATH):
        if not p.exists():
            abort(f"Archivo no encontrado: {p}")

    # ── Paso 1: Token y Sign ─────────────────────────────────────────────────
    token, sign = get_token_sign()
    auth = {"Token": token, "Sign": sign, "Cuit": CUIT}

    # ── Pasos 2-4: WSFEv1 ────────────────────────────────────────────────────
    transport   = Transport(timeout=60, operation_timeout=60)
    wsfe_client = zeep.Client(wsdl=WSFE_WSDL, transport=transport)

    pv     = get_pv(wsfe_client, auth)
    ultimo = get_ultimo(wsfe_client, auth, pv, cbte_tipo=11)
    result = emitir_factura_c(wsfe_client, auth, pv, ultimo)

    # ── Resumen ───────────────────────────────────────────────────────────────
    sep("RESUMEN FINAL")
    print(f"  PUNTO DE VENTA:  {result.get('PtoVta', '—')}")
    print(f"  TIPO:            Factura C (código 11)")
    print(f"  NÚMERO:          {result.get('CbteNro', '—')}")
    print(f"  CAE:             {result.get('CAE', '—')}")
    print(f"  VENCIMIENTO CAE: {result.get('CAEFchVto', '—')}")
    resultado = result.get("Resultado", "—")
    marca     = "✓" if resultado == "A" else ("✗" if resultado == "R" else "—")
    print(f"  RESULTADO:       {resultado}  {marca}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# ALTERNATIVA: firma CMS con OpenSSL subprocess (descomentar si cryptography falla)
# ═══════════════════════════════════════════════════════════════════════════════
# def _sign_cms_openssl(data: bytes) -> str:
#     import subprocess, tempfile
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as f:
#         f.write(data); xml_file = f.name
#     out_file = xml_file + ".p7"
#     try:
#         subprocess.run([
#             "openssl", "cms", "-sign",
#             "-in",    xml_file,
#             "-signer", str(CERT_PATH),
#             "-inkey",  str(KEY_PATH),
#             "-outform", "DER",
#             "-out",   out_file,
#             "-nodetach",        # datos adjuntos (requerido por WSAA)
#             "-nocerts",         # omitir certs extra (opcional)
#         ], check=True, capture_output=True)
#         with open(out_file, "rb") as f:
#             return base64.b64encode(f.read()).decode("ascii")
#     finally:
#         os.unlink(xml_file)
#         if os.path.exists(out_file):
#             os.unlink(out_file)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        print("\n⛔  Excepción no manejada:")
        traceback.print_exc()
        sys.exit(1)
