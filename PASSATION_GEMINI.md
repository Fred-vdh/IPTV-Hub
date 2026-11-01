# Message de reprise — IPTV Hub (à transmettre à Gemini)

> Copie-colle intégralement ce message à Gemini pour reprendre le chantier avec tout le contexte.

---

## 0. Le projet

**IPTV Hub** — lecteur IPTV & VOD multiplateforme (Windows + Linux), écrit en **Python 3.10+**
avec **PyQt6** et un moteur de rendu vidéo **libmpv + OpenGL** (pas d'Electron).
Design inspiré d'IPTVnator. Version courante : **2.3.0** (`README.md`, tag `v2.3.0`).

Fonctionnalités : TV en direct (EPG), VOD films, séries (saisons/épisodes + suivi de visionnage),
gestionnaire de téléchargements hors-ligne, listes de chaînes personnalisées, synchronisation
QR/auto entre appareils, favoris/historique, **i18n complet FR/EN/ES/DE**, mode **Multiview**
(jusqu'à 4 écrans).

Structure principale :
- `main.py` : point d'entrée, garde anti-crash.
- `core/` : `database.py` (SQLite), `player_controller.py` (libmpv), `mpv_render.py`,
  `image_loader.py`, `i18n.py`, `qt_worker_utils.py`, `native_crash_log.py`, `auto_sync_manager.py`,
  `download_manager.py`, `xtream_client.py`, `tmdb_client.py`, `models.py`.
- `ui/` : `main_window.py`, `widgets/*` (vues), `dialogs/*`, `icons.py`.
- `tests/` : suite `unittest`/`pytest` (offscreen).
- `docs/screenshots/`, `assets/`, `build.spec` (PyInstaller).

---

## 1. Environnement de travail & commandes utiles

- OS : **Windows** (PowerShell). Shell non interactif.
- **Pas de venv** : tout tourne sur le **Python système (3.13)**, qui exécute aussi l'appli.
- `pytest 9.1.1`, `ruff 0.15.9` installés système.
- Tests GUI : **obligatoirement** `QT_QPA_PLATFORM=offscreen`.
- ⚠️ Comportements à connaître :
  - Lancer les tests **un fichier à la fois** : les runs pytest **groupés** renvoient `exit 1`
    à cause de **vidages de threads au teardown** (tmdb / mpv), ce ne sont **pas** de vrais échecs.
  - Dans un test GUI, garder une **référence module-level** au `QApplication`
    (`_APP = QApplication.instance() or QApplication(sys.argv)`), sinon il est GC-é →
    `QWidget: Must construct a QApplication before a QWidget` → `abort` (faux positif).
  - `deleteLater()` (DeferredDelete) n'est traité que par une **vraie boucle d'événements** :
    `processEvents()` seul ne le déclenche pas (piège récurrent).

Exemples :
```powershell
cd 'e:\prog-ia\IPTV'
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_series_resume_next_episode.py -q
python -m ruff check ui/widgets/series_details_view.py
pyinstaller build.spec --clean -y    # packaging
```

---

## 2. Chronologie des sessions (ce qui a déjà été fait)

Tout est aussi consigné dans **`PASSATION_FIX_CRASH_OSD_SERIE.md`** (à la racine, sections §1 à §11).

### Session A — Crash au retour OSD pendant la lecture d'un épisode de série (§1–§7)
- **Symptôme** : clic « Retour » de l'OSD en lisant un épisode → app disparaît sans trace,
  exit `0xc0000409` (fast-fail, pile dans `Qt6Core.dll`).
- **Cause** : la fiche série gardait une **référence Python à un `SeriesInfoWorker` (QThread)
  déjà détruit côté C++** par `deleteLater()`. Au retour, `self._worker.isRunning()` levait
  `RuntimeError: wrapped C/C++ object ... has been deleted`, et **PyQt convertit toute exception
  non gérée dans un slot en `qFatal()` → `abort()`** → crash natif muet.
- **Correctif** : nouveau module **`core/qt_worker_utils.py`** :
  `is_worker_alive`, `is_worker_running`, `track_worker`, `forget_worker`, `stop_worker`,
  `stop_tracked_worker`. Point clé : `track_worker` se connecte au **signal natif**
  `QThread.finished.__get__(worker, QThread)` (et non `worker.finished`, souvent redéfini avec une
  signature métier). Durcissement de tous les `.isRunning()/.wait()` non protégés dans
  `series_details_view.py`, `movie_details_view.py`, `dashboard_view.py`, `main_window.py`,
  `replay_view.py`, `vod_grid.py`, `artist_filmography_dialog.py`, `manage_playlists_dialog.py`,
  `movie_details_dialog.py`, `auto_sync_manager.py`.
- **Filet anti-crash muet** : `main.py::_install_crash_guard()` → `sys.excepthook` +
  `threading.excepthook` écrivent dans **`%APPDATA%\IPTV_Hub\iptv_errors.log`**.
- **Tests** : nouveau `tests/test_worker_lifecycle.py` (7). Packaging OK, log vide au démarrage.

### Session B — Cause RÉELLE du crash natif (avance rapide OSD / épisode suivant) (§8)
- **Constat** : crashs `0xc0000005` dans `python313.dll` à des offsets tombant dans
  **`Python/traceback.c`** (code d'affichage des traces CPython), sur une fenêtre de ~24 octets →
  **même instruction**, cause indépendante du fix de marshalling.
- **Cause** : `faulthandler.enable(all_threads=True)` sur Windows vidait les piles à **chaque**
  exception SEH ; or **libmpv lève en permanence une SEH interne bénigne** (`0xE24C4A02`) pendant
  `mpv_wait_event` / `mpv_get_property` → vidages massifs → journal entremêlé → AV dans le code de
  trace.
- **Correctif** :
  - **`core/native_crash_log.py` (nouveau)** : VEH minimaliste, **1 ligne** par exception
    (heure, thread, code, nom, adresse + module/décalage), **jamais** de parcours des trames Python
    sauf code mortel (AV, heap, stack overflow, fast-fail). `faulthandler.enable()` **proscrit sur
    Windows** (gardé sur POSIX).
  - **`main.py`** : installe ce journal à la place de `faulthandler.enable()`.
  - **`core/player_controller.py`** : plus **aucun appel Qt depuis le thread libmpv** —
    `threading.get_ident()` (au lieu de `QThread.currentThread()`), et file `collections.deque` +
    verrou vidée par un `QTimer` du thread Qt (au lieu d'un `pyqtSignal(object)` inter-threads).
  - **`ui/widgets/gl_video_surface.py`** : le callback `mpv_render_update` lève un simple drapeau
    Python ; c'est le timer de repeint (thread GUI) qui redessine.
  - **`core/mpv_render.py`** : le thunk ctypes reste **vivant** pendant `mpv_render_context_free()`.
  - Tests : `tests/test_native_crash_log.py` (13) + `tests/test_player_observer_thread_marshal.py`
    étendu (8) verts. Build OK.

### Session C — Multiview : sortie fiable + sélecteur de chaîne (§9)
- **Symptômes** : « Quitter Multiview » mort, écrans résiduels après départ de la TV en direct,
  sélecteur de chaîne vide (méthodes DB inexistantes avalées par `except Exception`).
- **Correctifs** : `ui/widgets/multiview_widget.py` (émission `exit_requested` en **premier** puis
  `deactivate(staggered=True)` ; libération en 2 phases `suspend()` / `destroy_player()` étalée par
  la boucle d'événements ; `set_layout_mode()` ferme les écrans masqués avant de les cacher ;
  robustesse par étapes protégées), `ui/main_window.py` (`_leave_multiview()` complet appelé depuis
  toutes les navigations), `ui/dialogs/channel_picker_dialog.py` (**réécrit**, 2 colonnes sources →
  chaînes, ordre « Toutes → Listes personnalisées → CATÉGORIES », accès DB corrigés avec cache).
- Tests : `tests/test_channel_picker_scopes.py` (7), `tests/test_multiview_exit_integration.py`,
  `tests/test_multiview.py` étendu.

### Session D — Bandeau OSD par écran Multiview (§10)
- Chaque écran Multiview reçoit un bandeau OSD **identique au lecteur solo** (nom, programme EPG,
  badge DIRECT/SÉRIE/REPLAY/FILM, icônes crayon/corbeille), transmis via
  `MultiViewWidget(epg_provider=lambda tvg_id: self.db.get_current_program(tvg_id))`.
- `core/i18n.py` : nouvelle clé « Supprimer la chaîne de cet écran » (fr/en/es/de).
- Tests : `tests/test_multiview.py` (+9 → 18 verts), contrôles visuels par `QWidget.grab()`.

### Session E — Vignettes d'épisodes manquantes dans une fiche série (§11, 06/10/2026)
- **Symptôme** : vignettes de « Lanterns » restant sur l'image par défaut.
- **Cause** : l'API Xtream renvoie **deux domaines d'images** ; l'un (souvent port 8080) est **mort
  (HTTP 404)**, l'autre sert **le même fichier** (HTTP 200). En plus, `ImageLoader` sur échec
  supprimait l'abonné et n'émettait que `image_failed` — la carte d'épisode n'écoutait rien, donc la
  **chaîne de repli n'était jamais tentée**.
- **Correctif** : `core/image_loader.py` (`on_failed` callback + `_report_failure`, et
  `ImageLoader.alternate_host_urls(url, known_urls, limit=2)` qui bascule de domaine) ;
  `ui/widgets/series_details_view.py` (`EpisodeCardWidget` chaîne de candidats vignette → backdrop →
  affiche saison → affiche série, bascule de domaine à chaque échec, plafond `_max_attempts = 12` ;
  `_collect_known_image_urls()` ; backdrop idem).
- Tests : `tests/test_episode_thumb_fallback.py` (22). Test live : 8/8 vignettes « Lanterns ».

### Session F (la plus récente) — Bouton « Lecture » d'une série repart trop loin/devant
- **Symptôme rapporté** : après avoir remarqué des épisodes comme « non lu » pour revenir en arrière,
  le bouton **« Lecture »** ressortait le **dernier épisode vu/entamé** au lieu de **l'épisode non
  lu le plus en arrière**.
- **Cause racine** : `SeriesDetailsView._get_resume_or_next_episode()` ancrait la cible sur le
  **dernier épisode ayant eu une activité**, puis cherchait le prochain non lu **après** lui. Si un
  épisode plus loin restait partiel (« actif »), il était repris, en ignorant les épisodes antérieurs
  qu'on venait de remettre en « non lu ».
- **Correctif** (`ui/widgets/series_details_view.py`, ~lignes 2197-2236) : cible = **premier épisode
  non terminé dans l'ordre de la série** :
  - premier non vu de la série à ratio `0 < r < 0.90` → `"resume"` ;
  - s'il est en index 0 → `"start"` ;
  - sinon → `"continue"` ;
  - tous vus → `"restart"` (premier épisode).
- **Tests ajoutés** dans `tests/test_series_resume_next_episode.py` :
  `test_marking_episodes_unwatched_moves_resume_back` et
  `test_reset_episodes_while_last_still_partially_watched` (ce dernier couvre exactement le cas du
  bug : dernier épisode encore partiel). Résultat : **12/12 verts**. `ruff` : **All checks passed**.

---

## 3. Règles de codage à perpétuer (importantes)

1. **Cycle de vie des `QThread`** : tout worker stocké sur un widget passe par `track_worker(...)` ;
   tout accès ultérieur par `is_worker_running(...)` / `stop_tracked_worker(...)`.
   **Ne jamais** appeler directement `.isRunning()`, `.wait()`, `.requestInterruption()` sur un
   worker dont le cycle de vie n'est pas garanti (risque de `qFatal`/`abort` sous Windows).
2. **Jamais d'appel Qt depuis le thread libmpv** : communiquer via drapeaux Python + `QTimer` du
   thread GUI (modèle en place dans `player_controller.py` / `gl_video_surface.py`).
3. **Pas de `faulthandler.enable()` sur Windows** : utiliser `core/native_crash_log.py`.
4. **Diagnostic d'un crash** : lire les premières lignes de `%APPDATA%\IPTV_Hub\iptv_errors.log`
   (elles nomment le module fautif et son décalage).
5. Traduire toute chaîne UI via `core/i18n.tr()` et **ajouter la clé dans les 4 langues**.

---

## 4. Échecs de tests **pré-existants** (ne PAS croire à une régression)

Ces anomalies existaient **avant** les corrections ci-dessus et n'ont **aucun rapport** (prouvé par
A/B avec `git worktree --detach`). Ne pas les « corriger » en les attribuant à un de ces fixes :
- `test_manage_playlists_dialog_title_and_badges` ;
- `test_refresh_playlist_no_screen_change` ;
- `test_vod_grid_async::test_poster_widget_disconnects_image_loader` ;
- **crash natif libmpv de `tests/test_series_video_integration.py`** (réseau réel TMDB/Xtream +
  lecture mpv réelle sans nettoyage du player → abort dans le thread mpv ; sort en `exit 3`).

---

## 5. État Git actuel

- `HEAD = 5e2dd4c` (`fix(downloads): isoler l'environnement de test et ignorer les entrées
  factices`), branche `main`, alignée `origin/main`.
- **Rien n'est encore committé** pour les Sessions A→F. Le working tree contient un mélange de
  **travail préexistant de l'utilisateur non commité** (i18n, icons, image_loader, multiview…,
  ~33 fichiers modifiés) **et** les correctifs de ces sessions. Ne pas attribuer tout le diff aux
  fixes ci-dessus.
- Fichiers **nouveaux** clés : `core/qt_worker_utils.py`, `core/native_crash_log.py`,
  `ui/dialogs/channel_picker_dialog.py`, `ui/widgets/multiview_widget.py`,
  `tests/test_worker_lifecycle.py`, `tests/test_episode_thumb_fallback.py`,
  `tests/test_native_crash_log.py`, `tests/test_channel_picker_scopes.py`,
  `tests/test_multiview.py`, `tests/test_multiview_exit_integration.py`,
  `tests/test_player_observer_thread_marshal.py`, `tests/test_icons_pixmap_cache.py`,
  `tests/test_playlist_card_connections.py`, `tests/test_render_context_teardown.py`.
- Fichiers **nouveaux** de doc/technique : `PASSATION_FIX_CRASH_OSD_SERIE.md`, `PASSATION_GEMINI.md`
  (ce message).

---

## 6. Pistes restantes / TODO (optionnel)

1. **Committer** proprement les Sessions A→F (le working tree est très volumineux et non commité).
2. **Fiabiliser** `tests/test_series_video_integration.py` en **mockant** `XtreamClient.get_series_info`,
   `core.tmdb_client.find_best_trailer` et en **fermant proprement le `PlayerController`**
   (modèle : `TestReturnFromOsdIntegration` dans `tests/test_worker_lifecycle.py`).
3. Mettre à jour `PASSATION_FIX_CRASH_OSD_SERIE.md` avec la **Session F** (correctif bouton Lecture).
4. Vérifier le comportement manuel de la Session F (voir §7) puis, si validé, packager une release.

---

## 7. Vérifications manuelles à faire côté utilisateur (Session F)

1. Regarder une série jusqu'à p. ex. S01E06 (arrêter l'épisode en plein milieu).
2. Décocher (« non lu ») S01E03 → S01E06.
3. Cliquer **« Lecture »** : le bouton doit afficher **« Reprendre : S01E03 … »** et lancer cet
   épisode (et non relancer S01E06).

---

**Résumé pour Gemini en une phrase** : IPTV Hub (Python/PyQt6/libmpv, v2.3.0, Windows) — on vient
de corriger le bouton « Lecture » d'une fiche série pour qu'il reparte de l'**épisode non lu le plus
en arrière** (`SeriesDetailsView._get_resume_or_next_episode`, 12/12 tests verts) ; le working tree
porte en plus un gros lot de correctifs non commités (crash OSD/natif, Multiview, vignettes) ;
reste à committer, fiabiliser le test de crash mpv pré-existant et documenter Session F.
