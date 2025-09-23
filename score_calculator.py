import sys
import zipfile
import io
import re
import json
from jinja2 import Environment, FileSystemLoader

def extract_players_countries_as_dict(gamestate_data):
    match = re.search(r'players_countries\s*=\s*\{([^}]+)\}', gamestate_data, re.DOTALL)
    if not match:
        print("No players_countries block found.")
        return {}

    raw_entries = match.group(1).strip().split('\n')
    entries = [entry.strip().strip('"') for entry in raw_entries if entry.strip()]

    result = {}
    for i in range(0, len(entries) - 1, 2):
        key = entries[i]
        value = entries[i+1]
        result[key] = value

    if len(entries) % 2 != 0:
        result[entries[-1]] = None

    return result

def extract_country_data(gamestate_data, players_countries):
    in_countries_block = False
    brace_depth = 0
    current_tag = None
    parent_block = None
    regiment_block = False
    current_data = {}
    result = []


    tag_to_player = {tag: player for player, tag in players_countries.items()}

    i = 0
    while i < len(gamestate_data):
        line = gamestate_data[i].strip()

        if not in_countries_block and line.startswith('countries'):
            if '{' in line:
                in_countries_block = True
                brace_depth = 1
                i += 1
                continue

        if in_countries_block:
            if brace_depth == 1:
                if '=' in line and '{' in line:
                    parts = line.split('=')
                    current_tag = parts[0].strip()

                    current_data = {
                        'tag': current_tag,
                        'original_tag': current_tag,
                        'player': tag_to_player[current_tag] if current_tag in tag_to_player else 'Unknown',
                        'victory_cards': [],
                        'victory_card_score': 0,
                        'losses': 0,
                        'max_morale' : 0
                    }

                    if(len(current_tag) != 3):
                        current_data = None

                    brace_depth += 1
                    i += 1
                    continue

            elif brace_depth >= 2:
                if current_data is not None:
                    if brace_depth == 2:
                        if line.startswith('raw_development'):
                            val = line.split('=')[1].strip()
                            current_data['development'] = float(val)

                        elif line.startswith('victory_card'):
                            parent_block = 'victory_card'

                        elif line.startswith('active_idea_groups'):
                            parent_block = 'active_idea_groups'
                            current_data['active_idea_groups'] = []

                        elif line.startswith('max_manpower'):
                            current_data['max_manpower'] = line.split('=')[1].strip()

                        elif line.startswith('army_professionalism'):
                            val = line.split('=')[1].strip()
                            current_data['professionalism'] = float(val)


                    elif brace_depth == 3:
                        if line.startswith('lastmonthincometable'):
                            i += 1
                            line = gamestate_data[i].strip()
                            val = line.split(" ")
                            current_data['tax_income'] = float(val[0])
                            current_data['production_income'] = float(val[1])
                            current_data['trade_income'] = float(val[2])
                            i += 2
                            continue
    
                        if line.startswith('no_of_dev_clicks'):
                            val = line.split('=')[1].strip()
                            current_data['dev_clicks'] = float(val)
                        
                        elif line.startswith('starting_development'):
                            val = line.split('=')[1].strip()
                            current_data['starting_development'] = float(val)
                            
                        elif parent_block == 'victory_card':
                            if line.startswith('area'):
                                val = line.split('=')[1].strip()

                                current_data['victory_cards'].append({
                                    'area': val,
                                    'score': 0.0,
                                    'was_fulfilled': 'false',
                                })

                            elif line.startswith('was_fulfilled'):
                                val = line.split('=')[1].strip()

                                current_data['victory_cards'][-1]['was_fulfilled'] = val
                                if val == 'yes':
                                    current_data['victory_cards'][-1]['score'] = 15
                                else:
                                    current_data['victory_cards'][-1]['score'] = 0
                                
                                current_data['victory_card_score'] = current_data['victory_card_score'] + current_data['victory_cards'][-1]['score']

                                parent_block = None

                        elif line.startswith('members'):
                            parent_block = 'losses'

                        elif line.startswith('regiment'):
                            regiment_block = True

                    elif brace_depth == 4:
                        if line.startswith('changed_tag_from'):
                            val = line.split('=')[1].strip("\"")
                            current_data['original_tag'] = val

                        elif parent_block == 'losses':
                            val = line.split(" ")
                            if len(val) >= 7:
                                current_data['losses'] += int(val[0]) + int(val[3]) + int(val[6])
                            parent_block = None
                        
                        elif regiment_block and line.startswith('morale'):
                            val = line.split('=')[1].strip()
                            morale = float(val)
                            if morale > current_data['max_morale']:
                                current_data['max_morale'] = morale
                            regiment_block = False

                previous_brace_depth = brace_depth
                brace_depth += line.count('{')
                brace_depth -= line.count('}')
                if(previous_brace_depth > brace_depth):
                    parent_block = None

                if brace_depth == 1:
                    if current_data is not None and current_data['player'] != "Unknown":
                        result.append(current_data)
                    current_data = None

                elif brace_depth == 0:
                    break

        i += 1

    return result

