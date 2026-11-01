# Passation — Correctif du crash au retour OSD pendant la lecture d'un épisode de série

> Mémo destiné à la reprise du chantier (Gemini). État : **corrigé, validé et packagé**.

## 1. Symptôme

- Clic sur le bouton **Retour** de l'OSD pendant la lecture d'un épisode (ouverture depuis la fiche série).
- L'application disparaît instantanément, **sans traceback ni message** (console désactivée en production).
- Code de sortie Windows : **`0xc0000409`** (`STATUS_STACK_BUFFER_OVERRUN` / fast-fail), pile dans `Qt6Core.dll`.

## 2. Cause racine (démontrée)

1. La fiche série lance un `SeriesInfoWorker` (QThread) qu'elle garde dans `self._worker`.
2. Le worker terminé est détruit côté C++ par `deleteLater()`, mais la fiche conserve sa **référence Python** (wrapper mort).
3. Au clic sur Retour :
   `MainWindow._return_to_vod_grid` → `_stop_series_details_playback` → `SeriesDetailsView.detach_video_widget` → `stop_active_workers` → `self._worker.isRunning()`
4. `RuntimeError: wrapped C/C++ object of type SeriesInfoWorker has been deleted`.
5. **PyQt convertit toute exception Python non gérée dans un slot en `qFatal()` → `abort()`** → crash natif silencieux.

Deux enseignements à conserver :

- Sous Windows, `abort()` (donc `qFatal`) passe par `__fastfail` → **aucun handler** (WER, `faulthandler`, `procdump`, debugger) ne l'intercepte. Donc : **ne pas chercher la trace après coup, la prévenir en amont**.
- `deleteLater()` (DeferredDelete) **n'est traité que par une vraie boucle d'événements** : `processEvents()` seul ne le déclenche pas. Un test qui n'utilise que `processEvents()` ne reproduit donc **pas** ce bug (piège rencontré).

## 3. Solution implémentée

### a) Nouveau module `core/qt_worker_utils.py` (racine du correctif)

API publique :

| Fonction | Rôle |
|---|---|
| `is_worker_alive(worker)` | `True` si l'objet C++ existe encore (absorbe le `RuntimeError`) |
| `is_worker_running(worker)` | `True` si le thread tourne ; `False` si arrêté **ou détruit** |
| `track_worker(owner, attr_name, worker)` | Stocke la référence **et** branche la destruction : `forget_worker(...)` + `worker.deleteLater()` |
| `forget_worker(owner, attr_name, worker)` | Repasse `owner.<attr_name>` à `None` si elle pointe sur ce worker |
| `stop_worker(worker, timeout_ms=200)` | `requestInterruption()` + `wait()` sans jamais lever |
| `stop_tracked_worker(owner, attr_name, timeout_ms=200)` | Arrête puis purge la référence (sans jamais lever) |

Point technique **critique** : `track_worker` se connecte au **signal natif** via
`QThread.finished.__get__(worker, QThread)`, et **non** à `worker.finished`.
Plusieurs workers du projet **redéfinissent** `finished` avec une signature métier
(`pyqtSignal(dict)` par ex.) : `worker.finished` pointerait alors vers le signal
personnalisé et `deleteLater()` ne serait jamais appelé.

### b) Durcissement des appels non protégés (même pattern bug partout)

Remplacement de `x.isRunning()` / `x.wait()` / connexions `finished` par les helpers :

- `ui/widgets/series_details_view.py` (chemin exact du bug : `stop_active_workers`, `stop_workers`)
- `ui/widgets/movie_details_view.py`
- `ui/widgets/dashboard_view.py`
- `ui/main_window.py`
- `ui/widgets/replay_view.py`, `ui/widgets/vod_grid.py`
- `ui/dialogs/artist_filmography_dialog.py`, `ui/dialogs/manage_playlists_dialog.py`, `ui/dialogs/movie_details_dialog.py`
- `core/auto_sync_manager.py` (imports ajoutés)

### c) Filet anti-crash muet — `main.py`

`_install_crash_guard()` (appelée au démarrage, ligne ~108) :

- `sys.excepthook` personnalisé → écrit traceback complet dans **`%APPDATA%\IPTV_Hub\iptv_errors.log`** puis délègue à `sys.__excepthook__`.
- `threading.excepthook` idem pour les threads.
- `faulthandler.enable(file=..., all_threads=True)` pour les crashs natifs.

