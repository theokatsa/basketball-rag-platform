from sqlalchemy import text
from sqlalchemy.orm import Session


def get_all_teams(db: Session):
    sql = text(
        """
        select id,
               nba_team_id,
               abbreviation,
               full_name,
               city,
               nickname,
               state,
               year_founded
        from teams
        order by full_name
        """
    )
    return db.execute(sql).mappings().all()


def get_team_by_id(db: Session, team_id: int):
    sql = text(
        """
        select id,
               nba_team_id,
               abbreviation,
               full_name,
               city,
               nickname,
               state,
               year_founded
        from teams
        where id = :team_id
        """
    )
    return db.execute(sql, {"team_id": team_id}).mappings().first()
