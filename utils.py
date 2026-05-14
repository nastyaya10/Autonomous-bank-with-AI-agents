import logging
import sys

logger = logging.getLogger("BankAgents")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def log_message(from_agent: str, to_agent: str, message: dict):
    logger.info(f"📨 {from_agent} → {to_agent}: {message}")


def write_report(message: str):
    with open("report.txt", "a", encoding="utf-8") as f:
        f.write(message + "\n")