Objectif : **plus jamais de crash silencieux** ; tout futur plantage devient diagnosticable.

## 4. Tests / validation

- `tests/test_worker_lifecycle.py` (**nouveau**, 7 tests) :
  - helpers unitaires (worker détruit par `sip.delete()` → aucune levée),
  - purge de la référence après fin de thread,
  - `SeriesDetailsView.stop_active_workers()` / `stop_workers()` / `MovieDetailsView.stop_active_workers()` avec workers morts,
  - **test d'intégration du geste utilisateur** : `MainWindow` → `_open_series_details` → `_return_to_vod_grid`.
- Piège à conserver dans les tests : garder une **référence module-level** au `QApplication`
  (`_APP = QApplication.instance() or QApplication(sys.argv)`), sinon il est GC-é et
  tout `QWidget()` ultérieur déclenche `QWidget: Must construct a QApplication before a QWidget` → `abort` (faux positif).
- Résultats : `test_worker_lifecycle.py` **7/7**, `test_i18n.py` **14/14**, `test_category_sort_preferences.py` **2/2**, `py_compile` OK sur les 12 fichiers.
- Harnais de repro sur la **vraie base** (`%APPDATA%\IPTV_Hub\iptv.db`, série « Good Omens » id 4268549) avec vraie boucle d'événements : **« AUCUN CRASH DETECTE »**.
- `pytest 9.1.1` installé dans le Python système (`Python313`) — c'est lui qui exécute l'appli.

## 5. Packaging

- Rebuild effectué : `pyinstaller build.spec --clean -y` → **exit 0**.
- `dist\IPTV_Hub\IPTV_Hub.exe` régénéré ; `core.qt_worker_utils` bien présent dans `build\build\Analysis-00.toc`.
- Test de fumée : l'exe démarre, et `%APPDATA%\IPTV_Hub\iptv_errors.log` est créé puis reste **vide (0 octet)** → aucun crash au démarrage.

## 6. Points restants / points d'attention

1. **`tests/test_series_video_integration.py::test_main_window_series_navigation` crashe déjà AVANT ce correctif** (prouvé via `git worktree add --detach ... HEAD` → même `abort`, même pile `ssl`/`urllib`, exit 3).
   Cause : le test fait du **réseau réel (TMDB/Xtream)** et de la **lecture libmpv réelle** sans nettoyage du player → access violation / abort dans le thread mpv.
   → À rendre fiable en mockant `XtreamClient.get_series_info`, `core.tmdb_client.find_best_trailer` et en fermant le `PlayerController` (modèle : `TestReturnFromOsdIntegration` dans `tests/test_worker_lifecycle.py`). **Hors périmètre du fix OSD.**
2. Le working tree contient beaucoup de **travail préexistant non commité de l'utilisateur** (~29 fichiers : i18n, icons, image_loader, multiview…) ; ne pas attribuer tout le diff au fix du crash.
3. Rien n'est encore **commité** pour ce fix (`HEAD = 5e2dd4c`). Fichiers concernés : `core/qt_worker_utils.py` (nouveau), `tests/test_worker_lifecycle.py` (nouveau) + les 12 fichiers listés en §3b/3c.
4. Reproduire un crash à volonté : lancer l'appli, ouvrir une fiche série, lire un épisode, cliquer Retour OSD. Toute régression apparaîtra désormais dans `%APPDATA%\IPTV_Hub\iptv_errors.log`.
5. Le fichier de test `tests/test_worker_lifecycle.py` contient aussi un `_DummyWorker` (aucun réseau) : réutilisable pour tout nouveau test de cycle de vie.

## 7. Règle de codage à perpétuer

> Tout `QThread` stocké sur un widget doit passer par `track_worker(...)`, et tout accès
> ultérieur doit passer par `is_worker_running(...)` / `stop_tracked_worker(...)`.
> Ne jamais appeler directement `.isRunning()`, `.wait()`, `.requestInterruption()`
> sur un worker dont le cycle de vie n'est pas garanti.

---

## 8. Mise à jour du 05/10/2026 (20h10) — cause RÉELLE du crash natif : trouvée, reproduite et corrigée

### 8.1 Ce que le build de 19h41 n'avait pas corrigé

Après ce build, deux scénarios crashaient encore : **appuis répétés sur l'OSD « +10 s »** et
**clic OSD « épisode suivant »** (première image affichée puis crash).

### 8.2 Preuves (journal d'événements Windows `Application Error`)