# def get_country_with_most_losses(country_data):
#     result = {
#         'tag': None,
#         'losses': -1
#     }

#     for country in country_data:
#         losses = country.get('losses', 0)
#         if losses > result['losses']:
#             result['losses'] = losses
#             result['tag'] = country['tag']

#     return result

# def get_most_dev_province(gamestate_data):
#     in_provinces_block = False
#     brace_depth = 0
#     current_province = None
#     current_data = {}
#     result = {'development': 0.0}

#     i = 0
#     while i < len(gamestate_data):
#         line = gamestate_data[i].strip()

#         if not in_provinces_block:
#             brace_depth += line.count('{')
#             brace_depth -= line.count('}')
#             if line.startswith('provinces={') and brace_depth == 1:
#                 in_provinces_block = True
#                 brace_depth = 1
#                 i += 1
#                 continue

#         if in_provinces_block:
#             if brace_depth == 1:
#                 if '=' in line and '{' in line:
#                     parts = line.split('=')
#                     current_province = parts[0].strip()

#                     current_data = {
#                         'id': current_province,
#                         'development': 0,
#                     }
#                     brace_depth += 1
#                     i += 1
#                     continue

#             elif brace_depth >= 2:
#                 if current_data is not None:
#                     if line.startswith('name') and brace_depth == 2:
#                         val = line.split('=')[1].strip('""')
#                         current_data['name'] = val

#                     elif line.startswith('owner') and brace_depth == 2:
#                         val = line.split('=')[1].strip('""')
#                         current_data['owner'] = val

#                     elif line.startswith('base_tax') and brace_depth == 2:
#                         val = line.split('=')[1].strip()
#                         current_data['base_tax'] = float(val)
#                         current_data['development'] += float(val)

#                     elif line.startswith('base_production') and brace_depth == 2:
#                         val = line.split('=')[1].strip()
#                         current_data['base_production'] = float(val)
#                         current_data['development'] += float(val)

#                     elif line.startswith('base_manpower') and brace_depth == 2:
#                         val = line.split('=')[1].strip()
#                         current_data['base_manpower'] = float(val)
#                         current_data['development'] += float(val)

#                 brace_depth += line.count('{')
#                 brace_depth -= line.count('}')

#                 if brace_depth == 1:
#                     if current_data is not None and current_data['development'] > result['development']:
#                         result = current_data
#                     current_data = None

#                 elif brace_depth == 0:
#                     break

#         i += 1
#     return result

def enrich_country_data_with_ideas(country_data):
    tag_to_file = {}

    with open('./eu4_data/00_countries.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.match(r'(\w+)\s*=\s*"([^"]+)"', line)
            if match:
                tag, path = match.groups()
                tag_to_file[tag] = path

    for entry in country_data:
        original_tag = entry.get('original_tag')
        tag = entry.get('tag')
        filename = tag_to_file.get(original_tag)
        entry['name'] = tag_to_file.get(tag).split('/')[-1].replace('.txt', '').replace('_', ' ').title() if filename else 'Unknown'

    return country_data

