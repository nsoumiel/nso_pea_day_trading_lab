# PEA Day Trading Lab — 0.1.0

Application personnelle gratuite, **simulation exclusivement**. Aucun compte Bourse Direct ni clé de courtier. Capital virtuel 5 000 EUR, une position, deux entrées maximum par jour sur l'ensemble du portefeuille. Achat du maximum d'actions entières permis par le cash après frais. Aucun levier. Le stop ATR ne plafonne donc PAS le risque à 0,25 % du capital.

## Ce qui est livré

- Package Python 3.11+, testé localement avec Python 3.12.
- Moteur commun de backtest et de rejeu paper en différé, portefeuille partagé multi-titres.
- Opening Range 15 minutes, VWAP approximatif, RVOL cumulé comparé aux 20 séances complètes précédentes, EMA20, ATR14 et filtre CAC 40.
- Achat à l'ouverture de la bougie suivant le signal ; stops/gaps, objectif 2R et sortie de séance.
- Frais Bourse Direct confirmés par l'utilisateur, plafond PEA, comptabilité Decimal et tests TTF.
- Import CSV local, collecte Yahoo via yfinance sans clé, archivage SQLite.
- Telegram sortant, journal à rotation, rapports JSON et CSV. Pas de commandes Telegram entrantes dans cette version.
- Dockerfile et Compose pour un NAS compatible Container Manager.

**Gratuité ne veut pas dire temps réel garanti.** Le connecteur Yahoo est non officiel, limité et potentiellement différé. Le moniteur est un rejeu paper en heure de marché, pas un simulateur garantissant qu'un ordre manuel aurait pu être exécuté au moment où le message est reçu. Chaque alerte porte « PAPER DIFFÉRÉ — ne pas exécuter ce signal ancien ». Aucun WebSocket revendiqué dans cette version.

## Validation de cette livraison

21 tests unitaires/intégration hors réseau réussis, plus lancement CLI demo/backtest. Les données de démonstration sont SYNTHÉTIQUES : aucun résultat de cette démonstration ne mesure une performance réelle. La collecte Yahoo, l'installation des dépendances optionnelles et le conteneur n'ont pas pu être validés de bout en bout dans l'environnement de livraison. Aucun message Telegram n'a été envoyé : le token reste chez vous.

## Démarrage sur Windows/Linux avec Python 3.12

Depuis le répertoire du projet :

```bash
python -m venv .venv
```

Linux : `source .venv/bin/activate`. Windows PowerShell : `.venv\Scripts\Activate.ps1`.

```bash
python -m pip install -e ".[yahoo]"
python -m unittest discover -s tests -v
pea-lab demo
pea-lab backtest --source synthetic
```

