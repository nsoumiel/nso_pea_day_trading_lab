# Architecture 0.1

## Modules livrés

| Fichier | Rôle |
|---|---|
| models.py | Contrats Bar et Config, validation, UTC, Decimal |
| providers.py | CSV et adaptateur Yahoo facultatif |
| calendar.py | Calendrier XPAR/CSV et horaires de liquidation |
| strategy.py | Indicateurs causaux et stratégie pure |
| costs.py | Courtage, quantité all-in, TTF par panier de règlement |
| engine.py | Moteur multi-actifs partagé, portefeuille, fills, statistiques |
| storage.py | SQLite WAL, schéma versionné, bougies immuables, événements et file Telegram |
| notifications.py | Telegram sortant et secrets locaux |
| cli.py | Collecte, backtest, rejeu paper différé, reprise et exports |
| demo.py | Données SYNTHÉTIQUES isolées sous source=synthetic |

Stratégie -> signal -> ordre virtuel en attente -> exécution suivante -> portefeuille -> événement enregistré -> notification. Une unique instance du portefeuille pour tous les titres. La priorité entre signaux de même instant est RVOL décroissant puis symbole alphabétique.

Le futur fournisseur WebSocket doit produire le même contrat Bar, en indiquant clairement la provenance et les droits. Ne jamais mélanger des volumes de places différentes sous une même source. Le futur moteur temps réel devra distinguer heure de marché, réception et exécution, et traiter les prix réellement disponibles après réception d'un signal. Le mode actuel est volontairement nommé delayed-paper.

## Stockage

Tables bars, sessions, runs, events, notifications, schema_version. runs contient configuration, rapport et état du moniteur ; events conserve SIGNAL, REJECTED, BUY, SELL. Les autres candidats ne satisfaisant pas la stratégie ne créent pas d'événement pour éviter une avalanche de lignes. Version de code et SHA256 du jeu de données dans chaque rapport. Le schéma est initialisé en version 1 ; les migrations futures devront être explicites.

Les frais sont arrondis au centime. Les prix simulés gardent les décimales nécessaires ; quantités toujours entières. Le stop et l'objectif restent fixes après l'achat dans cette stratégie initiale. La capacité en actions utilise le cash effectif du moment et les frais d'entrée.

## Validation avant élargissement

1. Valider 5 symboles et l'indice sur le NAS avec status.
2. Vérifier les heures, volumes, séances complètes et événements d'entreprise.
3. Vérifier qu'un premier backtest réel est exploitable (même si zéro trade).
4. Collecter progressivement plusieurs mois et séparer les périodes de recherche/validation/test.
5. Mesurer la sensibilité aux coûts. Aucun retour réel avant preuve de fraîcheur et d'exécutabilité.

Extensions prévues : adaptateur WebSocket qualifié, instrument master ISIN/PEA/TTF daté, actions de sociétés, état incrémental, dashboard, commandes Telegram autorisées, analyses par mois et exposition. Aucune de ces extensions n'est présentée comme déjà implémentée.
