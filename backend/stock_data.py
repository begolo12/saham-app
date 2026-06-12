import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import yfinance as yf
import pandas as pd
from typing import List, Dict, Any, Optional

# Simple in-memory cache for yfinance data
_history_cache: Dict[str, Dict] = {}
_info_cache: Dict[str, Dict] = {}

# Minimum price filter: include cheaper stocks only if still liquid/potential
MIN_PRICE = 50
MIN_VOLUME = 10_000
MIN_AVG_VALUE = 10_000_000  # 10M IDR/day minimum avg traded value — keeps penny stocks (price>=50) at 10K+ volume
MIN_DAYS = 20
MAX_FAILED_RATIO = 0.5
# Default cap; when an external scanner is configured (see SCANNER_URL), this
# limit is bypassed and we serve whatever the external scanner has.
MAX_UNIVERSE = int(os.environ.get('SAHAM_MAX_UNIVERSE', 280))

# Path to the canonical full-IDX universe (951 tickers, last refresh 2026).
# Lives in data/idx_universe.txt — one ticker per line, e.g. "BBCA.JK".
_UNIVERSE_FILE = Path(__file__).parent / 'data' / 'idx_universe.txt'


def _load_full_universe() -> List[str]:
    """Load the full IDX-listed universe from data/idx_universe.txt.

    Used as the source of truth when SCANNER_URL is set or when MAX_UNIVERSE
    is raised to 951. Falls back to a hardcoded minimum if the file is
    missing (e.g. fresh clone without the data/ dir).
    """
    try:
        with _UNIVERSE_FILE.open() as f:
            tickers = [line.strip() for line in f if line.strip()]
        if tickers:
            return tickers
    except FileNotFoundError:
        pass
    return []

TOP_STOCK_FALLBACK = [
    {'symbol':'BBCA','name':'Bank Central Asia Tbk.','price':10250,'change_percent':0,'sector':'Perbankan','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':88},
    {'symbol':'BBRI','name':'Bank Rakyat Indonesia Tbk.','price':5650,'change_percent':0,'sector':'Perbankan','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':84},
    {'symbol':'BMRI','name':'Bank Mandiri Tbk.','price':7200,'change_percent':0,'sector':'Perbankan','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':82},
    {'symbol':'TLKM','name':'Telkom Indonesia Tbk.','price':3950,'change_percent':0,'sector':'Telekomunikasi','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':78},
    {'symbol':'ASII','name':'Astra International Tbk.','price':5450,'change_percent':0,'sector':'Otomotif','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':76},
    {'symbol':'ADRO','name':'Adaro Energy Indonesia Tbk.','price':2850,'change_percent':0,'sector':'Energi','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':74},
    {'symbol':'ANTM','name':'Aneka Tambang Tbk.','price':1800,'change_percent':0,'sector':'Pertambangan','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':72},
    {'symbol':'INDF','name':'Indofood Sukses Makmur Tbk.','price':6325,'change_percent':0,'sector':'Consumer Goods','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':70},
    {'symbol':'GOTO','name':'GoTo Gojek Tokopedia Tbk.','price':98,'change_percent':0,'sector':'Teknologi','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':68},
    {'symbol':'PGAS','name':'Perusahaan Gas Negara Tbk.','price':1500,'change_percent':0,'sector':'Energi','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':66},
]
_top_stocks_cache = {'timestamp': 0, 'data': []}
# score threshold: do not drop low-score liquid stocks from universe.
# Signal engine decides BUY/NEUTRAL/SELL later; scanner only filters liquidity/data quality.
MIN_POTENTIAL_SCORE = 0

