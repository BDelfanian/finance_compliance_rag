from src.orchestrator.multi_agent_orchestrator import run_orchestrator

result = run_orchestrator(
    query="What governance, risk management, and oversight responsibilities does the management body "
    "have for ICT risk, incident reporting, and third-party ICT providers under CSSF, DORA, and "
    "EBA requirements?",
    model_version="gpt-4.1",
)

print(result["answer"]["answer"])
print(result["summary"]["answer"])
print(result["risk"]["warnings"])
print(result["confidence"])
