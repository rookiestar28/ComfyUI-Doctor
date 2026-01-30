# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | Français | [Italiano](README.it.md) | [Español](README.es.md) | [English](../README.md) | [Roadmap & État du développement](../ROADMAP.md)

Une suite de diagnostics d'exécution continue et en temps réel pour ComfyUI comprenant **une analyse alimentée par LLM**, **un chat de débogage interactif** et **plus de 50 modèles de correction**. Intercepte automatiquement toutes les sorties du terminal dès le démarrage, capture des traces Python complètes (tracebacks) et fournit des suggestions de correction priorisées avec extraction de contexte au niveau du nœud. Prend désormais en charge la **gestion des motifs basée sur JSON** avec rechargement à chaud et **prise en charge i18n complète** pour 9 langues (en, zh_TW, zh_CN, ja, de, fr, it, es, ko).

## Dernières mises à jour (Jan 2026) - Cliquer pour développer

<details>
<summary><strong>Nouvelle fonctionnalité : F14 Diagnostics Proactifs (Bilan de Santé + Signature d'Intention)</strong></summary>

- Une section **Diagnostics (Diagnostics)** a été ajoutée à l'onglet **Statistiques (Statistics)** pour dépanner de manière proactive les problèmes de flux de travail (sans LLM).
- **Bilan de Santé (Health Check)** : Comprend le contrôle des flux de travail (lint), des actifs d'environnement (env assets) et des contrôles de confidentialité, et fournit des suggestions de correction exploitables.
- **Signature d'Intention (Intent Signature)** : Système d'inférence d'intention déterministe, fournissant des **Intentions Top-K + Preuves** pour aider à déterminer ce que le flux de travail "essaie de faire".
- Comprend le renforcement de l'UX : Replis sécurisés (par ex. "Aucune intention dominante détectée") et mécanismes améliorés d'assainissement des preuves.

</details>

<details>
<summary><strong>(v1.5.8) QoL: Auto-open Right Error Report Panel Toggle</strong></summary>

- Added a **dedicated toggle** in **Doctor → Settings** to control whether the **right-side error report panel** auto-opens when a new error is detected.
- **Default: ON** for new installs, and the choice is persisted.

</details>

<details>
<summary><strong>Gestion Intelligente du Budget de Jetons (v1.5.0)</strong></summary>

**Gestion Contextuelle Intelligente (Optimisation des Coûts) :**

- **Découpage automatique** : Pour les LLM distants (réduction de 60-80% des jetons)
- **Stratégie progressive** : Élagage du workflow → suppression des infos système → troncature de la trace
- **Opt-in Local** : Découpage léger pour Ollama/LMStudio (limites de 12K/16K)
- **Observabilité Améliorée** : Suivi des jetons étape par étape & Outil de validation A/B

**Résilience Réseau :**

- **Backoff Exponentiel** : Réessai automatique pour erreurs 429/5xx avec jitter
- **Protection du Streaming** : Watchdog de 30s pour chunks SSE bloqués
- **Limites de Débit & Concurrence** : Token bucket (30/min) + Sémaphore de concurrence (max 3)

**Nouvelle Configuration :**

| Config Key | Default | Description |
|------------|---------|-------------|
| `r12_enabled_remote` | `true` | Activer le budget intelligent (Remote) |
| `retry_max_attempts` | `3` | Max réessais |
| `stream_chunk_timeout` | `30` | Timeout de flux (sec) |

</details>

<details>
<summary><strong>Correctif Majeur: Gouvernance du Pipeline & Sécurité des Plugins (v1.4.5)</strong></summary>

**Renforcement de la Sécurité :**

- **Protection SSRF++** : Remplacement des vérifications de sous-chaînes par une analyse Host/Port appropriée ; blocage des redirections sortantes (`allow_redirects=False`)
- **Entonnoir de Nettoyage Sortant** : Une limite unique (`outbound.py`) garantit le nettoyage de TOUTES les charges utiles externes ; `privacy_mode=none` autorisé uniquement pour les LLM locaux vérifiés

**Système de Confiance des Plugins :**

- **Sécurisé par défaut** : Plugins désactivés par défaut, nécessitent une liste d'autorisation explicite (Allowlist) + Manifeste/SHA256
- **Classification de Confiance** : `trusted` (approuvé) | `unsigned` (non signé) | `untrusted` (non approuvé) | `blocked` (bloqué)
- **Confinement du Système de Fichiers** : Confinement par realpath, refus des liens symboliques, limites de taille, règles strictes de nom de fichier
- **Signature HMAC Optionnelle** : Vérification de l'intégrité par secret partagé (pas de signature à clé publique)

**Gouvernance du Pipeline :**

- **Contrats de Métadonnées** : Versionnage de schéma + validation post-exécution + Quarantaine pour les clés invalides
- **Politique de Dépendance** : Application de `requires/provides` ; dépendance manquante → étape ignorée, statut `degraded` (dégradé)
- **Contre-pression du Logger** : `DroppingQueue` avec gestion des priorités + métriques de rejet
- **Transfert avant démarrage** : Désinstallation propre du Logger avant la prise en charge par SmartLogger

**Observabilité :**

- Point de terminaison `/doctor/health` : Expose les métriques de file d'attente, les comptes de rejets, les blocages SSRF et le statut du pipeline

**Résultats des Tests** : 159 tests Python réussis | 17 tests de Gate Phase 2

</details>

<details>
<summary><strong>Amélioration: CI Gates & Outillage Plugins</strong></summary>

**T11 - CI Gate de Version Phase 2 :**

- Workflow GitHub Actions (`phase2-release-gate.yml`) : Impose 4 suites pytest + E2E
- Script de validation locale (`scripts/phase2_gate.py`) : Supporte les modes `--fast` et `--e2e`

**T12 - Vérificateur Statique de Sécurité Sortante :**

- Analyseur basé sur AST (`scripts/check_outbound_safety.py`) détecte les modèles de contournement
- 6 règles de détection : `RAW_FIELD_IN_PAYLOAD`, `DANGEROUS_FALLBACK`, `POST_WITHOUT_SANITIZATION`, etc.
- Workflow CI + 8 tests unitaires + Documentation (`docs/OUTBOUND_SAFETY.md`)

**A8 - Outillage de Migration de Plugin :**

- `scripts/plugin_manifest.py` : Génère un manifeste avec des hachages SHA256
- `scripts/plugin_allowlist.py` : Scanne les plugins et suggère une configuration
- `scripts/plugin_validator.py` : Valide le manifeste et la configuration
- `scripts/plugin_hmac_sign.py` : Génère des signatures HMAC optionnelles
- Documentation mise à jour : `docs/PLUGIN_MIGRATION.md`, `docs/PLUGIN_GUIDE.md`

</details>

<details>
<summary><strong>Amélioration: Docs CSP & Télémétrie</strong></summary>

**S1 - Docs de Conformité CSP :**

- Vérification que tous les actifs se chargent localement (`web/lib/`) ; les URL CDN sont uniquement en secours
- Ajout de la section "CSP Compatibility" au README
- Audit de code terminé (en attente de vérification manuelle)

**S3 - Infrastructure de Télémétrie Locale :**

- Backend : `telemetry.py` (TelemetryStore, RateLimiter, détection PII)
- 6 Points de Terminaison API : `/doctor/telemetry/{status,buffer,track,clear,export,toggle}`
- Frontend : Contrôles UI des paramètres pour la gestion de la télémétrie
- Sécurité : Vérification de l'origine (403 Cross-Origin), limite de charge utile 1KB, liste blanche de champs
- **Désactivé par défaut** : Aucun enregistrement/Réseau sauf activation explicite
- 81 chaînes i18n (9 clés × 9 langues)

**Résultats des Tests** : 27 Tests Unitaires Télémétrie | 8 Tests E2E

</details>

<details>
<summary><strong>Amélioration : Renforcement Runner E2E & UI Confiance/Santé</strong></summary>

**Renforcement Runner E2E (Support WSL `/mnt/c`) :**

- Correction des problèmes de permission du cache de traduction Playwright sur WSL
- Ajout d'un répertoire temporaire accessible en écriture (`.tmp/playwright`) sous le repo
- Remplacement `PW_PYTHON` pour la compatibilité multiplateforme

**Panneau UI Confiance & Santé :**

- Ajout du panneau "Trust & Health" à l'onglet Statistiques (Statistics)
- Affiche : pipeline_status, ssrf_blocked, dropped_logs
- Liste de confiance des plugins (avec badges et raisons)
- Point de terminaison de scan uniquement `GET /doctor/plugins` (pas d'importation de code)

**Résultats des Tests** : 61/61 Tests E2E Réussis | 159/159 Tests Python Réussis

</details>

<details>
<summary><strong>Mises à jour précédentes (v1.4.0, Jan 2026)</strong></summary>

- Migration A7 Preact Terminée (Phase 5A–5C : Îlots Chat/Stats, registre, rendu partagé, solutions de repli robustes).
- Renforcement de l'Intégration : Couverture Playwright E2E renforcée.
- Correctifs UI : Correction du timing de l'infobulle de la barre latérale.

</details>

<details>
<summary><strong>Tableau de bord statistiques</strong></summary>

**Suivez votre stabilité ComfyUI en un coup d'œil !**

ComfyUI-Doctor inclut désormais un **Tableau de bord statistiques** qui fournit des informations sur les tendances d'erreurs, les problèmes courants et la progression de la résolution.

**Fonctionnalités** :

- 📊 **Tendances d'erreurs** : Suivez les erreurs sur 24h/7j/30j
- 🔥 **Top 5 des motifs** : Voyez quelles erreurs se produisent le plus fréquemment
- 📈 **Répartition par catégorie** : Visualisez les erreurs par catégorie (Mémoire, Flux de travail, Chargement de modèle, etc.)
- ✅ **Suivi de résolution** : Surveillez les erreurs résolues vs non résolues
- 🌍 **Support i18n complet** : Disponible dans les 9 langues

![Tableau de bord statistiques](../../assets/statistics_panel.png)

**Comment utiliser** :

1. Ouvrez le panneau latéral Doctor (cliquez sur l'icône 🏥 à gauche)
2. Développez la section "📊 Statistiques d'erreurs"
3. Consultez les analyses et tendances d'erreurs en temps réel
4. Marquez les erreurs comme résolues/ignorées pour suivre vos progrès

**API Backend** :

- `GET /doctor/statistics?time_range_days=30` - Récupérer les statistiques
- `POST /doctor/mark_resolved` - Mettre à jour le statut de résolution

**Couverture des tests** : 17/17 tests backend ✅ | 14/18 tests E2E (taux de réussite 78%)

**Détails de mise en œuvre** : Voir `.planning/260104-F4_STATISTICS_RECORD.md`

</details>

<details>
<summary><strong>CI de validation des motifs</strong></summary>

**Des contrôles qualités automatisés protègent désormais l'intégrité des motifs !**

ComfyUI-Doctor inclut désormais des **tests d'intégration continue** pour tous les motifs d'erreur, garantissant des contributions zéro défaut.

**Ce que T8 valide** :

- ✅ **Format JSON** : Les 8 fichiers de motifs se compilent correctement
- ✅ **Syntaxe Regex** : Les 57 motifs ont des expressions régulières valides
- ✅ **Complétude i18n** : Couverture de traduction à 100% (57 motifs × 9 langues = 513 vérifications)
- ✅ **Conformité Schéma** : Champs requis (`id`, `regex`, `error_key`, `priority`, `category`)
- ✅ **Qualité Métadonnées** : Plages de priorité valides (50-95), ID uniques, catégories correctes

**Intégration GitHub Actions** :

- Se déclenche à chaque push/PR affectant `patterns/`, `i18n.py` ou les tests
- S'exécute en ~3 secondes pour 0 $ (niveau gratuit GitHub Actions)
- Bloque les fusions si la validation échoue

**Pour les contributeurs** :

```bash
# Validation locale avant commit
python scripts/run_pattern_tests.py

# Sortie :
✅ All 57 patterns have required fields
✅ All 57 regex patterns compile successfully
✅ en: All 57 patterns have translations
✅ zh_TW: All 57 patterns have translations
... (9 langues au total)
```

**Résultats des tests** : Taux de réussite de 100% sur tous les contrôles

**Détails de mise en œuvre** : Voir `.planning/260103-T8_IMPLEMENTATION_RECORD.md`

</details>

<details>
<summary><strong>Refonte du système de motifs (ÉTAPE 1-3 Terminée)</strong></summary>

ComfyUI-Doctor a subi une mise à niveau architecturale majeure avec **plus de 57 motifs d'erreur** et une **gestion des motifs basée sur JSON** !

**ÉTAPE 1 : Correctif de l'architecture Logger**

- Implémentation de SafeStreamWrapper avec traitement en arrière-plan basé sur une file d'attente
- Élimination des risques de blocage (deadlock) et des conditions de concurrence (race conditions)
- Correction des conflits d'interception de logs avec le LogInterceptor de ComfyUI

**ÉTAPE 2 : Gestion des motifs JSON (F2)**

- Nouveau PatternLoader avec capacité de rechargement à chaud (pas de redémarrage nécessaire !)
- Les motifs sont maintenant définis dans des fichiers JSON sous le répertoire `patterns/`
- 22 motifs intégrés dans `patterns/builtin/core.json`
- Facile à étendre et à maintenir

**ÉTAPE 3 : Extension des motifs communautaires (F12)**

- **35 nouveaux motifs communautaires** couvrant les extensions populaires :
  - **ControlNet** (8 motifs) : Chargement de modèle, pré-traitement, dimensionnement d'image
  - **LoRA** (6 motifs) : Erreurs de chargement, compatibilité, problèmes de poids
  - **VAE** (5 motifs) : Échec d'encodage/décodage, précision, tuilage
  - **AnimateDiff** (4 motifs) : Chargement de modèle, nombre de trames, longueur de contexte
  - **IPAdapter** (4 motifs) : Chargement de modèle, encodage d'image, compatibilité
  - **FaceRestore** (3 motifs) : Modèles CodeFormer/GFPGAN, détection
  - **Divers** (5 motifs) : Checkpoints, échantillonneurs, planificateurs, CLIP
- Support i18n complet pour l'anglais, le chinois traditionnel et le chinois simplifié
- Total : **57 motifs d'erreur** (22 intégrés + 35 communautaires)

**Avantages** :

- ✅ Couverture d'erreurs plus complète
- ✅ Rechargement à chaud des motifs sans redémarrer ComfyUI
- ✅ La communauté peut contribuer des motifs via des fichiers JSON
- ✅ Base de code plus propre et maintenable

</details>

<details>
<summary><strong>Mises à jour précédentes (Déc 2025)</strong></summary>

### F9 : Extension du support multilingue

Nous avons étendu le support linguistique de 4 à 9 langues ! ComfyUI-Doctor fournit désormais des suggestions d'erreurs en :

- **English** Anglais (en)
- **繁體中文** Chinois Traditionnel (zh_TW)
- **简体中文** Chinois Simplifié (zh_CN)
- **日本語** Japonais (ja)
- **🆕 Deutsch** Allemand (de)
- **🆕 Français** (fr)
- **🆕 Italiano** Italien (it)
- **🆕 Español** Espagnol (es)
- **🆕 한국어** Coréen (ko)

Les 57 motifs d'erreur sont entièrement traduits dans toutes les langues, assurant une qualité de diagnostic cohérente dans le monde entier.

### F8 : Intégration des paramètres de la barre latérale

Les paramètres ont été rationalisés ! Configurez Doctor directement depuis la barre latérale :

- Cliquez sur l'icône ⚙️ dans l'en-tête de la barre latérale pour accéder à tous les paramètres
- Sélection de la langue (9 langues)
- Changement rapide de fournisseur d'IA (OpenAI, DeepSeek, Groq, Gemini, Ollama, etc.)
- Remplissage automatique de l'URL de base lors du changement de fournisseur
- Gestion de la clé API (saisie protégée par mot de passe)
- Configuration du nom du modèle
- Les paramètres persistent entre les sessions avec localStorage
- Retour visuel lors de la sauvegarde (✅ Enregistré ! / ❌ Erreur)

Le panneau Paramètres de ComfyUI affiche désormais uniquement le commutateur Activer/Désactiver - tous les autres paramètres ont été déplacés vers la barre latérale pour une expérience plus propre et intégrée.

</details>

---

## Fonctionnalités

- **Surveillance automatique des erreurs** : Capture toutes les sorties du terminal et détecte les traces Python en temps réel
- **Analyse intelligente des erreurs** : Plus de 57 motifs d'erreur (22 intégrés + 35 communautaires) avec des suggestions exploitables
- **Extraction du contexte du nœud** : Identifie quel nœud a causé l'erreur (ID du nœud, Nom, Classe)
- **Contexte de l'environnement système** : Inclut automatiquement la version Python, les paquets installés (pip list) et les informations OS dans l'analyse IA
- **Support multilingue** : 9 langues prises en charge (Anglais, Chinois Traditionnel, Chinois Simplifié, Japonais, Allemand, Français, Italien, Espagnol, Coréen)
- **Gestion des motifs basée sur JSON** : Rechargement à chaud des motifs d'erreur sans redémarrer ComfyUI
- **Support des motifs communautaires** : Couvre ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore, et plus
- **Nœud inspecteur de débogage** : Inspection approfondie des données circulant dans votre flux de travail
- **Historique des erreurs** : Maintient un tampon des erreurs récentes via l'API
- **API RESTful** : Sept points de terminaison pour l'intégration frontend
- **Analyse alimentée par IA** : Analyse d'erreur LLM en un clic avec support de plus de 8 fournisseurs (OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio, et plus)
- **Interface de chat interactive** : Assistant de débogage IA multi-tours intégré dans la barre latérale de ComfyUI
- **Interface latérale interactive** : Panneau d'erreur visuel avec localisation du nœud et diagnostics instantanés
- **Configuration flexible** : Panneau de configuration complet pour la personnalisation du comportement

### 🆕 Interface de Chat IA

La nouvelle interface de chat interactive offre une expérience de débogage conversationnelle directement dans la barre latérale gauche de ComfyUI. Lorsqu'une erreur survient, cliquez simplement sur "Analyze with AI" pour démarrer une conversation multi-tours avec votre LLM préféré.

<div align="center">
<img src="../../assets/chat-ui.png" alt="Interface de Chat IA">
</div>

**Caractéristiques clés :**

- **Conscient du contexte** : Inclut automatiquement les détails de l'erreur, les informations sur le nœud et le contexte du flux de travail
- **Conscient de l'environnement** : Inclut la version Python, les paquets installés et les informations OS pour un débogage précis
- **Réponses en streaming** : Réponses LLM en temps réel avec un formatage correct
- **Conversations multi-tours** : Posez des questions de suivi pour approfondir les problèmes
- **Toujours accessible** : La zone de saisie reste visible en bas avec un positionnement collant
- **Supporte plus de 8 fournisseurs LLM** : OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio, et plus
- **Mise en cache intelligente** : Liste des paquets mise en cache pendant 24 heures pour éviter l'impact sur les performances

**Comment utiliser :**

1. Lorsqu'une erreur survient, ouvrez la barre latérale Doctor (panneau de gauche)
2. Cliquez sur le bouton "✨ Analyze with AI" dans la zone de contexte d'erreur
3. L'IA analysera automatiquement l'erreur et fournira des suggestions
4. Continuez la conversation en tapant des questions de suivi dans la zone de saisie
5. Appuyez sur Entrée ou cliquez sur "Send" pour envoyer votre message

> **💡 Astuce API gratuite** : [Google AI Studio](https://aistudio.google.com/app/apikey) (Gemini) offre un niveau gratuit généreux sans carte de crédit requise. Parfait pour commencer avec le débogage alimenté par IA sans aucuns frais !

---

## Installation

### Option 1 : Utiliser ComfyUI-Manager (Recommandé)

1. Ouvrez ComfyUI et cliquez sur le bouton **Manager** dans le menu
2. Sélectionnez **Install Custom Nodes**
3. Recherchez `ComfyUI-Doctor`
4. Cliquez sur **Install** et redémarrez ComfyUI

### Option 2 : Installation manuelle (Git Clone)

1. Naviguez vers votre répertoire de nœuds personnalisés ComfyUI :

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. Clonez ce dépôt :

   ```bash
   git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
   ```

3. Redémarrez ComfyUI

4. Recherchez le message d'initialisation dans la console :

   ```text
   [ComfyUI-Doctor] Initializing Smart Debugger...
   [ComfyUI-Doctor] Log file: .../logs/comfyui_debug_2025-12-28.log
   
   ==================== SYSTEM SNAPSHOT ====================
   OS: Windows 11
   Python: 3.12.3
   PyTorch: 2.0.1+cu118
   CUDA Available: True
   ...
   ```

---

## Utilisation

### Mode Passif (Automatique)

Une fois installé, ComfyUI-Doctor fait automatiquement :

- Enregistre toutes les sorties de la console dans le répertoire `logs/`
- Détecte les erreurs et fournit des suggestions
- Enregistre les informations sur l'environnement système

**Exemple de sortie d'erreur** :

```
Traceback (most recent call last):
  ...
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB

----------------------------------------
ERROR LOCATION: Node ID: #42 | Name: KSampler
SUGGESTION: OOM (Out Of Memory) : Votre VRAM GPU est pleine. Essayez :
   1. Réduire la taille du lot (Batch Size)
   2. Utiliser le drapeau '--lowvram'
   3. Fermer d'autres applications GPU
----------------------------------------
```

### Mode Actif (Nœud de débogage)

1. Faites un clic droit sur le canevas → `Add Node` → `Smart Debug Node`
2. Connectez le nœud en ligne avec n'importe quelle connexion (prend en charge l'entrée joker `*`)
3. Exécutez votre flux de travail

**Exemple de sortie** :

```text
[DEBUG] Data Inspection:
  Type: Tensor
  Shape: torch.Size([1, 4, 64, 64])
  Dtype: torch.float16
  Device: cuda:0
  Stats (All): Min=-3.2156, Max=4.8912, Mean=0.0023
```

Le nœud transmet les données sans affecter l'exécution du flux de travail.

---

## Interface Utilisateur (UI) Frontend

ComfyUI-Doctor fournit une interface de barre latérale interactive pour la surveillance des erreurs et les diagnostics en temps réel.

### Accéder au panneau Doctor

Cliquez sur le bouton **🏥 Doctor** dans le menu ComfyUI (barre latérale gauche) pour ouvrir le panneau Doctor. Le panneau glisse depuis le côté droit de l'écran.

### Caractéristiques de l'interface

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Rapport d'erreur">
</div>

L'interface Doctor se compose de deux panneaux :

#### Panneau latéral gauche (Barre latérale Doctor)

Cliquez sur l'icône **🏥 Doctor** dans le menu gauche de ComfyUI pour accéder à :

- **Panneau de configuration** (icône ⚙️) : Configurez la langue, le fournisseur d'IA, les clés API et la sélection de modèle
- **Carte de contexte d'erreur** : Lorsqu'une erreur survient, affiche :
  - **💡 Suggestion** : Conseil concis et exploitable (ex. "Vérifiez les connexions d'entrée et assurez-vous que les exigences du nœud sont satisfaites.")
  - **Horodatage** : Moment où l'erreur s'est produite
  - **Contexte du nœud** : ID et nom du nœud (si applicable)
  - **✨ Analyze with AI** : Lancez un chat interactif pour un débogage détaillé
- **Interface de chat IA** : Conversation multi-tours avec votre LLM pour une analyse approfondie des erreurs
- **Zone de saisie collante** : Toujours accessible en bas pour les questions de suivi

#### Panneau d'erreur droit (Dernier diagnostic)

Notifications d'erreur en temps réel dans le coin supérieur droit :

![Rapport d'erreur Doctor](../../assets/error-report.png)

- **Indicateur d'état** : Point coloré montrant la santé du système
  - 🟢 **Vert** : Système fonctionnant normalement, aucune erreur détectée
  - 🔴 **Rouge (pulsant)** : Erreur active détectée
- **Carte du dernier diagnostic** : Affiche l'erreur la plus récente avec :
  - **Résumé de l'erreur** : Brève description de l'erreur (thème rouge, pliable pour les erreurs longues)
  - **💡 Suggestion** : Conseil concis et exploitable (thème vert)
  - **Horodatage** : Moment où l'erreur s'est produite
  - **Contexte du nœud** : ID, nom et classe du nœud
  - **🔍 Localiser le nœud sur le canevas** : Centre et met en évidence automatiquement le nœud problématique

**Principes de conception clés** :

- ✅ **Suggestions concises** : Seul le conseil exploitable est affiché (ex. "Vérifiez les connexions d'entrée...") au lieu de descriptions d'erreurs verbeuses
- ✅ **Séparation visuelle** : Les messages d'erreur (rouge) et les suggestions (vert) sont clairement distingués
- ✅ **Troncature intelligente** : Les erreurs longues affichent les 3 premières + 3 dernières lignes avec détails complets pliables
- ✅ **Mises à jour en temps réel** : Les deux panneaux se mettent à jour automatiquement lorsque de nouvelles erreurs surviennent via des événements WebSocket

---

## Analyse d'erreur alimentée par IA

ComfyUI-Doctor s'intègre aux services LLM populaires pour fournir des suggestions de débogage intelligentes et contextuelles.

### Fournisseurs d'IA pris en charge

#### Services Cloud

- **OpenAI** (GPT-4, GPT-4o, etc.)
- **DeepSeek** (DeepSeek-V2, DeepSeek-Coder)
- **Groq Cloud** (Llama 3, Mixtral - inférence LPU ultra-rapide)
- **Google Gemini** (Gemini Pro, Gemini Flash)
- **xAI Grok** (Grok-2, Grok-beta)
- **OpenRouter** (Accès à Claude, GPT-4 et plus de 100 modèles)

#### Services Locaux (Aucune clé API requise)

- **Ollama** (`http://127.0.0.1:11434`) - Exécutez Llama, Mistral, CodeLlama localement
- **LMStudio** (`http://localhost:1234/v1`) - Inférence de modèle locale avec GUI

> **💡 Compatibilité multiplateforme** : Les URL par défaut peuvent être remplacées via des variables d'environnement :
>
> - `OLLAMA_BASE_URL` - Point de terminaison Ollama personnalisé (défaut : `http://127.0.0.1:11434`)
> - `LMSTUDIO_BASE_URL` - Point de terminaison LMStudio personnalisé (défaut : `http://localhost:1234/v1`)
>
> Cela évite les conflits entre les instances Ollama Windows et WSL2, ou lors de l'exécution dans des configurations Docker/personnalisées.

### Configuration

![Panneau de configuration](../../assets/settings.png)

Configurez l'analyse IA dans le panneau **Barre latérale Doctor** → **Settings** :

1. **AI Provider** : Sélectionnez dans le menu déroulant. L'URL de base se remplira automatiquement.
2. **AI Base URL** : Le point de terminaison API (auto-peuplé, mais personnalisable)
3. **AI API Key** : Votre clé API (laissez vide pour les LLM locaux comme Ollama/LMStudio)
4. **AI Model Name** :
   - Sélectionnez un modèle dans la liste déroulante (automatiquement peuplée depuis l'API de votre fournisseur)
   - Cliquez sur le bouton d'actualisation 🔄 pour recharger les modèles disponibles
   - Ou cochez "Saisir le nom du modèle manuellement" pour taper un nom de modèle personnalisé
5. **Mode de confidentialité** : Sélectionnez le niveau de désinfection PII pour les services d'IA cloud (voir la section [Mode de confidentialité (Désinfection PII)](#mode-de-confidentialité-désinfection-pii) ci-dessous pour plus de détails)

### Utilisation de l'analyse IA

1. Le panneau Doctor s'ouvre automatiquement lorsqu'une erreur survient.
2. Examinez les suggestions intégrées, ou cliquez sur le bouton ✨ Analyze with AI sur la carte d'erreur.
3. Attendez que le LLM analyse l'erreur (généralement 3-10 secondes).
4. Examinez les suggestions de débogage générées par l'IA.

**Note de sécurité** : Votre clé API est transmise de manière sécurisée du frontend au backend uniquement pour la demande d'analyse. Elle n'est jamais enregistrée ou stockée de manière persistante.

### Mode de confidentialité (Désinfection PII)

ComfyUI-Doctor inclut une **désinfection automatique des PII (Informations Personnellement Identifiables)** pour protéger votre vie privée lors de l'envoi de messages d'erreur aux services d'IA cloud.

**Trois niveaux de confidentialité** :

| Niveau | Description | Ce qui est supprimé | Recommandé pour |
| ----- | ----------- | --------------- | --------------- |
| **None** | Aucune désinfection | Rien | LLM Locaux (Ollama, LMStudio) |
| **Basic** (Défaut) | Protection standard | Chemins utilisateur, clés API, emails, adresses IP | La plupart des utilisateurs avec des LLM Cloud |
| **Strict** | Confidentialité maximale | Tout de Basic + IPv6, empreintes SSH | Exigences Entreprise/Conformité |

**Ce qui est désinfecté** (Niveau Basic) :

- ✅ Chemins utilisateur Windows : `C:\Users\john\file.py` → `<USER_PATH>\file.py`
- ✅ Accueil Linux/macOS : `/home/alice/test.py` → `<USER_HOME>/test.py`
- ✅ Clés API : `sk-abc123...` → `<API_KEY>`
- ✅ Adresses email : `user@example.com` → `<EMAIL>`
- ✅ IPs privées : `192.168.1.1` → `<PRIVATE_IP>`
- ✅ Identifiants URL : `https://user:pass@host` → `https://<USER>@host`

**Ce qui n'est PAS supprimé** :

- ❌ Messages d'erreur (nécessaires pour le débogage)
- ❌ Noms de modèles, noms de nœuds
- ❌ Structure du flux de travail
- ❌ Chemins de fichiers publics (`/usr/bin/python`)

**Configurer le mode de confidentialité** : Ouvrez la barre latérale Doctor → Settings → Menu déroulant 🔒 Privacy Mode. Les modifications s'appliquent immédiatement à toutes les demandes d'analyse IA.

**Conformité RGPD** : Cette fonctionnalité prend en charge l'article 25 du RGPD (Protection des données dès la conception) et est recommandée pour les déploiements d'entreprise.

### Tableau de bord statistiques

![Panneau statistiques](../../assets/statistics_panel.png)

Le **Tableau de bord statistiques** fournit des informations en temps réel sur vos modèles d'erreurs ComfyUI et les tendances de stabilité.

**Fonctionnalités** :

- **📊 Tendances d'erreurs** : Erreurs totales et comptes pour les derniers 24h/7j/30j
- **🔥 Principaux motifs d'erreur** : Les 5 types d'erreurs les plus fréquents avec le nombre d'occurrences
- **📈 Répartition par catégorie** : Répartition visuelle par catégorie d'erreur (Mémoire, Flux de travail, Chargement de modèle, Cadre, Générique)
- **✅ Suivi de résolution** : Suivez les erreurs résolues, non résolues et ignorées
- **🧭 Contrôles de statut** : Marquer la dernière erreur comme Résolu / Non résolu / Ignoré depuis l’onglet Statistiques
- **🛡️ Confiance et Santé (Trust & Health)** : Voir les métriques `/doctor/health` et le rapport de confiance des plugins (scan uniquement)
- **📊 Télémétrie Anonyme (Anonymous Telemetry) (En construction 🚧)** : Opt-in tampon local pour les événements d'utilisation (basculer/voir/effacer/exporter)

**Comment utiliser** :

1. Ouvrez la barre latérale Doctor (cliquez sur l'icône 🏥 à gauche)
2. Trouvez la section pliable **📊 Statistiques d'erreurs**
3. Cliquez pour développer et afficher vos analyses d'erreurs
4. Utilisez les boutons **Marquer comme** pour définir l’état de la dernière erreur (Résolu / Non résolu / Ignoré)
5. Faites défiler jusqu'au bas de l'onglet Statistiques pour trouver **Confiance et Santé** et **Télémétrie Anonyme**.

**Contrôles du statut** :

- Les boutons ne sont activés que lorsqu’un horodatage de la dernière erreur est disponible
- Les mises à jour de statut sont conservées dans l’historique et actualisent automatiquement le taux de résolution

**Comprendre les données** :

- **Total (30j)** : Erreurs cumulées au cours des 30 derniers jours
- **Dernières 24h** : Erreurs au cours des dernières 24 heures (aide à identifier les problèmes récents)
- **Taux de résolution** : Montre les progrès vers la résolution des problèmes connus
  - 🟢 **Résolu** : Problèmes que vous avez corrigés
  - 🟠 **Non résolu** : Problèmes actifs nécessitant une attention
  - ⚪ **Ignoré** : Problèmes non critiques que vous avez choisi d'ignorer
- **Top Motifs** : Identifie quels types d'erreurs nécessitent une attention prioritaire
- **Catégories** : Vous aide à comprendre si les problèmes sont liés à la mémoire, aux flux de travail, aux échecs de chargement de modèle, etc.

**Persistance de l'état du panneau** : L'état ouvert/fermé du panneau est enregistré dans le localStorage de votre navigateur, de sorte que votre préférence persiste entre les sessions.

### Exemple de configuration de fournisseur

| Fournisseur      | URL de base                                                | Exemple de modèle            |
|------------------|------------------------------------------------------------|------------------------------|
| OpenAI           | `https://api.openai.com/v1`                                | `gpt-4o`                     |
| DeepSeek         | `https://api.deepseek.com/v1`                              | `deepseek-chat`              |
| Groq             | `https://api.groq.com/openai/v1`                           | `llama-3.1-70b-versatile`    |
| Gemini           | `https://generativelanguage.googleapis.com/v1beta/openai`  | `gemini-1.5-flash`           |
| Ollama (Local)   | `http://localhost:11434/v1`                                | `llama3.1:8b`                |
| LMStudio (Local) | `http://localhost:1234/v1`                                 | Modèle chargé dans LMStudio  |

---

## Paramètres

You can also customize ComfyUI-Doctor behavior via the **Doctor sidebar → Settings** tab.

### 1. Show error notifications (Afficher les notifications d'erreur)

**Fonction** : Active/désactive les cartes de notification d'erreur flottantes (toasts) dans le coin supérieur droit.
**Utilisation** : Désactivez si vous préférez vérifier les erreurs manuellement dans la barre latérale sans interruptions visuelles.

### 2. Auto-open panel on error (Ouvrir automatiquement le panneau en cas d'erreur)

**Function**: Automatically opens the **right-side error report panel** when a new error is detected.
**Usage**: **Default: ON**. Disable if you prefer to keep the panel closed and open it manually.

### 3. Error Check Interval (ms)

**Fonction** : Fréquence des vérifications d'erreur frontend-backend (en millisecondes). Défaut : `2000`.
**Utilisation** : Des valeurs plus basses (ex. 500) donnent un retour plus rapide mais augmentent la charge ; des valeurs plus élevées (ex. 5000) économisent les ressources.

### 4. Suggestion Language (Langue de suggestion)

**Fonction** : Langue pour les rapports de diagnostic et les suggestions du Doctor.
**Utilisation** : Prend actuellement en charge l'anglais, le chinois traditionnel, le chinois simplifié et le japonais (d'autres à venir). Les changements s'appliquent aux nouvelles erreurs.

### 5. Enable Doctor (requires restart)

**Fonction** : Interrupteur principal pour le système d'interception de logs.
**Utilisation** : Désactivez pour désactiver complètement la fonctionnalité principale de Doctor (nécessite un redémarrage de ComfyUI).

### 6. AI Provider

**Fonction** : Sélectionnez votre fournisseur de services LLM préféré dans un menu déroulant.
**Options** : OpenAI, DeepSeek, Groq Cloud, Google Gemini, xAI Grok, OpenRouter, Ollama (Local), LMStudio (Local), Personnalisé.
**Utilisation** : La sélection d'un fournisseur remplit automatiquement l'URL de base appropriée. Pour les fournisseurs locaux (Ollama/LMStudio), une alerte affiche les modèles disponibles.

### 7. AI Base URL

**Fonction** : Le point de terminaison API pour votre service LLM.
**Utilisation** : Rempli automatiquement lorsque vous sélectionnez un fournisseur, mais peut être personnalisé pour les points de terminaison auto-hébergés ou personnalisés.

### 8. AI API Key

**Fonction** : Votre clé API pour l'authentification avec les services LLM cloud.
**Utilisation** : Requis pour les fournisseurs de cloud (OpenAI, DeepSeek, etc.). Laissez vide pour les LLM locaux (Ollama, LMStudio).
**Sécurité** : La clé est transmise uniquement lors des demandes d'analyse et n'est jamais enregistrée ou persistée.

### 9. AI Model Name

**Fonction** : Spécifiez quel modèle utiliser pour l'analyse des erreurs.
**Utilisation** :

- **Mode liste déroulante** (défaut) : Sélectionnez un modèle dans la liste automatiquement peuplée. Cliquez sur le bouton d'actualisation 🔄 pour recharger les modèles disponibles.
- **Mode saisie manuelle** : Cochez "Saisir le nom du modèle manuellement" pour taper un nom de modèle personnalisé (ex. `gpt-4o`, `deepseek-chat`, `llama3.1:8b`).
- Les modèles sont automatiquement récupérés depuis l'API de votre fournisseur sélectionné lorsque vous changez de fournisseur ou cliquez sur actualiser.
- Pour les LLM locaux (Ollama/LMStudio), la liste déroulante affiche tous les modèles disponibles localement.

> Remarque : **Confiance et Santé (Trust & Health)** et **Télémétrie Anonyme (Anonymous Telemetry)** ont été déplacés vers l'onglet **Statistiques (Statistics)**.

> Remarque : **F14 Diagnostics Proactifs (Proactive Diagnostics)** est accessible depuis l'onglet **Statistiques (Statistics)** → section **Diagnostics (Diagnostics)**.
> Utilisez **Run / Refresh** pour générer un rapport, afficher la liste des problèmes et utiliser les actions fournies (comme localiser le nœud).
> Si vous avez besoin d'afficher le rapport dans une autre langue, modifiez d'abord la **Suggestion Language** dans les paramètres.

---

## Points de terminaison API

### GET `/debugger/last_analysis`

Récupérer l'analyse d'erreur la plus récente :

```bash
curl http://localhost:8188/debugger/last_analysis
```

**Exemple de réponse** :

```json
{
  "status": "running",
  "log_path": ".../logs/comfyui_debug_2025-12-28.log",
  "language": "zh_TW",
  "supported_languages": ["en", "zh_TW", "zh_CN", "ja"],
  "last_error": "Traceback...",
  "suggestion": "SUGGESTION : ...",
  "timestamp": "2025-12-28T06:49:11",
  "node_context": {
    "node_id": "42",
    "node_name": "KSampler",
    "node_class": "KSamplerNode",
    "custom_node_path": "ComfyUI-Impact-Pack"
  }
}
```

### GET `/debugger/history`

Récupérer l'historique des erreurs (20 dernières entrées) :

```bash
curl http://localhost:8188/debugger/history
```

### POST `/debugger/set_language`

Changer la langue de suggestion (voir la section Changement de langue).

### POST `/doctor/analyze`

Analyser une erreur en utilisant le service LLM configuré.

**Charge utile** :

```json
{
  "error": "Traceback...",
  "node_context": {...},
  "api_key": "your-api-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o",
  "language": "en"
}
```

**Réponse** :

```json
{
  "analysis": "AI-generated debugging suggestions..."
}
```

### POST `/doctor/verify_key`

Vérifier la validité de la clé API en testant la connexion au fournisseur LLM.

**Charge utile** :

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key"
}
```

**Réponse** :

```json
{
  "success": true,
  "message": "API key is valid",
  "is_local": false
}
```

### POST `/doctor/list_models`

Lister les modèles disponibles du fournisseur LLM configuré.

**Charge utile** :

```json
{
  "base_url": "http://localhost:11434/v1",
  "api_key": ""
}
```

**Réponse** :

```json
{
  "success": true,
  "models": [
    {"id": "llama3.1:8b", "name": "llama3.1:8b"},
    {"id": "mistral:7b", "name": "mistral:7b"}
  ],
  "message": "Found 2 models"
}
```

---

## Fichiers journaux

Tous les journaux sont stockés dans :

```text
<ComfyUI user directory>/ComfyUI-Doctor/logs/
```

Format du nom de fichier : `comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

Le système conserve automatiquement les 10 fichiers journaux les plus récents (configurable via `config.json`).

---

## Configuration

Créez `config.json` pour personnaliser le comportement :

```json
{
  "max_log_files": 10,
  "buffer_limit": 100,
  "traceback_timeout_seconds": 5.0,
  "history_size": 20,
  "default_language": "zh_TW",
  "enable_api": true,
  "privacy_mode": "basic"
}
```

**Paramètres** :

- `max_log_files` : Nombre maximum de fichiers journaux à conserver
- `buffer_limit` : Taille du tampon de traceback (nombre de lignes)
- `traceback_timeout_seconds` : Délai d'attente pour les tracebacks incomplets
- `history_size` : Nombre d'erreurs à conserver dans l'historique
- `default_language` : Langue de suggestion par défaut
- `enable_api` : Activer les points de terminaison API
- `privacy_mode` : Niveau de désinfection PII - `"none"`, `"basic"` (défaut), ou `"strict"`

---

## Motifs d'erreur pris en charge

ComfyUI-Doctor peut détecter et fournir des suggestions pour :

- Inadéquations de type (ex. fp16 vs float32)
- Inadéquations de dimension
- Mémoire CUDA/MPS insuffisante (OOM)
- Erreurs de multiplication matricielle
- Conflits périphérique/type
- Modules Python manquants
- Échecs d'assertion
- Erreurs Clé/Attribut
- Inadéquations de forme (Shape mismatches)
- Erreurs de fichier non trouvé
- Erreurs de chargement SafeTensors
- Échecs d'exécution CUDNN
- Bibliothèque InsightFace manquante
- Inadéquations Modèle/VAE
- JSON de prompt invalide

Et plus encore...

---

## Conseils

1. **Associer avec ComfyUI Manager** : Installez automatiquement les nœuds personnalisés manquants
2. **Vérifier les fichiers journaux** : Les traces complètes sont enregistrées pour le signalement des problèmes
3. **Utiliser la barre latérale intégrée** : Cliquez sur l'icône 🏥 Doctor dans le menu de gauche pour des diagnostics en temps réel
4. **Débogage de nœud** : Connectez les nœuds de débogage pour inspecter le flux de données suspect

---

## Licence

Licence MIT

---

## Contribuer

Les contributions sont les bienvenues ! N'hésitez pas à soumettre une Pull Request.

**Signaler des problèmes** : Vous avez trouvé un bug ou avez une suggestion ? Ouvrez un ticket (issue) sur GitHub.
**Soumettre des PR** : Aidez à améliorer la base de code avec des corrections de bugs ou des améliorations générales.
**Demandes de fonctionnalités** : Vous avez des idées de nouvelles fonctionnalités ? Faites-le nous savoir s'il vous plaît.
