import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("BankAgents")


def log_message(from_agent: str, to_agent: str, message: dict):
    logger.info(f"📨 {from_agent} → {to_agent}: {message}")


def write_report(message: str):
    with open("report.txt", "a", encoding="utf-8") as f:
        f.write(message + "\n")
