# Installation Synology

Le modèle exact et la version DSM restent à confirmer. La méthode ci-dessous suppose que Container Manager (ou Docker selon DSM) est disponible pour le NAS.

1. Dans DSM, installer Container Manager via le Centre de paquets.
2. Extraire cette archive dans un dossier, par exemple `/volume1/docker/pea_day_trading_lab` (adapter au volume réel).
3. Copier `.env.example` vers `.env`. Renseigner seulement le token Telegram localement.
4. Ouvrir une session SSH avec un compte autorisé à utiliser Docker. Se placer dans le dossier du projet.

```bash
cd /volume1/docker/pea_day_trading_lab
mkdir -p data
docker compose build
docker compose run --rm pea-lab demo
docker compose run --rm pea-lab backtest --source synthetic
docker compose run --rm pea-lab telegram-test
docker compose run --rm pea-lab collect --days 59
docker compose run --rm pea-lab backtest --source yahoo
```

Selon l'installation, la commande peut être `docker-compose`. Ne pas désinstaller/remplacer le Python Synology. L'image Python 3.12 est indépendante du Python de DSM. La construction télécharge des dépendances publiques gratuites ; elle nécessite Internet.

Après vérification de la collecte et de la connexion Telegram :

```bash
docker compose up -d
docker compose logs --tail 100 -f
```

Le fichier Compose démarre `monitor`. Aucun port n'est exposé, aucune clé OpenAI/Bourse Direct n'est demandée. Pour arrêter :

```bash
docker compose down
```

Les fichiers persistent dans le dossier `data` monté dans le conteneur. Par prudence, le conteneur ne redémarre pas automatiquement après une erreur : consulter les logs et résoudre la cause avant de relancer. Les écritures du conteneur peuvent appartenir à root ; adapter `user: UID:GID` et les permissions du dossier selon le compte DSM choisi, sans chmod global.

L'interface Container Manager peut aussi créer un Projet à partir du dossier contenant `compose.yaml`. Ne lancer le projet qu'après la collecte initiale. Sans accès Docker/Container Manager, demander une installation Python utilisateur >=3.11 adaptée au modèle exact ; le chemin Python3.9 fourni ne suffit pas.

Sauvegarde : arrêter le moniteur puis copier tout le dossier `data`, y compris d'éventuels fichiers SQLite WAL/SHM, ou utiliser l'API sqlite3.backup. Ne pas sauvegarder uniquement le fichier principal pendant une écriture.
