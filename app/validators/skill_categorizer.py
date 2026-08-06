"""
Skill Categorizer: Validates and corrects skill categorization in resumes.
Ensures that skills are placed in correct categories (Languages, Frameworks, Tools, etc.)
and removes miscategorized items.

Phase 4 Fix: Prevents methodologies and academic disciplines from being listed as programming languages.
"""

# Define skill categories with examples
PROGRAMMING_LANGUAGES = {
    'python', 'java', 'c++', 'c#', 'javascript', 'typescript',
    'go', 'rust', 'kotlin', 'scala', 'swift', 'objective-c', 'ruby', 'php', 'perl', 'r',
    'matlab', 'vb', 'visual basic', 'cobol', 'fortran', 'assembly', 'bash',
    'shell', 'powershell', 'lua', 'groovy', 'elixir', 'erlang', 'clojure',
    'haskell', 'lisp', 'prolog', 'dart', 'julia', 'ada', 'pascal', 'delphi',
    'sql', 'plsql', 'tsql', 't-sql', 'vbscript', 'jscript', 'actionscript',
    'groovy', 'eiffel', 'scheme', 'forth', 'smalltalk', 'applescript',
    'c', 'objective-c', 'swift', 'kotlin', 'scala', 'erlang', 'elixir',
    'f#', 'ocaml', 'reason', 'purescript', 'elm', 'idris', 'agda'
}

FRAMEWORKS_LIBRARIES = {
    'react', 'angular', 'vue', 'vue.js', 'svelte', 'ember', 'backbone',
    'knockout', 'jquery', 'd3', 'd3.js', 'three.js', 'babylon.js',
    'django', 'flask', 'fastapi', 'aiohttp', 'tornado',
    'express', 'node', 'node.js', 'nest.js', 'next.js', 'nuxt', 'gatsby',
    'spring', 'spring boot', 'spring mvc', 'hibernate', 'mybatis',
    'asp.net', 'asp.net core', '.net', '.net core', 'ef', 'entity framework',
    'rails', 'sinatra', 'hanami', 'dry-rb',
    'laravel', 'symfony', 'doctrine', 'yii',
    'pytorch', 'tensorflow', 'keras', 'scikit-learn', 'sklearn',
    'pandas', 'numpy', 'scipy', 'matplotlib', 'seaborn', 'plotly',
    'spark', 'hadoop', 'kafka', 'flink',
    'hugging face', 'transformers', 'torch', 'jax'
}

DATABASES = {
    'postgresql', 'postgres', 'mysql', 'mariadb', 'sqlite',
    'mongodb', 'cassandra', 'dynamodb', 'couchdb', 'couchbase',
    'redis', 'memcached', 'elasticsearch', 'solr',
    'neo4j', 'arangodb', 'orientdb',
    'firestore', 'realtime database', 'dynamodb',
    'oracle', 'sql server', 'db2', 'informix'
}

TOOLS_PLATFORMS = {
    'docker', 'kubernetes', 'docker-compose', 'podman',
    'aws', 'azure', 'gcp', 'google cloud', 'heroku', 'vercel', 'netlify',
    'git', 'github', 'gitlab', 'bitbucket', 'svn', 'mercurial',
    'jenkins', 'travis ci', 'circleci', 'gitlab ci', 'github actions',
    'jira', 'confluence', 'asana', 'trello', 'monday.com',
    'slack', 'discord', 'teams', 'zoom',
    'vscode', 'vs code', 'visual studio', 'intellij', 'webstorm', 'pycharm',
    'postman', 'insomnia', 'thunderclient',
    'linux', 'ubuntu', 'centos', 'macos', 'windows',
    'windows server', 'nginx', 'apache', 'iis',
    'grafana', 'prometheus', 'datadog', 'new relic',
    'terraform', 'ansible', 'puppet', 'chef', 'saltstack'
}

