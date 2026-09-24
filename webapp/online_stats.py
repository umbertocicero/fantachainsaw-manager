"""Importa statistiche stagionali dalle schede ufficiali Fantacalcio."""
import re
import unicodedata
from urllib.parse import quote
from urllib.request import Request, urlopen


USER_AGENT = "FantaAstaLive/1.0 (+local fantasy football tool)"


def _slug(value):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value


def _number(value):
    match = re.search(r"-?\d+(?:[,.]\d+)?", re.sub(r"<[^>]+>", " ", value))
    if not match:
        return None
    return float(match.group().replace(",", "."))


def _structured_value(html, label):
    pattern = (
        r'<th[^>]*itemprop="name description"[^>]*>\s*'
        + re.escape(label)
        + r"\s*</th>\s*<td[^>]*>(.*?)</td>"
    )
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return _number(match.group(1)) if match else None


def fetch_player_stats(player, timeout=8):
    """Restituisce le statistiche stagionali ufficiali, oppure None se la scheda
    non è raggiungibile o il formato della pagina è cambiato."""
    url = (
        "https://www.fantacalcio.it/serie-a/squadre/"
        f"{quote(_slug(player['squadra']))}/{quote(_slug(player['nome']))}/{player['id']}"
    )
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception:
        return None

    matches = _structured_value(html, "Partite a voto")
    goals = _structured_value(html, "Gol")
    assists = _structured_value(html, "Assist")
    if matches is None or goals is None or assists is None:
        return None

    media_match = re.search(
        r'<meta[^>]+itemprop="name description"[^>]+content="Media voto".*?'
        r'<meta[^>]+itemprop="value"[^>]+content="([^"]+)"',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    fantamedia_match = re.search(
        r'<meta[^>]+itemprop="name description"[^>]+content="FantaMedia".*?'
        r'<meta[^>]+itemprop="value"[^>]+content="([^"]+)"',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    media = _number(media_match.group(1)) if media_match else None
    fantamedia = _number(fantamedia_match.group(1)) if fantamedia_match else None
    if fantamedia is None:
        return None

    return {
        "partite_valutate": int(matches),
        "gol": int(goals),
        "assist": int(assists),
        "media_voto": media,
        "fantamedia": fantamedia,
        "fantamedia_corretta": fantamedia,
        "online_url": url,
    }
