import os
import argparse
import urllib.parse



def debug(msg):
    print(f"[DEBUG] {msg}")

def verbose_debug(msg):
    print(f"[VERBOSE DEBUG] {msg}")


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


def build_mermaid_graph(pid, p, fams, name_of):
    """Build a Mermaid graph showing the person's immediate family relationships."""
    lines = ["```mermaid", "flowchart TD", 
            "classDef person fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;",
            "classDef internal-link fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;"]
    
    # Helper to create node IDs and labels
    def node_id(iid): return f'id{iid.replace("@", "")}'
    def node_label(iid): 
        name = name_of.get(iid, iid)
        # Remove problematic characters from display name
        name = name.replace('"', "'")
        return name
    def make_node(iid):
        node = node_id(iid)
        name = node_label(iid)
        lines.append(f'{node}["{name}"]')
        lines.append(f'class {node} internal-link')
        return node
    
    # Add the central person
    person_node = make_node(pid)
    
    # Add parents and their relationship
    if p["famc"] in fams:
        fam = fams[p["famc"]]
        if fam.get("husband") or fam.get("wife"):
            # Parents
            father_node = None
            mother_node = None
            if fam.get("husband"):
                father_node = make_node(fam["husband"])
            if fam.get("wife"):
                mother_node = make_node(fam["wife"])
            
            # Marriage connection
            if father_node and mother_node:
                marriage_node = f'marriage_{node_id(fam["id"])}'
                lines.append(f'{marriage_node}((" "))')
                lines.append(f'{father_node} --- {marriage_node}')
                lines.append(f'{mother_node} --- {marriage_node}')
                lines.append(f'{marriage_node} --> {person_node}')
            else:
                # Single parent
                parent_node = father_node or mother_node
                lines.append(f'{parent_node} --> {person_node}')
    
    # Add spouses and children
    for fid in p["fams"]:
        if fid not in fams:
            continue
        fam = fams[fid]
        
        # Add spouse
        spouse_id = None
        if fam.get("husband") == pid and fam.get("wife"):
            spouse_id = fam["wife"]
        elif fam.get("wife") == pid and fam.get("husband"):
            spouse_id = fam["husband"]
        
        if spouse_id:
            spouse_node = make_node(spouse_id)
            
            # Marriage connection
            marriage_node = f'marriage_{node_id(fid)}'
            lines.append(f'{marriage_node}((" "))')
            lines.append(f'{person_node} --- {marriage_node}')
            lines.append(f'{spouse_node} --- {marriage_node}')
            
            # Add children
            for child_id in fam.get("children", []):
                child_node = make_node(child_id)
                lines.append(f'{marriage_node} --> {child_node}')
        else:
            # Single parent with children
            for child_id in fam.get("children", []):
                child_node = make_node(child_id)
                lines.append(f'{person_node} --> {child_node}')
    
    lines.append("```")
    return "\n".join(lines)


##############################################################################
# 3) BUILD NOTES (wiki-links + bios)
##############################################################################

