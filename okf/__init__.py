"""okf-curation: convierte repos, Jira y Confluence en un repo OKF para agentes de código. Ver METODOLOGIA.md."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def skill(name: str) -> str:
    """Cuerpo de una skill (sin frontmatter): las skills son los prompts del pipeline."""
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    return text.split("---", 2)[2].strip() if text.startswith("---") else text
