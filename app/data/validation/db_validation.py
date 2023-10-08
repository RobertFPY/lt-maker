
from typing import List
from app.data.database.database import Database
from app.data.resources.resources import Resources
from app.events.python_eventing.preprocessor import Preprocessor

def validate_events(database: Database, resources: Resources) -> List:
    ppsr = Preprocessor(database.events)
    all_errors = []
    for event in database.events:
        if event.is_python_event():
            all_errors += ppsr.verify_event(event.nid, event.source)
    return all_errors

def validate_all(database: Database, resources: Resources) -> List:
    event_errors = validate_events(database, resources)
    all_errors = event_errors
    return all_errors