| heure | build | module fautif | code | Fault offset |
|---|---|---|---|---|
| 19:33:18 | avant fix | python313.dll | 0xc0000005 | **0x2b62dc** |
| 19:34:28 | avant fix | python313.dll | 0xc0000005 | **0x2b62dc** |
| 19:47:30 | build 19:41 | python313.dll | 0xc0000005 | **0x2b62f3** |
| 19:48:32 | build 19:41 | python313.dll | 0xc0000005 | **0x2b62ef** |

Quatre fautes dans une fenêtre de **24 octets** : la **même instruction**, avant comme après le
correctif de marshalling (donc cause indépendante). Résolution par la table d'export PE de
`python313.dll` : ces décalages tombent dans la plage de **`Python/traceback.c`**
(juste après l'export `_Py_DisplaySourceLine`) → **le crash survenait dans le code d'affichage
des traces de CPython**, pas dans un correctif applicatif.

### 8.3 Mécanisme exact

`main.py` appelait `faulthandler.enable(file=..., all_threads=True)`. Sur Windows, ce gestionnaire
d'exceptions vectorisé déclenche à **chaque** exception SEH un vidage de piles via
`_Py_DumpTracebackThreads()` (source CPython 3.13 confirmée : cette fonction parcourt la liste
**de tous les `PyThreadState`**). Or libmpv lève en permanence, et sans conséquence, une exception
SEH interne (`0xE24C4A02`) pendant ses appels d'API (`mpv_wait_event`, `mpv_get_property`,
`mpv_set_property`). Il en résultait des dizaines de vidages par seconde :

* écritures simultanées de plusieurs threads dans le même fichier → journal entremêlé/illisible ;
* trames lues en cours de mutation → lignes `File ???, line 500 in ???` ;
* puis **access violation dans le code d'affichage des traces** (les 4 empreintes ci-dessus).

### 8.4 Reproduction en laboratoire (A/B)