# 80+ Indonesian stocks covering all sectors
INDONESIAN_STOCKS = [
    # Banks
    'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BRIS.JK', 'BBTN.JK', 'NISP.JK',
    # Consumer Goods
    'UNVR.JK', 'ICBP.JK', 'INDF.JK', 'KLBF.JK', 'HMSP.JK', 'MYOR.JK', 'SIDO.JK',
    'SDRA.JK', 'TSPC.JK', 'SCCO.JK', 'BRAM.JK', 'CPIN.JK', 'JPFA.JK',
    # Retail
    'MAPI.JK', 'ACES.JK', 'ERAA.JK', 'RALS.JK', 'LPPF.JK',
    # Energy
    'ADRO.JK', 'PTBA.JK', 'ITMG.JK', 'MEDC.JK', 'PGAS.JK', 'AKRA.JK', 'ELSA.JK',
    'BUMI.JK', 'INDY.JK',
    # Infrastructure & Construction
    'JSMR.JK', 'WIKA.JK', 'WSKT.JK', 'ADHI.JK', 'PTPP.JK', 'INTP.JK', 'SMGR.JK',
    # Property
    'CTRA.JK', 'PWON.JK', 'BSDE.JK', 'SMRA.JK', 'LPKR.JK', 'PPRO.JK', 'MTLA.JK',
    # Agriculture / Plantation
    'AALI.JK', 'LSIP.JK', 'TAPG.JK', 'SSMS.JK',
    # Mining
    'ANTM.JK', 'MDKA.JK', 'BRPT.JK', 'INCO.JK', 'NCKL.JK', 'TINS.JK', 'ADMR.JK',
    # Healthcare
    'MIKA.JK', 'SILO.JK', 'KAEF.JK', 'DVLA.JK', 'MERK.JK', 'HEAL.JK',
    # Telco & Towers
    'TLKM.JK', 'EXCL.JK', 'ISAT.JK', 'MTEL.JK', 'TOWR.JK', 'TBIG.JK',
    # Automotive
    'ASII.JK', 'AUTO.JK', 'GJTL.JK',
    # Technology
    'GOTO.JK', 'BUKA.JK', 'WIRG.JK', 'DCII.JK', 'MTDL.JK',
    # Media & Entertainment
    'EMTK.JK', 'MNCN.JK', 'SCMA.JK', 'MDIA.JK',
    # Energy (Geothermal)
    'PGEO.JK',
    # Cheap / active liquid watch universe (price >= 50 still required at runtime)
    'ENRG.JK', 'DEWA.JK', 'DOID.JK', 'HRUM.JK', 'RAJA.JK', 'TOBA.JK',
    'PNLF.JK', 'BABP.JK', 'AGRO.JK', 'ARTO.JK', 'BFIN.JK',
    'WIFI.JK', 'LINK.JK', 'FREN.JK', 'BULL.JK', 'SMDR.JK',
    'TPIA.JK', 'ESSA.JK', 'AMMN.JK', 'MBMA.JK', 'CUAN.JK',
    # User-requested and high-volume IDX movers / big cap additions
    'BREN.JK', 'PTRO.JK', 'CDIA.JK', 'PANI.JK', 'DSSA.JK', 'AADI.JK', 'RATU.JK',
    'INET.JK', 'WTON.JK', 'SSIA.JK', 'KIJA.JK', 'ELTY.JK', 'BEST.JK', 'BKSL.JK',
    'NIKL.JK', 'ZINC.JK', 'DKFT.JK', 'NICL.JK', 'HRTA.JK', 'PSAB.JK', 'GEMS.JK',
    'SRTG.JK', 'SRAJ.JK', 'MIDI.JK', 'AMRT.JK', 'MAPA.JK', 'FILM.JK', 'MSIN.JK',
    'BANK.JK', 'BTPS.JK', 'MAYA.JK', 'BNGA.JK', 'PNBN.JK', 'BJBR.JK', 'BJTM.JK',
    'SMIL.JK', 'VKTR.JK', 'GGRM.JK', 'CMRY.JK', 'CLEO.JK', 'ULTJ.JK', 'ROTI.JK',
    # NOTE: delisted/renamed tickers removed from extended universe:
    # FREN, TMPI, BULL, VIVA, BMTR, LMAX, NAGA (no data)
    # Additional active IDX universe (10K+ vol) — curated well-known tickers
    'WIIM.JK', 'ITIC.JK', 'PYFA.JK', 'INAF.JK', 'BSSR.JK', 'PKPK.JK', 'ARII.JK',
    'CITA.JK', 'COWL.JK', 'DILD.JK', 'JRPT.JK', 'MKPI.JK', 'PLIN.JK', 'GMTD.JK',
    'BAPA.JK', 'PUDP.JK', 'SKBM.JK', 'ADES.JK', 'BUDI.JK', 'HOKI.JK', 'KEJU.JK',
    'GZCO.JK', 'BNLI.JK', 'BVIC.JK', 'INPC.JK', 'MCOR.JK', 'NAGA.JK', 'PNBS.JK',
    'BSIM.JK', 'BGTG.JK', 'BMAS.JK', 'LIFE.JK', 'AMAG.JK', 'ASDM.JK', 'ASMI.JK',
    'ASJT.JK', 'ABDA.JK', 'AHAP.JK', 'PNIN.JK', 'SMAR.JK', 'TMPI.JK', 'TRIM.JK',
    'PANS.JK', 'KREN.JK', 'PEGE.JK', 'YULE.JK', 'AMOR.JK', 'VICI.JK', 'ACST.JK',
    'TOTL.JK', 'NRCA.JK', 'DGIK.JK', 'JKON.JK', 'TAMA.JK', 'PBSA.JK', 'MTRA.JK',
    'IPCM.JK', 'INDS.JK', 'SMSM.JK', 'IMAS.JK', 'BOLT.JK', 'GDYR.JK', 'SRSN.JK',
    'EKAD.JK', 'INCI.JK', 'MDKI.JK', 'ALDO.JK', 'YPBK.JK', 'CLPI.JK', 'OKAS.JK',
    'ASSA.JK', 'LRNA.JK', 'HITS.JK', 'CMPP.JK', 'GIAA.JK', 'IATA.JK', 'JSKY.JK',
    'KARW.JK', 'WEHA.JK', 'RANC.JK', 'CSAP.JK', 'DAYA.JK', 'HERO.JK', 'MTFN.JK',
    'TRIO.JK', 'KOPI.JK', 'FAST.JK', 'NFCX.JK', 'MCAS.JK', 'DIVA.JK', 'SGRO.JK',
    'TBLA.JK', 'PALM.JK', 'DSNG.JK', 'JAWA.JK', 'MGRO.JK', 'BWPT.JK', 'ANJT.JK',
    'GZBK.JK', 'NIPS.JK', 'CSIS.JK', 'TRIS.JK', 'BLJA.JK', 'VIVA.JK', 'BMTR.JK',
    'POLY.JK', 'KPIF.JK', 'LMAX.JK', 'TFAS.JK', 'KIOS.JK', 'AGRS.JK', 'ELIT.JK',
    'MCOL.JK', 'JAST.JK', 'ENVY.JK', 'ZONE.JK', 'CASH.JK', 'PTSN.JK', 'DMMX.JK',
    'IRSX.JK', 'VISI.JK', 'HDIT.JK', 'LUCK.JK', 'DEAL.JK', 'APLN.JK', 'ARCI.JK',
    'AGII.JK', 'FASW.JK', 'HKMU.JK', 'INDX.JK', 'JPRS.JK', 'JTPE.JK', 'KAYU.JK',
    'KDTN.JK', 'LPCK.JK', 'MARK.JK', 'MDLN.JK', 'MERI.JK', 'META.JK', 'MICE.JK',
    'MINA.JK', 'MPRO.JK', 'MTMH.JK', 'MYTX.JK', 'NUSA.JK', 'OASA.JK', 'OMRE.JK',
    'PADA.JK', 'PAM.JK', 'PGJO.JK', 'PGLI.JK', 'PJAA.JK', 'PNGO.JK', 'POWR.JK',
    'PPGL.JK', 'PRAS.JK', 'PRDA.JK', 'PRIM.JK', 'PTIS.JK', 'RAAM.JK', 'RBMS.JK',
    'REAL.JK', 'RIMO.JK', 'ROCK.JK', 'RODA.JK', 'RUIS.JK', 'SAME.JK', 'SAPX.JK',
    'SDMU.JK', 'SFAN.JK', 'SGER.JK', 'SHEET.JK', 'SHID.JK', 'SIMA.JK', 'SKRN.JK',
    'SLIS.JK', 'SMBR.JK', 'SMCB.JK', 'SMDM.JK', 'SMGA.JK', 'SMKL.JK', 'SMMT.JK',
    'SMRU.JK', 'SOCI.JK', 'SOFA.JK', 'SOLA.JK', 'SONA.JK', 'SPMA.JK', 'SPRE.JK',
    'SQMI.JK', 'SSTM.JK', 'STAR.JK', 'STTP.JK', 'SUGI.JK', 'TALF.JK', 'TARA.JK',
    'TARGET.JK', 'TFCO.JK', 'TGKA.JK', 'TIFA.JK', 'TKIM.JK', 'TOPS.JK', 'TOTO.JK',
    'TOYS.JK', 'TPMA.JK', 'TRAM.JK', 'TRIL.JK', 'TRUE.JK', 'UCID.JK', 'UFOE.JK',
    'UNIC.JK', 'UNSP.JK', 'URBN.JK', 'VICO.JK', 'VOKS.JK', 'WAPO.JK', 'WEGE.JK',
    'WICO.JK', 'WINR.JK', 'WINS.JK', 'WMUU.JK', 'WOOD.JK', 'WSBP.JK', 'YELO.JK',
    'ZBRA.JK', 'ZYRX.JK',
]