def get_empire_data(gamestate_data):
    current_block = None
    brace_depth = 0
    electors_block = False
    HRE_data = {
        'hre_dismantled': False,
        'emperor': None,
        'level': 0,
        'electors': [],
    }
    CHINA_data = {
        'emperor': None,
        'level': 0,
    }

    i = 0
    while i < len(gamestate_data):
        line = gamestate_data[i].strip()

        if current_block is None:
            brace_depth += line.count('{')
            brace_depth -= line.count('}')
            if line.startswith('empire={') and brace_depth == 1:
                current_block = 'HRE'
                brace_depth = 1
                i += 1
                continue
            if line.startswith('celestial_empire={') and brace_depth == 1:
                current_block = 'CHINA'
                brace_depth = 1
                i += 1
                continue

        if current_block == 'HRE':
            if line.startswith('hre_dismantled='):
                val = line.split('=')[1].strip('""')
                HRE_data['hre_dismantled'] = val
                if val == 'yes':
                    current_block = None
                    brace_depth = 1

            elif line.startswith('emperor='):
                val = line.split('=')[1].strip('""')
                HRE_data['emperor'] = val

            elif line.startswith('passed_reform='):
                HRE_data['level'] += 1
            
            elif line.startswith('electors='):
                electors_block = True
            
            elif electors_block and brace_depth == 2:
                val = line.split(" ")
                HRE_data['electors'] = val
                electors_block = False


            brace_depth += line.count('{')
            brace_depth -= line.count('}')

            if brace_depth == 0:
                current_block = None

        if current_block == 'CHINA':

            if line.startswith('emperor='):
                val = line.split('=')[1].strip('""')
                CHINA_data['emperor'] = val

            elif line.startswith('passed_reform='):
                CHINA_data['level'] += 1

            brace_depth += line.count('{')
            brace_depth -= line.count('}')

            if brace_depth == 0:
                current_block = None

        i += 1
    return HRE_data, CHINA_data

