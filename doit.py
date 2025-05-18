import os
import argparse


def debug(msg):
    print(f"[DEBUG] {msg}")


def safe_filename(name: str) -> str:
    """Return a filename-safe version of *name* (עברית, (), ', -, _)."""
    allowed = "-_ ()'"
    return "".join(c if c.isalnum() or c in allowed else "_" for c in name).strip()


##############################################################################
# 1) PARSE GEDCOM → (individuals, families)
##############################################################################

def parse_gedcom_file(path):
    """Parse a GEDCOM file into dictionaries of individuals and families."""
    debug(f"Loading GEDCOM file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    individuals, families = {}, {}
    current_id = current_type = None
    in_birt = in_deat = False

    for raw in lines:
        raw = raw.rstrip("\r\n")
        if not raw.strip():
            continue
        parts = raw.split(" ", 2)
        if len(parts) < 2:
            continue
        level, tag = parts[0], parts[1]
        try:
            level = int(level)
        except ValueError:
            continue
        data = parts[2].strip() if len(parts) > 2 else ""

        # New record pointer
        if level == 0 and tag.startswith("@"):
            current_id = tag
            current_type = data.split(" ", 1)[0] if data else "UNKNOWN"
            if current_type == "INDI":
                individuals.setdefault(current_id, {})
            elif current_type == "FAM":
                families.setdefault(current_id, {})
            in_birt = in_deat = False
            continue

        # Individuals
        if current_type == "INDI":
            indi = individuals[current_id]
            if level == 1:
                in_birt = in_deat = False
                if tag == "NAME":
                    indi["NAME"] = data
                elif tag == "FAMC":
                    indi["FAMC"] = data
                elif tag == "FAMS":
                    indi.setdefault("FAMS", []).append(data)
                elif tag == "BIRT":
                    indi["BIRT"] = {}
                    in_birt = True
                elif tag == "DEAT":
                    indi["DEAT"] = {}
                    in_deat = True
                elif tag in ("OCCU", "NOTE", "RESI"):
                    indi[tag] = data
                else:
                    indi[tag] = data
            elif level == 2:
                if in_birt:
                    indi.setdefault("BIRT", {})[tag] = data
                elif in_deat:
                    indi.setdefault("DEAT", {})[tag] = data

        # Families
        elif current_type == "FAM":
            fam = families[current_id]
            if level == 1:
                if tag in ("HUSB", "WIFE"):
                    fam[tag] = data
                elif tag == "CHIL":
                    fam.setdefault("CHIL", []).append(data)
                else:
                    fam[tag] = data

    return individuals, families


##############################################################################
# 2) NORMALISE HELPERS
##############################################################################

def norm_individual(iid, d):
    birt, deat = d.get("BIRT", {}), d.get("DEAT", {})
    fams = d.get("FAMS", [])
    if isinstance(fams, str):
        fams = [fams]
    return {
        "id": iid,
        "name": d.get("NAME", "").replace("/", "").strip(),
        "birth_date": birt.get("DATE", ""),
        "birth_place": birt.get("PLAC", ""),
        "death_date": deat.get("DATE", ""),
        "death_place": deat.get("PLAC", ""),
        "occupation": d.get("OCCU", ""),
        "notes": d.get("NOTE", ""),
        "famc": d.get("FAMC", ""),
        "fams": fams,
    }


def norm_family(fid, d):
    kids = d.get("CHIL", [])
    if isinstance(kids, str):
        kids = [kids]
    return {"id": fid, "husband": d.get("HUSB", ""), "wife": d.get("WIFE", ""), "children": kids}


##############################################################################
# 3) BUILD NOTES (wiki-links + bios)
##############################################################################

def build_obsidian_notes(individuals, families, out_dir, bios_dir):
    inds = {i: norm_individual(i, d) for i, d in individuals.items()}
    fams = {f: norm_family(f, d) for f, d in families.items()}
    name_of = {i: info["name"] or i for i, info in inds.items()}

    wl  = lambda lbl: f"[[{lbl or 'Unknown'}]]"
    ptr = lambda iid: wl(name_of.get(iid, iid)) if iid else ""

    people_dir = os.path.join(out_dir, "People")
    os.makedirs(people_dir, exist_ok=True)

    for pid, p in inds.items():
        parents, siblings = [], []
        if p["famc"] and p["famc"] in fams:
            fam = fams[p["famc"]]
            parents  = [ptr(x) for x in (fam.get("husband"), fam.get("wife")) if x]
            siblings = [ptr(c) for c in fam["children"] if c != pid]

        spouses, children = [], []
        for fid in p["fams"]:
            fam = fams.get(fid)
            if not fam:
                continue
            if fam.get("husband") == pid and fam.get("wife"):
                spouses.append(ptr(fam["wife"]))
            elif fam.get("wife") == pid and fam.get("husband"):
                spouses.append(ptr(fam["husband"]))
            children.extend(ptr(c) for c in fam["children"] if c != pid)

        id_clean = pid.replace("@", "")
        bio_text = ""
        for ext in ("md", "MD"):
            bio_path = os.path.join(bios_dir, f"{id_clean}.{ext}")
            if os.path.isfile(bio_path):
                with open(bio_path, encoding="utf-8") as bf:
                    bio_text = bf.read().strip()
                break

        bp_link = wl(p["birth_place"]) if p["birth_place"] else ""
        dp_link = wl(p["death_place"]) if p["death_place"] else ""

        lines = [
            f"# {p['name']}",
            f"**Birth**: {p['birth_date']}" + (f" at {bp_link}" if bp_link else ""),
            f"**Death**: {p['death_date']}" + (f" at {dp_link}" if dp_link else ""),
            f"**Occupation**: {p['occupation'] or '—'}",
            "\n**Parents**:\n"   + ("\n".join(parents)  or "—"),
            "\n**Siblings**:\n" + ("\n".join(siblings) or "—"),
            "\n**Spouse**:\n"   + ("\n".join(spouses)  or "—"),
            "\n**Children**:\n" + ("\n".join(children) or "—"),
            "\n**Notes**:\n"    + (p['notes'] or "—"),
        ]

        if bio_text:
            lines += ["", "**Biography**:", bio_text]

        lines.append(f"\n**GEDCOM ID**: {pid}")

        out_path = os.path.join(people_dir, safe_filename(p["name"] or pid) + ".md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


##############################################################################
# 4) CREATE People/index.md  ### NEW
##############################################################################

def write_people_index(people_dir):
    """Create (or overwrite) People/index.md with a list of all profiles."""
    files = sorted(
        f for f in os.listdir(people_dir)
        if f.lower().endswith(".md") and f != "index.md"
    )
    lines = ["# All People\n"]
    lines += [f"* [[{f[:-3]}]]" for f in files]   # strip .md
    with open(os.path.join(people_dir, "index.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


##############################################################################
# 5) CLI
##############################################################################

def main():
    argp = argparse.ArgumentParser(description="GEDCOM ➜ Obsidian notes + bios merge")
    argp.add_argument("gedcom_file", help="Path to .ged file")
    argp.add_argument("-o", "--output", default="ObsidianVault", help="Output directory")
    argp.add_argument("--bios-dir", default=None, help="Directory with bio *.md files (default: <output>/bios)")
    args = argp.parse_args()

    args.bios_dir = args.bios_dir or os.path.join(args.output, "bios")

    os.makedirs(args.output, exist_ok=True)
    debug("Parsing GEDCOM …")
    inds, fams = parse_gedcom_file(args.gedcom_file)
    debug(f"{len(inds)} individuals • {len(fams)} families")
    debug("Building Markdown notes …")
    build_obsidian_notes(inds, fams, args.output, args.bios_dir)

    ### NEW: כתוב עמוד אינדקס לאנשים
    write_people_index(os.path.join(args.output, "People"))

    debug(f"Done → {args.output}")


if __name__ == "__main__":
    main()
