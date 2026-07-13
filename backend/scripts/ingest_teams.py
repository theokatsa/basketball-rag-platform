from sqlalchemy import text
from nba_api.stats.static import teams

from db_utils import engine


def ingest_teams():
    nba_teams = teams.get_teams()

    with engine.begin() as conn:
        for team in nba_teams:
            conn.execute(
                text(
                    """
                    insert into teams (
                        nba_team_id,
                        abbreviation,
                        full_name,
                        city,
                        nickname,
                        state,
                        year_founded
                    )
                    values (
                        :nba_team_id,
                        :abbreviation,
                        :full_name,
                        :city,
                        :nickname,
                        :state,
                        :year_founded
                    )
                    on conflict (nba_team_id)
                    do update set
                        abbreviation = excluded.abbreviation,
                        full_name = excluded.full_name,
                        city = excluded.city,
                        nickname = excluded.nickname,
                        state = excluded.state,
                        year_founded = excluded.year_founded;
                    """
                ),
                {
                    "nba_team_id": team["id"],
                    "abbreviation": team["abbreviation"],
                    "full_name": team["full_name"],
                    "city": team["city"],
                    "nickname": team["nickname"],
                    "state": team["state"],
                    "year_founded": team["year_founded"],
                },
            )

    print(f"Upserted {len(nba_teams)} teams.")


if __name__ == "__main__":
    ingest_teams()
