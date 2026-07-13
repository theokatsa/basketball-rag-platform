import os
import time
from datetime import date, datetime

from dotenv import load_dotenv
from nba_api.stats.endpoints import commonallplayers, commonplayerinfo
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from .env")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def _parse_season(from_year: str | None, to_year: str | None, fallback: str) -> str:
    if not from_year or not to_year:
        return fallback
    try:
        return f"{int(from_year)}-{str(int(to_year))[-2:]}"
    except ValueError:
        return fallback


def _parse_birthdate(value: str | date | None) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value.split("T")[0], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _calc_age(birthdate: date | None) -> int | None:
    if not birthdate:
        return None
    today = date.today()
    years = today.year - birthdate.year
    if (today.month, today.day) < (birthdate.month, birthdate.day):
        years -= 1
    return years


def ingest_players(
    season: str = "2024-25",
    batch_size: int = 100,
    skip_existing_profiles: bool = True,
    skip_existing_players: bool = True,
):
    print(f"Fetching NBA players for season {season}...")

    response = commonallplayers.CommonAllPlayers(
        is_only_current_season=0,
        league_id="00",
        season=season,
    )

    df = response.get_data_frames()[0]

    print(f"Fetched {len(df)} players")

    records = []
    for _, row in df.iterrows():
        nba_player_id = int(row["PERSON_ID"])
        full_name = row["DISPLAY_FIRST_LAST"]

        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        is_active = bool(row["ROSTERSTATUS"])

        records.append(
            {
                "nba_player_id": nba_player_id,
                "full_name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "is_active": is_active,
            }
        )

    upsert_sql = text(
        """
        insert into players (
            nba_player_id,
            full_name,
            first_name,
            last_name,
            is_active
        )
        values (
            :nba_player_id,
            :full_name,
            :first_name,
            :last_name,
            :is_active
        )
        on conflict (nba_player_id)
        do update set
            full_name = excluded.full_name,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            is_active = excluded.is_active;
        """
    )

    with engine.begin() as conn:
        existing_rows = conn.execute(
            text("select nba_player_id from players")
        ).mappings().all()
        existing_player_ids = {row["nba_player_id"] for row in existing_rows}

    if skip_existing_players:
        new_records = [r for r in records if r["nba_player_id"] not in existing_player_ids]
    else:
        new_records = records

    if new_records:
        with engine.begin() as conn:
            conn.execute(text("set local statement_timeout = '120s'"))
            for start in range(0, len(new_records), batch_size):
                batch = new_records[start : start + batch_size]
                conn.execute(upsert_sql, batch)
                print(
                    f"Upserted {min(start + batch_size, len(new_records))}/{len(new_records)}"
                )
    else:
        print("Players already loaded. Skipping player upserts.")

    with engine.begin() as conn:
        player_rows = conn.execute(
            text("select id, nba_player_id from players")
        ).mappings().all()
        player_id_map = {
            row["nba_player_id"]: row["id"] for row in player_rows
        }

        team_rows = conn.execute(
            text("select id, nba_team_id from teams")
        ).mappings().all()
        team_id_map = {row["nba_team_id"]: row["id"] for row in team_rows}

        existing_profile_rows = conn.execute(
            text("select player_id from player_profiles")
        ).mappings().all()
        existing_profile_ids = {row["player_id"] for row in existing_profile_rows}

    select_profile_id_sql = text(
        """
        select id
        from player_profiles
        where player_id = :player_id
        """
    )

    update_profile_sql = text(
        """
        update player_profiles
        set season = :season,
            team_id = :team_id,
            position = :position,
            age = :age,
            height = :height,
            weight = :weight,
            description = :description
        where id = :id
        """
    )

    insert_profile_sql = text(
        """
        insert into player_profiles (
            player_id,
            season,
            team_id,
            position,
            age,
            height,
            weight,
            description
        )
        values (
            :player_id,
            :season,
            :team_id,
            :position,
            :age,
            :height,
            :weight,
            :description
        )
        """
    )

    print("Fetching player bio data...")
    processed = 0
    skipped = 0

    for record in records:
        nba_player_id = record["nba_player_id"]
        player_id = player_id_map.get(nba_player_id)
        if not player_id:
            continue
        if skip_existing_profiles and player_id in existing_profile_ids:
            skipped += 1
            continue

        try:
            info = commonplayerinfo.CommonPlayerInfo(player_id=nba_player_id)
            info_df = info.get_data_frames()[0]
            if info_df.empty:
                continue

            row = info_df.iloc[0]
            team_id = team_id_map.get(int(row["TEAM_ID"])) if row["TEAM_ID"] else None
            player_season = _parse_season(row.get("FROM_YEAR"), row.get("TO_YEAR"), season)
            birthdate = _parse_birthdate(row.get("BIRTHDATE"))

            payload = {
                "player_id": player_id,
                "season": player_season,
                "team_id": team_id,
                "position": row.get("POSITION"),
                "age": _calc_age(birthdate),
                "height": row.get("HEIGHT"),
                "weight": row.get("WEIGHT"),
                "description": None,
            }

            with engine.begin() as conn:
                profile_id = conn.execute(
                    select_profile_id_sql, {"player_id": player_id}
                ).scalar()

                if profile_id:
                    payload["id"] = profile_id
                    conn.execute(update_profile_sql, payload)
                else:
                    conn.execute(insert_profile_sql, payload)

            processed += 1
            if processed % 25 == 0:
                print(f"Updated profiles: {processed}/{len(records)}")

            time.sleep(0.6)
        except Exception as exc:
            print(f"Failed profile for nba_player_id={nba_player_id}: {exc}")

    print("Done.")
    if new_records:
        print(f"Upserted players: {len(new_records)}")
    print(f"Updated profiles: {processed}")
    if skip_existing_profiles:
        print(f"Skipped existing profiles: {skipped}")


if __name__ == "__main__":
    ingest_players()
