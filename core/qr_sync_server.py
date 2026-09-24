"""
Passerelle de synchronisation locale par QR Code pour IPTV Hub.
Fournit un mini-serveur HTTP éphémère et sécurisé permettant d'exporter
et d'importer les données utilisateur via un smartphone sans passer par Internet.
"""

import io
import json
import socket
import logging
import platform
import secrets
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import List, Optional, Tuple, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap
import qrcode

from core.database import Database
from core.sync_manager import export_sync_data, merge_sync_data

logger = logging.getLogger(__name__)


def get_local_ip_addresses() -> List[str]:
    """
    Détecte les adresses IPv4 locales de la machine.
    Place en première position l'adresse IP active connectée à la passerelle par défaut.
    Exclut le loopback (127.*) et les adresses APIPA (169.254.*).
    """
    ips: List[str] = []

    # 1. Sonde UDP vers une IP externe (ne transmet aucun paquet sur le réseau)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        if primary_ip and not primary_ip.startswith("127.") and not primary_ip.startswith("169.254."):
            ips.append(primary_ip)
    except Exception:
        pass

    # 2. Énumération des interfaces de l'hôte
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip not in ips and not ip.startswith("127.") and not ip.startswith("169.254."):
                ips.append(ip)
    except Exception:
        pass

    return ips or ["127.0.0.1"]


