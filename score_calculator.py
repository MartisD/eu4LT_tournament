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
                        'victory_card_score': 0.0,
                        'losses': 0,
                    }

                    if(len(current_tag) != 3):
                        current_data = None

                    brace_depth += 1
                    i += 1
                    continue

            elif brace_depth >= 2:
                if current_data is not None:
                    if line.startswith('raw_development') and brace_depth == 2:
                        val = line.split('=')[1].strip()
                        current_data['development'] = float(val)

                    elif line.startswith('victory_card') and brace_depth == 2:
                        parent_block = 'victory_card'

                    elif line.startswith('active_idea_groups') and brace_depth == 2:
                        parent_block = 'active_idea_groups'
                        current_data['active_idea_groups'] = []

                    elif line.startswith('starting_development') and brace_depth == 3:
                        val = line.split('=')[1].strip()
                        current_data['starting_development'] = float(val)

                    elif line.startswith('changed_tag_from') and brace_depth == 4:
                        val = line.split('=')[1].strip("\"")
                        current_data['original_tag'] = val

                    elif parent_block == 'victory_card' and line.startswith('area') and brace_depth == 3:
                        val = line.split('=')[1].strip()

                        current_data['victory_cards'].append({
                            'area': val,
                            'score': 0.0,
                            'was_fulfilled': 'false',
                        })

                    elif parent_block == 'victory_card' and line.startswith('score') and brace_depth == 3:
                        val = line.split('=')[1].strip()

                        current_data['victory_cards'][-1]['score'] = float(val)
                        current_data['victory_card_score'] = current_data['victory_card_score'] + float(val)

                    elif parent_block == 'victory_card' and line.startswith('was_fulfilled') and brace_depth == 3:
                        val = line.split('=')[1].strip()

                        current_data['victory_cards'][-1]['was_fulfilled'] = val
                        parent_block = None

                    elif parent_block == 'active_idea_groups' and not line.startswith('}')  and brace_depth == 3:
                        val = line
                        current_data['active_idea_groups'].append(val)

                    elif brace_depth == 3 and line.startswith('members'):
                        parent_block = 'losses'
                    
                    elif parent_block == 'losses' and brace_depth == 4:
                        val = line.split(" ")
                        if len(val) >= 7:
                            current_data['losses'] += int(val[0]) + int(val[3]) + int(val[6])
                        parent_block = None

                previous_brace_depth = brace_depth
                brace_depth += line.count('{')
                brace_depth -= line.count('}')
                if(previous_brace_depth > brace_depth):
                    parent_block = None

                if brace_depth == 1:
                    if current_data is not None:
                        result.append(current_data)
                    current_data = None

                elif brace_depth == 0:
                    break

        i += 1

    return result

def get_country_with_most_losses(country_data):
    result = {
        'tag': None,
        'losses': -1
    }

    for country in country_data:
        losses = country.get('losses', 0)
        if losses > result['losses']:
            result['losses'] = losses
            result['tag'] = country['tag']

    return result

def get_most_dev_province(gamestate_data):
    in_provinces_block = False
    brace_depth = 0
    current_province = None
    current_data = {}
    result = {'development': 0.0}

    i = 0
    while i < len(gamestate_data):
        line = gamestate_data[i].strip()

        if not in_provinces_block:
            brace_depth += line.count('{')
            brace_depth -= line.count('}')
            if line.startswith('provinces={') and brace_depth == 1:
                in_provinces_block = True
                brace_depth = 1
                i += 1
                continue

        if in_provinces_block:
            if brace_depth == 1:
                if '=' in line and '{' in line:
                    parts = line.split('=')
                    current_province = parts[0].strip()

                    current_data = {
                        'id': current_province,
                        'development': 0,
                    }
                    brace_depth += 1
                    i += 1
                    continue

            elif brace_depth >= 2:
                if current_data is not None:
                    if line.startswith('name') and brace_depth == 2:
                        val = line.split('=')[1].strip('""')
                        current_data['name'] = val

                    elif line.startswith('owner') and brace_depth == 2:
                        val = line.split('=')[1].strip('""')
                        current_data['owner'] = val

                    elif line.startswith('base_tax') and brace_depth == 2:
                        val = line.split('=')[1].strip()
                        current_data['base_tax'] = float(val)
                        current_data['development'] += float(val)

                    elif line.startswith('base_production') and brace_depth == 2:
                        val = line.split('=')[1].strip()
                        current_data['base_production'] = float(val)
                        current_data['development'] += float(val)

                    elif line.startswith('base_manpower') and brace_depth == 2:
                        val = line.split('=')[1].strip()
                        current_data['base_manpower'] = float(val)
                        current_data['development'] += float(val)

                brace_depth += line.count('{')
                brace_depth -= line.count('}')

                if brace_depth == 1:
                    if current_data is not None and current_data['development'] > result['development']:
                        result = current_data
                    current_data = None

                elif brace_depth == 0:
                    break

        i += 1
    return result

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

        if not filename:
            continue

        file_path = filename

        with open('eu4_data/'+ file_path, 'r', encoding='utf-8', errors='ignore') as f:
            contents = f.read()

        match = re.search(r'historical_idea_groups\s*=\s*\{([^}]+)\}', contents)
        if match:
            raw_ideas = match.group(1).strip()
            ideas = [idea.strip() for idea in raw_ideas.splitlines() if idea.strip()]
            if 'naval_ideas' in ideas:
                ideas[ideas.index('naval_ideas')] = 'quantity_ideas'
            entry['historical_idea_groups'] = ideas
        else:
            print(f"[!] historical_idea_groups not found for {tag}")
            entry['historical_idea_groups'] = []

    return country_data

