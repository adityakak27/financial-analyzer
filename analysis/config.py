"""Paths, ticker lists and constants for the Mispricing Radar study.

No side effects on import (no directory creation, no network calls).
"""
from __future__ import annotations

from pathlib import Path

ANALYSIS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ANALYSIS_ROOT.parent

DATA_PROCESSED_DIR = ANALYSIS_ROOT / "data" / "processed"
RAW_PRICES_DIR = ANALYSIS_ROOT / "data" / "raw" / "prices"
OUTPUTS_DIR = ANALYSIS_ROOT / "outputs"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
REPORT_DIR = ANALYSIS_ROOT / "report"

DB_PATH = PROJECT_ROOT / "data" / "finchat.db"

# Extra tickers to expand the sample beyond the base 19-ticker UNIVERSE (user-approved).
EXTRA_TICKERS: dict[str, str] = {
    "IBM": "IBM Corp.", "CSCO": "Cisco Systems Inc.", "HPQ": "HP Inc.",
    "HPE": "Hewlett Packard Enterprise", "DELL": "Dell Technologies Inc.",
    "KLAC": "KLA Corp.", "LRCX": "Lam Research Corp.", "MCHP": "Microchip Technology Inc.",
    "ON": "ON Semiconductor Corp.", "SWKS": "Skyworks Solutions Inc.",
    "TER": "Teradyne Inc.", "FTNT": "Fortinet Inc.",
    # ANSS (ANSYS) and JNPR (Juniper) were dropped: both were acquired (by Synopsys in
    # 2024 and HPE in 2025 respectively) and no longer appear in SEC's active ticker map.
    "AKAM": "Akamai Technologies Inc.",
    "NTAP": "NetApp Inc.", "STX": "Seagate Technology Holdings",
    "WDC": "Western Digital Corp.", "GLW": "Corning Inc.",
    "APH": "Amphenol Corp.", "MSI": "Motorola Solutions Inc.",
    "ZBRA": "Zebra Technologies Corp.", "KEYS": "Keysight Technologies Inc.",
    "GDDY": "GoDaddy Inc.", "EPAM": "EPAM Systems Inc.",
    "VRSN": "VeriSign Inc.", "CDW": "CDW Corp.", "FICO": "Fair Isaac Corp.",
    "PTC": "PTC Inc.", "TYL": "Tyler Technologies Inc.",
    "NXPI": "NXP Semiconductors N.V.", "MPWR": "Monolithic Power Systems Inc.",
    "TRMB": "Trimble Inc.", "ANET": "Arista Networks Inc.",
    "ADSK": "Autodesk Inc.", "CTSH": "Cognizant Technology Solutions Corp.",
    "ACN": "Accenture plc", "JBL": "Jabil Inc.", "FFIV": "F5 Inc.",
    "DXC": "DXC Technology Co.",
}

# Manual sub-industry map (SIC codes are blank for this filer set, so we classify by hand).
SUB_INDUSTRY: dict[str, str] = {
    "AAPL": "Hardware & Equipment",
    "MSFT": "Software & Services",
    "NVDA": "Semiconductors",
    "AVGO": "Semiconductors",
    "ORCL": "Software & Services",
    "CRM": "Software & Services",
    "ADBE": "Software & Services",
    "AMD": "Semiconductors",
    "QCOM": "Semiconductors",
    "TXN": "Semiconductors",
    "INTU": "Software & Services",
    "NOW": "Software & Services",
    "MU": "Semiconductors",
    "AMAT": "Semiconductors",
    "ADI": "Semiconductors",
    "SNPS": "Software & Services",
    "CDNS": "Software & Services",
    "PANW": "Software & Services",
    "INTC": "Semiconductors",
    # Expansion tickers (analysis/config.py EXTRA_TICKERS)
    "IBM": "Hardware & Equipment", "CSCO": "Hardware & Equipment", "HPQ": "Hardware & Equipment",
    "HPE": "Hardware & Equipment", "DELL": "Hardware & Equipment", "NTAP": "Hardware & Equipment",
    "STX": "Hardware & Equipment", "WDC": "Hardware & Equipment", "GLW": "Hardware & Equipment",
    "APH": "Hardware & Equipment", "MSI": "Hardware & Equipment", "ZBRA": "Hardware & Equipment",
    "KEYS": "Hardware & Equipment", "ANET": "Hardware & Equipment", "TRMB": "Hardware & Equipment",
    "JBL": "Hardware & Equipment", "FFIV": "Hardware & Equipment",
    "KLAC": "Semiconductors", "LRCX": "Semiconductors", "MCHP": "Semiconductors",
    "ON": "Semiconductors", "SWKS": "Semiconductors", "TER": "Semiconductors",
    "NXPI": "Semiconductors", "MPWR": "Semiconductors",
    "FTNT": "Software & Services", "AKAM": "Software & Services", "VRSN": "Software & Services",
    "FICO": "Software & Services", "PTC": "Software & Services", "TYL": "Software & Services",
    "ADSK": "Software & Services", "EPAM": "Software & Services", "CTSH": "Software & Services",
    "ACN": "Software & Services", "GDDY": "Software & Services", "CDW": "Software & Services",
    "DXC": "Software & Services",
}

FY_START = 2018
FY_END = 2024

# Winsorization bounds applied within each fiscal year.
WINSOR_LOW_PCT = 0.05
WINSOR_HIGH_PCT = 0.95

# Mispricing verdict thresholds (on the gap z-score).
UNDERVALUED_Z = -1.0
OVERVALUED_Z = 1.0

# Piotroski F groups.
PIOTROSKI_LOW_MAX = 3
PIOTROSKI_MID_MAX = 6

# Altman Z zones.
ALTMAN_DISTRESS_MAX = 1.81
ALTMAN_GREY_MAX = 3.0

# Beneish M flag threshold (standard literature cutoff).
BENEISH_FLAG = -1.78

RANDOM_SEED = 42
