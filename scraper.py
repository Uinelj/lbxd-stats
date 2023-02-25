import requests
from bs4 import BeautifulSoup
from datetime import datetime

LBXD_BASEURL = "https://letterboxd.com/csi/film/{movie}/rating-histogram/"


def score(movie):
    """
    Get the score of a movie.

    If the movies doesn't have a score given by letterboxd,
    computes one from the individual notes given.
    """

    # get page
    url = LBXD_BASEURL.format(movie=movie)
    resp = requests.get(url).text
    soup = BeautifulSoup(resp, "html.parser")

    # timestamp
    now = datetime.now()

    # try to get averaged score
    try:
        avg_str = soup.select_one(".display-rating")["title"]
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