def add_modifier_data(country_data):
    import json
    with open('./modifier_scores.json', 'r', encoding='utf-8') as f:
        modifier_data = json.load(f)

    tag_to_countries = {}
    for country in country_data:
        orig_tag = country['original_tag']
        tag_to_countries.setdefault(orig_tag, []).append(country)

    filtered_countries = []
    for orig_tag, countries in tag_to_countries.items():
        countries_with_mod = [c for c in countries if modifier_data.get(orig_tag) is not None]
        if not countries_with_mod:
            continue

        changed_tag_countries = [c for c in countries_with_mod if c['original_tag'] != c['tag']]
        if changed_tag_countries:
            for country in changed_tag_countries:
                country['modifiers'] = modifier_data[orig_tag]
                filtered_countries.append(country)
        else:
            for country in countries_with_mod:
                country['modifiers'] = modifier_data[orig_tag]
                filtered_countries.append(country)

    return filtered_countries

def generate_html_report(date, sorted_data, most_dev_province, hre_data, china_data, losses_data):
    env = Environment(loader=FileSystemLoader('./templates'))
    template = env.get_template('report_template.html')

    html_content = template.render(
        date=date,
        sorted_data=sorted_data,
        most_dev_province=most_dev_province,
        hre_data=hre_data,
        china_data=china_data,
        losses_data=losses_data
    )

    return html_content

def calculate_country_scores(country_data, most_dev_province, hre_data, china_data, losses_data):
    for country in country_data:
        if 'development' not in country:
            country['development'] = 0.0
        if 'starting_development' not in country:
            country['starting_development'] = 0.0

        growth_score = country['development'] / (country['starting_development'] if country['starting_development'] > 0 else 1)
        growth_score = min(growth_score, 20)
        victory_card_score = 0.0
        if 'victory_card_score' in country:
            victory_card_score = country['victory_card_score'] / 100

        historical_idea_score = 0
        if 'active_idea_groups' in country and 'historical_idea_groups' in country:
            for index, idea in enumerate(country['active_idea_groups']):
                if idea.split('=')[0].strip() == country['historical_idea_groups'][index-1]:
                    if int(idea.split('=')[1].strip()) == 7:
                        historical_idea_score += 15

        misc_score = 0
        if most_dev_province.get('owner') == country.get('tag'):
            misc_score += 10

        if country.get('tag') == losses_data['tag']:
            misc_score += 10

        if hre_data.get('emperor') == country.get('tag'):
            misc_score += 10

        if china_data.get('emperor') == country.get('tag'):
            misc_score += 3
            misc_score += china_data.get('level', 0) * 1

        if country.get('tag') in hre_data.get('electors') or hre_data.get('emperor') == country.get('tag'):
            misc_score += hre_data.get('level', 0) * 5

        modifier_score = 0
        if 'modifiers' in country:
            for modifier in country['modifiers']:
                modifier_score += modifier.get('count', 0) * 3

        total_score = growth_score + victory_card_score + historical_idea_score + misc_score + modifier_score

        country['growth_score'] = growth_score
        country['victory_card_score'] = victory_card_score
        country['historical_idea_score'] = historical_idea_score
        country['misc_score'] = misc_score
        country['modifier_score'] = modifier_score
        country['total_score'] = total_score

    return country_data

def print_country_table(sorted_data):
    # Table header
    header = [
        "No", "Player", "Tag", "Country Name", "Growth Score", "VC Score",
        "Hist Ideas", "Misc", "Modifier", "Total Score"
    ]
    # Calculate column widths
    col_widths = [4, 15, 18, 20, 13, 9, 10, 8, 10, 12]
    # Print header
    print("".join(str(header[i]).ljust(col_widths[i]) for i in range(len(header))))
    print("-" * sum(col_widths))
    # Print rows
    for idx, country in enumerate(sorted_data, 1):
        tag_str = country['tag']
        if country.get('original_tag') and country['original_tag'] != country['tag']:
            tag_str += f" (Original - {country['original_tag']})"
        row = [
            str(idx),
            str(country.get('player', '')),
            tag_str,
            str(country.get('name', '')),
            f"{country.get('growth_score', 0):.2f}",
            f"{country.get('victory_card_score', 0):.2f}",
            str(country.get('historical_idea_score', '')),
            str(country.get('misc_score', '')),
            str(country.get('modifier_score', '')),
            f"{country.get('total_score', 0):.2f}",
        ]
        print("".join(str(row[i]).ljust(col_widths[i]) for i in range(len(row))))


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
        most_dev_province = get_most_dev_province(gamestate_data.splitlines())
        country_data = extract_country_data(gamestate_data.splitlines(), players_countries)
        country_data = add_modifier_data(country_data)
        country_data = enrich_country_data_with_ideas(country_data)
        HRE_data, CHINA_data = get_empire_data(gamestate_data.splitlines())
        losses_data = get_country_with_most_losses(country_data)
        

        country_data = calculate_country_scores(country_data, most_dev_province, HRE_data, CHINA_data, losses_data)

        # priority for players
        # sorted_data = sorted(
        #     country_data,
        #     key=lambda x: (x['player'] != 'Unknown', x['total_score']),
        #     reverse=True
        # )

        sorted_data = sorted(
            country_data,
            key=lambda x: (x['total_score']),
            reverse=True
        )

        html_report = generate_html_report(date, sorted_data, most_dev_province, HRE_data, CHINA_data, losses_data)

        # print_country_table(sorted_data)


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