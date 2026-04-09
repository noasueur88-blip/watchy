# PulsePanel Discord Pro

Panel admin moderne en Next.js avec login securise et connexion a un vrai bot Discord.

## Demarrage

1. Copier `.env.example` en `.env.local`
2. Renseigner `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `JWT_SECRET`, `DISCORD_BOT_TOKEN` et `DISCORD_GUILD_ID`
3. Lancer `npm install`
4. Lancer `npm run dev`

## Fonctions

- page de login admin
- dashboard protege par cookie HTTP-only
- route API de connexion/deconnexion
- route API qui recupere les infos du serveur Discord
- interface responsive plus propre que la version statique initiale