def add_manual_stats_from_json(country_data, json_path='manual_stats.json'):
    """
    Loads manual stats (force_limit, naval_force_limit, discipline) from a JSON file
    and updates the corresponding countries in country_data.
    The JSON should be a dict: { "TAG": { "force_limit": X, "naval_force_limit": Y, "discipline": Z }, ... }
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            manual_stats = json.load(f)
    except FileNotFoundError:
        print(f"Manual stats file '{json_path}' not found. Skipping manual stats.")
        return country_data

    for country in country_data:
        tag = country.get('tag')
        if tag in manual_stats:
            for stat in ['force_limit', 'naval_force_limit', 'discipline']:
                if stat in manual_stats[tag]:
                    country[stat] = manual_stats[tag][stat]
    return country_data

def get_top_stats(country_data):
    stats = {
        'development': [],
        'dev_clicks': [],
        'tax_income': [],
        'trade_income': [],
        'production_income': [],
        'max_manpower': [],
        'max_morale': [],
        'losses': [],
        'force_limit': [],
        'naval_force_limit': [],
        'discipline': []
    }
    # Prepare lists for each stat, filtering out missing values
    for stat in stats.keys():
        stats[stat] = [
            (country['tag'], float(country.get(stat, 0)))
            for country in country_data if stat in country
        ]
        # Sort descending by value
        stats[stat].sort(key=lambda x: x[1], reverse=True)

    # Get top 3, 2, 1 for each stat
    top_stats = {}
    for stat, values in stats.items():
        top_stats[stat] = values[:3]
    return top_stats

def generate_html_report(date, sorted_data, hre_data, china_data, top_stats):
    env = Environment(loader=FileSystemLoader('./templates'))
    template = env.get_template('report_template.html')

    html_content = template.render(
        date=date,
        sorted_data=sorted_data,
        hre_data=hre_data,
        china_data=china_data,
        top_stats=top_stats,
    )

    return html_content

def calculate_country_scores(country_data, hre_data, china_data, top_stats):
    for country in country_data:
        if 'development' not in country:
            country['development'] = 0.0
        if 'starting_development' not in country:
            country['starting_development'] = 0.0

        growth_score = country['development'] / (country['starting_development'] if country['starting_development'] > 0 else 1)
        growth_score = min(growth_score, 20)
        victory_card_score = 0
        if 'victory_card_score' in country:
            victory_card_score = country['victory_card_score']


        misc_score = 0

        if hre_data.get('emperor') == country.get('tag'):
            misc_score += 10

        if china_data.get('emperor') == country.get('tag'):
            misc_score += 5
            misc_score += china_data.get('level', 0) * 3

        if country.get('tag') in hre_data.get('electors') or hre_data.get('emperor') == country.get('tag'):
            misc_score += hre_data.get('level', 0) * 5

        country['top_1'] = []
        country['top_1_score'] = 0
        country['top_2'] = []
        country['top_2_score'] = 0
        country['top_3'] = []
        country['top_3_score'] = 0
        for stat in top_stats:
            for idx, (tag, value) in enumerate(top_stats[stat]):
                if tag == country.get('tag'):
                    if idx == 0:
                        country['top_1'].append({stat: value})
                        country['top_1_score'] += 7
                    elif idx == 1:
                        country['top_2'].append({stat: value})
                        country['top_2_score'] += 5
                    elif idx == 2:
                        country['top_3'].append({stat: value})
                        country['top_3_score'] += 3
    

        total_score = growth_score + victory_card_score + misc_score + country['top_1_score'] + country['top_2_score'] + country['top_3_score']

        country['growth_score'] = growth_score
        country['victory_card_score'] = victory_card_score
        country['misc_score'] = misc_score
        country['total_score'] = total_score

    return country_data

def print_country_table(sorted_data):
    headers = [
        ("No", 2),
        ("Player", 15),
        ("Tag", 22),
        ("Country Name", 18),
        ("Growth", 7),
        ("VC", 7),
        ("Misc", 5),
        ("Top 1", 7),
        ("Top 2", 7),
        ("Top 3", 7),
        ("Total", 8)
    ]
    # Build header
    header_line = " ".join(f"{h:<{w}}" for h, w in headers)
    sep_line = "-" * len(header_line)
    lines = [header_line, sep_line]
    # Build rows
    for idx, country in enumerate(sorted_data, 1):
        tag_str = country['tag']
        if country.get('original_tag') and country['original_tag'] != country['tag']:
            tag_str += f" (Orig: {country['original_tag']})"
        row = [
            str(idx),
            str(country.get('player', ''))[:15],
            tag_str[:22],
            str(country.get('name', ''))[:18],
            f"{country.get('growth_score', 0):.2f}",
            str(country.get('victory_card_score', 0)),
            str(country.get('misc_score', '')),
            str(country.get('top_1_score', 0)),
            str(country.get('top_2_score', 0)),
            str(country.get('top_3_score', 0)),
            f"{country.get('total_score', 0):.2f}",
        ]
        lines.append(" ".join(f"{val:<{w}}" for val, (_, w) in zip(row, headers)))
    # Wrap in code block
    return "```\n" + "\n".join(lines) + "\n```"


def main():
    if len(sys.argv) != 2:
        print("Usage: python score_calculator.py <save_file.eu>")
        return

    save_file = sys.argv[1]

    try:
        with open(save_file, 'rb') as f:
            zip_bytes = io.BytesIO(f.read())

        with zipfile.ZipFile(zip_bytes) as z:
            with z.open('gamestate') as gamestate_file:
                gamestate_data = gamestate_file.read().decode('utf-8', errors='ignore')

        with zipfile.ZipFile(zip_bytes) as z:
            with z.open('meta') as gamestate_file:
                meta_data = gamestate_file.read().decode('utf-8', errors='ignore')

        date = re.search(r'date=.+', meta_data)
        date = date.group(0).split("=")[1] if date else "Unknown date"

        players_countries = extract_players_countries_as_dict(gamestate_data)
        country_data = extract_country_data(gamestate_data.splitlines(), players_countries)
        country_data = enrich_country_data_with_ideas(country_data)
        # country_data = add_modifier_data(country_data)
        country_data = add_manual_stats_from_json(country_data, 'manual_stats.json')
        HRE_data, CHINA_data = get_empire_data(gamestate_data.splitlines())
        
        top_stats = get_top_stats(country_data)

        country_data = calculate_country_scores(country_data, HRE_data, CHINA_data, top_stats)

        # Only keep countries with a player (not 'Unknown')
        # sorted_data = sorted(
        #     [c for c in country_data if c.get('player') != 'Unknown'],
        #     key=lambda x: x['total_score'],
        #     reverse=True
        # )
        sorted_data = sorted(
            country_data,
            key=lambda x: (x['total_score']),
            reverse=True
        )


        html_report = generate_html_report(date, sorted_data, HRE_data, CHINA_data, top_stats)

        print(print_country_table(sorted_data))


        with open('index.html', 'w') as report_file:
            report_file.write(html_report)

    except FileNotFoundError as e:
        print(f"File not found: {e.filename}")
    except KeyError as e:
        print(e)
    except zipfile.BadZipFile:
        print(f"The file '{save_file}' is not a valid zip archive.")

if __name__ == "__main__":
    main()