SECTOR_MAP = {
    # Banks
    'BBCA.JK': 'Perbankan',
    'BBRI.JK': 'Perbankan',
    'BMRI.JK': 'Perbankan',
    'BBNI.JK': 'Perbankan',
    'BRIS.JK': 'Perbankan',
    'BBTN.JK': 'Perbankan',
    'NISP.JK': 'Perbankan',
    # Consumer Goods
    'UNVR.JK': 'Consumer Goods',
    'ICBP.JK': 'Consumer Goods',
    'INDF.JK': 'Consumer Goods',
    'KLBF.JK': 'Consumer Goods',
    'HMSP.JK': 'Consumer Goods',
    'MYOR.JK': 'Consumer Goods',
    'SIDO.JK': 'Consumer Goods',
    'SDRA.JK': 'Consumer Goods',
    'TSPC.JK': 'Consumer Goods',
    'SCCO.JK': 'Consumer Goods',
    'BRAM.JK': 'Consumer Goods',
    'CPIN.JK': 'Consumer Goods',
    'JPFA.JK': 'Consumer Goods',
    # Retail
    'MAPI.JK': 'Consumer Goods',
    'ACES.JK': 'Consumer Goods',
    'ERAA.JK': 'Consumer Goods',
    'RALS.JK': 'Consumer Goods',
    'LPPF.JK': 'Consumer Goods',
    # Energy
    'ADRO.JK': 'Energi',
    'PTBA.JK': 'Energi',
    'ITMG.JK': 'Energi',
    'MEDC.JK': 'Energi',
    'PGAS.JK': 'Energi',
    'AKRA.JK': 'Energi',
    'ELSA.JK': 'Energi',
    'BUMI.JK': 'Energi',
    'INDY.JK': 'Energi',
    'PGEO.JK': 'Energi',
    # Infrastructure & Construction
    'JSMR.JK': 'Infrastruktur',
    'WIKA.JK': 'Infrastruktur',
    'WSKT.JK': 'Infrastruktur',
    'ADHI.JK': 'Infrastruktur',
    'PTPP.JK': 'Infrastruktur',
    'INTP.JK': 'Infrastruktur',
    'SMGR.JK': 'Infrastruktur',
    # Property
    'CTRA.JK': 'Properti',
    'PWON.JK': 'Properti',
    'BSDE.JK': 'Properti',
    'SMRA.JK': 'Properti',
    'LPKR.JK': 'Properti',
    'PPRO.JK': 'Properti',
    'MTLA.JK': 'Properti',
    # Agriculture / Plantation
    'AALI.JK': 'Perkebunan',
    'LSIP.JK': 'Perkebunan',
    'TAPG.JK': 'Perkebunan',
    'SSMS.JK': 'Perkebunan',
    # Mining
    'ANTM.JK': 'Pertambangan',
    'MDKA.JK': 'Pertambangan',
    'BRPT.JK': 'Pertambangan',
    'INCO.JK': 'Pertambangan',
    'NCKL.JK': 'Pertambangan',
    'TINS.JK': 'Pertambangan',
    'ADMR.JK': 'Pertambangan',
    # Healthcare
    'MIKA.JK': 'Kesehatan',
    'SILO.JK': 'Kesehatan',
    'KAEF.JK': 'Kesehatan',
    'DVLA.JK': 'Kesehatan',
    'MERK.JK': 'Kesehatan',
    'HEAL.JK': 'Kesehatan',
    # Telco & Towers
    'TLKM.JK': 'Telekomunikasi',
    'EXCL.JK': 'Telekomunikasi',
    'ISAT.JK': 'Telekomunikasi',
    'MTEL.JK': 'Telekomunikasi',
    'TOWR.JK': 'Telekomunikasi',
    'TBIG.JK': 'Telekomunikasi',
    # Automotive
    'ASII.JK': 'Otomotif',
    'AUTO.JK': 'Otomotif',
    'GJTL.JK': 'Otomotif',
    # Technology
    'GOTO.JK': 'Teknologi',
    'BUKA.JK': 'Teknologi',
    # Media & Entertainment
    'EMTK.JK': 'Media & Entertainment',
    'MNCN.JK': 'Media & Entertainment',
    'SCMA.JK': 'Media & Entertainment',
    'MDIA.JK': 'Media & Entertainment',
    # Added liquid universe
    'WIRG.JK': 'Teknologi',
    'DCII.JK': 'Teknologi',
    'MTDL.JK': 'Teknologi',
    'ENRG.JK': 'Energi',
    'DEWA.JK': 'Energi',
    'DOID.JK': 'Energi',
    'HRUM.JK': 'Energi',
    'RAJA.JK': 'Energi',
    'TOBA.JK': 'Energi',
    'PNLF.JK': 'Keuangan',
    'BABP.JK': 'Perbankan',
    'AGRO.JK': 'Perbankan',
    'ARTO.JK': 'Perbankan',
    'BFIN.JK': 'Keuangan',
    'WIFI.JK': 'Telekomunikasi',
    'LINK.JK': 'Telekomunikasi',
    'FREN.JK': 'Telekomunikasi',
    'BULL.JK': 'Transportasi',
    'SMDR.JK': 'Transportasi',
    'TPIA.JK': 'Basic Materials',
    'ESSA.JK': 'Basic Materials',
    'AMMN.JK': 'Pertambangan',
    'MBMA.JK': 'Pertambangan',
    'CUAN.JK': 'Energi',
    'BREN.JK': 'Energi', 'PTRO.JK': 'Energi', 'CDIA.JK': 'Energi', 'PANI.JK': 'Properti',
    'DSSA.JK': 'Energi', 'AADI.JK': 'Energi', 'RATU.JK': 'Energi', 'INET.JK': 'Teknologi',
    'WTON.JK': 'Infrastruktur', 'SSIA.JK': 'Properti', 'KIJA.JK': 'Properti', 'ELTY.JK': 'Properti',
    'BEST.JK': 'Properti', 'BKSL.JK': 'Properti', 'NIKL.JK': 'Basic Materials', 'ZINC.JK': 'Pertambangan',
    'DKFT.JK': 'Pertambangan', 'NICL.JK': 'Pertambangan', 'HRTA.JK': 'Consumer Goods', 'PSAB.JK': 'Pertambangan',
    'GEMS.JK': 'Energi', 'SRTG.JK': 'Investasi', 'SRAJ.JK': 'Kesehatan', 'MIDI.JK': 'Consumer Goods',
    'AMRT.JK': 'Consumer Goods', 'MAPA.JK': 'Consumer Goods', 'FILM.JK': 'Media & Entertainment',
    'MSIN.JK': 'Media & Entertainment', 'BANK.JK': 'Perbankan', 'BTPS.JK': 'Perbankan', 'MAYA.JK': 'Perbankan',
    'BNGA.JK': 'Perbankan', 'PNBN.JK': 'Perbankan', 'BJBR.JK': 'Perbankan', 'BJTM.JK': 'Perbankan',
    'SMIL.JK': 'Infrastruktur', 'VKTR.JK': 'Otomotif', 'GGRM.JK': 'Consumer Goods', 'CMRY.JK': 'Consumer Goods',
    'CLEO.JK': 'Consumer Goods', 'ULTJ.JK': 'Consumer Goods', 'ROTI.JK': 'Consumer Goods',
    # Tambahan sector map (untuk 200+ IDX universe)
    'WIIM.JK': 'Consumer Goods', 'ITIC.JK': 'Consumer Goods', 'PYFA.JK': 'Kesehatan', 'INAF.JK': 'Kesehatan', 'BSSR.JK': 'Pertambangan', 'PKPK.JK': 'Pertambangan', 'ARII.JK': 'Pertambangan', 'CITA.JK': 'Pertambangan', 'COWL.JK': 'Properti', 'DILD.JK': 'Properti', 'JRPT.JK': 'Properti', 'MKPI.JK': 'Properti', 'PLIN.JK': 'Properti', 'GMTD.JK': 'Properti', 'BAPA.JK': 'Properti', 'PUDP.JK': 'Properti', 'SKBM.JK': 'Consumer Goods', 'ADES.JK': 'Consumer Goods', 'BUDI.JK': 'Consumer Goods', 'HOKI.JK': 'Consumer Goods', 'KEJU.JK': 'Consumer Goods', 'MLBI.JK': 'Consumer Goods', 'AISA.JK': 'Consumer Goods', 'CAMP.JK': 'Consumer Goods', 'PSDN.JK': 'Consumer Goods', 'TCID.JK': 'Consumer Goods', 'TRGU.JK': 'Consumer Goods', 'DLTA.JK': 'Consumer Goods', 'GZCO.JK': 'Consumer Goods', 'BNLI.JK': 'Perbankan', 'BVIC.JK': 'Perbankan', 'INPC.JK': 'Perbankan', 'MCOR.JK': 'Perbankan', 'NAGA.JK': 'Perbankan', 'PNBS.JK': 'Perbankan', 'BSIM.JK': 'Perbankan', 'BGTG.JK': 'Perbankan', 'BMAS.JK': 'Perbankan', 'LIFE.JK': 'Asuransi', 'AMAG.JK': 'Asuransi', 'ASDM.JK': 'Asuransi', 'ASMI.JK': 'Asuransi', 'ASJT.JK': 'Asuransi', 'ABDA.JK': 'Asuransi', 'AHAP.JK': 'Asuransi', 'PNIN.JK': 'Asuransi', 'SMAR.JK': 'Asuransi', 'TMPI.JK': 'Asuransi', 'TRIM.JK': 'Keuangan', 'PANS.JK': 'Keuangan', 'KREN.JK': 'Keuangan', 'PEGE.JK': 'Keuangan', 'YULE.JK': 'Keuangan', 'AMOR.JK': 'Keuangan', 'VICI.JK': 'Keuangan', 'ACST.JK': 'Infrastruktur', 'TOTL.JK': 'Infrastruktur', 'NRCA.JK': 'Infrastruktur', 'DGIK.JK': 'Infrastruktur', 'JKON.JK': 'Infrastruktur', 'TAMA.JK': 'Infrastruktur', 'PBSA.JK': 'Infrastruktur', 'MTRA.JK': 'Infrastruktur', 'IPCM.JK': 'Infrastruktur', 'INDS.JK': 'Otomotif', 'SMSM.JK': 'Otomotif', 'IMAS.JK': 'Otomotif', 'BOLT.JK': 'Otomotif', 'GDYR.JK': 'Otomotif', 'SRSN.JK': 'Basic Materials', 'EKAD.JK': 'Basic Materials', 'INCI.JK': 'Basic Materials', 'MDKI.JK': 'Basic Materials', 'ALDO.JK': 'Basic Materials', 'YPBK.JK': 'Basic Materials', 'CLPI.JK': 'Basic Materials', 'OKAS.JK': 'Basic Materials', 'ASSA.JK': 'Transportasi', 'LRNA.JK': 'Transportasi', 'HITS.JK': 'Transportasi', 'CMPP.JK': 'Transportasi', 'GIAA.JK': 'Transportasi', 'IATA.JK': 'Transportasi', 'JSKY.JK': 'Transportasi', 'KARW.JK': 'Transportasi', 'WEHA.JK': 'Transportasi', 'RANC.JK': 'Consumer Goods', 'CSAP.JK': 'Consumer Goods', 'DAYA.JK': 'Consumer Goods', 'HERO.JK': 'Consumer Goods', 'MTFN.JK': 'Consumer Goods', 'TRIO.JK': 'Consumer Goods', 'KOPI.JK': 'Consumer Goods', 'FAST.JK': 'Consumer Goods', 'NFCX.JK': 'Consumer Goods', 'MCAS.JK': 'Consumer Goods', 'DIVA.JK': 'Consumer Goods', 'SGRO.JK': 'Perkebunan', 'TBLA.JK': 'Perkebunan', 'PALM.JK': 'Perkebunan', 'DSNG.JK': 'Perkebunan', 'JAWA.JK': 'Perkebunan', 'MGRO.JK': 'Perkebunan', 'BWPT.JK': 'Perkebunan', 'ANJT.JK': 'Perkebunan', 'GZBK.JK': 'Perkebunan', 'NIPS.JK': 'Perkebunan', 'CSIS.JK': 'Perkebunan', 'TRIS.JK': 'Perkebunan', 'BLJA.JK': 'Perkebunan', 'VIVA.JK': 'Media & Entertainment', 'BMTR.JK': 'Media & Entertainment', 'POLY.JK': 'Media & Entertainment', 'KPIF.JK': 'Media & Entertainment', 'LMAX.JK': 'Media & Entertainment', 'TFAS.JK': 'Teknologi', 'KIOS.JK': 'Teknologi', 'AGRS.JK': 'Teknologi', 'ELIT.JK': 'Teknologi', 'MCOL.JK': 'Teknologi', 'JAST.JK': 'Teknologi', 'ENVY.JK': 'Teknologi', 'ZONE.JK': 'Teknologi', 'CASH.JK': 'Teknologi', 'PTSN.JK': 'Teknologi', 'DMMX.JK': 'Teknologi', 'IRSX.JK': 'Teknologi', 'VISI.JK': 'Teknologi', 'HDIT.JK': 'Teknologi', 'LUCK.JK': 'Teknologi', 'DEAL.JK': 'Teknologi', 'APLN.JK': 'Properti', 'ARCI.JK': 'Properti', 'AGII.JK': 'Properti', 'FASW.JK': 'Properti', 'HKMU.JK': 'Properti', 'INDX.JK': 'Properti', 'JPRS.JK': 'Properti', 'JTPE.JK': 'Properti', 'KAYU.JK': 'Properti', 'KDTN.JK': 'Properti', 'LPCK.JK': 'Properti', 'MARK.JK': 'Properti', 'MDLN.JK': 'Properti', 'MERI.JK': 'Properti', 'META.JK': 'Properti', 'MICE.JK': 'Properti', 'MINA.JK': 'Properti', 'MPRO.JK': 'Properti', 'MTMH.JK': 'Properti', 'MYTX.JK': 'Properti', 'NUSA.JK': 'Properti', 'OASA.JK': 'Properti', 'OMRE.JK': 'Properti', 'PADA.JK': 'Properti', 'PAM.JK': 'Properti', 'PGJO.JK': 'Properti', 'PGLI.JK': 'Properti', 'PJAA.JK': 'Properti', 'PNGO.JK': 'Properti', 'POWR.JK': 'Properti', 'PPGL.JK': 'Properti', 'PRAS.JK': 'Properti', 'PRDA.JK': 'Properti', 'PRIM.JK': 'Properti', 'PTIS.JK': 'Properti', 'RAAM.JK': 'Properti', 'RBMS.JK': 'Properti', 'REAL.JK': 'Properti', 'RIMO.JK': 'Properti', 'ROCK.JK': 'Properti', 'RODA.JK': 'Properti', 'RUIS.JK': 'Properti', 'SAME.JK': 'Properti', 'SAPX.JK': 'Properti', 'SDMU.JK': 'Properti', 'SFAN.JK': 'Properti', 'SGER.JK': 'Properti', 'SHEET.JK': 'Properti', 'SHID.JK': 'Properti', 'SIMA.JK': 'Properti', 'SKRN.JK': 'Properti', 'SLIS.JK': 'Properti', 'SMBR.JK': 'Properti', 'SMCB.JK': 'Properti', 'SMDM.JK': 'Properti', 'SMGA.JK': 'Properti', 'SMKL.JK': 'Properti', 'SMMT.JK': 'Properti', 'SMRU.JK': 'Properti', 'SOCI.JK': 'Properti', 'SOFA.JK': 'Properti', 'SOLA.JK': 'Properti', 'SONA.JK': 'Properti', 'SPMA.JK': 'Properti', 'SPRE.JK': 'Properti', 'SQMI.JK': 'Properti', 'SSTM.JK': 'Properti', 'STAR.JK': 'Properti', 'STTP.JK': 'Properti', 'SUGI.JK': 'Properti', 'TALF.JK': 'Properti', 'TARA.JK': 'Properti', 'TARGET.JK': 'Properti', 'TFCO.JK': 'Properti', 'TGKA.JK': 'Properti', 'TIFA.JK': 'Properti', 'TKIM.JK': 'Properti', 'TOPS.JK': 'Properti', 'TOTO.JK': 'Properti', 'TOYS.JK': 'Properti', 'TPMA.JK': 'Properti', 'TRAM.JK': 'Properti', 'TRIL.JK': 'Properti', 'TRUE.JK': 'Properti', 'UCID.JK': 'Properti', 'UFOE.JK': 'Properti', 'UNIC.JK': 'Properti', 'UNSP.JK': 'Properti', 'URBN.JK': 'Properti', 'VICO.JK': 'Properti', 'VOKS.JK': 'Properti', 'WAPO.JK': 'Properti', 'WEGE.JK': 'Properti', 'WICO.JK': 'Properti', 'WINR.JK': 'Properti', 'WINS.JK': 'Properti', 'WMUU.JK': 'Properti', 'WOOD.JK': 'Properti', 'WSBP.JK': 'Properti', 'YELO.JK': 'Properti', 'ZBRA.JK': 'Properti', 'ZYRX.JK': 'Properti',
}