Charge de travail identique (lecteurs `PlayerController(render_mode=True)` + `MPVVideoWidget`
affichés/fermés en boucle + churn de threads Python, comme l'application) :

| mode | résultat |
|---|---|
| `faulthandler.enable(all_threads=True)` | **access violation, offset 0x2b62dc** (identique à la production) |
| nouveau journal VEH | **exit 0**, 40 itérations, sortie propre |

### 8.5 Correctif

* **`core/native_crash_log.py` (nouveau)** : VEH minimaliste qui journalise **une ligne** par
  exception (heure, thread, code, nom, adresse + module/décalage, accès pour une AV) **sans
  jamais parcourir les trames Python** ; vidage Python complet **uniquement** pour les codes
  mortels (AV, corruption de tas, débordement de pile, fast-fail). `faulthandler.enable()` est
  proscrit sur Windows (conservé tel quel sur POSIX, où les signaux ne sont émis que sur faute réelle).
* **`main.py`** : `_install_crash_guard()` installe ce journal au lieu de `faulthandler.enable()`.
* **`core/player_controller.py`** : plus aucun appel Qt depuis le thread libmpv — comparaison
  `threading.get_ident()` (au lieu de `QThread.currentThread()`, qui faisait fabriquer à Qt un
  QThread « adopté » à chaque notification) et file `collections.deque` + verrou vidée par un
  QTimer du thread Qt (au lieu du signal inter-threads `pyqtSignal(object)`).
* **`ui/widgets/gl_video_surface.py`** : le callback `mpv_render_update` lève un simple drapeau
  Python (`_redraw_pending`) ; c'est le timer de repeint (thread GUI, 33 ms) qui redessine — plus
  d'`emit()` depuis le thread interne de libmpv.
* **`core/mpv_render.py`** : le thunk ctypes du callback de mise à jour reste **vivant** pendant
  `mpv_render_context_free()` (il était libéré avant, alors que libmpv pouvait encore l'appeler).

### 8.6 Validation

* `tests/test_native_crash_log.py` (nouveau, 13 tests) et
  `tests/test_player_observer_thread_marshal.py` étendu (8 tests) : **verts**.
* 12 fichiers de tests touchés (stream/buffering, OSD, épisode suivant, multiview, chapitres,
  sous-titres, cycle de vie des workers, core…) : **exit 0 en exécution individuelle**.
* Build : `pyinstaller build.spec --clean -y` → `dist\IPTV_Hub\IPTV_Hub.exe` (20:08:33,
  9 240 987 octets). Test de fumée 35 s : processus vivant, et le journal contient
  l'en-tête `surveillance des fautes natives (VEH, processus …)` suivi de **5 lignes compactes**
  (au lieu des milliers de vidages corrompus).

### 8.7 Reste ouvert (distinct et antérieur)

* Le crash **en fin d'exécution de `pytest` groupé** est un **abort Qt** (`0xc0000409`,
  Qt6Core.dll) sans rapport avec l'AV ci-dessus ; il existe depuis avant ce travail
  (`test_series_video_integration.py` sort en 3, seul comme en groupe).
* Diagnostic d'un futur crash : lire les premières lignes ajoutées à
  `%APPDATA%\IPTV_Hub\iptv_errors.log` (elles nomment désormais le module fautif et son décalage).

## 9. Mise à jour du 05/10/2026 (21h00) — Multiview : sortie fiable + sélecteur de chaîne par listes / catégories

### 9.1 Symptômes rapportés

* Le Multiview « reste figé » : après des erreurs de flux, un clic sur **« Quitter Multiview »**
  ne réagissait plus, la mosaïque restant bloquée sur 2 écrans.
* Quitter la **TV en direct** laissait des écrans Multiview actifs (il n'en restait pas « que
  l'écran de base »).
* La fenêtre de sélection d'une chaîne d'un écran secondaire n'affichait qu'une liste à plat :
  ni listes personnalisées, ni catégories.

### 9.2 Causes identifiées

1. **Thread GUI bloqué dans le gestionnaire de clic** : `_on_exit_clicked()` appelait `stop_all()`
   → `player.cleanup()` (`mpv_terminate_destroy`) **avant** d'émettre `exit_requested`. Sur un flux
   en cours de connexion, cette libération dure plusieurs secondes (voire ne revient jamais si le
   cœur mpv est bloqué) : le bouton semblait « mort » et l'interface figée. Même problème dans
   `set_layout_mode()`, qui fermait les écrans masqués (→ `mpv_command "stop"`) de façon synchrone.
2. **Aucune désactivation du Multiview en quittant la TV en direct** : `_on_section_changed()`
   arrêtait le lecteur principal mais laissait les 2 à 4 lecteurs du Multiview diffuser, et
   `player_stack` restait sur la page Multiview.
3. **États résiduels** : `cleanup()` ne réinitialisait pas l'écran (chaîne, titre, page) → écrans
   « occupés » avec un lecteur mort à la ré-entrée dans le mode.
4. **Sélecteur de chaîne inopérant** : `ChannelPickerDialog` appelait
   `db.get_channels_by_playlist()` / `db.get_channels_by_stream_type()`, **méthodes inexistantes**
   dans `core/database.py` ; l'exception était avalée par un `except Exception` → liste vide.

### 9.3 Correctifs

* **`ui/widgets/multiview_widget.py`**
  * `_on_exit_clicked()` : **émet `exit_requested` en premier** (le lecteur solo reprend aussitôt la
    chaîne qui avait le focus audio), puis `deactivate(staggered=True)`.
  * Libération en deux phases : `suspend()` (arrêt + `mpv_render_context_free`, rapide, exécuté
    pendant que le widget est encore affiché) puis `destroy_player()` (destruction du cœur libmpv,
    potentiellement lente), cette dernière étant répartie **un écran à la fois par la boucle
    d'événements** (`_post_teardown` / `_teardown_next`, pas de 80 ms). L'ordre critique imposé par
    libmpv (contexte de rendu **avant** cœur mpv) est conservé.
  * `deactivate(staggered=…)` : remise à zéro de **tous** les écrans (placeholder
    « + Ajouter une chaîne », titre, audio, page) et arrêt/destruction des lecteurs ; nouveaux
    accesseurs `is_active`, `active_channel()`, `has_running_slots()`.
  * `set_layout_mode()` : les écrans masqués sont fermés **avant** d'être cachés (contexte OpenGL
    encore valide) ; la disposition choisie (2, 3 ou 4 écrans) est **mémorisée**.
  * Robustesse : chaque étape (stop, contexte de rendu, cleanup, émission de signal) est protégée —
    un lecteur bloqué ou planté ne peut plus interrompre la sortie du Multiview.
* **`ui/main_window.py`**
  * `_leave_multiview()` : désactive intégralement le Multiview et ramène `player_stack` sur
    **l'écran de base** ; retourne la chaîne du focus audio.
  * Appelé depuis `_on_multiview_exit()` (bouton « Quitter Multiview »), `_on_section_changed()`
    (toute navigation, donc tout départ de la TV en direct), `_return_to_vod_grid()` (bouton retour)
    et `_open_settings_view()`. Au retour sur « TV en direct », la chaîne du focus audio est
    reprise en solo.
* **`ui/dialogs/channel_picker_dialog.py`** (réécrit)
  * Deux colonnes : à gauche les **sources**, à droite les chaînes de la source + recherche.
  * Ordre demandé : **Toutes les chaînes**, puis **Listes personnalisées**, puis **CATÉGORIES**
    (filtrées : déduites des chaînes TV en direct activées ; groupes vides ou désactivés exclus).
  * Accès base corrigés (`db.get_channels(...)`, `db.get_custom_channel_lists_with_counts(...)`,
    `db.get_channels_for_custom_list(...)`) avec cache par source ; sélection par défaut sur la
    première liste personnalisée.

### 9.4 Validation

* Nouveaux tests : `tests/test_channel_picker_scopes.py` (7) — ordre listes personnalisées →
  catégories, filtrage par catégorie, recherche dans la source, sélection.
* `tests/test_multiview.py` étendu (+5) : remise à zéro complète des écrans, signal de sortie,
  lecteur libmpv bloqué, libération différée via la boucle d'événements, changement de disposition.
* Nouveau `tests/test_multiview_exit_integration.py` (3) : sortie du Multiview depuis `MainWindow`,
  désactivation sur changement de section, reprise de la chaîne au retour sur la TV en direct.
* Suite complète exécutée **fichier par fichier** : tous verts, sauf 5 échecs **antérieurs et sans
  rapport** (`test_refresh_playlist_no_screen_change`, `test_new_features`,
  `test_rounded_posters_and_square_episodes`, `test_vod_grid_async`, `test_series_video_integration`
  = abort Qt déjà connu).
* Build : `pyinstaller build.spec --clean -y` → `dist\IPTV_Hub\IPTV_Hub.exe` (20:55:44,
  9 251 921 octets). Test de fumée 28 s : processus vivant, journal sans aucune trace Python.

### 9.5 À vérifier côté utilisateur

1. Lancer `dist\IPTV_Hub\IPTV_Hub.exe`, ouvrir le Multiview (2, 3 ou 4 écrans), lancer deux chaînes
   puis cliquer **« Quitter Multiview »** → retour immédiat à l'écran de base, aucun écran résiduel.
2. Quitter la TV en direct (autre section, bouton retour, paramètres) puis y revenir : plus aucun
   écran Multiview actif, l'écran de base est seul affiché.
3. Dans un écran du Multiview, cliquer sur le crayon (« Changer la chaîne de cet écran ») : la
   colonne de gauche affiche **Toutes les chaînes**, puis **Listes personnalisées**, puis
   **CATÉGORIES**.

### 9.6 Détails restants

* `ui/main_window - Copie.py` (copie parasite non suivie par git) est toujours présent : à
  supprimer quand tu veux, il n'est référencé nulle part.
* L'abort en fin de `pytest` groupé (`0xc0000409`, Qt6Core.dll) reste antérieur et indépendant.

---

## 10. Bandeau OSD des écrans Multiview (nom + programme + actions)

*Demande :* le petit bandeau en haut de chaque écran Multiview était trop petit. Il fallait retrouver
le **même type d'OSD** que celui d'une chaîne diffusée en solo, avec **en plus** les icônes pour
**changer** ou **supprimer** la chaîne de l'écran — tout en tenant dans la largeur attribuée à la
diffusion de la chaîne.

### 10.1 Cause

* Le bandeau était un `QFrame` de seulement **34 px** de haut, avec un titre en **12 px**, des icônes
  de **15/16 px** et un bouton « fermer » discret : visuellement beaucoup moins lisible que l'OSD du
  lecteur solo (titre 15 px, programme 13 px, badge « DIRECT », barre translucide arrondie).
* Il n'était **rattaché à aucun layout** : il flottait donc à sa taille de contenu (~200 px), sans
  jamais occuper la largeur de l'écran, et aucun texte n'était tronqué.
* Aucune information de programme : le nom de la chaîne était la seule donnée affichée.

### 10.2 Correctif

* **`ui/widgets/multiview_widget.py`**
  * Nouveau `_build_top_bar()` : le bandeau reprend exactement les codes visuels de l'OSD du lecteur
    solo (`rgba(28, 36, 52, 0.95)`, bordure `#3d4f72`, rayons 10 px), avec les mêmes tailles
    (titre **15 px** gras blanc, programme **13 px** `#818cf8`, badge « DIRECT » rouge 10 px).
  * Contenu : icône audio (18 px), nom de la chaîne, **programme en cours (EPG)**, badge du type de
    flux, puis les **deux icônes d'action** — crayon (« Changer la chaîne de cet écran ») et
    **corbeille** (« Supprimer la chaîne de cet écran », libère l'écran). Hauteur **44 px**.
  * `_sync_banner_geometry()` (appelé depuis `resizeEvent` et à chaque `set_channel`) : le bandeau est
    positionné en haut de l'écran, occupe la **largeur complète de la surface vidéo moins 8 px de
    marge** et ne peut jamais la dépasser (écrans très étroits : plein largeur).
  * `_update_banner_elision()` : même stratégie que l'OSD solo — le titre est prioritaire, le
    programme est tronqué puis masqué dès que la place manque (seuil 220 px d'espace utile).
  * `_epg_text_for()` : programme en cours via le fournisseur EPG, repli sur le groupe de la chaîne,
    erreurs du fournisseur tolérées. Rafraîchissement automatique toutes les 60 s (`EPG_REFRESH_MS`)
    tant qu'une chaîne occupe l'écran, arrêté à la fermeture de l'écran.
  * `reset_slot()` : masque le bandeau, vide titre/programme et arrête le rafraîchissement EPG.
  * `_update_banner_badge()` : badge DIRECT / SÉRIE / REPLAY / FILM identique à celui du lecteur solo.
* **`ui/main_window.py`** : `MultiViewWidget` reçoit `epg_provider=lambda tvg_id:
  self.db.get_current_program(tvg_id)` — le **même fournisseur** que `video_widget.controls`, il est
  transmis à chacun des 4 écrans.
* **`core/i18n.py`** : nouvelle clé « Supprimer la chaîne de cet écran » (fr / en / es / de).

### 10.3 Validation

* `tests/test_multiview.py` étendu (+9, soit **18 verts**) : fidélité à l'OSD solo (hauteur, tailles,
  badge, deux icônes), **le bandeau ne dépasse jamais la largeur de l'écran**, troncature d'un nom
  très long (avec « … »), masquage du programme sur écran étroit, affichage du programme EPG et
  réinitialisation à la fermeture, repli sur le groupe, tolérance à une panne du fournisseur EPG,
  badge selon le type de flux, transmission du fournisseur EPG par `MultiViewWidget`.
* `tests/test_multiview_exit_integration.py`, `tests/test_channel_picker_scopes.py`,
  `tests/test_osd_mouse_and_resize.py` et `tests/test_i18n.py` : **tous verts**.
* Contrôle visuel par capture (`QWidget.grab()` hors écran) en disposition **1x2** et **2x2** :
  bandeau pleine largeur de chaque écran, nom lisible, programme, badge « DIRECT », crayon et
  corbeille alignés à droite, noms longs tronqués proprement.

### 10.4 À vérifier côté utilisateur

1. Lancer `dist\IPTV_Hub\IPTV_Hub.exe`, passer en Multiview (2, 3 ou 4 écrans) : chaque écran affiche
   en haut un bandeau du même style que l'OSD d'une chaîne en solo, avec son nom, le programme en
   cours, le badge « DIRECT » et les deux icônes (crayon / corbeille).
2. Réduire la fenêtre ou passer en 4 écrans : le bandeau reste **dans la largeur de l'écran** (les
   textes sont tronqués avec « … », le programme disparaît sur écran très étroit).
3. Cliquer sur le crayon (changer de chaîne) et sur la corbeille (libérer l'écran) : le bandeau suit
   immédiatement l'état de l'écran.

---

## 11. Vignettes d'épisodes manquantes dans une fiche série (06/10/2026)

### 11.1 Symptôme rapporté

Dans la fiche de la série **« Lanterns »**, plusieurs vignettes d'épisodes restent sur **l'image par
défaut**, alors que dans une autre série (**« Spin City »**) toutes les vignettes s'affichent.

### 11.2 Cause racine (démontrée sur les données réelles)

Diagnostic effectué directement dans la base de l'utilisateur (`%APPDATA%\IPTV_Hub\iptv.db`,
lecture seule) :

* Les 8 épisodes de « Lanterns » reçoivent de l'API Xtream l'URL
  `http://1.pi-cname.com:8080/images/..._big.jpg` → **HTTP 404 sur 100 % des visuels**, alors que
  **le même fichier, au même chemin**, est bien servi par `http://i.pure-redirect.com/images/...`
  (le domaine de l'affiche de la série) → **HTTP 200**. Vérifié : les 8 vignettes et le backdrop
  (0,83 Mo) sont récupérables depuis le domaine sain.
* Ce n'est pas un cas isolé : sur les 39 séries en cache, **21 sont touchées** (191 vignettes sur le
  domaine mort), dont **14 avec 100 % de leurs vignettes mortes** (Women in Blue, Neagley,
  City of Blood, Minerva, Surveillant !, Route 187, Simoun, Chasseurs d'héritiers, etc.).
* L'API renvoie donc **deux domaines d'images** pour un même fournisseur ; l'un d'eux (parfois porté
  sur le port 8080) est hors service côté fournisseur.
* **Bug applicatif aggravant** : lorsque le téléchargement d'une vignette échouait,
  `ImageLoader` supprimait l'abonné et émettait uniquement `image_failed` — la carte d'épisode
  n'écoutait rien. La chaîne de repli existante (backdrop série → affiche de saison → affiche de
  série) **n'était donc jamais tentée** : la vignette restait définitivement sur l'image par défaut.

### 11.3 Correctif

* **`core/image_loader.py`**
  * `load_image(..., on_failed=callback)` : nouvel abonnement d'échec par URL (`_failed_subscribers`),
    nettoyé comme les abonnements de succès (échec, `cancel_target`, destruction du widget).
  * `_report_failure(url)` : libère les abonnés et **appelle les callbacks d'échec** (le signal
    `image_failed` reste émis pour compatibilité).
  * `ImageLoader.alternate_host_urls(url, known_urls, limit=2)` : génère les **mêmes URLs servies
    par d'autres domaines d'images connus du fournisseur** (même chemin et mêmes paramètres,
    schéma de l'URL de référence conservé, doublons ignorés).
* **`ui/widgets/series_details_view.py`**
  * `EpisodeCardWidget` : la vignette est chargée via une **chaîne de candidats**
    (vignette de l'épisode → backdrop → affiche de saison → affiche de série). À chaque échec :
    d'abord **bascule de domaine** (même image sur le domaine de l'affiche), puis candidat suivant,
    enfin image par défaut. Plafond de sécurité : `_max_attempts = 12` requêtes par carte
    (aucune boucle possible, vérifié par test).
  * `_collect_known_image_urls()` : liste des URLs d'images connues de la série (affiche déjà
    affichée en premier, puis cover, backdrops, affiches de saisons, vignettes des épisodes) ;
    transmise aux cartes pour déduire les domaines valides du fournisseur.
  * Le **backdrop de la fiche** bénéficie de la même bascule (`_load_backdrop_image` /
    `_on_backdrop_failed`, une seule tentative de bascule pour rester sobre).
  * `load_series()` réinitialise l'état de chargement du backdrop (changement de série).

