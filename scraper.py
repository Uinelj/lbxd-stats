import json
import re
import time

import requests
from enum import Enum
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from urllib.parse import urlparse

log = logging.getLogger(__name__)

LBXD_RATING_BASEURL = "https://letterboxd.com/csi/film/{movie}/rating-histogram/"
LBXD_BASEURL = "https://letterboxd.com/film/{movie}/"
LBXD_HOMEPAGE = "https://letterboxd.com/"

# Letterboxd/Cloudflare now reject requests that look like bots: the default
# `python-requests` User-Agent is met with a "Just a moment..." 403 challenge
# page, and the /csi and /films/ajax fragment endpoints are challenged unless
# the request carries full browser headers. This session is shared by every
# request so the daily fetch never crashes on a 403 (same technique as the
# https://github.com/Uinelj/letttermcp project).
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
_BROWSER_HEADERS = {
    "User-Agent": _BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://letterboxd.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

_CLOUDFLARE_RE = re.compile(r"<title>\s*Just a moment", re.IGNORECASE)
_LD_JSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

session = requests.Session()
session.headers.update(_BROWSER_HEADERS)


class LetterboxdError(Exception):
    """Raised when Letterboxd cannot be scraped (e.g. a Cloudflare challenge)."""


def _get(url, retries=5, backoff=2.5):
    """GET a Letterboxd URL with browser headers, retrying on Cloudflare challenges.

    Returns the requests.Response for a successful (non-challenged) response,
    or for a genuine HTTP error (the caller decides how to handle it). Raises
    LetterboxdError only if the Cloudflare challenge persists after all retries.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=20)
        except requests.RequestException as e:
            last_exc = e
            log.info(
                f"network error for {url} (attempt {attempt}/{retries}): "
                f"{type(e).__name__}: {e}"
            )
        else:
            if resp.status_code == 200 and not _CLOUDFLARE_RE.search(resp.text):
                return resp
            # 403/401/429 or a "Just a moment" challenge -> retryable
            if (
                resp.status_code in (401, 403, 429)
                or _CLOUDFLARE_RE.search(resp.text)
            ):
                log.info(
                    f"Letterboxd blocked {url} (status={resp.status_code}, "
                    f"attempt {attempt}/{retries})"
                )
            else:
                # genuine 4xx/5xx (e.g. 404) -> let the caller decide
                return resp
        if attempt < retries:
            time.sleep(backoff * attempt)
    if last_exc is not None:
        raise LetterboxdError(f"Could not fetch {url}: {last_exc}")
    raise LetterboxdError(f"Cloudflare challenge persisted for {url}")


def tmdb_id(movie):
    """Get the TMDB id for a Letterboxd movie slug from its film page."""
    url = LBXD_BASEURL.format(movie=movie)
    try:
        resp = _get(url)
    except LetterboxdError:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    # Letterboxd now exposes the TMDB id as a data attribute on the film page.
    el = soup.select_one("[data-tmdb-id]")
    if el is not None and el.get("data-tmdb-id"):
        try:
            return int(el["data-tmdb-id"])
        except (TypeError, ValueError):
            pass
    # Fallback: the external TMDb link (its data-track-action is now "TMDB").
    for link in soup.find_all("a"):
        action = link.get("data-track-action") or ""
        if action.upper() == "TMDB" and link.get("href"):
            path = urlparse(link.get("href")).path
            try:
                return int(path.split("/")[-2])  # get last component
            except ValueError:
                continue
    return None


def score(movie):
    """
    Get the score of a movie (weighted average + number of ratings).

    Letterboxd used to expose this on the /csi/film/<movie>/rating-histogram/
    page (the .display-rating element, which has since been removed) and that
    endpoint is now behind a Cloudflare challenge. We read the same numbers
    from the film page's JSON-LD aggregateRating instead. The returned schema is
    kept identical so it stays compatible with the existing measures.jsonl
    history.
    """
    log.info(f"Getting score for {movie}")

    now = datetime.now()
    url = LBXD_BASEURL.format(movie=movie)
    try:
        resp = _get(url)
        resp.raise_for_status()
    except (LetterboxdError, requests.HTTPError) as e:
        log.info(f"could not get score for {movie}: {e}")
        return None

    m = _LD_JSON_RE.search(resp.text)
    if not m:
        return None
    raw = m.group(1).replace("/* <![CDATA[ */", "").replace("/* ]]> */", "").strip()
    raw = _HTML_COMMENT_RE.sub("", raw).strip()
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    aggregate = (data.get("aggregateRating") or {}) if isinstance(data, dict) else {}
    rating = aggregate.get("ratingValue")
    count = aggregate.get("ratingCount")
    if rating is None or count is None:
        return None
    return {
        "rating": float(rating),
        "count": int(count),
        "timestamp": now,
        "movie": movie,
        "computed": False,
    }


def clean_str(s, timestamp):
    """
    Goes from `Weighted average of 4.08 based on 222,119 ratings`
    to `{'rating': 4.08, 'count': 222386}`
    """
    toks = s.split(" ")
    rating = float(toks[3])
    count = int(toks[6].split("\xa0")[0].replace(",", ""))
    # datetime object containing current date and time
    return {"rating": rating, "count": count, "timestamp": timestamp}


def compute_score(soup):
    """
    Computes a score from the list of individual notes
    """
    score = 0.0
    counts = 0

    # get vote list
    assert len(soup.select_one(".rating-histogram ul").findAll("li")) == 10

    for star_idx, li in enumerate(
        soup.select_one(".rating-histogram ul").findAll("li")
    ):
        rating = (star_idx) / 2.0 + 0.5

        # it means there's no votes
        if li.text.strip() == "":
            count = 0
        else:
            tok = int(li.text.split("\xa0")[0])
            count = tok
        score += rating * count
        counts += count
    return {"rating": score / counts, "count": counts}


def popular_movies():
    """get popular movies and their scores"""
    r = _get("https://letterboxd.com").text
    soup = BeautifulSoup(r, "html.parser")
    movies = list()
    for movie in soup.select_one(".-p150").findAll("li"):
        movieid = movie["data-film-slug"][
            6:-1
        ]  # move from /film/bienvenue/ to bienvenue
        movies.append(movieid)
    return movies


class PopularPeriod(Enum):
    AllTime = ""
    Year = "this/year"
    Month = "this/month"
    Week = "this/week"


def popular_movies_v2(period: PopularPeriod, page: int = 1):
    """get popular movies from the popular page"""
    log.info(f"Getting popular movies for {period.value} (page {page})")
    url = f"https://letterboxd.com/films/ajax/popular/{period.value}/page/{page}"
    r = _get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    movies = list()
    for movie in soup.select_one(".poster-list").findAll("div"):
        movieid = movie["data-film-slug"][
            6:-1
        ]  # move from /film/bienvenue/ to bienvenue
        movies.append(movieid)
    return movies


def popular_movies_v3(period: PopularPeriod, page: int = 1):
    """get popular movies from the popular browser-list fragment"""
    log.info(f"Getting popular movies for {period.value} (page {page})")
    # Letterboxd moved the popular listing from /films/ajax/popular/<period>/
    # (now a 404) to the /csi/films/films-browser-list/popular/<period>/ fragment.
    if period.value:
        url = (
            f"https://letterboxd.com/csi/films/films-browser-list/popular/"
            f"{period.value}/"
        )
    else:
        url = "https://letterboxd.com/csi/films/films-browser-list/popular/"
    try:
        r = _get(url)
        r.raise_for_status()
    except (LetterboxdError, requests.HTTPError) as e:
        log.warning(
            f"could not fetch popular movies for {period.value or 'AllTime'}: {e}"
        )
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    movies = list()
    poster_list = soup.select_one(".poster-list")
    root = poster_list if poster_list is not None else soup
    for div in root.find_all("div", attrs={"data-item-slug": True}):
        # data-item-slug is the clean film slug (e.g. "interstellar"); strip any
        # leading /film/ just in case the markup changes again.
        slug = div["data-item-slug"].strip("/").split("/")[-1]
        if slug:
            movies.append(slug)
    return movies


def popular_movies_homepage():
    """Scrape film slugs from the Letterboxd home page.

    The home page is served without a Cloudflare challenge (unlike the
    /csi/films/films-browser-list/popular fragment), so it is a reliable way to
    keep ingesting new films even when the popular-listing ajax endpoint is
    blocked. See https://github.com/Uinelj/letttermcp for the same technique.
    """
    log.info("Getting popular movies from the home page")
    try:
        resp = _get(LBXD_HOMEPAGE)
        resp.raise_for_status()
    except (LetterboxdError, requests.HTTPError) as e:
        log.warning(f"could not fetch home page: {e}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    movies = []
    seen = set()
    for el in soup.find_all(attrs={"data-item-slug": True}):
        # Only keep actual films (skip lists / people): the poster link must
        # point to /film/<slug>/.
        link = el.get("data-target-link") or el.get("data-item-link") or ""
        if "/film/" not in link:
            continue
        slug = el["data-item-slug"].strip("/").split("/")[-1]
        if slug and slug not in seen:
            seen.add(slug)
            movies.append(slug)
    return movies


def parse_list_page(list_url: str):
    r = _get(list_url)
    soup = BeautifulSoup(r.text, "html.parser")

    for movie in soup.select_one(".poster-list").findAll("div"):
        movieid = movie["data-film-slug"][
            6:-1
        ]  # move from /film/bienvenue/ to bienvenue
        yield movieid


def get_last_page_number(list_url: str):
    r = _get(list_url)
    soup = BeautifulSoup(r.text, "html.parser")
    # get last item in pagination links
    try:
        last = (
            soup.select_one(".paginate-pages > ul:nth-child(1)")
            .findAll("a")[-1]
            .get_text()
        )
    except AttributeError as e:
        log.info(f"list {list_url} probably has no pagination.")
        log.debug(e)
        last = 1

    print(last)
    return int(last)


def parse_list(list_url: str, page_start=None, page_end=None):
    """
    Gets movies from list
    """
    log.info(f"Getting movies from list at {list_url}")
    movies = list()
    current_page = page_start if page_start is not None else 1

    if page_end is None:
        # get max page
        page_end = get_last_page_number(list_url)

    log.info(f"Getting list {list_url} (pages {page_start}->{page_end})")
    for page_number in range(current_page, page_end + 1):
        list_page_url = list_url + f"/page/{page_number}"
        print(list_page_url)
        movies.extend(parse_list_page(list_page_url))
    return movies


if __name__ == "__main__":
    # testing on regular lists
    print(parse_list("https://letterboxd.com/ujj/list/top-2022/"))
    # testing on watchlist
    print(parse_list("https://letterboxd.com/ujj/watchlist/"))
    # testing on film lists
    print(parse_list("https://letterboxd.com/ujj/films/"))
