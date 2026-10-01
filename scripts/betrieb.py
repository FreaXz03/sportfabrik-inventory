"""Berichte für den Pilotbetrieb (Paket 3): Bestandsprüfung, Tagesabschluss,
Stand der Eröffnungszählung. Nur Lesezugriffe.

Im Container (auf dem Server):
    docker compose --env-file .env.server exec -T app python scripts/betrieb.py pruefe
    docker compose --env-file .env.server exec -T app python scripts/betrieb.py tagesabschluss SF1 > abschluss.csv
    docker compose --env-file .env.server exec -T app python scripts/betrieb.py tagesabschluss SF1 --datum 2026-10-02
    docker compose --env-file .env.server exec -T app python scripts/betrieb.py zaehlstatus SF1 --seit "2026-10-02 06:00"

`pruefe` beendet sich mit Code 1, wenn der Bestand nicht zur Summe der
Lagerbewegungen passt (Regel 2). `tagesabschluss` schreibt CSV auf die
Standardausgabe (Spalten: art, ean, marke, bezeichnung, lieferanten_artikelnr,
farbe, groesse, menge, grund) und eine Zusammenfassung auf die Fehlerausgabe.
Zeiten sind Zürcher Zeit.
"""

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SPALTEN = ["art", "ean", "marke", "bezeichnung", "lieferanten_artikelnr", "farbe", "groesse", "menge", "grund"]


def _lagerort_id(session, code):
    from sqlalchemy import select

    from app.core.models import Lagerort

    lagerort_id = session.scalar(select(Lagerort.id).where(Lagerort.code == code.upper()))
    if lagerort_id is None:
        raise SystemExit(f"Unbekannter Lagerort: {code}")
    return lagerort_id


def main(argv=None, session_factory=None, out=None, err=None) -> int:
    from app.services.betriebsberichte import pruefe_bestand, tagesabschluss, zaehlstatus

    out = out or sys.stdout
    err = err or sys.stderr
    if session_factory is None:
        from app.core.database import SessionLocal as session_factory

    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    teil = cli.add_subparsers(dest="befehl", required=True)
    p = teil.add_parser("pruefe", help="Bestand gegen Lagerbewegungen prüfen")
    p.add_argument("lagerort", nargs="?", help="Lagerort-Code, sonst alle")
    p = teil.add_parser("tagesabschluss", help="Buchungen eines Tages als CSV")
    p.add_argument("lagerort")
    p.add_argument("--datum", type=date.fromisoformat, help="YYYY-MM-DD, Standard heute")
    p = teil.add_parser("zaehlstatus", help="Fortschritt der Eröffnungszählung")
    p.add_argument("lagerort")
    p.add_argument("--seit", required=True, type=datetime.fromisoformat, help="YYYY-MM-DD HH:MM (Zürcher Zeit)")
    p.add_argument("--liste", action="store_true", help="auch alle offenen Zeilen ausgeben")
    args = cli.parse_args(argv)

    with session_factory() as session:
        if args.befehl == "pruefe":
            lagerort_id = _lagerort_id(session, args.lagerort) if args.lagerort else None
            ergebnis = pruefe_bestand(session, lagerort_id)
            print(f"Geprüft: {ergebnis['geprueft']} Zeilen, negativ: {ergebnis['negativ']}", file=out)
            for z in ergebnis["abweichungen"]:
                print(
                    f"ABWEICHUNG Variante {z['varianten_id']} Lagerort {z['lagerort_id']}: "
                    f"Bestand {z['bestand']}, Summe der Bewegungen {z['summe_bewegungen']}",
                    file=out,
                )
            print("OK" if ergebnis["ok"] else "FEHLER: Bestand passt nicht zu den Lagerbewegungen", file=out)
            return 0 if ergebnis["ok"] else 1

        if args.befehl == "tagesabschluss":
            from zoneinfo import ZoneInfo

            tag = args.datum or datetime.now(ZoneInfo("Europe/Zurich")).date()
            bericht = tagesabschluss(session, _lagerort_id(session, args.lagerort), tag)
            schreiber = csv.DictWriter(out, fieldnames=SPALTEN, extrasaction="ignore", lineterminator="\n")
            schreiber.writeheader()
            schreiber.writerows(bericht["zeilen"])
            print(
                f"{bericht['lagerort']['code']} {bericht['tag']}: verkauft {bericht['verkauft_stueck']} Stück, "
                f"{bericht['zaehlungen']} Zählung(en), {len(bericht['zeilen'])} Zeile(n)",
                file=err,
            )
            return 0

        status = zaehlstatus(session, _lagerort_id(session, args.lagerort), args.seit)
        print(
            f"{args.lagerort.upper()} seit {args.seit:%Y-%m-%d %H:%M}: {status['gezaehlt']} von "
            f"{status['zeilen']} Zeilen gezählt, {status['offen']} offen ({status['offen_stueck']} Stück im System)",
            file=out,
        )
        if args.liste:
            for z in status["offen_liste"]:
                name = " ".join(filter(None, [z["marke"], z["bezeichnung"], z["farbe"], z["groesse"]]))
                print(f"  offen: {z['ean'] or '-'}  {name}  Bestand {z['bestand']}", file=out)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