def generate_qr_pixmap(url: str, size: int = 240, fg_color: str = "#ffffff", bg_color: str = "#182030") -> QPixmap:
    """Génère un QPixmap haute résolution pour l'URL spécifiée."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    pil_img = qr.make_image(fill_color=fg_color, back_color=bg_color).convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)

    qimg = QImage()
    qimg.loadFromData(buf.getvalue())
    pixmap = QPixmap.fromImage(qimg)

    if size > 0:
        return pixmap.scaled(size, size)
    return pixmap


MOBILE_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "fr": {
        "title": "Passerelle de synchronisation",
        "device_prefix": "Appareil :",
        "subtitle": "Transférez vos listes, favoris et progression de lecture entre vos appareils.",
        "save_card_title": "Sauvegarder cet appareil",
        "save_card_desc": "Télécharge un fichier .json complet sur ce téléphone (listes, favoris, progression, etc.) pour le transférer plus tard.",
        "btn_download": "Télécharger le fichier de sauvegarde",
        "sync_card_title": "Synchroniser cet appareil",
        "sync_card_desc": "Injecte un fichier de sauvegarde présent sur ce téléphone pour fusionner vos données vers cet appareil.",
        "dropzone_title": "📄 Sélectionner un fichier .json",
        "dropzone_hint": "Touchez ici pour choisir le fichier",
        "prev_origin": "Origine :",
        "prev_date": "Date :",
        "prev_playlists": "Playlists :",
        "prev_favorites": "Favoris :",
        "prev_last_watched": "Dernière reprise :",
        "data_to_sync": "Données à synchroniser",
        "chk_playlists": "Playlists & identifiants",
        "chk_progress": "Progression & historique de lecture",
        "chk_favorites": "Favoris & chaînes masquées",
        "chk_settings": "Préférences & paramètres",
        "btn_upload": "Envoyer vers cet appareil",
        "syncing": "Synchronisation en cours...",
        "success_btn": "Envoyé avec succès !",
        "retry_btn": "Réessayer",
        "footer": "IPTV Hub • Connexion réseau locale sécurisée",
        "unknown_date": "Date inconnue",
        "no_resume": "Aucune reprise",
        "err_invalid_file": "Erreur : Le fichier sélectionné n'est pas un fichier de sauvegarde valide.",
        "err_network": "Erreur de communication réseau :",
        "success_alert": "✅ Synchronisation réussie ! Les données ont été fusionnées sur l'appareil.",
    },
    "en": {
        "title": "Sync Gateway",
        "device_prefix": "Device:",
        "subtitle": "Transfer your playlists, favorites and playback progress between your devices.",
        "save_card_title": "Backup this device",
        "save_card_desc": "Downloads a full .json backup file to this phone (playlists, favorites, progress, etc.) to transfer later.",
        "btn_download": "Download backup file",
        "sync_card_title": "Sync this device",
        "sync_card_desc": "Uploads a backup file from this phone to merge your data onto this device.",
        "dropzone_title": "📄 Select a .json file",
        "dropzone_hint": "Tap here to choose a file",
        "prev_origin": "Origin:",
        "prev_date": "Date:",
        "prev_playlists": "Playlists:",
        "prev_favorites": "Favorites:",
        "prev_last_watched": "Last watched:",
        "data_to_sync": "Data to synchronize",
        "chk_playlists": "Playlists & credentials",
        "chk_progress": "Playback progress & history",
        "chk_favorites": "Favorites & hidden channels",
        "chk_settings": "Preferences & settings",
        "btn_upload": "Send to this device",
        "syncing": "Syncing in progress...",
        "success_btn": "Sent successfully!",
        "retry_btn": "Retry",
        "footer": "IPTV Hub • Secure local network connection",
        "unknown_date": "Unknown date",
        "no_resume": "No resume",
        "err_invalid_file": "Error: The selected file is not a valid backup file.",
        "err_network": "Network communication error:",
        "success_alert": "✅ Sync successful! Data merged onto this device.",
    },
    "es": {
        "title": "Pasarela de sincronización",
        "device_prefix": "Dispositivo:",
        "subtitle": "Transfiera sus listas, favoritos y progreso de reproducción entre sus dispositivos.",
        "save_card_title": "Guardar este dispositivo",
        "save_card_desc": "Descarga un archivo .json completo en este teléfono (listas, favoritos, progreso, etc.) para transferirlo más tarde.",
        "btn_download": "Descargar archivo de copia de seguridad",
        "sync_card_title": "Sincronizar este dispositivo",
        "sync_card_desc": "Sube un archivo de copia de seguridad desde este teléfono para combinar datos en este dispositivo.",
        "dropzone_title": "📄 Seleccionar un archivo .json",
        "dropzone_hint": "Toque aquí para elegir el archivo",
        "prev_origin": "Origen:",
        "prev_date": "Fecha:",
        "prev_playlists": "Listas:",
        "prev_favorites": "Favoritos:",
        "prev_last_watched": "Última reproducción:",
        "data_to_sync": "Datos para sincronizar",
        "chk_playlists": "Listas e identificadores",
        "chk_progress": "Progreso e historial de reproducción",
        "chk_favorites": "Favoritos y canales ocultos",
        "chk_settings": "Preferencias y ajustes",
        "btn_upload": "Enviar a este dispositivo",
        "syncing": "Sincronización en curso...",
        "success_btn": "¡Enviado con éxito!",
        "retry_btn": "Reintentar",
        "footer": "IPTV Hub • Conexión de red local segura",
        "unknown_date": "Fecha desconocida",
        "no_resume": "Sin reanudación",
        "err_invalid_file": "Error: El archivo seleccionado no es válido.",
        "err_network": "Error de comunicación de red:",
        "success_alert": "✅ ¡Sincronización exitosa! Datos combinados en este dispositivo.",
    },
    "de": {
        "title": "Sync-Gateway",
        "device_prefix": "Gerät:",
        "subtitle": "Übertragen Sie Wiedergabelisten, Favoriten und Wiedergabefortschritt zwischen Ihren Geräten.",
        "save_card_title": "Dieses Gerät sichern",
        "save_card_desc": "Lädt eine vollständige .json-Sicherungsdatei auf dieses Telefon herunter, um sie später zu übertragen.",
        "btn_download": "Sicherungsdatei herunterladen",
        "sync_card_title": "Dieses Gerät synchronisieren",
        "sync_card_desc": "Überträgt eine Sicherungsdatei von diesem Telefon, um Daten auf diesem Gerät zusammenzuführen.",
        "dropzone_title": "📄 Eine .json-Datei auswählen",
        "dropzone_hint": "Tippen Sie hier, um eine Datei auszuwählen",
        "prev_origin": "Herkunft:",
        "prev_date": "Datum:",
        "prev_playlists": "Wiedergabelisten:",
        "prev_favorites": "Favoriten:",
        "prev_last_watched": "Zuletzt gesehen:",
        "data_to_sync": "Zu synchronisierende Daten",
        "chk_playlists": "Wiedergabelisten & Zugangsdaten",
        "chk_progress": "Wiedergabefortschritt & Verlauf",
        "chk_favorites": "Favoriten & ausgeblendete Kanäle",
        "chk_settings": "Einstellungen & Optionen",
        "btn_upload": "An dieses Gerät senden",
        "syncing": "Synchronisierung läuft...",
        "success_btn": "Erfolgreich gesendet!",
        "retry_btn": "Wiederholen",
        "footer": "IPTV Hub • Sichere lokale Netzwerkverbindung",
        "unknown_date": "Unbekanntes Datum",
        "no_resume": "Keine Fortsetzung",
        "err_invalid_file": "Fehler: Die ausgewählte Datei ist keine gültige Sicherungsdatei.",
        "err_network": "Netzwerkkommunikationsfehler:",
        "success_alert": "✅ Synchronisierung erfolgreich! Daten auf diesem Gerät zusammengeführt.",
    }
}


def get_mobile_html(device_name: str, token: str, lang: str = "fr") -> str:
    """Génère la page web mobile responsive embarquée traduite (sans dépendance externe)."""
    t = MOBILE_TRANSLATIONS.get(lang, MOBILE_TRANSLATIONS["fr"])

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>IPTV Hub — {t['title']}</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: #151d30;
      --card-border: #24304c;
      --primary: #4f46e5;
      --primary-hover: #4338ca;
      --success: #10b981;
      --success-dark: #065f46;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --radius: 14px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    body {{
      background: var(--bg);
      color: var(--text);
      padding: 20px 16px 40px;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
    }}
    .container {{ width: 100%; max-width: 480px; }}
    .header {{
      text-align: center;
      margin-bottom: 24px;
    }}
    .logo-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: #1e293b;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 13px;
      color: #cbd5e1;
      margin-bottom: 12px;
      border: 1px solid #334155;
    }}
    .device-indicator {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
    }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 6px; letter-spacing: -0.3px; }}
    p.subtitle {{ font-size: 14px; color: var(--text-muted); line-height: 1.4; }}

    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 20px;
      margin-bottom: 20px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }}
    .card-title {{
      font-size: 17px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
    }}
    .card-title .icon {{ font-size: 20px; }}
    .card-desc {{ font-size: 13px; color: var(--text-muted); margin-bottom: 16px; line-height: 1.4; }}

    .btn {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      padding: 14px;
      border-radius: 10px;
      border: none;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
    }}
    .btn-download {{
      background: linear-gradient(135deg, #4f46e5, #3b82f6);
      color: white;
    }}
    .btn-download:active {{ opacity: 0.85; transform: scale(0.98); }}

    .btn-upload {{
      background: linear-gradient(135deg, #10b981, #059669);
      color: white;
      margin-top: 14px;
    }}
    .btn-upload:active {{ opacity: 0.85; transform: scale(0.98); }}
    .btn:disabled {{ opacity: 0.45; cursor: not-allowed; transform: none; }}

    .file-dropzone {{
      border: 2px dashed #334155;
      border-radius: 10px;
      padding: 18px 12px;
      text-align: center;
      cursor: pointer;
      background: rgba(15, 23, 42, 0.4);
      transition: border-color 0.2s;
    }}
    .file-dropzone:hover {{ border-color: #6366f1; }}
    .file-dropzone span {{ font-size: 13px; color: #94a3b8; display: block; margin-top: 4px; }}
    input[type="file"] {{ display: none; }}

    .preview-box {{
      display: none;
      margin-top: 14px;
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 12px;
      font-size: 13px;
    }}
    .preview-row {{
      display: flex;
      justify-content: space-between;
      padding: 4px 0;
      border-bottom: 1px solid #1e293b;
    }}
    .preview-row:last-child {{ border-bottom: none; }}
    .preview-label {{ color: var(--text-muted); }}
    .preview-val {{ font-weight: 600; color: #e2e8f0; }}

    .options-group {{
      margin-top: 14px;
      background: #0f172a;
      border-radius: 8px;
      padding: 10px 12px;
    }}
    .options-title {{ font-size: 12px; color: var(--text-muted); font-weight: 600; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
    .option-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 5px 0;
      font-size: 13px;
    }}
    .option-item input[type="checkbox"] {{
      width: 17px;
      height: 17px;
      accent-color: #4f46e5;
      cursor: pointer;
    }}

    .alert {{
      display: none;
      margin-top: 14px;
      padding: 12px 14px;
      border-radius: 8px;
      font-size: 13px;
      line-height: 1.4;
    }}
    .alert-success {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid var(--success);
      color: #6ee7b7;
    }}
    .alert-error {{
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid #ef4444;
      color: #fca5a5;
    }}

    .footer {{
      text-align: center;
      font-size: 12px;
      color: #64748b;
      margin-top: 10px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo-badge">
        <div class="device-indicator"></div>
        <span>{t['device_prefix']} <strong>{device_name}</strong></span>
      </div>
      <h1>{t['title']}</h1>
      <p class="subtitle">{t['subtitle']}</p>
    </div>

    <!-- 1. EXPORTATION -->
    <div class="card">
      <div class="card-title">
        <span class="icon">📥</span>
        <span>{t['save_card_title']}</span>
      </div>
      <p class="card-desc">
        {t['save_card_desc']}
      </p>
      <a href="/api/export?token={token}" id="btnDownload" class="btn btn-download">
        {t['btn_download']}
      </a>
    </div>

    <!-- 2. IMPORTATION -->
    <div class="card">
      <div class="card-title">
        <span class="icon">🚀</span>
        <span>{t['sync_card_title']}</span>
      </div>
      <p class="card-desc">
        {t['sync_card_desc']}
      </p>

      <div class="file-dropzone" onclick="document.getElementById('fileInput').click()">
        <strong>{t['dropzone_title']}</strong>
        <span id="fileNameLabel">{t['dropzone_hint']}</span>
      </div>
      <input type="file" id="fileInput" accept=".json,application/json">

      <!-- Résumé dynamique du fichier -->
      <div class="preview-box" id="previewBox">
        <div class="preview-row">
          <span class="preview-label">{t['prev_origin']}</span>
          <span class="preview-val" id="prevDevice">-</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">{t['prev_date']}</span>
          <span class="preview-val" id="prevDate">-</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">{t['prev_playlists']}</span>
          <span class="preview-val" id="prevPlaylists">-</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">{t['prev_favorites']}</span>
          <span class="preview-val" id="prevFavs">-</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">{t['prev_last_watched']}</span>
          <span class="preview-val" id="prevLastWatched">-</span>
        </div>
      </div>

      <!-- Options sélectives -->
      <div class="options-group" id="optionsGroup" style="display: none;">
        <div class="options-title">{t['data_to_sync']}</div>
        <label class="option-item">
          <input type="checkbox" id="chkPlaylists" checked> {t['chk_playlists']}
        </label>
        <label class="option-item">
          <input type="checkbox" id="chkProgress" checked> {t['chk_progress']}
        </label>
        <label class="option-item">
          <input type="checkbox" id="chkFavorites" checked> {t['chk_favorites']}
        </label>
        <label class="option-item">
          <input type="checkbox" id="chkSettings" checked> {t['chk_settings']}
        </label>
      </div>

      <button id="btnUpload" class="btn btn-upload" disabled>
        {t['btn_upload']}
      </button>

      <div id="statusAlert" class="alert"></div>
    </div>

    <div class="footer">
      {t['footer']}
    </div>
  </div>

  <script>
    let selectedPayload = null;
    const token = "{token}";
    const txtUnknownDate = "{t['unknown_date']}";
    const txtNoResume = "{t['no_resume']}";
    const txtErrInvalid = "{t['err_invalid_file']}";
    const txtErrNetwork = "{t['err_network']}";
    const txtSyncing = "{t['syncing']}";
    const txtSuccessBtn = "{t['success_btn']}";
    const txtRetryBtn = "{t['retry_btn']}";
    const txtSuccessAlert = "{t['success_alert']}";

    const fileInput = document.getElementById('fileInput');
    const fileNameLabel = document.getElementById('fileNameLabel');
    const previewBox = document.getElementById('previewBox');
    const optionsGroup = document.getElementById('optionsGroup');
    const btnUpload = document.getElementById('btnUpload');
    const statusAlert = document.getElementById('statusAlert');

    fileInput.addEventListener('change', function(e) {{
      const file = e.target.files[0];
      if (!file) return;

      fileNameLabel.textContent = file.name;
      const reader = new FileReader();

      reader.onload = function(evt) {{
        try {{
          const parsed = JSON.parse(evt.target.result);
          if (!parsed || (!parsed.playlists && !parsed.persistent_favorites && !parsed.playback_progress)) {{
            throw new Error(txtErrInvalid);
          }}
          selectedPayload = parsed;
          displayPreview(parsed);
          optionsGroup.style.display = 'block';
          btnUpload.disabled = false;
          hideAlert();
        }} catch(err) {{
          selectedPayload = null;
          previewBox.style.display = 'none';
          optionsGroup.style.display = 'none';
          btnUpload.disabled = true;
          showAlert(txtErrInvalid, false);
        }}
      }};
      reader.readAsText(file);
    }});

    function displayPreview(data) {{
      const meta = data.metadata || {{}};
      const device = meta.device_name || data.source_machine || "Inconnu";
      const rawDate = meta.exported_at || meta.synced_at || data.synced_at || "";
      let dateStr = txtUnknownDate;
      if (rawDate) {{
        try {{
          const d = new Date(rawDate);
          dateStr = d.toLocaleDateString() + " " + d.toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}});
        }} catch(e) {{
          dateStr = rawDate.substring(0, 16);
        }}
      }}

      const playlistsCount = (data.playlists || []).length;
      const favsCount = (data.persistent_favorites || []).length;

      let lastWatched = txtNoResume;
      const progressList = data.playback_progress || [];
      if (progressList.length > 0) {{
        const sorted = [...progressList].sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
        const top = sorted[0];
        if (top && top.channel_name) {{
          const mins = Math.floor((top.playback_position || 0) / 60);
          lastWatched = top.channel_name + " (" + mins + " min)";
        }}
      }}

      document.getElementById('prevDevice').textContent = device;
      document.getElementById('prevDate').textContent = dateStr;
      document.getElementById('prevPlaylists').textContent = playlistsCount;
      document.getElementById('prevFavs').textContent = favsCount;
      document.getElementById('prevLastWatched').textContent = lastWatched;
      previewBox.style.display = 'block';
    }}

    btnUpload.addEventListener('click', async function() {{
      if (!selectedPayload) return;

      btnUpload.disabled = true;
      btnUpload.textContent = txtSyncing;
      hideAlert();

      // Préparation du payload filtré selon les cases cochées
      const payloadToSend = JSON.parse(JSON.stringify(selectedPayload));
      if (!document.getElementById('chkPlaylists').checked) {{
        payloadToSend.playlists = [];
      }}
      if (!document.getElementById('chkProgress').checked) {{
        payloadToSend.playback_progress = [];
        payloadToSend.watch_history = [];
      }}
      if (!document.getElementById('chkFavorites').checked) {{
        payloadToSend.persistent_favorites = [];
        payloadToSend.persistent_disabled_channels = [];
        payloadToSend.persistent_disabled_groups = [];
        payloadToSend.custom_channel_lists = [];
      }}
      if (!document.getElementById('chkSettings').checked) {{
        payloadToSend.settings = {{}};
      }}

      try {{
        const resp = await fetch('/api/import?token=' + encodeURIComponent(token), {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payloadToSend)
        }});

        const res = await resp.json();
        if (res.success) {{
          showAlert("✅ " + (res.message || txtSuccessAlert), true);
          btnUpload.textContent = txtSuccessBtn;
        }} else {{
          showAlert("❌ " + (res.error || "Error"), false);
          btnUpload.disabled = false;
          btnUpload.textContent = txtRetryBtn;
        }}
      }} catch(e) {{
        showAlert("❌ " + txtErrNetwork + " " + e.message, false);
        btnUpload.disabled = false;
        btnUpload.textContent = txtRetryBtn;
      }}
    }});

    function showAlert(msg, isSuccess) {{
      statusAlert.textContent = msg;
      statusAlert.className = 'alert ' + (isSuccess ? 'alert-success' : 'alert-error');
      statusAlert.style.display = 'block';
    }}

    function hideAlert() {{
      statusAlert.style.display = 'none';
    }}
  </script>
</body>
</html>
"""


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Serveur HTTP multithreadé non-bloquant."""
    daemon_threads = True
    allow_reuse_address = True


class QRSyncHTTPHandler(BaseHTTPRequestHandler):
    """Gestionnaire de requêtes HTTP pour la passerelle de synchronisation."""

    def log_message(self, format, *args):
        logger.debug("QR Sync HTTP: %s", format % args)

    def _send_json_response(self, data: Dict[str, Any], status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store")
        self.end_headers()
        self.wfile.write(body)

    def _verify_token(self) -> bool:
        expected_token = getattr(self.server, "auth_token", "")
        path_parts = self.path.split("?", 1)
        query = path_parts[1] if len(path_parts) > 1 else ""
        params = {}
        for p in query.split("&"):
            if "=" in p:
                k, v = p.split("=", 1)
                params[k] = v

        req_token = params.get("token") or self.headers.get("X-Auth-Token")
        return bool(expected_token and req_token == expected_token)

    def do_GET(self):
        # 1. Vérification du token
        if not self._verify_token():
            self.send_response(403)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"403 Forbidden - Jeton invalide ou expire")
            return

        # Notification client connecté
        server_obj = getattr(self.server, "sync_server_instance", None)
        if server_obj:
            client_ip = self.client_address[0]
            server_obj.notify_client_connected(client_ip)

        path_parts = self.path.split("?", 1)
        path_only = path_parts[0]
        query = path_parts[1] if len(path_parts) > 1 else ""

        # Route : / (Page mobile)
        if path_only in ("/", "/index.html"):
            device_name = platform.node() or "Appareil IPTV"
            token = getattr(self.server, "auth_token", "")
            app_lang = getattr(self.server, "current_app_language", "fr")

            for part in query.split("&"):
                if part.startswith("lang="):
                    val = part.split("=")[1].lower()
                    if val in ("fr", "en", "es", "de"):
                        app_lang = val

            html_content = get_mobile_html(device_name, token, lang=app_lang).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_content)))
            self.send_header("Cache-Control", "no-cache, no-store")
            self.end_headers()
            self.wfile.write(html_content)
            return

        # Route : /api/export (Téléchargement du fichier)
        if path_only == "/api/export":
            db = getattr(self.server, "db", None)
            if not db:
                self._send_json_response({"error": "Base de donnees indisponible"}, 500)
                return

            payload = export_sync_data(db)
            now_str = datetime.now().strftime("%Y-%m-%d_%Hh%M")
            filename = f"iptv_sync_{now_str}.json"
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache, no-store")
            self.end_headers()
            self.wfile.write(body)

            if server_obj:
                server_obj.notify_export_completed()
            return

        # Route : /api/status
        if path_only == "/api/status":
            self._send_json_response({"status": "ready", "device": platform.node()})
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if not self._verify_token():
            self.send_response(403)
            self.end_headers()
            return

        path_only = self.path.split("?", 1)[0]

        # Route : /api/import
        if path_only == "/api/import":
            server_obj = getattr(self.server, "sync_server_instance", None)
            db = getattr(self.server, "db", None)
            if not db:
                self._send_json_response({"success": False, "error": "Base de données locale inaccessible"}, 500)
                return

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length <= 0 or content_length > 50 * 1024 * 1024:  # Limite 50 Mo
                    self._send_json_response({"success": False, "error": "Taille de charge utile invalide"}, 400)
                    return

                raw_body = self.rfile.read(content_length)
                payload = json.loads(raw_body.decode("utf-8"))

                # Fusion intelligente (Smart Merge / Union)
                stats = merge_sync_data(db, payload)

                from core.i18n import tr
                msg_parts = []
                if stats.get("playlists_synced", 0) > 0:
                    msg_parts.append(f"{stats['playlists_synced']} {tr('liste(s)')}")
                if stats.get("favorites_added", 0) > 0:
                    msg_parts.append(f"{stats['favorites_added']} {tr('favori(s)')}")
                if stats.get("custom_lists_added", 0) > 0 or stats.get("custom_list_items_added", 0) > 0:
                    msg_parts.append(f"{stats.get('custom_lists_added', 0)} {tr('liste(s) personnalisée(s)')}")
                if stats.get("progress_updated", 0) > 0:
                    msg_parts.append(f"{stats['progress_updated']} {tr('reprise(s)')}")

                summary_msg = ", ".join(msg_parts) if msg_parts else tr("Toutes les données sont déjà à jour.")

                self._send_json_response({
                    "success": True,
                    "message": summary_msg,
                    "stats": stats,
                })

                if server_obj:
                    server_obj.notify_import_completed(stats)

            except Exception as e:
                logger.error("Erreur lors de l'import par QR Sync: %s", e)
                self._send_json_response({"success": False, "error": str(e)}, 500)
            return

        self.send_response(404)
        self.end_headers()


class QRSyncServer(QObject):
    """
    Contrôleur Qt pour le serveur HTTP de synchronisation QR.
    Gère le cycle de vie du serveur, l'authentification et émet des signaux Qt pour l'UI.
    """
    server_started = pyqtSignal(str, int, str)  # ip, port, token
    client_connected = pyqtSignal(str)          # client_ip
    export_completed = pyqtSignal()
    import_completed = pyqtSignal(dict)         # stats
    server_stopped = pyqtSignal()
    server_error = pyqtSignal(str)

    def __init__(self, db: Database, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.db = db
        self.server: Optional[ThreadedHTTPServer] = None
        self.token: str = ""
        self.port: int = 8989
        self.current_ip: str = "127.0.0.1"
        self._server_thread = None

        from core.i18n import I18nManager
        self.current_app_language: str = I18nManager.instance().current_language

        # Temporisateur d'inactivité (10 minutes)
        self._inactivity_timer = QTimer(self)
        self._inactivity_timer.setSingleShot(True)
        self._inactivity_timer.setInterval(10 * 60 * 1000)  # 10 min
        self._inactivity_timer.timeout.connect(self.stop)

    def start(self, preferred_ip: Optional[str] = None, base_port: int = 8989) -> Tuple[bool, str]:
        """
        Démarre le serveur HTTP local éphémère sur un port libre.
        """
        if self.server:
            self.stop()

        all_ips = get_local_ip_addresses()
        self.current_ip = preferred_ip if (preferred_ip and preferred_ip in all_ips) else all_ips[0]
        self.token = secrets.token_hex(8)

        # Recherche d'un port disponible à partir de base_port
        server_started = False
        last_err = ""
        for port in range(base_port, base_port + 20):
            try:
                # Écoute sur 0.0.0.0 pour accepter les connexions du Wi-Fi local
                self.server = ThreadedHTTPServer(("0.0.0.0", port), QRSyncHTTPHandler)
                self.server.auth_token = self.token
                self.server.db = self.db
                self.server.sync_server_instance = self
                self.server.current_app_language = self.current_app_language
                self.port = port
                server_started = True
                break
            except OSError as e:
                last_err = str(e)
                continue

        if not server_started:
            err_msg = f"Impossible de démarrer le serveur local : {last_err}"
            logger.error(err_msg)
            self.server_error.emit(err_msg)
            return False, err_msg

        import threading
        self._server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._server_thread.start()

        self._inactivity_timer.start()
        logger.info("Passerelle QR Sync démarrée sur http://%s:%d/?token=%s", self.current_ip, self.port, self.token)
        self.server_started.emit(self.current_ip, self.port, self.token)
        return True, self.get_sync_url()

    def set_active_ip(self, ip: str):
        """Met à jour l'adresse IP active (pour régénérer l'URL/QR Code sans redémarrer)."""
        self.current_ip = ip

    def get_sync_url(self) -> str:
        """Retourne l'URL complète avec le jeton d'authentification et la langue."""
        return f"http://{self.current_ip}:{self.port}/?token={self.token}&lang={self.current_app_language}"

    def stop(self):
        """Arrête proprement le serveur HTTP et libère le port."""
        self._inactivity_timer.stop()
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as e:
                logger.debug("Erreur lors de la fermeture du serveur HTTP: %s", e)
            self.server = None

        self._server_thread = None
        self.server_stopped.emit()
        logger.info("Passerelle QR Sync arrêtée.")

    def notify_client_connected(self, client_ip: str):
        self.client_connected.emit(client_ip)

    def notify_export_completed(self):
        self.export_completed.emit()

    def notify_import_completed(self, stats: Dict[str, int]):
        self.import_completed.emit(stats)
