"""This module contains various functions and classes to handle errors in the framework."""

import re
import traceback

from OpenOrchestrator.database.queues import QueueElement, QueueStatus
from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from office365.runtime.client_request_exception import ClientRequestException

from robot_framework import config
from robot_framework import error_screenshot

# Loft for hvor meget fejltekst der skrives til OO-loggen og koeelementets
# status. En office365 ClientRequestException kan baere serverens fulde
# svartekst i .message — for et afvist add_item kan det vaere en gengivelse af
# de feltvaerdier der blev forsoegt skrevet. Uden et loft kunne den slippe
# igennem alligevel via en lang repr() eller traceback.
MAX_ERROR_LENGTH = 2000

_LIST_NAME_PATTERN = re.compile(r"getbytitle\('([^']+)'\)", re.IGNORECASE)


class BusinessError(Exception):
    """An empty exception used to identify errors caused by breaking business rules"""


def _describe_error(error: Exception) -> str:
    """Beskriver en fejl kort til logning.

    En office365 ClientRequestException's .message/.args stammer fra
    serverens svartekst — for et afvist add_item kan den indeholde de
    indsendte feltvaerdier. Den bruges derfor ALDRIG her; i stedet vises
    HTTP-statuskoden og, hvis den kan udledes af request-URL'en, listenavnet.
    """
    if isinstance(error, ClientRequestException):
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", "?")
        url = getattr(response, "url", "") or ""
        match = _LIST_NAME_PATTERN.search(url)
        list_part = f", liste '{match.group(1)}'" if match else ""
        return f"{type(error).__name__} (HTTP {status}{list_part})"
    return repr(error)


def _format_traceback(error: Exception) -> str:
    """Formaterer stakken uden den afsluttende 'Type: besked'-linje.

    Den linje svarer til str(error) og kan for en ClientRequestException
    indeholde serverens svartekst — se _describe_error, som daekker den del.
    """
    return "".join(traceback.format_tb(error.__traceback__))


def _truncate(text: str, limit: int = MAX_ERROR_LENGTH) -> str:
    """Afkorter en logtekst til et fornuftigt loft."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"... (afkortet, {len(text)} tegn i alt)"


def handle_error(message: str, error: Exception, queue_element: QueueElement | None, orchestrator_connection: OrchestratorConnection) -> None:
    """Handles an error caught during the process.
    Logs an error to OpenOrchestrator.
    Marks the queue element (if any) as failed.
    Sends an error email.

    Args:
        message: A message to prepend to the error message.
        error: The exception that should be handled.
        queue_element: The queue element to fail, if any.
        orchestrator_connection: A connection to OpenOrchestrator.
    """
    error_msg = _truncate(
        f"{message}: {_describe_error(error)}\n\nTrace:\n{_format_traceback(error)}"
    )
    error_email = orchestrator_connection.get_constant(config.ERROR_EMAIL).value
    smtp_server = orchestrator_connection.get_constant(config.SMTP_SERVER_CONSTANT).value
    smtp_port = orchestrator_connection.get_constant(config.SMTP_PORT_CONSTANT).value

    orchestrator_connection.log_error(error_msg)
    if queue_element:
        orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.FAILED, error_msg)
    error_screenshot.send_error_screenshot(
        error_email, error, orchestrator_connection.process_name, smtp_server, smtp_port
    )


def log_exception(orchestrator_connection: OrchestratorConnection) -> callable:
    """Creates a function to be used as an exception hook that logs any uncaught exception in OpenOrchestrator.

    Args:
        orchestrator_connection: The connection to OpenOrchestrator.

    Returns:
        callable: A function that can be assigned to sys.excepthook.
    """
    def inner(exception_type, value, traceback_string):
        orchestrator_connection.log_error(f"Uncaught Exception:\nType: {exception_type}\nValue: {value}\nTrace: {traceback_string}")
    return inner
