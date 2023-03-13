import logging
import os
from dataclasses import dataclass

import psycopg2
import requests
from telegram.ext import CommandHandler, Updater

conn = psycopg2.connect(
    host="your_host",
    database="codeforces",
    user="your_username",
    password="your_password",
)

cursor = conn.cursor()


@dataclass
class Problem:
    name: str
    number: str
    tags: list[str]
    solved_count: int
    rating: int


def get_all_problems() -> list[Problem]:
    problems_resp = _request_all_problems()
    return _map_problems(problems_resp)


# call the get_all_problems function and save the result to a variable
all_problems = get_all_problems()


def _request_all_problems() -> dict:
    endpoint = "https://codeforces.com/api/problemset.problems"
    resp = requests.get(endpoint)
    return resp.json()


def _map_problems(problems_response: dict) -> list[Problem]:
    problems_part = problems_response["result"]["problems"]
    statistics = problems_response["result"]["problemStatistics"]

    problems = []
    for p, s in zip(problems_part, statistics):
        problem = Problem(
            number=_get_number(p),
            rating=_get_rating(p),
            name=p["name"],
            tags=p["tags"],
            solved_count=s["solvedCount"],
        )

        problems.append(problem)

    return problems


def _get_rating(problems_response: dict) -> int:
    rating = 0
    if "rating" in problems_response:
        rating = problems_response["rating"]

    return rating


def _get_number(problems_response: dict) -> str:
    return str(problems_response["contestId"]) + problems_response["index"]


def save_problems_to_db(
    problems: list[Problem],
    conn: psycopg2.extensions.connection,
    cursor: psycopg2.extensions.cursor,
) -> None:
    for problem in problems:
        cursor.execute(
            """
            INSERT INTO problems (name, number, tags, solved_count, rating)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                problem.name,
                problem.number,
                problem.tags,
                problem.solved_count,
                problem.rating,
            ),
        )

    conn.commit()


all_problems = get_all_problems()

save_problems_to_db(all_problems, conn, cursor)

cursor.close()
conn.close()


# Retrieve problems from database
def get_problems_from_db(rating: int, tag: str) -> list[Problem]:
    cursor.execute(
        """
        SELECT name, number, tags, solved_count, rating FROM problems
        WHERE rating = %s AND %s = ANY(tags)
        ORDER BY solved_count DESC
        LIMIT 10
        """,
        (rating, tag),
    )

    problems = []
    for p in cursor.fetchall():
        problem = Problem(
            name=p[0], number=p[1], tags=p[2], solved_count=p[3], rating=p[4]
        )
        problems.append(problem)

    return problems


from dotenv import load_dotenv

load_dotenv()


logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s, %(levelname)s, %(name)s, %(message)s"
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fmtstr = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
fmtdate = "%H:%M:%S"
formatter = logging.Formatter(fmtstr, fmtdate)


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "Welcome to the Codeforces problems bot! Type /help for more information."
    )


def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "To get problems by rating and tag, type:\n/rating <rating> <tag>"
    )


def rating_command(update, context):
    try:
        rating, tag = context.args
        rating = int(rating)
    except ValueError:
        update.message.reply_text(
            "Invalid input. Please enter a rating followed by a tag."
        )
        return

    problems = get_problems_from_db(rating, tag)
    if not problems:
        update.message.reply_text("No problems found.")
        return

    response = "Here are the top 10 problems:\n"
    for i, problem in enumerate(problems):
        response += f"{i + 1}. {problem.name} (solved count: {problem.solved_count}, rating: {problem.rating})\n"
    update.message.reply_text(response)


def main() -> None:
    updater = Updater(os.environ.get("TELEGRAM_BOT_TOKEN"))

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("rating", rating_command))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
