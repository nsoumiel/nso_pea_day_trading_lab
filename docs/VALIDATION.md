# Validation 0.1.0

- Python 3.12.14.
- 21 tests unittest réussis (frais, TTF, cash, exécution, trous de données, calendrier, indicateurs, répétabilité et absence d'anticipation).
- CLI demo : 7 956 bougies SYNTHÉTIQUES, isolées de Yahoo.
- CLI backtest --source synthetic : exécution complète, 6 trades clos, aucune position finale. Ces chiffres vérifient le logiciel, pas sa rentabilité.
- Compilation de tous les modules réussie.
- Intégrations Yahoo/exchange_calendars, Telegram et construction Docker non validées en réseau dans l'environnement de livraison. Aucun téléchargement réel ni message Telegram revendiqué.
- La validation automatique de l'installation des dépendances réseau a échoué faute de disponibilité du service de revue. Les tests locaux ne nécessitent pas ces dépendances optionnelles.
