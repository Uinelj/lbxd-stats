import requests
from enum import Enum
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from urllib.parse import urlparse

log = logging.getLogger(__name__)

LBXD_RATING_BASEURL = "https://letterboxd.com/csi/film/{movie}/rating-histogram/"
LBXD_BASEURL = "https://letterboxd.com/film/{movie}/"


def tmdb_id(movie):
    url = LBXD_BASEURL.format(movie=movie)
    resp = requests.get(url).text
    soup = BeautifulSoup(resp, "html.parser")
    for link in soup.select("a.micro-button"):
        if link.get("data-track-action") == "TMDb":
            path = urlparse(link.get("href")).path
            _id = int(path.split("/")[-2])  # get last component
            return _id
    return None


def score(movie):
    """
    Get the score of a movie.

    If the movies doesn't have a score given by letterboxd,
    computes one from the individual notes given.
    """
    log.info(f"Getting score for {movie}")

    # get page
    url = LBXD_RATING_BASEURL.format(movie=movie)
    resp = requests.get(url).text
    soup = BeautifulSoup(resp, "html.parser")

    # timestamp
    now = datetime.now()

    # try to get averaged score
    try:
        avg_str = soup.select_one(".display-rating")
        if avg_str is None:
            return None
        avg_str = avg_str["data-original-title"]
        # clean string to extract rating/count
        metrics = clean_str(avg_str, now)
        metrics["movie"] = movie
        metrics["computed"] = False
        return metrics

    except TypeError:
        # if it fails, compute one
        metrics = compute_score(soup)
        metrics["timestamp"] = now
        metrics["movie"] = movie
        metrics["computed"] = True

        return metrics

    except AttributeError as e:
        log.warn(e)
        # prolly no rating
        return None


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
    r = requests.get("https://letterboxd.com").text
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
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    movies = list()
    for movie in soup.select_one(".poster-list").findAll("div"):
        movieid = movie["data-film-slug"][
            6:-1
        ]  # move from /film/bienvenue/ to bienvenue
        movies.append(movieid)
    return movies


def popular_movies_v3(period: PopularPeriod, page: int = 1):
    """get popular movies from the popular page"""
    log.info(f"Getting popular movies for {period.value} (page {page})")
    url = f"https://letterboxd.com/films/ajax/popular/{period.value}/page/{page}"
    r = requests.get(url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    movies = list()

    for li in soup.find_all("li", class_="posteritem"):
        # Get score
        score = li.get("data-average-rating")

        # Get film data from the inner div
        div = li.find("div", class_="react-component")
        movieid = div.attrs["data-item-slug"]
        movies.append(movieid)
    return movies


def parse_list_page(list_url: str):
    r = requests.get(list_url)
    soup = BeautifulSoup(r.text, "html.parser")

    for movie in soup.select_one(".poster-list").findAll("div"):
        movieid = movie["data-film-slug"][
            6:-1
        ]  # move from /film/bienvenue/ to bienvenue
        yield movieid


def get_last_page_number(list_url: str):
    r = requests.get(list_url)
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
