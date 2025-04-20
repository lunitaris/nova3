# backend/utils/startup_log.py
startup_events = []

def add_startup_event(message: str):
    startup_events.append(message)

def log_startup_summary(logger):
    if not startup_events:
        return
    logger.info("")
    logger.info("🚀=================== NOVA IA LOCAL - INITIALISATION ===================🚀")
    for event in startup_events:
        if isinstance(event, dict):
            icon = event.get("icon", "✅")
            label = event.get("label", "Système")
            msg = event.get("message", "")
            logger.info(f"{icon}  {label} : {msg}")
        elif isinstance(event, str):
            logger.info(f"✅  {event}")
    logger.info("=======================================================================\n")
