# ComfyUI-Doctor

[English](../../README.md) | [繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | Français | [Italiano](README.it.md) | [Español](README.es.md)

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor est un assistant de diagnostic et de debogage en temps reel pour ComfyUI. Il capture les erreurs d'execution, identifie le contexte probable du noeud, affiche des suggestions locales et peut utiliser un chat LLM optionnel pour une analyse plus approfondie.

## Etat actuel

- Ajout de controles de compatibilite hote pour ComfyUI, ComfyUI frontend et Desktop.
- L'integration des reglages frontend privilegie l'API ComfyUI settings actuelle, avec les anciens fallbacks isoles dans un adaptateur de compatibilite.
- Les erreurs d'execution peuvent etre enrichies avec la lineage issue des evenements execution/progress recents.
- Le strict admin-token mode est disponible pour les serveurs partages, avec des avertissements plus clairs pour le loopback convenience mode.
- Le server-side credential store documente les metadonnees de chiffrement et la conception encrypt-then-MAC actuelle.
- Une coverage baseline lane optionnelle a ete ajoutee; le full validation flow par defaut ne change pas.

## Fonctionnalites principales

- Surveillance de la console et des tracebacks des le demarrage de ComfyUI.
- 58 patterns d'erreurs JSON: 22 core patterns et 36 community extension patterns.
- Extraction du node ID, name, class et custom-node path quand les evenements hote le permettent.
- Doctor sidebar avec onglets Chat, Statistics et Settings.
- Workflow LLM pour OpenAI-compatible APIs, Anthropic, Gemini, xAI, OpenRouter, Ollama et LMStudio.
- Privacy modes pour masquer path, credential-looking values, email et private IP avant les appels Cloud LLM.
- Server-side credential store optionnel, admin-gated, avec encryption-at-rest.
- Diagnostics, statistics, plugin trust report, telemetry controls et community feedback preview/submit.
- Support de l'anglais, chinois traditionnel, chinois simplifie, japonais, coreen, allemand, francais, italien et espagnol.

## Installation

### ComfyUI-Manager

1. Ouvrez ComfyUI et cliquez sur **Manager**.
2. Selectionnez **Install Custom Nodes**.
3. Recherchez `ComfyUI-Doctor`.
4. Installez puis redemarrez ComfyUI.

### Installation manuelle

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Apres redemarrage, **Doctor** doit apparaitre dans la sidebar gauche.

## Utilisation de base

- **Diagnostic automatique**: Doctor capture les erreurs, les compare aux patterns connus et affiche le dernier diagnostic.
- **Doctor Sidebar**: Chat pour l'erreur courante et les conversations LLM; Statistics pour les tendances, diagnostics et health information; Settings pour language, provider, model, privacy et credential source.
- **Smart Debug Node**: Ajoutez-le dans une connexion workflow pour inspecter type, shape, dtype, device et statistiques sans modifier la sortie.

## Documentation

- [User Guide](../USER_GUIDE.md)
- [Configuration and Security](../CONFIGURATION_SECURITY.md)
- [API Reference](../API_REFERENCE.md)
- [Validation Guide](../VALIDATION.md)
- [Plugin Guide](../PLUGIN_GUIDE.md)
- [Outbound Safety](../OUTBOUND_SAFETY.md)

## Validation

Windows:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Linux / WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

## Licence

MIT License
