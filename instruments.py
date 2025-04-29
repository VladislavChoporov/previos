from tinkoff.invest import AsyncClient
import os
from dotenv import load_dotenv

load_dotenv()

async def get_market_instruments(user_state=None):
    async with AsyncClient(os.getenv("TINKOFF_TOKEN")) as client:
        response = await client.instruments.shares()

        filtered = []
        MOEXBMI_TICKERS = [
            "ABIO", "ABRD", "AFKS", "AFLT", "AKRN", "ALRS", "APTK", "AQUA", "ASTR", "BANE", "BANEP",
            "BELU", "BLNG", "BSPB", "CARM", "CBOM", "CHMF", "CHMK", "CNRU", "CNTL", "CNTLP", "DATA",
            "DELI", "DIAS", "DVEC", "ELFV", "ELMT", "ENPG", "ETLN", "EUTR", "FEES", "FESH", "FIXP",
            "FLOT", "GAZP", "GCHE", "GECO", "GEMC", "GTRK", "HEAD", "HNFG", "HYDR", "IRAO", "IRKT",
            "IVAT", "JETL", "KAZT", "KAZTP", "KLSB", "KLVZ", "KMAZ", "KRKNP", "KROT", "KZOS", "KZOSP",
            "LEAS", "LIFE", "LKOH", "LNZL", "LNZLP", "LSNG", "LSNGP", "LSRG", "MAGN", "MBNK", "MDMG",
            "MGKL", "MGNT", "MGTSP", "MOEX", "MRKC", "MRKP", "MRKS", "MRKU", "MRKV", "MRKZ", "MSNG",
            "MSRS", "MSTT", "MTLR", "MTLRP", "MTSS", "MVID", "NKHP", "NKNC", "NKNCP", "NLMK", "NMTP",
            "NSVZ", "NVTK", "OGKB", "OKEY", "OZON", "OZPH", "PHOR", "PIKK", "PLZL", "PMSB", "PMSBP",
            "POSI", "PRFN", "PRMD", "QIWI", "RAGR", "RASP", "RBCM", "RENI", "RKKE", "RNFT", "ROLO",
            "ROSN", "RTKM", "RTKMP", "RUAL", "SBER", "SBERP", "SFIN", "SGZH", "SIBN", "SMLT", "SNGS",
            "SNGSP", "SOFL", "SPBE", "SVAV", "SVCB", "T", "TATN", "TATNP", "TGKA", "TGKB", "TGKN",
            "TRMK", "TRNFP", "TTLK", "UGLD", "UNAC", "UNKL", "UPRO", "UWSN", "VEON-RX", "VKCO", "VRSB",
            "VSEH", "VSMO", "VTBR", "WUSH", "X5", "YAKG", "YDEX", "ZAYM"
        ]

        for inst in response.instruments:
            if inst.ticker in MOEXBMI_TICKERS:
                filtered.append({
                    "figi": inst.figi,
                    "ticker": inst.ticker,
                    "lot": inst.lot
                })

        return filtered
