import sys
import zipfile
import io
import re
from jinja2 import Environment, FileSystemLoader

class color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

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

def extract_country_data(lines, players_countries):
    in_countries_block = False
    brace_depth = 0
    current_tag = None
    parent_block = None
    current_data = {}
    result = []

    tag_to_player = {tag: player for player, tag in players_countries.items()}

    i = 0
    while i < len(lines):
        line = lines[i].strip()

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
                        'player': tag_to_player[current_tag] if current_tag in tag_to_player else 'Unknown',
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

                    elif parent_block == 'victory_card' and line.startswith('score') and brace_depth == 3:
                        val = line.split('=')[1].strip()
                        current_data['victory_card_score'] = float(val)
                        parent_block = None

                    elif parent_block == 'active_idea_groups' and not line.startswith('}')  and brace_depth == 3:
                        val = line
                        current_data['active_idea_groups'].append(val)

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

def get_most_dev_province(lines):
    in_provinces_block = False
    brace_depth = 0
    current_province = None
    current_data = {}
    result = {'development': 0.0}

    i = 0
    while i < len(lines):
        line = lines[i].strip()

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
        tag = entry.get('tag')
        filename = tag_to_file.get(tag)

        if not filename:
            continue

        file_path = filename

        with open('eu4_data/'+ file_path, 'r', encoding='utf-8', errors='ignore') as f:
            contents = f.read()

        match = re.search(r'historical_idea_groups\s*=\s*\{([^}]+)\}', contents)
        if match:
            raw_ideas = match.group(1).strip()
            ideas = [idea.strip() for idea in raw_ideas.splitlines() if idea.strip()]
            entry['historical_idea_groups'] = ideas
        else:
            print(f"[!] historical_idea_groups not found for {tag}")
            entry['historical_idea_groups'] = []

    return country_data

def generate_html_report(sorted_data, most_dev_province):
    # Load the Jinja2 template
    env = Environment(loader=FileSystemLoader('./templates'))
    template = env.get_template('report_template.html')

    # Render the template with data
    html_content = template.render(
        sorted_data=sorted_data,
        most_dev_province=most_dev_province
    )

    return html_content

def calculate_country_scores(country_data, most_dev_province):
    for country in country_data:
        if 'development' not in country or 'starting_development' not in country:
            country['growth_score'] = 0
            country['victory_card_score'] = 0
            country['historical_idea_score'] = 0
            country['misc_score'] = 0
            country['total_score'] = 0
            continue

        growth_score = country['development'] / country['starting_development'] if country['starting_development'] > 0 else 1
        growth_score = min(growth_score, 20)
        victory_card_score = 0
        if 'victory_card_score' in country:
            victory_card_score = country['victory_card_score'] / 100

        historical_idea_score = 0
        if 'active_idea_groups' in country and 'historical_idea_groups' in country:
            for idea in country['active_idea_groups']:
                if idea.split('=')[0].strip() in country['historical_idea_groups']:
                    if int(idea.split('=')[1].strip()) == 7:
                        historical_idea_score += 5

        misc_score = 0
        if most_dev_province.get('owner') == country.get('tag'):
            misc_score += 10

        total_score = growth_score + victory_card_score + historical_idea_score + misc_score

        country['growth_score'] = growth_score
        country['victory_card_score'] = victory_card_score
        country['historical_idea_score'] = historical_idea_score
        country['misc_score'] = misc_score
        country['total_score'] = total_score

    return country_data

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

        players_countries = extract_players_countries_as_dict(gamestate_data)
        most_dev_province = get_most_dev_province(gamestate_data.splitlines())
        country_data = extract_country_data(gamestate_data.splitlines(), players_countries)
        country_data = enrich_country_data_with_ideas(country_data)
        country_data = calculate_country_scores(country_data, most_dev_province)

        sorted_data = sorted(
            country_data,
            key=lambda x: (x['player'] != 'Unknown', x['total_score']),
            reverse=True
        )

        html_report = generate_html_report(sorted_data[:10], most_dev_province)

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