### 11.4 Validation

* Nouveau `tests/test_episode_thumb_fallback.py` : **22 tests verts**
  (`alternate_host_urls` : port, schéma, paramètres, doublons, limite, cas invalides ;
  notification d'échec de l'`ImageLoader` y compris image illisible et nettoyage à la destruction
  du widget ; carte d'épisode : bascule de domaine « Lanterns », repli sur le visuel de série,
  variante déjà en cache, absence de vignette d'épisode, image par défaut et plafond d'essais ;
  vue : domaine de référence en tête, transmission aux cartes, bascule du backdrop).
* **Test live réseau** (hors dépôt, script temporaire supprimé) avec les vraies données et les
  vraies URLs de l'utilisateur : **8/8 vignettes de « Lanterns » affichées** après bascule
  automatique, et backdrop chargé en 1280x720 depuis le domaine sain.
* Non-régression : `test_details_cursors`, `test_subtitles_and_episode_progress`,
  `test_series_db_cache`, `test_new_features`, `test_i18n`, `test_multiview*`,
  `test_worker_lifecycle`, `test_auto_play_next_episode`, `test_next_episode_overlay`,
  `test_series_resume_next_episode` → verts (seules subsistent des anomalies **antérieures et sans
  rapport** : `test_manage_playlists_dialog_title_and_badges`, `test_refresh_playlist_no_screen_change`,
  `test_vod_grid_async::test_poster_widget_disconnects_image_loader`, ainsi que le crash natif
  libmpv de `test_series_video_integration.py`, reproduit sans ces modifications).

