"""This module has functionality to send error emails via smtp.

Skaermbilledet er deliberat fjernet: robotten koerer headless og har ingen UI,
saa ImageGrab.grab() kan kun fange hvad der ELLERS er paa OO-workerens
skrivebord — potentielt en anden robots vindue eller en sagsbehandlers skaerm
med persondata. En robot uden UI har ingen legitim grund til at maile et
skaermbillede, saa funktionen sender nu kun fejlteksten.
"""

import smtplib
from email.message import EmailMessage
import traceback

from robot_framework import config


def send_error_screenshot(to_address: str | list[str], exception: Exception, process_name: str,
                           smtp_server: str, smtp_port: int):
    """Sends an email with an error report when an exception occurs.
    Sender address is set in the 'config' module. SMTP server and port are passed in by the
    caller, read at runtime from OpenOrchestrator constants — see config.SMTP_SERVER_CONSTANT
    and config.SMTP_PORT_CONSTANT — rather than being literals in this repository.

    Funktionsnavnet er bevaret af hensyn til de der kalder den, men den
    vedhaefter ikke laengere noget skaermbillede — se modulets docstring.

    Args:
        to_address: Email address or list of addresses to send the error report.
        exception: The exception that triggered the error.
        process_name: Name of the process from OpenOrchestrator.
        smtp_server: SMTP-relæets hostnavn, hentet fra en OpenOrchestrator-constant.
        smtp_port: SMTP-relæets port, hentet fra en OpenOrchestrator-constant.
    """
    # Create message
    msg = EmailMessage()
    msg['to'] = to_address
    msg['from'] = config.SCREENSHOT_SENDER
    msg['subject'] = f"Error: {process_name}"

    # Create an HTML message with the exception only — intet skaermbillede.
    html_message = f"""
    <html>
        <body>
            <p>Error type: {type(exception).__name__}</p>
            <p>Error message: {exception}</p>
            <p>{traceback.format_exc()}</p>
        </body>
    </html>
    """

    msg.set_content("Please enable HTML to view this message.")
    msg.add_alternative(html_message, subtype='html')

    # Send message
    with smtplib.SMTP(smtp_server, int(smtp_port)) as smtp:
        smtp.starttls()
        smtp.send_message(msg)
