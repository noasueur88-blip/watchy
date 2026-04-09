# Discord Secure Bot Python

Bot Discord en Python specialise dans la moderation de haute securite avec slash commands.

## Fonctionnalites

- Moderation protegee avec verification des permissions et de la hierarchie
- Commandes `/ban`, `/kick`, `/timeout`, `/untimeout`, `/purge`, `/lock`, `/unlock`
- Commande `/maintenance` pour mettre un serveur en maintenance ou le reouvrir
- Journalisation vers un salon de moderation
- Etat de maintenance conserve par serveur dans `data/guild-settings.json`

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` vers `.env` puis remplis les variables.

## Synchroniser les slash commands

```bash
python scripts/sync_commands.py
```

## Demarrage

```bash
python bot.py
```

## Commande maintenance

`/maintenance enabled:true reason:"Maintenance securite"` :
- envoie une annonce si un salon est configure
- empeche `@everyone` d'envoyer des messages dans les salons textuels
- laisse passer les roles definis dans `SECURITY_BYPASS_ROLE_IDS`

`/maintenance enabled:false` :
- retire le verrouillage applique par le bot et reouvre les salons
