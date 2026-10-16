"""Bezpečné chyby a ohraničené opakovanie verejných HTTP požiadaviek."""
import time
import requests


class DataError(Exception):
    pass


def error_reason(exc):
    """Nikdy nevracaj surovú URL alebo odpoveď obsahujúcu kľúč."""
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', None) or getattr(exc, 'status_code', None)
    if 'proxy' in name or 'tunnel connection' in message or 'connect tunnel' in message:
        return 'Prístup zablokoval alebo prerušil sieťový proxy; overte povolené domény.'
    if status == 429 or 'ratelimit' in name or 'too many requests' in message:
        return 'Limit API (HTTP 429); skúste neskôr. Zmena tickera tento limit neopraví.'
    if status in (401,403) or any(s in message for s in ('401', '403', 'invalid crumb', 'unauthorized')):
        return 'Poskytovateľ odmietol prístup (HTTP 401/403 alebo neplatná relácia); nejde o dôkaz nesprávneho tickera.'
    if status == 404:
        return 'Poskytovateľ nenašiel záznam (HTTP 404); overte symbol a pokrytie zdroja.'
    if 'timeout' in name or 'timed out' in message:
        return 'Vypršal čas požiadavky; skúste neskôr.'
    if status and status >= 500:
        return 'Dočasná chyba servera poskytovateľa (HTTP 5xx).'
    if 'ssl' in name or 'certificate' in message:
        return 'Zlyhalo overenie TLS certifikátu; overenie nebolo vypnuté.'
    if 'connection' in name:
        return 'Nepodarilo sa nadviazať sieťové spojenie.'
    return 'Zdroj vrátil neúplnú alebo nespracovateľnú odpoveď; správnosť tickera nemožno potvrdiť.'


def get_json(url, **kwargs):
    # Max. dve požiadavky. Dlhý Retry-After sa rešpektuje tým, že sa pokus neopakuje.
    for attempt in range(2):
        try:
            response = requests.get(url, timeout=20, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                delay = response.headers.get('Retry-After', '1')
                if attempt == 0 and delay.isdigit() and int(delay) <= 2:
                    time.sleep(max(1, int(delay)))
                    continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise DataError('Zdroj nevrátil JSON objekt.')
            return payload
        except requests.RequestException as exc:
            raise DataError(error_reason(exc)) from None
        except ValueError:
            raise DataError('Zdroj nevrátil platné JSON dáta.') from None
