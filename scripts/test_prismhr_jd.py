"""One-off test: PrismHR Associate Software Engineer JD."""

from __future__ import annotations

from resume_engine import generate_resume

JOB_TEXT = """
About the job
Start your engineering career on a system that genuinely matters.
PrismHR is the HR, payroll, and benefits platform used by employer-services organizations across the United States, backed by Vensure Employer Solutions. As an Associate Software Engineer you will join the team building and supporting the client-facing applications, working alongside product managers, designers, architects, QA and DevOps engineers, and engineering managers.

The first months are deliberately weighted toward learning~ building proficiency in our languages, tools, and patterns through training, pairing, and self-study, with real support from senior engineers rather than a link to the documentation.

From there you take on real work — writing, testing, debugging, and documenting application code as part of the delivery team; investigating and resolving technical issues including production questions escalated to engineering, which is one of the fastest ways to learn a large system; working with data through queries, analysis, and reporting to support decisions; researching technologies and bringing back a recommendation rather than a summary; and communicating progress and blockers clearly in team ceremonies. You will be given genuine ownership as you show readiness for it.

You will need~
Bachelor's degree in Computer Science or a related field
Strong analytical aptitude and solid computer science fundamentals — data structures, algorithms, databases
Ability to write and debug code in at least one language, shown through coursework, internships, personal projects, or early professional work
Strong communication, including explaining a concept clearly to someone who does not already understand it
Genuine appetite for continuous learning, since the stack and the domain will both be new

Nice to have~ internship or project experience with JavaScript, TypeScript, Node.js, SQL, or Git; exposure to Agile teams; interest in payroll or HR technology; any experience debugging something you did not write.

The schedule~ 6~00 PM - 3~00 AM IST, Monday to Friday, with the first four hours from the Noida office and the rest from home — no 3~00 AM commute. Early in a career, overlap is how you learn fastest~ same-day code review, real-time answers from the engineers who know the system, and a seat in design conversations rather than a summary afterward. Your mornings and afternoons are genuinely free.

Being straightforward~ a night shift is a real adjustment, particularly as a first or second job. Think about it honestly before applying, and talk to us about it in the screen rather than after you start.

Competitive compensation for the level, health coverage, structured onboarding and mentorship, learning support, and a defined progression path to Software Engineer. Apply now.

#VensureHRIndia
"""

if __name__ == "__main__":
    result = generate_resume(JOB_TEXT ,console=True)
    print(f"success={result.success}")
    print(f"pdf_path={result.pdf_path}")
    print(f"docx_path={getattr(result, 'docx_path', None)}")