### 11.5 À vérifier côté utilisateur

1. Ouvrir la fiche de **« Lanterns »** : les 8 vignettes de la saison 1 doivent s'afficher (elles
   arrivent via le domaine de l'affiche), et le fond de la fiche doit se charger.
2. Ouvrir une série mêlant vignettes saines et vignettes mortes (ex. **« Silo »**,
   **« Strange New Worlds »**) : plus aucune vignette par défaut.
3. Ouvrir une série saine (**« Spin City »**) : comportement inchangé (aucune requête
   supplémentaire, les visuels sont servis depuis le cache).

---

## 12. Bouton « Lecture » d'une fiche série : reprise au premier épisode non lu (Session F, 06-07/10/2026)

### 12.1 Symptôme rapporté

Après avoir regardé plusieurs épisodes d'une série (ex. jusqu'à S01E06) puis avoir décoché ou remis en « non lu » plusieurs épisodes antérieurs (ex. S01E03 à S01E06 pour recommencer à partir de S01E03), le bouton principal **« Lecture »** de la fiche série persistait à proposer ou lancer le **dernier épisode ayant eu une activité** (S01E06) au lieu de repartir de **l'épisode non lu le plus en arrière** (S01E03).

### 12.2 Cause racine

Dans `ui/widgets/series_details_view.py`, la méthode `_get_resume_or_next_episode()` cherchait la cible en ancrant d'abord son curseur sur le **dernier épisode ayant fait l'objet d'un visionnage** (ou visionnage partiel), puis tentait de proposer le prochain épisode non lu situé **après** lui.
Conséquences :
- Si un épisode plus avancé dans la série conservait une trace de progression partielle (ex. ratio `0 < r < 0.90`), il était toujours priorisé comme cible de reprise (`"resume"`), ignorant les épisodes antérieurs que l'utilisateur venait expressément de décocher / remettre en « non lu ».
- Le choix de la cible ne respectait pas le parcours séquentiel naturel de la série en cas de retour en arrière de l'utilisateur.

