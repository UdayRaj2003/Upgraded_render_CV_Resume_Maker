"""Quick AI connectivity check."""

from resume_engine.ai_client import AIClient
from resume_engine.config import load_ai_config
from resume_engine.models import JDJson

ai = load_ai_config()
print("base:", ai.api_base_url)
print("model:", ai.model_name)
client = AIClient(ai)
try:
    result = client.complete_json(
        system="Respond with a single JSON object only.",
        user=(
            "Extract a tiny JD JSON with keys role, domain, required_skills, "
            "preferred_skills, experience_required, keywords, responsibilities "
            "from: Associate Software Engineer needing JavaScript, Node.js, SQL, Git."
        ),
        schema=JDJson,
        timeout=90.0,
    )
    print("OK:", result.model_dump())
    print("tokens:", client.last_tokens)
except Exception as exc:
    print(f"ERR: {type(exc).__name__}: {exc}")