CONCEPTS_PATTERNS = {
    'algorithm', 'design pattern', 'microservice', 'rest', 'restful', 'api',
    'rest api', 'graphql', 'grpc', 'websocket', 'socket.io',
    'ci/cd', 'cicd', 'continuous', 'devops', 'agile', 'scrum',
    'tdd', 'bdd', 'pair programming', 'code review',
    'object-oriented', 'oop', 'functional', 'reactive',
    'sql', 'nosql', 'relational', 'non-relational',
    'mocking', 'testing', 'unit test', 'integration test', 'e2e test',
    'automation', 'deployment', 'infrastructure', 'infrastructure as code',
    'load balancing', 'caching', 'optimization', 'performance',
    'data structure', 'algorithm', 'big data', 'data pipeline',
    'machine learning', 'deep learning', 'nlp', 'computer vision',
    'security', 'encryption', 'authentication', 'authorization', 'oauth',
    'multithreading', 'concurrency', 'parallelism', 'async', 'promise',
    'memory management', 'garbage collection', 'heap', 'stack'
}

METHODOLOGIES = {
    'agile', 'scrum', 'kanban', 'xp', 'extreme programming',
    'waterfall', 'v-model', 'spiral',
    'lean', 'six sigma', 'kaizen',
    'tdd', 'bdd', 'ddd', 'domain-driven design',
    'pair programming', 'mob programming',
    'code review', 'pull request',
    'pair programming', 'code review', 'technical review',
    'devops', 'continuous integration', 'continuous delivery', 'continuous deployment'
}

ACADEMIC_DISCIPLINES = {
    'electrical engineering', 'mechanical engineering', 'civil engineering',
    'software engineering', 'computer science', 'information technology',
    'data science', 'machine learning engineering',
    'geomatics engineering', 'geospatial engineering',
    'geological engineering', 'petroleum engineering',
    'aerospace engineering', 'automotive engineering',
    'biomedical engineering', 'chemical engineering',
    'environmental engineering', 'marine engineering',
    'nuclear engineering', 'systems engineering',
    'gnss error modeling', 'gnss', 'gps', 'surveying',
    'artificial intelligence', 'ai'
}

SOFT_SKILLS = {
    'leadership', 'communication', 'collaboration', 'teamwork',
    'problem-solving', 'critical thinking', 'creativity',
    'adaptability', 'flexibility', 'resilience',
    'time management', 'organization', 'planning',
    'accountability', 'reliability', 'responsibility',
    'mentoring', 'coaching', 'training', 'teaching',
    'negotiation', 'persuasion', 'influence',
    'emotional intelligence', 'empathy', 'interpersonal',
    'attention to detail', 'analytical thinking', 'strategic thinking',
    'innovation', 'initiative', 'proactive', 'self-motivated'
}

# Non-technical terms that should never be in technical skill sections
NON_TECHNICAL_TERMS = {
    'ai-driven methods', 'innovation', 'problem-solving', 'attention to detail',
    'critical thinking', 'strategic thinking', 'leadership', 'collaboration',
    'communication', 'teamwork', 'agile', 'scrum', 'kanban',
    'soft skills', 'technical skills', 'transferable skills'
}


def is_programming_language(skill: str) -> bool:
    """Check if skill is a programming language."""
    skill_lower = skill.lower().strip()
    return skill_lower in PROGRAMMING_LANGUAGES


def is_framework_or_library(skill: str) -> bool:
    """Check if skill is a framework or library."""
    skill_lower = skill.lower().strip()
    return skill_lower in FRAMEWORKS_LIBRARIES


def is_database(skill: str) -> bool:
    """Check if skill is a database technology."""
    skill_lower = skill.lower().strip()
    return skill_lower in DATABASES


def is_tool_or_platform(skill: str) -> bool:
    """Check if skill is a tool or platform."""
    skill_lower = skill.lower().strip()
    for tool in TOOLS_PLATFORMS:
        if tool in skill_lower:
            return True
    return False


def is_concept(skill: str) -> bool:
    """Check if skill is a technical concept."""
    skill_lower = skill.lower().strip()
    for concept in CONCEPTS_PATTERNS:
        if concept in skill_lower:
            return True
    return False


def is_methodology(skill: str) -> bool:
    """Check if skill is a methodology or process."""
    skill_lower = skill.lower().strip()
    for method in METHODOLOGIES:
        if method in skill_lower:
            return True
    return False


def is_academic_discipline(skill: str) -> bool:
    """Check if skill is an academic discipline."""
    skill_lower = skill.lower().strip()
    for discipline in ACADEMIC_DISCIPLINES:
        if discipline in skill_lower:
            return True
    return False


def is_soft_skill(skill: str) -> bool:
    """Check if skill is a soft skill."""
    skill_lower = skill.lower().strip()
    for soft in SOFT_SKILLS:
        if soft in skill_lower:
            return True
    return False