### 12.3 Correctif

* **`ui/widgets/series_details_view.py`** (`_get_resume_or_next_episode()`) :
  - La recherche de la cible a été entièrement réalignée sur le **premier épisode non terminé dans l'ordre chronologique de la série** (`all_episodes_flat`).
  - Parcours séquentiel des épisodes : dès qu'un épisode n'est pas marqué comme validé / vu (`not is_w`), il devient la cible unique `target_ep`.
  - Qualification de l'action selon l'état de ce premier épisode non vu :
    1. Si `0.0 < prog_ratio < 0.90` → `"resume"` (reprise au milieu de l'épisode).
    2. Si `first_unwatched_idx == 0` → `"start"` (tout début de la série).
    3. Si des épisodes précédents sont terminés → `"continue"` (enchaînement sur le premier non vu).
  - Si tous les épisodes sont marqués vus (`first_unwatched_idx is None`) → `"restart"` (recommencer la série depuis le premier épisode de la saison 1).

### 12.4 Validation

* **`tests/test_series_resume_next_episode.py`** (exécuté avec `QT_QPA_PLATFORM=offscreen`) :
  - **12/12 tests verts**.
  - Nouveaux tests dédiés ajoutés pour verrouiller le comportement :
    - `test_marking_episodes_unwatched_moves_resume_back` : vérifie qu'en remettant des épisodes vus en « non lu », la cible recule immédiatement au premier épisode non lu.
    - `test_reset_episodes_while_last_still_partially_watched` : couvre fidèlement le cas du bug où le dernier épisode est encore partiellement entamé mais que des épisodes précédents ont été décochés.
* Contrôle de qualité de code : `python -m ruff check ui/widgets/series_details_view.py` → **All checks passed!**.

### 12.5 À vérifier côté utilisateur

1. Lancer l'application, ouvrir une série et avancer la lecture (ex. jusqu'à S01E06, arrêté en cours de route).
2. Depuis la fiche série, décocher ou remettre en « non lu » les épisodes S01E03 à S01E06.
3. Vérifier le bouton principal : il doit afficher **« Reprendre : S01E03 … »** et lancer cet épisode dès le clic.


