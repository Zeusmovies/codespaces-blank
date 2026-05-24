import re
import aiohttp
import warnings
import logging
from io import BytesIO
from PIL import Image
from info import DREAMXBOTZ_IMAGE_FETCH, TMDB_API_KEY
from imdb import Cinemagoer


logger = logging.getLogger(__name__)
ia = Cinemagoer()
LONG_IMDB_DESCRIPTION = False

def list_to_str(lst):
    if lst:
        return ", ".join(map(str, lst))
    return ""





Image.MAX_IMAGE_PIXELS = None
warnings.simplefilter("ignore", Image.DecompressionBombWarning)
async def fetch_image(url, size=(860, 1200)):
    if not DREAMXBOTZ_IMAGE_FETCH:
        logger.info("Image fetching is disabled.")
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch image: {response.status}")
                    return None

                data = await response.read()
                img = Image.open(BytesIO(data))
                img = img.resize(size, Image.LANCZOS)


                out = BytesIO()
                img.save(out, format="JPEG")
                out.seek(0)
                return out

    except aiohttp.ClientError as e:
        logger.error(f"HTTP request error in fetch_image: {e}")
    except IOError as e:
        logger.error(f"I/O error in fetch_image: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in fetch_image: {e}")

    return None


async def get_movie_details(query, id=False, file=None):
    try:
        if not id:
            query = query.strip().lower()
            title = query
            year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1])
                title = query.replace(year, "").strip()
            elif file is not None:
                year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
                if year:
                    year = list_to_str(year[:1])
            else:
                year = None
            movieid = ia.search_movie(title.lower(), results=10)
            if not movieid:
                return None
            if year:
                filtered = list(filter(lambda k: str(k.get('year')) == str(year), movieid))
                if not filtered:
                    filtered = movieid
            else:
                filtered = movieid
            movieid = list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
            if not movieid:
                movieid = filtered
            movieid = movieid[0].movieID
        else:
            movieid = query
        movie = ia.get_movie(movieid)
        ia.update(movie, info=['main', 'vote details'])
        if movie.get("original air date"):
            date = movie["original air date"]
        elif movie.get("year"):
            date = movie.get("year")
        else:
            date = "N/A"
        plot = movie.get('plot')
        if plot and len(plot) > 0:
            plot = plot[0]
        else:
            plot = movie.get('plot outline')
        if plot and len(plot) > 800:
            plot = plot[:800] + "..."
        poster_url = movie.get('full-size cover url')
        return {
            'title': movie.get('title'),
            'votes': movie.get('votes'),
            "aka": list_to_str(movie.get("akas")),
            "seasons": movie.get("number of seasons"),
            "box_office": movie.get('box office'),
            'localized_title': movie.get('localized title'),
            'kind': movie.get("kind"),
            "imdb_id": f"tt{movie.get('imdbID')}",
            "cast": list_to_str(movie.get("cast")),
            "runtime": list_to_str(movie.get("runtimes")),
            "countries": list_to_str(movie.get("countries")),
            "certificates": list_to_str(movie.get("certificates")),
            "languages": list_to_str(movie.get("languages")),
            "director": list_to_str(movie.get("director")),
            "writer": list_to_str(movie.get("writer")),
            "producer": list_to_str(movie.get("producer")),
            "composer": list_to_str(movie.get("composer")),
            "cinematographer": list_to_str(movie.get("cinematographer")),
            "music_team": list_to_str(movie.get("music department")),
            "distributors": list_to_str(movie.get("distributors")),
            'release_date': date,
            'year': movie.get('year'),
            'genres': list_to_str(movie.get("genres")),
            'poster_url': poster_url,
            'plot': plot,
            'rating': str(movie.get("rating", "N/A")),
            'url': f'https://www.imdb.com/title/tt{movieid}'
        }
    except Exception as e:
        logger.error(f"An error occurred in get_movie_details: {e}")
        return None

async def get_movie_detailsx(query, id=False, file=None):

    try:
        api_key = TMDB_API_KEY

        async with aiohttp.ClientSession() as session:

            # SEARCH MOVIE
            search_url = "https://api.themoviedb.org/3/search/movie"

            params = {
                "api_key": api_key,
                "query": str(query).strip()
            }

            async with session.get(search_url, params=params) as resp:

                if resp.status != 200:
                    logger.error(f"TMDB Search Failed: {resp.status}")
                    return None

                data = await resp.json()

            results = data.get("results")

            if not results:
                logger.error("No TMDB results found")
                return None

            movie = results[0]

            movie_id = movie.get("id")

            # DETAILS API
            details_url = f"https://api.themoviedb.org/3/movie/{movie_id}"

            details_params = {
                "api_key": api_key,
                "append_to_response": "credits"
            }

            async with session.get(details_url, params=details_params) as detail_resp:

                if detail_resp.status != 200:
                    logger.error(f"TMDB Details Failed: {detail_resp.status}")
                    return None

                details = await detail_resp.json()

            poster_path = details.get("poster_path")
            backdrop_path = details.get("backdrop_path")

            poster_url = (
                f"https://image.tmdb.org/t/p/w500{poster_path}"
                if poster_path else None
            )

            backdrop_url = (
                f"https://image.tmdb.org/t/p/original{backdrop_path}"
                if backdrop_path else None
            )

            cast = []
            directors = []
            writers = []

            for person in details.get("credits", {}).get("cast", [])[:10]:
                cast.append(person.get("name"))

            for crew in details.get("credits", {}).get("crew", []):

                if crew.get("job") == "Director":
                    directors.append(crew.get("name"))

                if crew.get("job") in ["Writer", "Screenplay"]:
                    writers.append(crew.get("name"))

            return {
                "title": details.get("title"),
                "localized_title": details.get("original_title"),
                "year": str(details.get("release_date", ""))[:4],
                "release_date": details.get("release_date"),
                "runtime": details.get("runtime"),
                "rating": details.get("vote_average"),
                "votes": details.get("vote_count"),
                "plot": details.get("overview"),
                "poster_url": poster_url,
                "backdrop_url": backdrop_url,
                "genres": [g["name"] for g in details.get("genres", [])],
                "languages": [lang["english_name"] for lang in details.get("spoken_languages", [])],
                "countries": [c["name"] for c in details.get("production_countries", [])],
                "cast": cast,
                "director": directors,
                "writer": writers,
                "tmdb_id": movie_id,
                "tmdb_url": f"https://www.themoviedb.org/movie/{movie_id}",
                "imdb_id": details.get("imdb_id"),
                "certificates": [],
                "producer": [],
                "composer": [],
                "cinematographer": [],
                "distributors": [],
                "box_office": None,
                "tagline": details.get("tagline"),
                "seasons": None
            }

    except Exception as e:
        logger.error(f"TMDB ERROR: {e}")
        return None

