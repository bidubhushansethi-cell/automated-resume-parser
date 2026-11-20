"""Skill dictionary grouped into the eight required categories.

Entry syntax: "Canonical|alias|alias". A leading "!" means case-sensitive match
anywhere; a leading "@" means case-sensitive and only inside the Skills section
(for ambiguous tokens such as C, R and Go).
"""
import re

CATEGORIES = [
    "Programming Languages", "Web Development", "Database Technologies", "Frameworks",
    "Machine Learning", "Data Science", "Cloud Computing", "Tools and Platforms",
]

_RAW = {
    "Programming Languages": [
        "Python", "Java", "JavaScript|ecmascript|es6", "TypeScript", "C++|cpp", "C#|csharp",
        "@C", "@R", "@Go|golang", "!Rust", "Kotlin", "!Swift", "PHP", "!Ruby", "Scala",
        "MATLAB", "Perl", "!Dart", "Bash|shell scripting", "PowerShell", "VBA", "Objective-C",
        "Lua", "Haskell",
    ],
    "Web Development": [
        "HTML|HTML5", "CSS|CSS3", "Bootstrap", "Tailwind CSS|tailwind", "Sass|SCSS", "jQuery",
        "REST API|REST APIs|RESTful|RESTful API", "GraphQL", "AJAX", "Webpack", "WebSockets",
        "Responsive Design", "Node.js|nodejs|node js", "Express.js|expressjs|express js",
        "JSON", "WordPress", "Web Development",
    ],
    "Database Technologies": [
        "SQL", "MySQL", "PostgreSQL|postgres|psql", "SQLite", "MongoDB|mongo", "Oracle",
        "SQL Server|mssql|ms sql", "Redis", "Cassandra", "DynamoDB", "Elasticsearch", "Firebase",
        "MariaDB", "Neo4j", "NoSQL", "PL/SQL", "T-SQL",
    ],
    "Frameworks": [
        "Django", "Flask", "FastAPI", "Spring Boot|Spring Framework|Spring MVC", "React|react.js|reactjs",
        "Angular|angularjs", "Vue.js|vue|vuejs", "Next.js|nextjs", "Nuxt", "Laravel",
        "Ruby on Rails", "ASP.NET", ".NET|dotnet|.net core", "Hibernate", "Svelte", "Symfony",
        "SQLAlchemy", "React Native", "Flutter", "Django REST Framework|DRF",
    ],
    "Machine Learning": [
        "Machine Learning|!ML", "Deep Learning", "TensorFlow", "PyTorch", "Keras",
        "scikit-learn|sklearn", "NLP|Natural Language Processing", "Computer Vision", "OpenCV",
        "XGBoost", "LightGBM", "Hugging Face|huggingface", "LLM|Large Language Models",
        "Generative AI|GenAI", "Reinforcement Learning", "spaCy", "NLTK", "Neural Networks",
        "LangChain", "BERT", "Artificial Intelligence",
    ],
    "Data Science": [
        "Data Science", "Pandas", "NumPy", "SciPy", "Matplotlib", "Seaborn", "Plotly",
        "Power BI|powerbi", "Tableau", "!Excel|MS Excel|Microsoft Excel", "Data Analysis|Data Analytics",
        "Data Visualization", "Statistics|Statistical Analysis", "!Apache Spark|PySpark|Spark",
        "Hadoop", "Big Data", "ETL", "Data Mining", "Jupyter", "Data Wrangling", "A/B Testing",
        "!Hive", "Airflow|Apache Airflow", "Kafka|Apache Kafka", "Looker", "Databricks", "Snowflake",
    ],
    "Cloud Computing": [
        "AWS|Amazon Web Services", "Azure|Microsoft Azure", "GCP|Google Cloud|Google Cloud Platform",
        "EC2", "S3", "AWS Lambda", "Kubernetes|k8s", "Terraform", "Ansible", "CloudFormation",
        "Serverless", "Heroku", "DigitalOcean", "OpenShift", "Cloud Computing", "DevOps",
    ],
    "Tools and Platforms": [
        "Git", "GitHub", "GitLab", "Bitbucket", "Jira", "Jenkins", "Docker", "Postman",
        "VS Code|Visual Studio Code", "Visual Studio", "IntelliJ", "PyCharm", "Eclipse", "Linux",
        "Unix", "Agile", "Scrum", "Kanban", "CI/CD|continuous integration", "Selenium", "JUnit",
        "pytest", "Figma", "Photoshop", "Confluence", "Trello", "Maven", "Gradle", "npm", "Nginx",
        "Swagger|OpenAPI", "Android Studio", "!Unity", "SAP", "Salesforce", "Microservices",
    ],
}


def _compile(alias: str, case_sensitive: bool):
    body = re.escape(alias).replace(r"\ ", r"[\s\-]+")
    pattern = r"(?<![A-Za-z0-9+#.])" + body + r"(?![A-Za-z0-9+#])"
    return re.compile(pattern, 0 if case_sensitive else re.I)


SKILL_INDEX = []  # (canonical, category, [compiled patterns], skills_section_only)
CATEGORY_OF = {}  # lower-case canonical name -> (canonical, category)

for _cat, _entries in _RAW.items():
    for _entry in _entries:
        _cs = _sec = False
        if _entry.startswith("@"):
            _cs = _sec = True
            _entry = _entry[1:]
        elif _entry.startswith("!"):
            _cs = True
            _entry = _entry[1:]
        _names = []
        for _n in _entry.split("|"):
            _names.append(_n.lstrip("!@"))
            if _n.startswith("!"):
                _cs = True
        _canon = _names[0]
        if _canon.lower() in CATEGORY_OF:  # keep the first category if duplicated
            continue
        CATEGORY_OF[_canon.lower()] = (_canon, _cat)
        SKILL_INDEX.append((_canon, _cat, [_compile(n, _cs) for n in _names], _sec))


def categorize(name: str) -> str:
    """Category for a skill name typed by a user; 'Other' if it is not in the dictionary."""
    hit = CATEGORY_OF.get((name or "").strip().lower())
    return hit[1] if hit else "Other"


def extract_skills(text: str, skills_section: str = "") -> list:
    found = {}
    for canon, cat, patterns, section_only in SKILL_INDEX:
        haystack = skills_section if section_only else text
        if haystack and any(p.search(haystack) for p in patterns):
            found[canon] = cat
    order = {c: i for i, c in enumerate(CATEGORIES)}
    return [{"name": n, "category": c}
            for n, c in sorted(found.items(), key=lambda kv: (order[kv[1]], kv[0].lower()))]
