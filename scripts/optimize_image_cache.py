"""
Script d'optimisation et de compactage du cache d'images existant pour IPTV Hub.
Parcourt les images enregistrées dans %APPDATA%/IPTV_Hub/cache/logos,
redimensionne les affiches trop grandes et les compresse intelligemment en multithreading.
"""

import os
import sys
import io
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

# Désactiver la limite de pixels pour éviter les avertissements DecompressionBombError sur les très grandes images
Image.MAX_IMAGE_PIXELS = None


def get_cache_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata and sys.platform == "win32":
        return Path(appdata) / "IPTV_Hub" / "cache" / "logos"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "IPTV_Hub" / "logos"
    return Path.home() / ".cache" / "IPTV_Hub" / "logos"


def has_real_transparency(img: Image.Image) -> bool:
    """Vérifie si l'image possède réellement des pixels translucides ou transparents."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        try:
            alpha = img.convert("RGBA").split()[-1]
            min_alpha, _ = alpha.getextrema()
            return min_alpha < 250
        except Exception:
            return True
    return False


def optimize_single_image(file_path: Path) -> tuple[int, int, bool]:
    """
    Optimise un fichier image sur disque.
    Retourne (taille_initiale, taille_finale, a_ete_modifie).
    """
    try:
        initial_size = file_path.stat().st_size
        if initial_size == 0:
            return (0, 0, False)

        with Image.open(file_path) as img:
            img.load()
            w, h = img.size
            if w <= 0 or h <= 0:
                return (initial_size, initial_size, False)

            is_alpha = has_real_transparency(img)

            # Calcul des dimensions cibles
            if is_alpha:
                max_w, max_h = 320, 320
            elif w > h:
                # Paysage (backdrop, fanart, bannière) : max 1920x1080
                max_w, max_h = 1920, 1080
            else:
                # Portrait (affiche de film, série) : max 400x600
                max_w, max_h = 400, 600

            needs_resize = (w > max_w or h > max_h)

            # Si l'image est déjà sous les cotes et déjà en JPEG léger, pas besoin de réencoder
            if not needs_resize and img.format == "JPEG" and initial_size < 100 * 1024:
                return (initial_size, initial_size, False)

            target_img = img
            if needs_resize:
                ratio = min(max_w / w, max_h / h)
                new_w = max(1, int(w * ratio))
                new_h = max(1, int(h * ratio))
                target_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            if is_alpha:
                # Conserver le format PNG avec transparence
                target_img.save(buf, format="PNG", optimize=True)
            else:
                # Convertir en JPEG qualité 85%
                rgb_img = target_img.convert("RGB")
                rgb_img.save(buf, format="JPEG", quality=85, optimize=True)

            compressed_bytes = buf.getvalue()
            new_size = len(compressed_bytes)

            # On ne remplace que si la taille est effectivement réduite
            if new_size < initial_size:
                file_path.write_bytes(compressed_bytes)
                return (initial_size, new_size, True)
            else:
                return (initial_size, initial_size, False)

    except Exception:
        # En cas d'erreur de lecture/écriture, laisser le fichier inchangé
        try:
            sz = file_path.stat().st_size
            return (sz, sz, False)
        except Exception:
            return (0, 0, False)


def main():
    cache_dir = get_cache_dir()
    if not cache_dir.exists():
        print(f"Dossier de cache introuvable : {cache_dir}")
        return

    files = [f for f in cache_dir.iterdir() if f.is_file()]
    total_files = len(files)
    if total_files == 0:
        print("Aucune image en cache à optimiser.")
        return

    print(f"Début de l'optimisation de {total_files} images dans {cache_dir}...")
    start_time = time.time()

    workers = min(16, max(4, os.cpu_count() or 4))
    print(f"Utilisation de {workers} threads de travail parallèles.")

    total_orig = 0
    total_new = 0
    modified_count = 0
    processed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(optimize_single_image, f): f for f in files}
        for future in as_completed(futures):
            orig_sz, new_sz, modified = future.result()
            total_orig += orig_sz
            total_new += new_sz
            if modified:
                modified_count += 1
            processed += 1
            if processed % 1000 == 0 or processed == total_files:
                pct = (processed / total_files) * 100
                saved_mb = (total_orig - total_new) / (1024 * 1024)
                print(f"Progression : {processed}/{total_files} ({pct:.1f}%) — Espace libéré jusqu'ici : {saved_mb:.1f} Mo")

    elapsed = time.time() - start_time
    orig_mb = total_orig / (1024 * 1024)
    new_mb = total_new / (1024 * 1024)
    saved_mb = orig_mb - new_mb
    pct_saved = (saved_mb / orig_mb * 100) if orig_mb > 0 else 0

    print("\n" + "=" * 60)
    print("RÉSULTAT DE L'OPTIMISATION DU CACHE D'IMAGES")
    print("=" * 60)
    print(f"Images traitées           : {total_files}")
    print(f"Images recompressées      : {modified_count}")
    print(f"Taille initiale du cache  : {orig_mb:.2f} Mo ({orig_mb / 1024:.2f} Go)")
    print(f"Nouvelle taille du cache  : {new_mb:.2f} Mo ({new_mb / 1024:.2f} Go)")
    print(f"Espace disque économisé   : {saved_mb:.2f} Mo ({saved_mb / 1024:.2f} Go)")
    print(f"Taux de réduction globale : {pct_saved:.1f} %")
    print(f"Temps de traitement       : {elapsed:.1f} secondes")
    print("=" * 60)


if __name__ == "__main__":
    main()
