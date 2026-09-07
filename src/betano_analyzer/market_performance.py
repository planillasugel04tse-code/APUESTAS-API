from __future__ import annotations

from .db import connect


def performance_by_competition_market() -> list[dict]:
    with connect() as db:
        rows = db.execute("""SELECT m.competition,
                                      LOWER(COALESCE(p.conservative_market,p.original_market)) AS market,
                                      COUNT(*) AS picks,
                                      SUM(pr.result='won') AS wins,
                                      SUM(pr.result='lost') AS losses,
                                      SUM(pr.result='push') AS pushes,
                                      SUM(CASE WHEN pr.result='won' THEN COALESCE(pr.actual_odds,p.conservative_odds,p.original_odds)-1
                                               WHEN pr.result='lost' THEN -1 ELSE 0 END) AS units
                               FROM pick_results pr JOIN picks p ON p.id=pr.pick_id
                               JOIN matches m ON m.id=p.match_id
                               WHERE pr.result IN ('won','lost','push')
                               GROUP BY m.competition, market ORDER BY units DESC""").fetchall()
    result = []
    for row in rows:
        n = row["picks"]
        units = row["units"] or 0.0
        result.append({"competition": row["competition"], "market": row["market"], "picks": n,
                       "wins": row["wins"], "losses": row["losses"], "pushes": row["pushes"],
                       "hit_rate": (row["wins"] or 0) / n if n else 0.0, "units": units,
                       "roi": units / n if n else 0.0,
                       "sample_status": "insuficiente" if n < 30 else "usable" if n < 100 else "robusto"})
    return result
