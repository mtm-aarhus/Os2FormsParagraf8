"""Test-opsaetning, delt af alle tests.

Stubber OpenOrchestrator, saa testene kan koere uden den fulde
OpenOrchestrator-installation (SQLAlchemy, NiceGUI, en rigtig
database-forbindelse osv.), som hverken kraeves af eller er relevant for det
testene her daekker. Er den rigtige pakke installeret i miljoeet, bruges den i
stedet — stubben tager kun over naar importen ellers ville fejle.
"""

import sys
import types


def _ensure_stub_openorchestrator() -> None:
    try:
        import OpenOrchestrator.orchestrator_connection.connection  # noqa: F401
        import OpenOrchestrator.database.queues  # noqa: F401
        return  # Den rigtige pakke er installeret og virker — brug den.
    except Exception:  # pylint: disable=broad-exception-caught
        pass  # Ikke installeret, eller installeret uden sine egne dependencies — stub den.

    root = types.ModuleType("OpenOrchestrator")
    orchestrator_connection_pkg = types.ModuleType("OpenOrchestrator.orchestrator_connection")
    connection_mod = types.ModuleType("OpenOrchestrator.orchestrator_connection.connection")
    database_pkg = types.ModuleType("OpenOrchestrator.database")
    queues_mod = types.ModuleType("OpenOrchestrator.database.queues")

    class OrchestratorConnection:  # minimal stub — kun brugt til typehints i testene
        """Stub for OpenOrchestrator.orchestrator_connection.connection.OrchestratorConnection."""

    class QueueElement:  # minimal stub med de felter process.py bruger
        """Stub for OpenOrchestrator.database.queues.QueueElement."""

        def __init__(self, id=None, data=None, reference=None):  # pylint: disable=redefined-builtin
            self.id = id
            self.data = data
            self.reference = reference

    class QueueStatus:  # minimal stub med de statusser exceptions.py bruger
        """Stub for OpenOrchestrator.database.queues.QueueStatus."""

        NEW = "NEW"
        IN_PROGRESS = "IN_PROGRESS"
        DONE = "DONE"
        FAILED = "FAILED"

    connection_mod.OrchestratorConnection = OrchestratorConnection
    orchestrator_connection_pkg.connection = connection_mod
    queues_mod.QueueElement = QueueElement
    queues_mod.QueueStatus = QueueStatus
    database_pkg.queues = queues_mod
    root.orchestrator_connection = orchestrator_connection_pkg
    root.database = database_pkg

    sys.modules["OpenOrchestrator"] = root
    sys.modules["OpenOrchestrator.orchestrator_connection"] = orchestrator_connection_pkg
    sys.modules["OpenOrchestrator.orchestrator_connection.connection"] = connection_mod
    sys.modules["OpenOrchestrator.database"] = database_pkg
    sys.modules["OpenOrchestrator.database.queues"] = queues_mod


_ensure_stub_openorchestrator()
