"""Current professional teams displayed by the league-wide application."""
import re

PRO_TEAM_NAMES = (
    'OpTic Texas',
    'Los Angeles Thieves',
    'FaZe Vegas',
    'Paris Gentle Mates',
    'Toronto KOI',
    'G2 Minnesota',
    'Riyadh Falcons',
    'Miami Heretics',
)


def normalize_team_name(value: str | None) -> str:
    """Lowercase and strip everything but ASCII letters/digits, for name comparisons."""
    return re.sub(r'[^a-z0-9]', '', (value or '').lower())


PRO_TEAM_NAMES_BY_NORMALIZED_NAME = {
    normalize_team_name(name): name
    for name in PRO_TEAM_NAMES
}


# This is the current 2026 professional roster snapshot. It is intentionally
# separate from PlayerGameStat.team, which is historical and can contain former
# teams, stand-ins, and non-CDL events returned by Breaking Point.
PRO_TEAM_ROSTERS_2026 = {
    'OpTic Texas': ('Dashy', 'Huke', 'Mercules', 'Shotzzy'),
    'Los Angeles Thieves': ('aBeZy', 'HyDra', 'Nium', 'Scrap'),
    'FaZe Vegas': ('04', 'Abuzah', 'Drazah', 'Simp'),
    'Paris Gentle Mates': ('Estreal', 'Ghosty', 'JoeDeceives', 'Sib'),
    'Toronto KOI': ('Abe', 'CleanX', 'Insight', 'Kips'),
    'G2 Minnesota': ('Envoy', 'Kremp', 'Nastie', 'Skyz'),
    'Riyadh Falcons': ('Alluka', 'Cellium', 'Exnid', 'KiSMET'),
    'Miami Heretics': ('MettalZ', 'ReeaL', 'RenKoR', 'SupeR'),
}