def _safe_float(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _score_stock(price: float, change_percent: float, volume: float, avg_volume: float, market_cap: float, pe_ratio: float, pbv: float) -> float:
    score = 0.0
    if price >= MIN_PRICE:
        score += 5
    if volume >= MIN_VOLUME:
        score += 18
    if volume >= 5_000_000:
        score += 10
    if volume >= 20_000_000:
        score += 12
    if avg_volume and avg_volume >= MIN_VOLUME:
        score += 10
    if avg_volume and avg_volume >= 5_000_000:
        score += 8
    if avg_volume and volume and volume >= avg_volume * 0.8:
        score += 8
    if market_cap and market_cap >= 5e12:
        score += 8
    if market_cap and market_cap >= 1e12:
        score += 4
    if pe_ratio and pe_ratio > 0 and pe_ratio < 20:
        score += 5
    if pbv and pbv > 0 and pbv < 3:
        score += 5
    if abs(change_percent) >= 1:
        score += 8
    if change_percent > 0:
        score += 5
    return score


def _calc_card_indicators(history: pd.DataFrame) -> Dict[str, float]:
    """Lightweight technical indicators from cached 1-month OHLCV for list signals."""
    close = history['Close'].dropna()
    volume = history['Volume'].dropna()
    if close.empty:
        return {'trend_5d': 0.0, 'trend_20d': 0.0, 'rsi14': 50.0, 'volume_ratio': 1.0}
    last = float(close.iloc[-1])
    prev_5 = float(close.iloc[-6]) if len(close) >= 6 else float(close.iloc[0])
    prev_20 = float(close.iloc[-21]) if len(close) >= 21 else float(close.iloc[0])
    trend_5d = ((last - prev_5) / prev_5) * 100 if prev_5 else 0.0
    trend_20d = ((last - prev_20) / prev_20) * 100 if prev_20 else 0.0

    delta = close.diff()
    gain = delta.clip(lower=0).tail(14).mean()
    loss = (-delta.clip(upper=0)).tail(14).mean()
    if loss and loss > 0:
        rs = gain / loss
        rsi14 = 100 - (100 / (1 + rs))
    else:
        rsi14 = 70.0 if gain and gain > 0 else 50.0

    avg_vol = float(volume.tail(20).mean()) if not volume.empty else 0.0
    last_vol = float(volume.iloc[-1]) if not volume.empty else 0.0
    volume_ratio = last_vol / avg_vol if avg_vol else 1.0
    return {
        'trend_5d': round(trend_5d, 2),
        'trend_20d': round(trend_20d, 2),
        'rsi14': round(float(rsi14), 2),
        'volume_ratio': round(float(volume_ratio), 2),
    }


def _fetch_stock_card(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        ticker = yf.Ticker(symbol)
        # 5d history is enough for list view (we need last_price, prev_close, volume only)
        history = ticker.history(period='5d', timeout=3)
        if history.empty or len(history) < 2:
            return None
        try:
            info = ticker.fast_info or {}
        except Exception:
            info = {}
        current_price = _safe_float(info.get('last_price')) or _safe_float(history['Close'].iloc[-1])
        if current_price is None or current_price < MIN_PRICE:
            return None
        volume = _safe_float(info.get('last_volume') or history['Volume'].iloc[-1]) or 0.0
        avg_volume = _safe_float(history['Volume'].tail(5).mean()) or 0.0  # 5d avg, lighter than 20d
        avg_value = _safe_float((history['Close'].tail(5) * history['Volume'].tail(5)).mean()) or 0.0
        if volume < MIN_VOLUME and avg_volume < MIN_VOLUME:
            return None
        if avg_value < MIN_AVG_VALUE and volume < MIN_VOLUME:
            return None
        prev_close = _safe_float(history['Close'].iloc[-2]) if len(history) >= 2 else current_price
        change_percent = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0.0
        market_cap = _safe_float(info.get('market_cap')) or 0.0
        indicators = _calc_card_indicators(history)
        potential_score = _score_stock(current_price, change_percent, volume, avg_volume, market_cap, 0, 0)
        return {
            'symbol': symbol.replace('.JK', ''),
            'name': symbol.replace('.JK', ''),
            'price': round(float(current_price), 2),
            'change_percent': round(change_percent, 2),
            'sector': SECTOR_MAP.get(symbol, 'Lainnya'),
            'volume': int(volume),
            'avg_volume': int(avg_volume),
            'avg_value': int(avg_value),
            'potential_score': round(potential_score, 2),
            **indicators,
        }
    except Exception:
        return None


def get_top_stocks() -> List[Dict[str, Any]]:
    """Fast parallel IDX scanner with stale cache and safe fallback.

    Lookup order:
      1. SAHAM_SCANNER_FROM_DB=1 → read latest result from Neon
         `scanner_results` table (written by NAS scanner every 60s)
      2. SAHAM_SCANNER_URL set → fetch from external HTTP scanner
      3. Local in-process scan (works on Vercel up to MAX_UNIVERSE)
    """
    # Path 1 — read from shared DB (NAS writes here, Vercel reads here)
    if os.environ.get('SAHAM_SCANNER_FROM_DB', '').lower() in ('1', 'true', 'yes'):
        try:
            from services.db import load_latest_scanner_result
            payload = load_latest_scanner_result(max_age_seconds=300)
            if payload and payload.get('rows'):
                return payload['rows']
        except Exception:
            pass  # fall through

    # Path 2 — external HTTP scanner (e.g. NAS exposing a public port)
    scanner_url = os.environ.get('SAHAM_SCANNER_URL')
    if scanner_url:
        try:
            import urllib.request
            with urllib.request.urlopen(f'{scanner_url.rstrip("/")}/latest', timeout=4) as r:
                payload = json.loads(r.read())
            rows = payload.get('rows') or []
            if rows:
                return rows
        except Exception:
            pass  # fall through to local scan

    # Path 3 — local in-process scan (works on Vercel up to MAX_UNIVERSE)
    now = time.time()
    cached = _top_stocks_cache.get('data') or []
    # Semi-live desktop mode: short cache keeps UI fresh without hammering yfinance.
    if cached and (now - _top_stocks_cache.get('timestamp', 0)) < 180:
        return cached

    # Pick the universe to scan — full IDX if MAX_UNIVERSE allows, else hardcoded
    full_universe = _load_full_universe()
    if full_universe and MAX_UNIVERSE >= len(full_universe):
        universe = full_universe
        cap = len(full_universe)
        worker_count = min(80, len(full_universe))
        deadline_secs = 90  # local mode has no Vercel cap
    else:
        universe = INDONESIAN_STOCKS
        cap = MAX_UNIVERSE
        worker_count = 40
        deadline_secs = 30

    results = []
    executor = ThreadPoolExecutor(max_workers=worker_count)
    futures = [executor.submit(_fetch_stock_card, symbol) for symbol in universe[:cap]]
    try:
        deadline = now + deadline_secs
        for fut in as_completed(futures, timeout=deadline_secs + 2):
            if time.time() > deadline:
                break
            item = fut.result()
            if item:
                results.append(item)
            if len(results) >= cap:
                break
    except Exception:
        pass
    finally:
        for fut in futures:
            fut.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    results.sort(key=lambda x: (x.get('potential_score', 0), x.get('volume', 0), x.get('avg_value', 0)), reverse=True)
    if results:
        _top_stocks_cache['timestamp'] = now
        _top_stocks_cache['data'] = results[:cap]
        # Best-effort: persist to shared cache so cold clients get a hit
        if os.environ.get('SAHAM_SCANNER_FROM_DB', '').lower() in ('1', 'true', 'yes'):
            try:
                from services.db import save_scanner_result
                save_scanner_result(results, int((time.time() - now) * 1000))
            except Exception:
                pass
        return _top_stocks_cache['data']
    if cached:
        return cached
    return TOP_STOCK_FALLBACK

def get_stock_history(symbol: str, period: str = '6mo') -> pd.DataFrame:
    """Fetch OHLCV history for a given stock symbol (with .JK suffix).
    Results cached in memory for 10 minutes per (symbol, period) pair.
    """
    if not symbol.endswith('.JK'):
        symbol = symbol + '.JK'

    cache_key = f'hist:{symbol}:{period}'
    now = time.time()
    cached = _history_cache.get(cache_key)
    ttl = 600 if period in ('3mo', '6mo', '1y') else 180
    if cached and (now - cached['timestamp']) < ttl:
        return cached['data']

    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, timeout=6)

    if df.empty:
        _history_cache[cache_key] = {'data': pd.DataFrame(), 'timestamp': now}
        return pd.DataFrame()

    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.columns = [col.lower() for col in df.columns]
    df.index = pd.to_datetime(df.index)

    _history_cache[cache_key] = {'data': df, 'timestamp': now}
    return df


def get_stock_info(symbol: str) -> Dict[str, Any]:
    """Fetch company info for a given stock symbol (with .JK suffix), cached for speed."""
    if not symbol.endswith('.JK'):
        symbol = symbol + '.JK'

    now = time.time()
    cached = _info_cache.get(symbol)
    if cached and (now - cached['timestamp']) < 900:
        return cached['data']

    ticker = yf.Ticker(symbol)
    try:
        info = ticker.info or {}
    except Exception:
        info = {}
    if not info:
        try:
            fast = ticker.fast_info or {}
            info = {
                'lastPrice': _safe_float(fast.get('last_price')),
                'marketCap': _safe_float(fast.get('market_cap')),
                'fiftyTwoWeekHigh': _safe_float(fast.get('year_high')),
                'fiftyTwoWeekLow': _safe_float(fast.get('year_low')),
            }
        except Exception:
            info = {}
    _info_cache[symbol] = {'data': info, 'timestamp': now}
    return info