def build_obsidian_notes(individuals, families, out_dir, bios_dir):
    # Dictionary to map places to their Wikipedia article names
    place_to_wiki = {
        # Australia
        "Subiaco, Perth, Western Australia, Australia": "Subiaco,_Western_Australia",
        "Perth, Western Australia, Australia": "Perth,_Western_Australia",
        "Perth, WA, Australia": "Perth,_Western_Australia",
        "Perth, Australia": "Perth,_Western_Australia",
        "Perth": "Perth,_Western_Australia",
        "Sydney, NSW, Australia": "Sydney",
        "Sydney, New South Wales, Australia": "Sydney",
        "Brisbane, Queensland, Australia": "Brisbane",
        
        # Israel
        "Rehovot, Israel": "Rehovot",
        "Rehovot, Center District, Israel": "Rehovot",
        "Jerusalem": "Jerusalem",
        
        # Europe
        "Wien, Austria": "Vienna",
        "Vienna, Vienna, Austria": "Vienna",
        "Nikolsburg (Mikulov), Moravia, Czechoslovakia": "Mikulov",
        "Blackburn, Lancashire, England (United Kingdom)": "Blackburn,_Lancashire",
        "Pitten or Schwarzau am Steinfeld, near Neunkirchen, Lower Austria, Austria": "Neunkirchen,_Lower_Austria",
        
        # Eastern Europe/Asia
        "Savran, Podolia, Odessa oblast, Ukraine": "Savran,_Ukraine",
        "Bershad, Ukraine": "Bershad",
        "Hamedan, Iran, Islamic Republic of": "Hamadan",
        
        # Add more mappings as needed
    }

    inds = {i: norm_individual(i, d) for i, d in individuals.items()}
    fams = {f: norm_family(f, d) for f, d in families.items()}
    name_of = {i: info["name"] or i for i, info in inds.items()}

    wl = lambda lbl: f"[[{lbl or 'Unknown'}]]"  # For person links
    def wl_place(place):
        if not place:   
            return ""
        # Try to find a mapping, if not found use the place name directly
        wiki_name = place_to_wiki.get(place, place.replace(" ", "_"))
        return f"[{place}](https://en.wikipedia.org/wiki/{wiki_name})"
    ptr = lambda iid: wl(name_of.get(iid, iid)) if iid else ""

    people_dir = os.path.join(out_dir, "People")
    os.makedirs(people_dir, exist_ok=True)

    verbose_debug(f"Output directory for profiles: {people_dir}")
    verbose_debug(f"Bios directory: {bios_dir}")
    verbose_debug(f"Checking if bios directory exists: {os.path.exists(bios_dir)}")
    if os.path.exists(bios_dir):
        verbose_debug(f"Listing files in bios directory: {os.listdir(bios_dir)}")

    # Build index of profiles for people
    profile_index_lines = ["All People", ""]
    for pid, p in inds.items():
        profile_index_lines.append(f"- [[{p['name']}]]")

    with open(os.path.join(people_dir, "index.md"), "w", encoding="utf-8") as f:
        f.write("# People\n\n")
        f.write("\n".join(profile_index_lines))
        f.write("\n")

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
        verbose_debug(f"Looking for bio for ID: {id_clean}")
        for ext in ("md", "MD"):
            bio_path = os.path.join(bios_dir, f"{id_clean}.{ext}")
            verbose_debug(f"Checking bio path: {bio_path}")
            verbose_debug(f"Bio file exists: {os.path.isfile(bio_path)}")
            if os.path.isfile(bio_path):
                with open(bio_path, encoding="utf-8") as bf:
                    bio_text = bf.read().replace('\r', '').strip()
                verbose_debug(f"Found bio for {p['name']} at {bio_path}")
                break

        bp_link = wl_place(p["birth_place"]) if p["birth_place"] else ""
        dp_link = wl_place(p["death_place"]) if p["death_place"] else ""

        # Generate Mermaid family tree diagram
        mermaid_diagram = build_mermaid_graph(pid, p, fams, name_of)

        lines = [
            "---",
            "type: profile",
            "title: " + p['name'],
            "---",
            f"**Birth**: {p['birth_date']}" + (f" at {bp_link}" if bp_link else ""),
            f"**Death**: {p['death_date']}" + (f" at {dp_link}" if dp_link else ""),
            f"**Occupation**: {p['occupation'] or '—'}",
            mermaid_diagram,
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

    # Build index of bios (profiles with biographies)
    bios_index_lines = ["Profiles with Biographies", "This page lists all family members who have biographical information.", ""]
    for pid, p in inds.items():
        id_clean = safe_filename(pid)
        for ext in ("md", "MD"):
            bio_path = os.path.join(bios_dir, f"{id_clean}.{ext}")
            verbose_debug(f"Checking bio path: {bio_path}")
            verbose_debug(f"Bio file exists: {os.path.isfile(bio_path)}")
            if os.path.isfile(bio_path):
                bios_index_lines.append(f"- [[{p['name']}]]")
                break

    with open(os.path.join(people_dir, "bios.md"), "w", encoding="utf-8") as f:
        f.write("# Biographies\n\n")
        f.write("\n".join(bios_index_lines))
        f.write("\n")


##############################################################################
# 4) CREATE People/index.md  ### NEW
##############################################################################

def write_people_index(people_dir):
    """Create/overwrite People/index.md with Markdown links."""
    files = sorted(
        f for f in os.listdir(people_dir)
        if f.lower().endswith(".md") and f != "index.md"
    )

    profile_files = []
    for fname in files:
        file_path = os.path.join(people_dir, fname)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if "type: profile" in content.split("---")[1]:
                profile_files.append(fname)

    lines = ["# All People\n"]
    for fname in profile_files:
        title = fname[:-3]                      # strip .md
        url   = urllib.parse.quote(fname)       # encode spaces/עברית
        lines.append(f"* [{title}]({url})")

    with open(os.path.join(people_dir, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


##############################################################################
# 5) CLI
##############################################################################

def collect_unique_places(individuals):
    """Collect all unique birth and death places from individuals."""
    places = set()
    for person in individuals.values():
        birth_place = person.get("BIRT", {}).get("PLAC")
        death_place = person.get("DEAT", {}).get("PLAC")
        if birth_place:
            places.add(birth_place)
        if death_place:
            places.add(death_place)
    return sorted(places)

def analyze_places(individuals):
    """Analyze and collect all unique places from the GEDCOM file.
    
    This helps maintain the place_to_wiki mapping dictionary by showing:
    1. All unique places that need mapping
    2. Which places are variants of the same location
    3. Places that might be missing from the mapping
    """
    places = {}  # place -> count
    for person in individuals.values():
        birth = person.get("BIRT", {})
        death = person.get("DEAT", {})
        residence = person.get("RESI", {})
        
        if "PLAC" in birth:
            place = birth["PLAC"]
            places[place] = places.get(place, 0) + 1
        if "PLAC" in death:
            place = death["PLAC"]
            places[place] = places.get(place, 0) + 1
        if "PLAC" in residence:
            place = residence["PLAC"]
            places[place] = places.get(place, 0) + 1
    
    # Sort by count descending
    sorted_places = sorted(places.items(), key=lambda x: (-x[1], x[0]))
    
    print("\nPlace Analysis:")
    print("===============")
    for place, count in sorted_places:
        print(f"{count:2d}x {place}")
    print("\nTotal unique places:", len(places))
    return places

def write_bios_index(people_dir, bios_dir):
    """Create/overwrite People/bios.md with links to profiles that have biographies."""
    # Get all biography files
    bio_ids = {
        os.path.splitext(f)[0] 
        for f in os.listdir(bios_dir) 
        if f.endswith(('.md', '.MD'))
    }
    
    # Get all profile files that have matching bios
    profiles_with_bios = []
    for fname in sorted(os.listdir(people_dir)):
        if not fname.endswith('.md') or fname in ('index.md', 'bios.md'):
            continue
            
        profile_path = os.path.join(people_dir, fname)
        with open(profile_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Extract the GEDCOM ID from the profile
        if '**GEDCOM ID**: @' in content:
            gedcom_id = content.split('**GEDCOM ID**: @')[1].split('@')[0]
            if gedcom_id in bio_ids:
                profiles_with_bios.append((fname[:-3], fname))  # (title, filename)

    # Create the index page
    lines = [
        "# Profiles with Biographies\n",
        "This page lists all family members who have biographical information.\n"
    ]
    
    if profiles_with_bios:
        for title, fname in profiles_with_bios:
            url = urllib.parse.quote(fname)
            lines.append(f"* [{title}]({url})")
    else:
        lines.append("*No biographical information available yet.*")

    with open(os.path.join(people_dir, "bios.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def main():
    argp = argparse.ArgumentParser(description="GEDCOM ➜ Obsidian notes + bios merge")
    argp.add_argument("gedcom_file", help="Path to .ged file")
    argp.add_argument("-o", "--output", default="ObsidianVault", help="Output directory")
    argp.add_argument("--bios-dir", default=None, help="Directory with bio *.md files (default: <o>/bios)")
    argp.add_argument("--analyze-places", action="store_true", help="Analyze unique places in the GEDCOM file")
    args = argp.parse_args()

    args.bios_dir = args.bios_dir or os.path.join(args.output, "bios")
    os.makedirs(args.output, exist_ok=True)
    os.makedirs(args.bios_dir, exist_ok=True)

    individuals, families = parse_gedcom_file(args.gedcom_file)
    
    if args.analyze_places:
        analyze_places(individuals)
        return

    build_obsidian_notes(individuals, families, args.output, args.bios_dir)

    people_dir = os.path.join(args.output, "People")
    write_people_index(people_dir)  # Write main index
    write_bios_index(people_dir, args.bios_dir)  # Write bios index

    debug(f"Done → {args.output}")


if __name__ == "__main__":
    main()