Sans Internet ni installation, le moteur se teste sous Linux avec :

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m pea_day_trading_lab demo
PYTHONPATH=src python -m pea_day_trading_lab backtest --source synthetic
```

La version Synology `/var/packages/Python3.9/target/usr/bin/python` n'est pas compatible avec ce projet (Python >=3.11). Préférer le conteneur Python 3.12 et conserver intact le Python géré par DSM. Voir `docs/SYNOLOGY.md`.

## Telegram

Copier `.env.example` vers `.env`, puis renseigner localement le token du bot. Le chat_id 8910228694 est déjà configuré. Ne pas partager le fichier `.env` ni committer les tokens.

```bash
pea-lab telegram-test
```

Cette commande envoie UN message au chat configuré. Les autres commandes ne contactent pas Telegram, sauf `monitor`. Aucun abonnement OpenAI ni appel API OpenAI n'est nécessaire au programme.

## Collecte gratuite et premier vrai backtest

```bash
pea-lab collect --days 59
pea-lab status
pea-lab backtest --source yahoo
```

La documentation yfinance limite les données intraday à environ 60 jours ; on demande 59 jours pour conserver une marge. Les 20 séances précédentes servent au RVOL : il restera souvent seulement quelques semaines évaluables. Des journées manquantes peuvent encore réduire cet échantillon. Un résultat à zéro trade n'est pas automatiquement un bug : vérifier l'indice, le nombre de séances complètes et la qualité des volumes.

La collecte reçoit les prix non ajustés, les horodatages de début de bougie UTC et les volumes. Elle ignore les bougies invalides, les périodes hors séance, les bougies non terminées et applique une marge supplémentaire de 20 minutes. Cette marge ne garantit PAS que Yahoo soit à jour. Toute erreur/limitation Yahoo est journalisée ; aucune donnée synthétique ne sert de remplacement à Yahoo. Les doublons sont ignorés, les premières observations stockées sont immuables.

Commencer par 5 titres si Yahoo limite les requêtes : TTE.PA, BNP.PA, AI.PA, MC.PA, SU.PA. Le reste peut être ajouté pour les backtests. Ne pas multiplier les processus ni contourner les limites Yahoo. Les droits de réutilisation des données dépendent du fournisseur ; usage personnel de recherche prévu.

## Rejeu paper continu

Après une collecte initiale complète pour préchauffer les indicateurs :

```bash
pea-lab monitor --once --no-telegram
pea-lab monitor
```

Le run `paper-1` commence à l'heure du premier lancement. Aucun trade historique n'est présenté comme une nouvelle opportunité. Les données ultérieurement reçues sont traitées dans l'ordre des heures de marché ; les alertes arrivent donc en différé. Le cash du portefeuille est conservé entre séances et reconstruit de manière déterministe après redémarrage.

Une modification ou un ajout tardif à l'historique déjà traité provoque un arrêt explicite, pour ne pas réécrire silencieusement les résultats. Après diagnostic, un nouveau laboratoire peut être démarré avec `--run-id paper-2`. Modifier la configuration exige également un nouveau run. Ne pas lancer deux moniteurs sur la même base. Après un arrêt brutal, le répertoire `data/lab.sqlite3.monitor.lock` peut rester présent : vérifier qu'aucun moniteur ne tourne avant de le supprimer.

Notifications mises en file d'attente SQLite avec identifiants stables et dix essais maximum ; après dix échecs elles restent en base pour diagnostic. Livraison « au moins une fois » : une réponse HTTP perdue peut exceptionnellement entraîner un doublon. Pas de promesse de livraison exactement une fois.

## Données CSV et calendrier

```text
symbol,timestamp_utc,open,high,low,close,volume
TTE.PA,2026-10-06T07:00:00+00:00,55,55.1,54.9,55.05,100000
```

Chaque ligne représente une bougie de cinq minutes TERMINÉE, étiquetée à son début. Inclure les bougies de `^FCHI` aux mêmes horaires. Volume zéro autorisé pour l'indice ; il n'est pas utilisé dans son filtre. Les prix doivent être bruts et tous issus d'une convention cohérente.

Calendrier CSV obligatoire, correspondant à la séance continue, hors enchère de clôture :

```text
date,open_utc,close_utc
2026-10-06,2026-10-06T07:00:00+00:00,2026-10-06T15:30:00+00:00
```

```bash
pea-lab import-csv mes_bougies.csv --calendar calendrier.csv --source local
pea-lab backtest --source local --trade-start 2026-09-15T00:00:00Z
```

`--trade-start` réserve les données précédentes au préchauffage. Faire varier ce point sans consulter/optimiser la période finale. Ne pas comparer uniquement le meilleur réglage sur le même petit historique.

## Lecture des résultats

`data/reports/<run>/report.json` : cash, equity valorisée nette de frais de liquidation estimés, PnL réalisé net, frais payés, win rate, profit factor, drawdown, statut flat, symboles manquants et empreinte des données. `trades.csv` contient toutes les transactions clôturées, `equity.csv` la courbe de capital. Les événements/signaux et runs sont également conservés dans SQLite.

Le PnL avant frais est calculé sur les prix exécutés AVEC glissement, donc ne doit pas être interprété comme un résultat sans spread. `slippage_bps` inclut demi-spread + glissement par côté, en plus du courtage. Comparer 2, 5 et 10 points de base par côté. 5 points de base = 0,05 % par côté. Les bornes de perte ne sont pas garanties en cas de gap.

Tarification actuelle appliquée à toute la période : 0,99 / 1,90 / 2,90 / 3,80 EUR, puis 0,09 %, avec plafond PEA 0,5 %. Les exécutions sont intégrales et les frais par ordre ; pas de modélisation des exécutions partielles.

La TTF des trades intégralement clôturés dans la journée est nulle en quantité, quelle que soit leur performance. Le module `costs.ttf` teste aussi les positions nettes résiduelles et le changement de taux en avril 2025, mais ne constitue pas un moteur fiscal général. Si une position ne peut être liquidée, `ttf_total` est null et les résultats sont incomplets : aucune exonération inventée.

## Limites de la version 0.1

- Pas d'ordres réels, pas d'interface graphique, pas de commandes Telegram entrantes.
- Pas de flux européen gratuit temps réel garanti ; Yahoo peut changer son API, retarder les données ou renvoyer HTTP 429.
- Calendrier XPAR fourni par exchange_calendars, à maintenir avec les annonces Euronext. Calendrier synthétique distinct pour la démo.
- Univers fixe actuel : biais de survivance. Éligibilité PEA de chaque ligne à vérifier dans Bourse Direct avant toute utilisation réelle. Pas de référentiel réglementaire historique automatique.
- Splits/dividendes non corrigés automatiquement : prix bruts. Vérifier/exclure les séances concernées, ou importer un historique retraité de façon cohérente. Aucun résultat réel certifié en leur présence.
- VWAP approximé par (high+low+close)/3 ; ATR = moyenne simple des 14 true ranges (pas lissage Wilder). EMA continue entre séances ; OR/VWAP remis à zéro chaque séance.
- RVOL : 20 séances antérieures complètes uniquement, comparées à la même heure ; les séances raccourcies ne fournissent pas de référence pour des horaires inexistants.
- Arrêt des entrées 60 minutes avant la clôture ; sortie à l'ouverture de la bougie située 10 minutes avant. Si données absentes pendant une position, le backtest est invalidé au lieu d'inventer une exécution.
- Pas de ventes partielles ; refus si la taille dépasse 1 % du volume de la bougie précédant l'entrée. Si stop et objectif touchés dans une même bougie, stop prioritaire.
- Recalcul complet du run à chaque cycle pour une logique déterministe simple, acceptable sur l'historique court ; une prochaine version pourra sérialiser l'état des indicateurs pour les gros historiques.
- Pas de statistiques annuelles extrapolées sur quelques semaines. Pas de mesure de rentabilité réelle fournie avec cette livraison.

Documentation détaillée : `docs/ARCHITECTURE.md`, `docs/SOURCES.md`, `docs/UNIVERSE.csv`.
