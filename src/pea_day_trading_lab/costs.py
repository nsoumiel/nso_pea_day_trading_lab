"""Barème courant Bourse Direct, ordres en ligne PEA Paris. Decimal accounting."""
from datetime import date
from decimal import Decimal
from .models import D, money


def brokerage(notional):
    n = D(notional)
    if n < 0:
        raise ValueError('Montant négatif')
    if n == 0:
        return Decimal('0.00')
    fee = next((D(f) for limit, f in [(500, '.99'), (1000, '1.90'),
                    (2000, '2.90'), (4400, '3.80')] if n <= limit), n * D('.0009'))
    return money(min(fee, n * D('.005')))


def max_quantity(cash, price, allocation=1.0):
    budget = D(cash) * D(allocation)
    p = D(price)
    if p <= 0:
        raise ValueError('Prix invalide')
    q = max(0, int(budget / p))
    while q and money(p * q) + brokerage(p * q) > budget:
        q -= 1
    return q


def ttf(buys, sells, day, taxable=True):
    """buys=[(integer quantity, unit price)], sells=integer quantity.

    Same ISIN/account/settlement bucket only. Complete day trades -> zero.
    Not a cross-market or multi-account tax engine. Current universe is isolated.
    """
    qty = sum(q for q, _ in buys)
    if any(q < 0 for q, _ in buys) or sells < 0:
        raise ValueError('Quantités négatives')
    net = max(0, qty - sells)
    if not taxable or not qty or not net:
        return Decimal('0.00')
    rate = D('.004') if day >= date(2025, 4, 1) else D('.003')
    avg = sum(D(p) * q for q, p in buys) / qty
    return money(net * avg * rate)