def validate_skill_category(skill: str, category: str) -> bool:
    """
    Validate that a skill belongs in the given category.

    Args:
        skill: The skill name
        category: The category it's assigned to (e.g., "Languages", "Frameworks & Libraries")

    Returns:
        True if skill is correctly categorized, False otherwise
    """
    skill_lower = skill.lower().strip()

    # Remove these from any technical section (they're not technical skills)
    if skill_lower in NON_TECHNICAL_TERMS:
        return False

    # Reject academic disciplines from technical sections
    if is_academic_discipline(skill):
        return False

    if category == 'Languages':
        # Only programming languages belong here
        return is_programming_language(skill) and not is_methodology(skill)

    elif category == 'Frameworks & Libraries':
        # Only frameworks and libraries belong here
        return is_framework_or_library(skill) and not is_methodology(skill)

    elif category == 'Databases':
        # Only database technologies belong here
        return is_database(skill)

    elif category in ['Tools & Platforms', 'Tools']:
        # Only tools and platforms (and databases as fallback) belong here
        return is_tool_or_platform(skill) or is_database(skill)

    elif category == 'Concepts':
        # Only technical concepts belong here
        return is_concept(skill) and not is_methodology(skill)

    elif category == 'Methodologies':
        # Only methodologies belong here
        return is_methodology(skill)

    elif category == 'Soft Skills':
        # Only soft skills belong here
        return is_soft_skill(skill)

    # Default: reject if we can't categorize it properly
    return True


def categorize_skill(skill: str) -> str:
    """
    Determine the correct category for a skill.

    Args:
        skill: The skill name

    Returns:
        The recommended category
    """
    skill_lower = skill.lower().strip()

    # Check in order of specificity
    if is_programming_language(skill):
        return 'Languages'
    elif is_framework_or_library(skill):
        return 'Frameworks & Libraries'
    elif is_database(skill):
        return 'Databases'
    elif is_tool_or_platform(skill):
        return 'Tools & Platforms'
    elif is_methodology(skill):
        return 'Methodologies'
    elif is_concept(skill):
        return 'Concepts'
    elif is_soft_skill(skill):
        return 'Soft Skills'
    elif is_academic_discipline(skill):
        return '[REMOVE - Academic Discipline]'
    else:
        # Unknown skill - conservative approach: only put in Concepts
        return 'Concepts'


def validate_and_fix_skills(skills_data: list) -> tuple[list, dict]:
    """
    Validate skill categorization and fix misplaced skills.

    Args:
        skills_data: List of skill group objects with 'category' and 'items' keys

    Returns:
        Tuple of (fixed_skills_data, report)
    """
    report = {
        'total_skills': 0,
        'removed_skills': 0,
        'recategorized_skills': 0,
        'removals': [],
        'recategorizations': [],
    }

    fixed_skills = []

    for group in skills_data:
        category = group.get('category', 'Unknown')
        items = group.get('items', [])

        report['total_skills'] += len(items)

        # Filter items: keep only valid ones for this category
        valid_items = []
        recategorized = {}  # Track skills that need recategorization

        for item in items:
            if validate_skill_category(item, category):
                valid_items.append(item)
            else:
                # Try to find the correct category
                correct_category = categorize_skill(item)

                if correct_category == '[REMOVE - Academic Discipline]':
                    report['removals'].append({
                        'skill': item,
                        'reason': 'Academic discipline should not be in technical sections'
                    })
                    report['removed_skills'] += 1
                else:
                    # Will recategorize later
                    if correct_category not in recategorized:
                        recategorized[correct_category] = []
                    recategorized[correct_category].append(item)
                    report['recategorizations'].append({
                        'skill': item,
                        'from': category,
                        'to': correct_category
                    })
                    report['recategorized_skills'] += 1

        # Add valid items for this category
        if valid_items:
            fixed_skills.append({'category': category, 'items': valid_items})

        # Add recategorized items to their correct groups
        for recategory, recategory_items in recategorized.items():
            # Check if this category already exists
            existing_group = None
            for g in fixed_skills:
                if g['category'] == recategory:
                    existing_group = g
                    break

            if existing_group:
                existing_group['items'].extend(recategory_items)
            else:
                fixed_skills.append({'category': recategory, 'items': recategory_items})

    return fixed_skills, report
