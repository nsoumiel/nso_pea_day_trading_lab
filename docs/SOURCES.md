# Sources consultées le 7 octobre 2026

- yfinance, projet officiel et usage personnel : https://github.com/ranaroussi/yfinance
- Limite intraday, intervalles, auto_adjust : https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html
- Alpha Vantage intraday : endpoint premium, non retenu : https://www.alphavantage.co/documentation/
- Quota gratuit Alpha Vantage : https://www.alphavantage.co/support/
- Backtesting.py : moteur libre nécessitant les données de l'utilisateur : https://kernc.github.io/backtesting.py/
- Backtrader : framework libre : https://www.backtrader.com/
- Calendriers : https://github.com/gerrymanoim/exchange_calendars
- Tarifs Bourse Direct : https://www.boursedirect.fr/fr/bourse/tarifs
- TTF : https://bofip.impots.gouv.fr/bofip/7575-PGP.html/identifiant=BOI-TCA-FIN-10-30-20250528
- Telegram Bot API : https://core.telegram.org/bots/api
- Fin de support Python 3.9 : https://peps.python.org/pep-0596/
- Compatibilité NAS Container Manager : https://www.synology.com/fr-fr/dsm/packages/ContainerManager

Décision : aucune souscription API payante. Backtesting.py et Backtrader offrent un moteur, pas trois ans de données intraday gratuites. Un petit moteur partagé et testé a été retenu pour expliciter les contraintes communes aux 20 titres et la comptabilité PEA. L'adaptateur Yahoo ne nécessite pas de clé. Le flux n'est pas garanti temps réel : usage recherche et rejeu différé.

Les 20 titres constituent une proposition d'univers fixe, pas une certification actualisée des membres du CAC40, de leur liquidité ou de l'éligibilité PEA chez le courtier. La composition des indices et les droits de marché évoluent.
